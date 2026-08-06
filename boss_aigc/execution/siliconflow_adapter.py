"""execution.siliconflow_adapter 硅基流动 SiliconFlow FLUX 系列适配器。

通过 SiliconFlow API（同步 OpenAI 兼容风格）实现电商真实出图。
- 文生图: POST /images/generations（model=black-forest-labs/FLUX.1-dev）
- 图生图: POST /images/generations（model=black-forest-labs/FLUX.1-Kontext-dev + image=base64 data URI）
- 同步返回: data.images[0].url（图片 URL 有效期 1 小时，需立即下载转存）

设计：SiliconFlow 为同步 API，submit 内部完成请求并下载图片到本地，
poll 直接返回缓存（与 NanoBananaAdapter 一致）。

参考文档: https://docs.siliconflow.cn/api-reference/images/images-generations
"""

from __future__ import annotations

import base64
import mimetypes
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from boss_aigc.config import get_settings
from boss_aigc.contracts.enums import ImageType, PlatformKind, TaskStatus
from boss_aigc.contracts.execution import Artifact
from boss_aigc.execution.adapter import PlatformAdapter
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="execution")

# 电商图片类型 → 专业 prompt 模板（参考 ModelScope 适配器风格）
_IMAGE_TYPE_PROMPTS: dict[ImageType, str] = {
    ImageType.MAIN: (
        "纯白色背景，商品居中放置，主体占画面70%，"
        "45度侧角拍摄，左侧柔光箱主光右侧弱光填充，"
        "无阴影无反光，商品材质纹理清晰可见，"
        "电商主图标准，800x800像素，"
        "pure white background, studio lighting, product centered, "
        "no text, no watermark, e-commerce main image"
    ),
    ImageType.DETAIL: (
        "浅色纯净背景，商品细节微距特写，"
        "展示材质纹理、工艺接缝、做工细节，"
        "柔和侧光突出立体感，浅景深虚化背景，焦点精准，"
        "电商详情页标准，750px宽，"
        "shallow depth of field, macro detail shot, "
        "material texture visible, no text, no watermark"
    ),
    ImageType.SCENE: (
        "真实生活场景，商品自然融入使用环境，"
        "自然窗光柔和照射，场景氛围有代入感，"
        "商品清晰突出，环境不喧宾夺主，"
        "电商场景图标准，"
        "lifestyle scene, natural lighting, "
        "product in use, no text, no watermark"
    ),
    ImageType.POSTER: (
        "简约大气背景，商品居中突出，"
        "精致光影设计感，上方留白用于文案，"
        "高端品牌质感，色彩搭配协调，"
        "电商营销海报标准，"
        "minimalist background, premium feel, "
        "clean composition, no text, no watermark"
    ),
    ImageType.CAROUSEL: (
        "浅色纯色背景，商品多角度展示，"
        "统一光线风格，构图均衡，"
        "系列图风格一致，色彩协调，"
        "电商轮播图标准，800x800像素，"
        "consistent lighting, multiple angles, "
        "uniform style, no text, no watermark"
    ),
}
_IMAGE_TYPE_NAMES: dict[ImageType, str] = {
    ImageType.MAIN: "商品主图", ImageType.DETAIL: "产品详情图",
    ImageType.SCENE: "场景图", ImageType.POSTER: "营销海报",
    ImageType.CAROUSEL: "轮播图",
}

# FLUX 模型偏好英文 prompt，品质关键词后缀
_QUALITY_SUFFIX = (
    ", professional product photography, 8k, high detail, "
    "sharp focus, accurate color, photorealistic"
)

# 图生图主体一致性约束（FLUX.1-Kontext-dev）
_IMAGE_EDIT_SUFFIX = (
    "，保持参考图商品的形状、颜色、材质、Logo、纹理完全一致，"
    "仅改变背景和光线，商品本身不可变形不可修改"
)


@dataclass
class _SFTaskState:
    """硅基流动任务内存状态。"""
    task_id: str
    params: dict[str, Any]
    submitted_at: datetime
    status: TaskStatus = TaskStatus.EXECUTING
    artifacts: list[Artifact] = field(default_factory=list)
    error_message: Optional[str] = None


