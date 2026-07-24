"""execution.nanobanana_adapter NanoBanana真实出图适配器实现。

接入NanoBanana模型（通过Ace Data Cloud）实现电商真实出图。
参考无量AI出图流程，支持：
- 图片类型选择：商品主图、产品详情图等
- 生成数量设置
- 自动构建电商场景prompt

API参考：
curl -X POST 'https://api.acedata.cloud/nano-banana/images' \
  -H 'authorization: Bearer {token}' \
  -H 'content-type: application/json' \
  -d '{"action": "generate", "prompt": "商品主图，牛仔裤，模特上身，白色背景"}'
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import requests

from boss_aigc.config import get_settings
from boss_aigc.contracts.enums import ImageType, PlatformKind, TaskStatus, TaskType
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
    ImageType.MAIN: "商品主图",
    ImageType.DETAIL: "产品详情图",
    ImageType.SCENE: "场景图",
    ImageType.POSTER: "营销海报",
    ImageType.CAROUSEL: "轮播图",
}


@dataclass
class _NanoBananaTaskState:
    """NanoBanana任务内存状态：跟踪单次submit后的请求状态与结果。"""

    task_id: str
    params: dict[str, Any]
    submitted_at: datetime
    status: TaskStatus = TaskStatus.EXECUTING
    artifacts: list[Artifact] = field(default_factory=list)
    error_message: Optional[str] = None
    api_response: Optional[dict[str, Any]] = None


class NanoBananaAdapter(PlatformAdapter):
    """NanoBanana真实出图适配器：通过Ace Data Cloud API调用NanoBanana模型。

    由于NanoBanana API是同步返回的（单次POST请求返回结果），
    适配器内部在submit时同步发起请求，poll时直接返回结果，
    保持与其他异步适配器相同的接口契约。

    Args:
        api_key: NanoBanana API key；为空时从全局config取。
        api_base: API base URL；为空时从全局config取。
        timeout: 请求超时时间（秒）。
    """

    kind: PlatformKind = PlatformKind.NANOBANANA

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.nanobanana_api_key
        self.api_base = api_base or settings.nanobanana_api_base
        self.timeout = timeout or settings.request_timeout_sec
        self._tasks: dict[str, _NanoBananaTaskState] = {}
        self._counter = 0

        if not self.api_key:
            logger.warning("NanoBanana API key未配置，将无法生成真实图片")

    def _build_prompt(self, params: dict[str, Any]) -> str:
        """根据参数构建NanoBanana prompt。

        组合：图片类型提示 + 商品名 + 风格 + 用户补充描述。
        """
        product = params.get("product", "商品")
        image_type_raw = params.get("image_type", ImageType.MAIN.value)
        if isinstance(image_type_raw, ImageType):
            image_type = image_type_raw
        else:
            try:
                image_type = ImageType(str(image_type_raw))
            except ValueError:
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

    def submit(self, params: dict[str, Any]) -> str:
        """提交生图任务到NanoBanana API。

        同步调用API，结果存入内部状态，poll时返回。
        """
        self._counter += 1
        task_id = f"nanobanana-{self._counter}"
        state = _NanoBananaTaskState(
            task_id=task_id,
            params=dict(params),
            submitted_at=datetime.now(),
        )
        self._tasks[task_id] = state

        if not self.api_key:
            state.status = TaskStatus.FAILED
            state.error_message = "NanoBanana API key未配置"
            logger.error("NanoBanana API key未配置，任务%s失败", task_id)
            return task_id

        try:
            prompt = self._build_prompt(params)
            quantity = self._resolve_quantity(params)
            logger.info("NanoBanana生图: task_id=%s, prompt=%s, quantity=%d", task_id, prompt[:100], quantity)

            url = f"{self.api_base.rstrip('/')}/images"
            headers = {
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            }

            artifacts: list[Artifact] = []
            for i in range(quantity):
                payload = {
                    "action": "generate",
                    "prompt": prompt,
                }
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                result = response.json()
                state.api_response = result

                image_url = self._extract_image_url(result)
                if image_url:
                    artifacts.append(Artifact(
                        artifact_id=f"{task_id}-art-{i + 1}",
                        kind="IMAGE",
                        url_or_path=image_url,
                        thumbnail_path=image_url,
                        metadata={
                            "source": "nanobanana",
                            "image_type": params.get("image_type", ImageType.MAIN.value),
                            "product": params.get("product"),
                            "prompt": prompt,
                            "width": 1024,
                            "height": 1024,
                        },
                    ))
                else:
                    logger.warning("NanoBanana返回结果中未找到图片URL: %s", str(result)[:200])

            if artifacts:
                state.artifacts = artifacts
                state.status = TaskStatus.DELIVERED
                logger.info("NanoBanana任务%s完成，生成%d张图片", task_id, len(artifacts))
            else:
                state.status = TaskStatus.FAILED
                state.error_message = "未获取到图片结果"
                logger.error("NanoBanana任务%s失败：未获取到图片", task_id)

        except requests.exceptions.Timeout:
            state.status = TaskStatus.FAILED
            state.error_message = f"请求超时（{self.timeout}秒）"
            logger.error("NanoBanana任务%s超时", task_id)
        except requests.exceptions.RequestException as e:
            state.status = TaskStatus.FAILED
            state.error_message = f"API请求失败: {str(e)}"
            logger.error("NanoBanana任务%s请求失败: %s", task_id, str(e))
        except Exception as e:
            state.status = TaskStatus.FAILED
            state.error_message = f"未知错误: {str(e)}"
            logger.error("NanoBanana任务%s未知错误: %s", task_id, str(e), exc_info=True)

        return task_id

    def poll(self, platform_task_id: str) -> tuple[TaskStatus, Optional[list[Artifact]]]:
        """轮询任务状态。NanoBanana是同步API，submit已完成请求，直接返回结果。"""
        state = self._tasks.get(platform_task_id)
        if state is None:
            return TaskStatus.FAILED, None

        if state.status == TaskStatus.CANCELLED:
            return TaskStatus.CANCELLED, None

        if state.status == TaskStatus.DELIVERED:
            return TaskStatus.DELIVERED, list(state.artifacts)

        if state.status == TaskStatus.FAILED:
            return TaskStatus.FAILED, None

        return TaskStatus.EXECUTING, None

    def cancel(self, platform_task_id: str) -> bool:
        """取消任务。NanoBanana是同步API，无法真正取消已提交的请求，仅标记状态。"""
        state = self._tasks.get(platform_task_id)
        if state is not None and state.status == TaskStatus.EXECUTING:
            state.status = TaskStatus.CANCELLED
        return True

    def normalize_result(self, raw: Any) -> Artifact:
        """标准化结果。"""
        if isinstance(raw, dict):
            return Artifact(
                artifact_id=raw.get("artifact_id") or f"nanobanana-art-{uuid.uuid4().hex[:8]}",
                kind=raw.get("kind", "IMAGE"),
                url_or_path=raw.get("url_or_path"),
                thumbnail_path=raw.get("thumbnail_path"),
                metadata=dict(raw.get("metadata", {})) or {"source": "nanobanana"},
            )
        return Artifact(
            artifact_id=f"nanobanana-art-{uuid.uuid4().hex[:8]}",
            kind="IMAGE",
            url_or_path=str(raw) if raw is not None else None,
            metadata={"source": "nanobanana"},
        )

    @staticmethod
    def _extract_image_url(result: dict[str, Any]) -> Optional[str]:
        """从NanoBanana API响应中提取图片URL。

        兼容多种可能的响应格式，尝试常见字段名。
        """
        if not isinstance(result, dict):
            return None

        for key in ["url", "image_url", "image", "data", "images", "result"]:
            value = result.get(key)
            if value is None:
                continue
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
            if isinstance(value, list) and len(value) > 0:
                first = value[0]
                if isinstance(first, str) and first.startswith(("http://", "https://")):
                    return first
                if isinstance(first, dict):
                    nested = NanoBananaAdapter._extract_image_url(first)
                    if nested:
                        return nested
            if isinstance(value, dict):
                nested = NanoBananaAdapter._extract_image_url(value)
                if nested:
                    return nested

        return None

    @staticmethod
    def _resolve_quantity(params: dict[str, Any]) -> int:
        """从params解析quantity，默认1张（电商场景一次不宜太多）。"""
        raw = params.get("quantity", 1)
        try:
            q = int(raw)
            return max(1, min(q, 8))
        except (TypeError, ValueError):
            return 1
