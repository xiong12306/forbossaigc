"""boss_aigc.delivery.packager 交付结果打包。

把执行层产出的 TaskResult 打包为 DeliveryPackage：
- 按 artifact.kind 分类统计（N 张图 / M 个视频 / K 段文案）
- 收集缩略图路径列表
- 生成给老板听的自然语言播报文本（summary_text）
- 透传 metadata 供下游通道使用
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from boss_aigc.contracts.execution import Artifact, TaskResult
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="delivery")

# artifact.kind 的中文名与量词映射，用于生成自然语言摘要
# 未知 kind 兜底为「个」
_KIND_LABELS: dict[str, tuple[str, str]] = {
    "IMAGE": ("图", "张"),
    "VIDEO": ("视频", "个"),
    "TEXT": ("文案", "段"),
}


class DeliveryPackage(BaseModel):
    """交付包：交付层打包后的产物，供推送通道发给老板。

    Attributes:
        result_id: 关联的 TaskResult.result_id。
        task_id: 关联的任务 ID。
        artifacts: 原始产出物列表（透传）。
        thumbnails: 缩略图路径列表（供卡片预览）。
        summary_text: 给老板的自然语言摘要文本（如「3 张主图出好了，您看一下」），
            可直接交给 TTS 播报或卡片展示。
        metadata: 附加元数据（如分类统计 / 完成时间）。
    """

    result_id: str = Field(default="", description="关联的 TaskResult.result_id")
    task_id: str = Field(default="", description="关联的任务 ID")
    artifacts: list[Artifact] = Field(
        default_factory=list, description="原始产出物列表"
    )
    thumbnails: list[str] = Field(
        default_factory=list, description="缩略图路径列表"
    )
    summary_text: str = Field(default="", description="给老板的自然语言摘要文本")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="附加元数据"
    )


def package_result(task_result: TaskResult) -> DeliveryPackage:
    """把 TaskResult 打包为 DeliveryPackage。

    流程：
        1. 按 artifact.kind 分类统计数量。
        2. 收集所有非空 thumbnail_path 到 thumbnails 列表。
        3. 生成自然语言摘要文本写入 summary_text。
        4. metadata 记录分类统计与原始 artifact 数。

    Args:
        task_result: 执行层产出的任务结果。

    Returns:
        DeliveryPackage：含原始 artifacts / 缩略图 / 摘要文本 / 元数据。
    """
    artifacts = list(task_result.artifacts or [])

    # 1. 分类统计
    kind_counts: dict[str, int] = {}
    thumbnails: list[str] = []
    for art in artifacts:
        kind_counts[art.kind] = kind_counts.get(art.kind, 0) + 1
        if art.thumbnail_path:
            thumbnails.append(art.thumbnail_path)

    # 2. 生成自然语言摘要
    summary_text = _build_summary_text(kind_counts, total=len(artifacts))

    # 3. metadata
    metadata: dict[str, Any] = {
        "kind_counts": dict(kind_counts),
        "total_artifacts": len(artifacts),
        "completed_at": (
            task_result.completed_at.isoformat()
            if task_result.completed_at
            else None
        ),
        "result_status": (
            task_result.status.value
            if hasattr(task_result.status, "value")
            else str(task_result.status)
        ),
    }

    logger.info(
        "已打包交付结果: result_id=%s, artifacts=%d, thumbnails=%d",
        task_result.result_id, len(artifacts), len(thumbnails),
    )

    return DeliveryPackage(
        result_id=task_result.result_id,
        task_id=task_result.task_id,
        artifacts=artifacts,
        thumbnails=thumbnails,
        summary_text=summary_text,
        metadata=metadata,
    )


def _build_summary_text(kind_counts: dict[str, int], total: int) -> str:
    """根据分类统计生成给老板听的自然语言播报文本。

    示例：
        - 仅图：「3 张主图出好了，您看一下」
        - 图+视频：「3 张图、1 个视频出好了，您看一下」
        - 空结果：「结果已出，但暂无产出物，您看一下」
    """
    if total == 0:
        return "结果已出，但暂无产出物，您看一下"

    parts: list[str] = []
    for kind, count in kind_counts.items():
        noun, quant = _KIND_LABELS.get(kind, ("个", "个"))
        parts.append(f"{count} {quant}{noun}")

    if len(parts) == 1:
        # 单一类型：用更口语化的表达
        kind = next(iter(kind_counts))
        count = kind_counts[kind]
        if kind == "IMAGE":
            return f"{count} 张图出好了，您看一下"
        return f"{parts[0]}出好了，您看一下"

    # 多类型：「3 张图、1 个视频出好了，您看一下」
    return f"{'、'.join(parts)}出好了，您看一下"
