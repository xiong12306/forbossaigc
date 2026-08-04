"""execution.modelscope_adapter 魔搭 ModelScope 免费文生图/图生图适配器。

通过 ModelScope API-Inference（异步）实现电商真实出图。
- 文生图: POST /images/generations（model=Qwen/Qwen-Image）
- 图生图: POST /images/generations（model=Qwen/Qwen-Image-Edit-2509 + image_url）
- 轮询: GET /tasks/{task_id}（X-ModelScope-Task-Type: image_generation）→ SUCCEED/FAILED
参考图通过 base64 data URI 传递（本地文件 ModelScope 服务器无法访问）。

设计：魔搭为真异步，但为契合现有调度器（run_step_with_retry 对异步有 busy-loop 隐患），
采用"同步包装"——submit 内部轮询到终态并缓存结果，poll 直接返回缓存（与 NanoBananaAdapter 一致）。
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

_IMAGE_TYPE_PROMPTS: dict[ImageType, str] = {
    ImageType.MAIN: (
        "纯白色背景，商品居中放置，主体占画面70%，"
        "45度侧角拍摄，左侧柔光箱主光右侧弱光填充，"
        "无阴影无反光，商品材质纹理清晰可见，"
        "拼多多电商主图标准，800x800像素，"
        "pure white background, studio lighting, product centered, "
        "no text, no watermark, e-commerce main image"
    ),
    ImageType.DETAIL: (
        "浅色纯净背景，商品细节微距特写，"
        "展示材质纹理、工艺接缝、做工细节，"
        "柔和侧光突出立体感，浅景深虚化背景，焦点精准，"
        "拼多多详情页标准，750px宽，"
        "shallow depth of field, macro detail shot, "
        "material texture visible, no text, no watermark"
    ),
    ImageType.SCENE: (
        "真实生活场景，商品自然融入使用环境，"
        "自然窗光柔和照射，场景氛围有代入感，"
        "商品清晰突出，环境不喧宾夺主，"
        "拼多多场景图标准，"
        "lifestyle scene, natural lighting, "
        "product in use, no text, no watermark"
    ),
    ImageType.POSTER: (
        "简约大气背景，商品居中突出，"
        "精致光影设计感，上方留白用于文案，"
        "高端品牌质感，色彩搭配协调，"
        "拼多多营销海报标准，"
        "minimalist background, premium feel, "
        "clean composition, no text, no watermark"
    ),
    ImageType.CAROUSEL: (
        "浅色纯色背景，商品多角度展示，"
        "统一光线风格，构图均衡，"
        "系列图风格一致，色彩协调，"
        "拼多多轮播图标准，800x800像素，"
        "consistent lighting, multiple angles, "
        "uniform style, no text, no watermark"
    ),
}
_IMAGE_TYPE_NAMES: dict[ImageType, str] = {
    ImageType.MAIN: "商品主图", ImageType.DETAIL: "产品详情图",
    ImageType.SCENE: "场景图", ImageType.POSTER: "营销海报",
    ImageType.CAROUSEL: "轮播图",
}

# 通用品质提升后缀（所有类型图片都追加的品质关键词）
_QUALITY_SUFFIX = (
    ", professional product photography, 8k, high detail, "
    "sharp focus, accurate color, photorealistic"
)

_IMAGE_EDIT_SUFFIX = (
    "，保持参考图商品的形状、颜色、材质、Logo、纹理完全一致，"
    "仅改变背景和光线，商品本身不可变形不可修改"
)

_NEGATIVE_PROMPT = (
    "low quality, blurry, distorted, deformed, watermark, text, signature, "
    "logo, brand name, error, worst quality, low resolution, jpeg artifacts, "
    "bad anatomy, extra limbs, disfigured, mosaic, pixelated, "
    "dark background, colored background, shadow on product, "
    "product not centered, cropped product, tilted composition"
)


@dataclass
class _MSTaskState:
    task_id: str
    params: dict[str, Any]
    submitted_at: datetime
    status: TaskStatus = TaskStatus.EXECUTING
    artifacts: list[Artifact] = field(default_factory=list)
    error_message: Optional[str] = None


class ModelScopeAdapter(PlatformAdapter):
    """魔搭 ModelScope 文生图适配器（同步包装的异步 API）。"""

    kind: PlatformKind = PlatformKind.MODELSCOPE

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> None:
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.modelscope_api_key
        self.api_base = (api_base or s.modelscope_api_base).rstrip("/")
        self.model = model or s.modelscope_model
        # httpx分阶段超时：连接超时短，读超时长（上传大base64/生成等待需要时间）
        self.submit_timeout = httpx.Timeout(
            connect=15.0,  # 连接15秒超时
            read=180.0,    # 提交上传读超时3分钟（上传大图+API排队）
            write=180.0,   # 写入超时3分钟
            pool=15.0,
        )
        self.poll_timeout = 300.0    # 总轮询超时5分钟
        self.poll_request_timeout = httpx.Timeout(
            connect=10.0,
            read=120.0,     # 轮询读超时2分钟，API偶发慢响应
            write=10.0,
            pool=10.0,
        )
        self.download_timeout = httpx.Timeout(
            connect=10.0,
            read=120.0,    # 下载图片超时2分钟
            write=10.0,
            pool=10.0,
        )
        self.poll_interval = s.poll_interval_sec if poll_interval is None else poll_interval
        self._tasks: dict[str, _MSTaskState] = {}
        self._counter = 0
        # 创建复用的httpx客户端，trust_env=False禁用系统代理（避免代理未启动导致连接超时）
        self._client = httpx.Client(trust_env=False, http2=False)
        if not self.api_key:
            logger.warning("ModelScope API key 未配置，将无法生成真实图片")

    def close(self) -> None:
        """关闭客户端连接"""
        self._client.close()

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    # ---------- prompt ----------
    def _build_prompt(self, params: dict[str, Any]) -> str:
        """按五要素公式构建提示词：产品主体 + 场景背景 + 光影风格 + 构图视角 + 画质要求。

        Qwen-Image 模型偏好结构化、具体的物理量描述，避免抽象形容词。
        图生图时追加主体一致性约束。
        """
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

        # 按五要素公式组织：产品主体 → 场景/背景 → 光影/构图 → 画质
        parts = [_IMAGE_TYPE_NAMES.get(image_type, "商品图") + "：" + product]
        # 类型专属描述（含场景背景、光影、构图、平台标准）
        parts.append(_IMAGE_TYPE_PROMPTS.get(image_type, _IMAGE_TYPE_PROMPTS[ImageType.MAIN]))
        # 用户自定义风格
        if style:
            parts.append(style + "风格")
        # 用户补充描述
        if user_prompt:
            parts.append(user_prompt)
        # 图生图：主体一致性约束
        if is_edit:
            parts.append(_IMAGE_EDIT_SUFFIX)
        # 通用品质要求
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
        """解析响应 JSON；非 JSON（如 200 + HTML 错误页）时带响应片段明确 raise，不掩盖真因。"""
        try:
            data = resp.json()
        except Exception as e:  # noqa: BLE001 - 归一化为可读错误
            raise RuntimeError(
                f"响应非 JSON（HTTP {resp.status_code}）: {resp.text[:200]}"
            ) from e
        return data or {}

    def _download_image(self, url: str) -> str:
        """下载远程图片到本地 uploads/ 目录，返回本地 URL（/uploads/xxx.png）。"""
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        # 从 URL 推断扩展名
        ext = ".png"
        path_str = url.split("?")[0].lower()
        for candidate in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            if candidate in path_str[-8:]:
                ext = candidate
                break
        filename = f"gen-{uuid.uuid4().hex[:12]}{ext}"
        filepath = uploads_dir / filename
        # 下载
        with self._client.stream("GET", url, timeout=self.download_timeout, follow_redirects=True) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        local_url = f"/uploads/{filename}"
        logger.info("图片已下载到本地: %s (origin: %s)", local_url, url[:80])
        return local_url

    @staticmethod
    def _resolve_image_url(ref: str) -> str:
        """将 reference_image 解析为 ModelScope 可用的 data URI。

        ModelScope 服务器无法访问本地文件，需要把图片转为 base64 data URI。
        - 已经是 http(s) URL: 直接使用（公网可访问）
        - 已经是 data: URI: 直接使用
        - 本地文件路径（绝对或相对）: 读取文件转为 base64 data URI
        """
        if ref.startswith(("http://", "https://", "data:")):
            return ref

        path = Path(ref)
        # /xxx 开头是 URL 路径，不是文件系统绝对路径；真正绝对路径（如 /Users/...）直接用
        is_abs_fs_path = path.is_absolute() and (len(ref) > 1 and ref[1] != "/" and not ref.startswith("/uploads/"))
        if not is_abs_fs_path:
            # 尝试多个位置解析：包目录、包目录下的 uploads、cwd
            pkg_dir = Path(__file__).resolve().parent  # boss_aigc/execution/
            pkg_root = pkg_dir.parent                   # boss_aigc/
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

    # ---------- 单张：提交 + 轮询到终态 ----------
    def _generate_one(self, prompt: str, params: dict[str, Any], idx: int, task_id: str) -> Artifact:
        reference_image = params.get("reference_image")
        is_edit = bool(reference_image)
        model_name = self.model

        submit_url = f"{self.api_base}/images/generations"
        submit_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
        }
        size = params.get("size", "1024x1024")  # 拼多多主图800x800，用1024生成后裁剪更清晰
        body: dict[str, Any] = {
            "prompt": prompt,
            "size": size,
            "negative_prompt": _NEGATIVE_PROMPT,
        }

        if is_edit:
            # 图生图：也是 /images/generations 端点，用 Qwen-Image-Edit-2509 模型 + image_url 字段
            edit_model = params.get("edit_model") or "Qwen/Qwen-Image-Edit-2509"
            model_name = edit_model
            body["model"] = edit_model
            ref_url = self._resolve_image_url(reference_image)
            body["image_url"] = [ref_url]
            logger.info("ModelScope 图生图: model=%s ref=%s", edit_model, reference_image)
        else:
            body["model"] = self.model
            # 用户自定义 negative_prompt 追加到默认值后
            if params.get("negative_prompt"):
                body["negative_prompt"] = _NEGATIVE_PROMPT + ", " + params["negative_prompt"]

        # 提交请求带重试，应对偶发网络问题
        submit_retries = 0
        max_submit_retries = 3
        resp = None
        while submit_retries < max_submit_retries:
            try:
                resp = self._client.post(submit_url, json=body, headers=submit_headers, timeout=self.submit_timeout)
                resp.raise_for_status()
                break
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                submit_retries += 1
                logger.warning("提交请求失败（重试%d/%d）: %s", submit_retries, max_submit_retries, type(e).__name__)
                if submit_retries >= max_submit_retries:
                    raise
                time.sleep(2)
        submit_data = self._parse_json(resp)
        ms_task_id = submit_data.get("task_id")
        if not ms_task_id:
            raise RuntimeError(f"提交未返回 task_id: {str(submit_data)[:200]}")

        logger.info("ModelScope 任务提交成功，ms_task_id=%s，开始轮询...", ms_task_id)

        # 注意：提交响应里可能立即返回task_status=SUCCEED，但这是假状态，实际任务还在PROCESSING，必须走轮询流程

        # 轮询：X-ModelScope-Task-Type 固定为 image_generation（官方文档要求，文生图/图生图都用这个值）
        poll_url = f"{self.api_base}/tasks/{ms_task_id}"
        poll_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-ModelScope-Task-Type": "image_generation",
        }
        deadline = time.monotonic() + self.poll_timeout
        poll_count = 0
        last_log_time = time.monotonic()
        consecutive_failures = 0
        while True:
            try:
                r = self._client.get(poll_url, headers=poll_headers, timeout=self.poll_request_timeout)
                r.raise_for_status()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                consecutive_failures += 1
                logger.warning("ModelScope 轮询请求失败（连续%d次）: %s，继续重试...", consecutive_failures, type(e).__name__)
                if consecutive_failures >= 10:
                    raise RuntimeError(f"连续{consecutive_failures}次轮询请求失败") from e
                time.sleep(3)
                continue
            consecutive_failures = 0
            data = self._parse_json(r)
            status = data.get("task_status")
            if status == "SUCCEED":
                logger.info("ModelScope 任务 %s 完成，开始下载图片", ms_task_id)
                # 兼容多种返回字段格式：output_images / images / outputs（API格式变更）
                images = data.get("output_images") or data.get("images") or []
                if not images and "outputs" in data:
                    # outputs 可能是列表，里面每个元素有 url 字段
                    outputs = data.get("outputs") or []
                    for out in outputs:
                        if isinstance(out, dict):
                            url = out.get("url") or out.get("image_url") or out.get("image")
                            if url:
                                images.append(url)
                        elif isinstance(out, str):
                            images.append(out)
                if not images:
                    # 最后兜底：打印完整响应方便排查
                    logger.error("SUCCEED 但未找到图片URL，完整响应: %s", str(data)[:500])
                    raise RuntimeError(f"SUCCEED 但未找到图片URL: {str(data)[:200]}")
                remote_url = images[0]
                # 下载到本地，避免第三方 OSS 不可访问/跨域/过期等问题
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
                        "source": "modelscope",
                        "model": model_name,
                        "mode": "image-to-image" if is_edit else "text-to-image",
                        "prompt": prompt,
                        "size": size,
                        "ms_task_id": ms_task_id,
                        "image_type": params.get("image_type", ImageType.MAIN.value),
                        "product": params.get("product"),
                        "reference_image": reference_image if is_edit else None,
                        "original_url": remote_url,
                    },
                )
            if status == "FAILED":
                raise RuntimeError(f"魔搭任务失败: {str(data)[:200]}")
            # 白名单：进行中状态继续轮询；其余未知状态立即暴露，勿用超时掩盖真因。
            if status not in ("PROCESSING", "PENDING", "RUNNING"):
                raise RuntimeError(
                    f"魔搭返回未知 task_status={status!r}: {str(data)[:200]}"
                )
            if time.monotonic() > deadline:
                raise TimeoutError(f"魔搭轮询超时（{self.poll_timeout}s），最后状态: {status}")
            # 每10秒打印一次进度日志，方便查看
            now = time.monotonic()
            if now - last_log_time > 10:
                elapsed = int(now - (deadline - self.poll_timeout))
                logger.info("ModelScope 任务 %s 处理中，已等待 %ds，状态: %s", ms_task_id, elapsed, status)
                last_log_time = now
            # 自适应轮询间隔：前5次快速检测（2s），之后拉长到（5s）避免频繁请求
            poll_count += 1
            if poll_count <= 5:
                time.sleep(2.0)
            else:
                time.sleep(5.0)

    # ---------- 接口 ----------
    def submit(self, params: dict[str, Any]) -> str:
        self._counter += 1
        task_id = f"modelscope-{self._counter}"
        state = _MSTaskState(task_id=task_id, params=dict(params), submitted_at=datetime.now())
        self._tasks[task_id] = state

        if not self.api_key:
            state.status = TaskStatus.FAILED
            state.error_message = "ModelScope API key 未配置"
            logger.error("ModelScope API key 未配置，任务 %s 失败", task_id)
            return task_id

        try:
            prompt = self._build_prompt(params)
            quantity = self._resolve_quantity(params)
            mode = "图生图" if params.get("reference_image") else "文生图"
            logger.info("ModelScope %s: task=%s model=%s qty=%d prompt=%s",
                        mode, task_id, self.model, quantity, prompt[:80])

            if quantity == 1:
                # 单张图：直接生成，无需线程池开销
                artifacts = [self._generate_one(prompt, params, 0, task_id)]
            else:
                # 多张图：并发生成，大幅缩短总耗时（3张图从~240s降到~80s）
                max_workers = min(quantity, 4)  # 最多4路并发，避免限流
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
                    # 按原始顺序排列
                    artifacts = [results[i] for i in range(quantity)]

            state.artifacts = artifacts
            state.status = TaskStatus.DELIVERED
            logger.info("ModelScope 任务 %s 完成，生成 %d 张", task_id, len(artifacts))
        except httpx.TimeoutException:
            state.status = TaskStatus.FAILED
            state.error_message = f"网络请求超时，请检查网络连接后重试"
            logger.error("ModelScope 任务 %s 网络超时", task_id)
        except httpx.HTTPError as e:
            state.status = TaskStatus.FAILED
            state.error_message = f"API 请求失败: {e}"
            logger.error("ModelScope 任务 %s 请求失败: %s", task_id, e)
        except Exception as e:  # noqa: BLE001 - 失败即失败，记明确原因
            state.status = TaskStatus.FAILED
            state.error_message = str(e)
            logger.error("ModelScope 任务 %s 失败: %s", task_id, e)
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
                artifact_id=raw.get("artifact_id") or f"modelscope-art-{uuid.uuid4().hex[:8]}",
                kind=raw.get("kind", "IMAGE"),
                url_or_path=raw.get("url_or_path"),
                thumbnail_path=raw.get("thumbnail_path"),
                metadata=dict(raw.get("metadata", {})) or {"source": "modelscope"},
            )
        return Artifact(
            artifact_id=f"modelscope-art-{uuid.uuid4().hex[:8]}",
            kind="IMAGE",
            url_or_path=str(raw) if raw is not None else None,
            metadata={"source": "modelscope"},
        )
