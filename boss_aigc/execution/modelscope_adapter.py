"""execution.modelscope_adapter 魔搭 ModelScope 免费文生图适配器。

通过 ModelScope API-Inference（异步）实现电商真实出图。
- 提交: POST /images/generations（X-ModelScope-Async-Mode: true）→ task_id
- 轮询: GET /tasks/{task_id}（X-ModelScope-Task-Type: image_generation）→ SUCCEED/FAILED
默认模型 Qwen/Qwen-Image（中文 prompt 友好）。免费额度 2000 次/天。

设计：魔搭为真异步，但为契合现有调度器（run_step_with_retry 对异步有 busy-loop 隐患），
采用"同步包装"——submit 内部轮询到终态并缓存结果，poll 直接返回缓存（与 NanoBananaAdapter 一致）。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

from boss_aigc.config import get_settings
from boss_aigc.contracts.enums import ImageType, PlatformKind, TaskStatus
from boss_aigc.contracts.execution import Artifact
from boss_aigc.execution.adapter import PlatformAdapter
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="execution")

_IMAGE_TYPE_PROMPTS: dict[ImageType, str] = {
    ImageType.MAIN: "商品主图，突出主体，白色/纯色背景，专业电商摄影，高清细节，提升点击率",
    ImageType.DETAIL: "产品详情图，展示卖点细节，材质特写，工艺展示，引导下单，专业商品摄影",
    ImageType.SCENE: "场景展示图，真实使用场景，生活化氛围，自然光线，代入感强",
    ImageType.POSTER: "营销海报，视觉冲击力，促销氛围，品牌质感，适合电商推广",
    ImageType.CAROUSEL: "轮播图，多角度展示，构图美观，色彩协调，适合店铺首页",
}
_IMAGE_TYPE_NAMES: dict[ImageType, str] = {
    ImageType.MAIN: "商品主图", ImageType.DETAIL: "产品详情图",
    ImageType.SCENE: "场景图", ImageType.POSTER: "营销海报",
    ImageType.CAROUSEL: "轮播图",
}


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
        self.timeout = timeout or s.request_timeout_sec
        self.poll_interval = s.poll_interval_sec if poll_interval is None else poll_interval
        self._tasks: dict[str, _MSTaskState] = {}
        self._counter = 0
        if not self.api_key:
            logger.warning("ModelScope API key 未配置，将无法生成真实图片")

    # ---------- prompt ----------
    def _build_prompt(self, params: dict[str, Any]) -> str:
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
        parts = [_IMAGE_TYPE_NAMES.get(image_type, "商品图") + "，" + product]
        if style:
            parts.append(style + "风格")
        parts.append(_IMAGE_TYPE_PROMPTS.get(image_type, _IMAGE_TYPE_PROMPTS[ImageType.MAIN]))
        if user_prompt:
            parts.append(user_prompt)
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

    # ---------- 单张：提交 + 轮询到终态 ----------
    def _generate_one(self, prompt: str, params: dict[str, Any], idx: int, task_id: str) -> Artifact:
        submit_url = f"{self.api_base}/images/generations"
        submit_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
            "X-ModelScope-Task-Type": "text-to-image-generation",
        }
        size = params.get("size", "1024x1024")
        body: dict[str, Any] = {"model": self.model, "prompt": prompt, "size": size}
        if params.get("negative_prompt"):
            body["negative_prompt"] = params["negative_prompt"]

        resp = httpx.post(submit_url, json=body, headers=submit_headers, timeout=self.timeout)
        resp.raise_for_status()
        submit_data = self._parse_json(resp)
        ms_task_id = submit_data.get("task_id")
        if not ms_task_id:
            raise RuntimeError(f"提交未返回 task_id: {str(submit_data)[:200]}")

        poll_url = f"{self.api_base}/tasks/{ms_task_id}"
        poll_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-ModelScope-Task-Type": "image_generation",
        }
        deadline = time.monotonic() + self.timeout
        while True:
            r = httpx.get(poll_url, headers=poll_headers, timeout=self.timeout)
            r.raise_for_status()
            data = self._parse_json(r)
            status = data.get("task_status")
            if status == "SUCCEED":
                images = data.get("output_images") or []
                if not images:
                    raise RuntimeError("SUCCEED 但 output_images 为空")
                url = images[0]
                return Artifact(
                    artifact_id=f"{task_id}-art-{idx + 1}",
                    kind="IMAGE",
                    url_or_path=url,
                    thumbnail_path=url,
                    metadata={
                        "source": "modelscope",
                        "model": self.model,
                        "prompt": prompt,
                        "size": size,
                        "ms_task_id": ms_task_id,
                        "image_type": params.get("image_type", ImageType.MAIN.value),
                        "product": params.get("product"),
                    },
                )
            if status == "FAILED":
                raise RuntimeError(f"魔搭任务失败: {str(data)[:200]}")
            # 白名单：仅 PENDING/RUNNING 继续轮询；其余未知状态立即暴露，勿用超时掩盖真因
            if status not in ("PENDING", "RUNNING"):
                raise RuntimeError(
                    f"魔搭返回未知 task_status={status!r}: {str(data)[:200]}"
                )
            if time.monotonic() > deadline:
                raise TimeoutError(f"魔搭轮询超时（{self.timeout}s）")
            time.sleep(self.poll_interval)

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
            logger.info("ModelScope 生图: task=%s model=%s qty=%d prompt=%s",
                        task_id, self.model, quantity, prompt[:80])
            artifacts = [self._generate_one(prompt, params, i, task_id) for i in range(quantity)]
            state.artifacts = artifacts
            state.status = TaskStatus.DELIVERED
            logger.info("ModelScope 任务 %s 完成，生成 %d 张", task_id, len(artifacts))
        except httpx.TimeoutException:
            state.status = TaskStatus.FAILED
            state.error_message = f"请求超时（{self.timeout}s）"
            logger.error("ModelScope 任务 %s 超时", task_id)
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