class SiliconFlowAdapter(PlatformAdapter):
    """硅基流动 SiliconFlow FLUX 系列文生图/图生图适配器（同步 API）。

    - 文生图使用 FLUX.1-dev（画质好，新用户送 2000 万 token）
    - 图生图使用 FLUX.1-Kontext-dev（专业图像编辑模型）
    - 同步返回，submit 内部完成请求 + 下载图片到本地 /uploads
    """

    kind: PlatformKind = PlatformKind.SILICONFLOW

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        edit_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.siliconflow_api_key
        self.api_base = (api_base or s.siliconflow_api_base).rstrip("/")
        self.model = model or s.siliconflow_model
        self.edit_model = edit_model or s.siliconflow_edit_model
        # httpx 分阶段超时：FLUX.1-dev 单图生成通常 5-30 秒，留足余量
        self.request_timeout = httpx.Timeout(
            connect=15.0,
            read=120.0,    # 生成读超时 2 分钟
            write=60.0,    # 上传大 base64 图 1 分钟
            pool=15.0,
        )
        self.download_timeout = httpx.Timeout(
            connect=10.0,
            read=60.0,
            write=10.0,
            pool=10.0,
        )
        self._tasks: dict[str, _SFTaskState] = {}
        self._counter = 0
        # 复用 httpx 客户端，禁用系统代理（项目惯例，避免代理未启动导致连接超时）
        self._client = httpx.Client(trust_env=False, http2=False)
        if not self.api_key:
            logger.warning("SiliconFlow API key 未配置，将无法生成真实图片")

    def close(self) -> None:
        """关闭客户端连接。"""
        self._client.close()

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    # ---------- prompt ----------
    def _build_prompt(self, params: dict[str, Any]) -> str:
        """构建 FLUX 偏好的英文 prompt（结构化五要素公式）。"""
        product = params.get("product", "商品")
        raw = params.get("image_type", ImageType.MAIN.value)
        if isinstance(raw, ImageType):
            image_type = raw
        else:
            try:
                image_type = ImageType(str(raw))
            except ValueError:
                logger.warning("未知 image_type=%r，回退为 MAIN", raw)
                image_type = ImageType.MAIN
        style = params.get("style", "")
        user_prompt = params.get("prompt", "")
        is_edit = bool(params.get("reference_image"))

        parts = [_IMAGE_TYPE_NAMES.get(image_type, "商品图") + "：" + product]
        parts.append(_IMAGE_TYPE_PROMPTS.get(image_type, _IMAGE_TYPE_PROMPTS[ImageType.MAIN]))
        if style:
            parts.append(style + "风格")
        if user_prompt:
            parts.append(user_prompt)
        if is_edit:
            parts.append(_IMAGE_EDIT_SUFFIX)
        parts.append(_QUALITY_SUFFIX)
        return "，".join(parts)

    @staticmethod
    def _resolve_quantity(params: dict[str, Any]) -> int:
        raw = params.get("quantity", 1)
        try:
            return max(1, min(int(raw), 8))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _parse_json(resp: httpx.Response) -> dict[str, Any]:
        """解析响应 JSON；非 JSON 时带响应片段明确 raise。"""
        try:
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                f"响应非 JSON（HTTP {resp.status_code}）: {resp.text[:200]}"
            ) from e
        return data or {}

    def _download_image(self, url: str) -> str:
        """下载远程图片到本地 uploads/，返回本地 URL。

        SiliconFlow 生成的图片 URL 有效期仅 1 小时，必须立即转存。
        """
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        ext = ".png"
        path_str = url.split("?")[0].lower()
        for candidate in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            if candidate in path_str[-8:]:
                ext = candidate
                break
        filename = f"sf-{uuid.uuid4().hex[:12]}{ext}"
        filepath = uploads_dir / filename
        with self._client.stream("GET", url, timeout=self.download_timeout, follow_redirects=True) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        local_url = f"/uploads/{filename}"
        logger.info("SiliconFlow 图片已下载到本地: %s", local_url)
        return local_url

    @staticmethod
    def _resolve_image_data(ref: str) -> str:
        """将 reference_image 解析为 SiliconFlow 可用的 base64 data URI。

        SiliconFlow 接受 image 字段为 data:image/xxx;base64,... 格式。
        - http(s) URL: 先下载再转 base64（避免 URL 不可达）
        - 已是 data: URI: 直接使用
        - 本地文件路径: 读取转 base64
        """
        if ref.startswith("data:"):
            return ref

        if ref.startswith(("http://", "https://")):
            # 远程 URL 先下载再转 base64
            import httpx as _httpx
            with _httpx.Client(trust_env=False, http2=False) as c:
                r = c.get(ref, timeout=_httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0))
                r.raise_for_status()
                content = r.content
                mime = r.headers.get("content-type", "image/png").split(";")[0].strip()
                data = base64.b64encode(content).decode("ascii")
                return f"data:{mime};base64,{data}"

        path = Path(ref)
        is_abs_fs_path = path.is_absolute() and (len(ref) > 1 and ref[1] != "/" and not ref.startswith("/uploads/"))
        if not is_abs_fs_path:
            pkg_dir = Path(__file__).resolve().parent
            pkg_root = pkg_dir.parent
            candidates = [
                pkg_root / ref.lstrip("/"),
                pkg_root / "uploads" / Path(ref).name,
                Path.cwd() / ref.lstrip("/"),
                Path.cwd() / "boss_aigc" / "uploads" / Path(ref).name,
            ]
            for c in candidates:
                if c.is_file():
                    path = c
                    break
        if not path.is_file():
            raise RuntimeError(f"参考图文件不存在: {ref}")

        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"

    # ---------- 单张生成 ----------
    def _generate_one(self, prompt: str, params: dict[str, Any], idx: int, task_id: str) -> Artifact:
        reference_image = params.get("reference_image")
        is_edit = bool(reference_image)
        model_name = self.edit_model if is_edit else self.model

        submit_url = f"{self.api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        size = params.get("size", "1024x1024")
        body: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "image_size": size,
        }

        if is_edit:
            # FLUX.1-Kontext-dev 图生图：传 image 字段（base64 data URI）
            ref_data = self._resolve_image_data(reference_image)
            body["image"] = ref_data
            logger.info("SiliconFlow 图生图: model=%s ref=%s", model_name, reference_image)

        # 提交请求（含重试，应对偶发网络问题）
        max_retries = 3
        resp = None
        for attempt in range(max_retries):
            try:
                resp = self._client.post(submit_url, json=body, headers=headers, timeout=self.request_timeout)
                resp.raise_for_status()
                break
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning("SiliconFlow 提交失败（重试%d/%d）: %s", attempt + 1, max_retries, type(e).__name__)
                if attempt >= max_retries - 1:
                    raise
                time.sleep(2)

        data = self._parse_json(resp)
        # 响应格式: {"images": [{"url": "..."}], "timings": {...}, "seed": 123}
        images = data.get("images") or []
        if not images:
            # 兼容其他可能字段
            if data.get("data"):
                images = data["data"]
            elif data.get("url"):
                images = [{"url": data["url"]}]

        if not images or not images[0].get("url"):
            raise RuntimeError(f"SiliconFlow 未返回图片 URL: {str(data)[:200]}")

        remote_url = images[0]["url"]
        # 立即下载转存（URL 仅 1 小时有效）
        try:
            local_url = self._download_image(remote_url)
        except Exception as e:  # noqa: BLE001
            logger.warning("下载远程图片失败，使用原始 URL: %s", e)
            local_url = remote_url

        return Artifact(
            artifact_id=f"{task_id}-art-{idx + 1}",
            kind="IMAGE",
            url_or_path=local_url,
            thumbnail_path=local_url,
            metadata={
                "source": "siliconflow",
                "model": model_name,
                "mode": "image-to-image" if is_edit else "text-to-image",
                "prompt": prompt,
                "size": size,
                "seed": data.get("seed"),
                "image_type": params.get("image_type", ImageType.MAIN.value),
                "product": params.get("product"),
                "reference_image": reference_image if is_edit else None,
                "original_url": remote_url,
            },
        )

    # ---------- 接口 ----------
    def submit(self, params: dict[str, Any]) -> str:
        self._counter += 1
        task_id = f"siliconflow-{self._counter}"
        state = _SFTaskState(task_id=task_id, params=dict(params), submitted_at=datetime.now())
        self._tasks[task_id] = state

        if not self.api_key:
            state.status = TaskStatus.FAILED
            state.error_message = "SiliconFlow API key 未配置"
            logger.error("SiliconFlow API key 未配置，任务 %s 失败", task_id)
            return task_id

        try:
            prompt = self._build_prompt(params)
            quantity = self._resolve_quantity(params)
            mode = "图生图" if params.get("reference_image") else "文生图"
            logger.info("SiliconFlow %s: task=%s model=%s qty=%d prompt=%s",
                        mode, task_id, self.model, quantity, prompt[:80])

            if quantity == 1:
                artifacts = [self._generate_one(prompt, params, 0, task_id)]
            else:
                # 多张图并发（FLUX 速度快，可适度提高并发）
                max_workers = min(quantity, 4)
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = {
                        pool.submit(self._generate_one, prompt, params, i, task_id): i
                        for i in range(quantity)
                    }
                    results: dict[int, Artifact] = {}
                    for future in as_completed(futures):
                        idx = futures[future]
                        try:
                            results[idx] = future.result()
                        except Exception as e:  # noqa: BLE001
                            logger.error("第%d张图片生成失败: %s", idx + 1, e)
                            raise
                    artifacts = [results[i] for i in range(quantity)]

            state.artifacts = artifacts
            state.status = TaskStatus.DELIVERED
            logger.info("SiliconFlow 任务 %s 完成，生成 %d 张", task_id, len(artifacts))
        except httpx.TimeoutException:
            state.status = TaskStatus.FAILED
            state.error_message = "网络请求超时，请检查网络连接后重试"
            logger.error("SiliconFlow 任务 %s 网络超时", task_id)
        except httpx.HTTPError as e:
            state.status = TaskStatus.FAILED
            state.error_message = f"API 请求失败: {e}"
            logger.error("SiliconFlow 任务 %s 请求失败: %s", task_id, e)
        except Exception as e:  # noqa: BLE001
            state.status = TaskStatus.FAILED
            state.error_message = str(e)
            logger.error("SiliconFlow 任务 %s 失败: %s", task_id, e)
        return task_id

    def poll(self, platform_task_id: str) -> tuple[TaskStatus, Optional[list[Artifact]]]:
        state = self._tasks.get(platform_task_id)
        if state is None:
            return TaskStatus.FAILED, None
        if state.status == TaskStatus.DELIVERED:
            return TaskStatus.DELIVERED, list(state.artifacts)
        if state.status == TaskStatus.FAILED:
            return TaskStatus.FAILED, None
        if state.status == TaskStatus.CANCELLED:
            return TaskStatus.CANCELLED, None
        return TaskStatus.EXECUTING, None

    def cancel(self, platform_task_id: str) -> bool:
        state = self._tasks.get(platform_task_id)
        if state is not None and state.status == TaskStatus.EXECUTING:
            state.status = TaskStatus.CANCELLED
        return True

    def normalize_result(self, raw: Any) -> Artifact:
        if isinstance(raw, dict):
            return Artifact(
                artifact_id=raw.get("artifact_id") or f"siliconflow-art-{uuid.uuid4().hex[:8]}",
                kind=raw.get("kind", "IMAGE"),
                url_or_path=raw.get("url_or_path"),
                thumbnail_path=raw.get("thumbnail_path"),
                metadata=dict(raw.get("metadata", {})) or {"source": "siliconflow"},
            )
        return Artifact(
            artifact_id=f"siliconflow-art-{uuid.uuid4().hex[:8]}",
            kind="IMAGE",
            url_or_path=str(raw) if raw is not None else None,
            metadata={"source": "siliconflow"},
        )
