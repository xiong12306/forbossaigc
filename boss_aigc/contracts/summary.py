"""contracts.summary 任务摘要契约。

TaskSummary 是「确认层」生成的卡片化摘要，
作为老板确认/修改/取消的依据；确认后才进入执行层。
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from boss_aigc.contracts.enums import (
    DeliveryChannel,
    PlatformKind,
    TaskType,
)


class TaskSummary(BaseModel):
    """任务摘要卡片：确认层产出的结构化卡片。

    Attributes:
        summary_id: 摘要唯一 ID。
        task_type: 任务类型。
        product: 目标商品名。
        params: 关键参数（数量/风格/尺寸/参考图等），自由结构。
        platform: 预计选用的执行平台。
        estimated_duration_sec: 预计耗时（秒）。
        estimated_cost: 预计消耗积分。
        delivery_channel: 预计交付方式。
        is_high_cost: 是否高成本任务（超过阈值需二次确认）。
    """

    summary_id: str = Field(..., description="摘要唯一 ID")
    task_type: TaskType = Field(..., description="任务类型")
    product: Optional[str] = Field(default=None, description="目标商品名")
    params: dict[str, Any] = Field(
        default_factory=dict, description="关键参数，自由结构"
    )
    platform: PlatformKind = Field(
        default=PlatformKind.MOCK, description="预计选用的执行平台"
    )
    estimated_duration_sec: int = Field(
        default=0, ge=0, description="预计耗时（秒）"
    )
    estimated_cost: int = Field(
        default=0, ge=0, description="预计消耗积分"
    )
    delivery_channel: DeliveryChannel = Field(
        default=DeliveryChannel.DIALOG, description="预计交付方式"
    )
    is_high_cost: bool = Field(
        default=False, description="是否高成本任务（超阈值需二次确认）"
    )
