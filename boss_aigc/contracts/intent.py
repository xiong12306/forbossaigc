"""contracts.intent 意图理解层数据契约。

TaskIntent 是「理解层」的产出，描述一条老板指令被解析成
结构化任务后的结果（任务类型、商品、槽位、缺失项、追问候选等）。
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from boss_aigc.contracts.enums import TaskType


class SlotValue(BaseModel):
    """槽位值：单个参数的解析结果。

    Attributes:
        name: 槽位名（如 quantity/style/size/platform）。
        value: 槽位值（类型不固定，故用 Any）。
        confidence: 解析置信度 0.0~1.0，低于阈值需追问。
    """

    name: str = Field(..., description="槽位名，如 quantity / style / size")
    value: Any = Field(..., description="槽位值，类型不固定")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="解析置信度 0.0~1.0"
    )


class TaskIntent(BaseModel):
    """任务意图：理解层把口语化指令解析为结构化任务的产物。

    Attributes:
        intent_id: 意图唯一 ID。
        task_type: 任务类型（出图/改图/生视频/写文案/查数据）。
        product: 目标商品名（如「保温杯」），缺失时为 None。
        slots: 已解析的槽位字典，key 为槽位名。
        raw_text: 老板的原始指令文本（用于日志与回溯）。
        confidence: 整体意图识别置信度。
        missing_slots: 缺失的关键槽位名列表，用于追问补全。
        needs_clarification: 是否需要老板澄清（模糊指令时为 True）。
        clarification_options: 候选对象/选项列表，让老板二选一。
    """

    intent_id: str = Field(..., description="意图唯一 ID")
    task_type: TaskType = Field(..., description="任务类型")
    product: Optional[str] = Field(default=None, description="目标商品名")
    slots: dict[str, SlotValue] = Field(
        default_factory=dict, description="已解析槽位字典"
    )
    raw_text: str = Field(default="", description="老板的原始指令文本")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="整体意图识别置信度"
    )
    missing_slots: list[str] = Field(
        default_factory=list, description="缺失的关键槽位名列表"
    )
    needs_clarification: bool = Field(
        default=False, description="是否需要老板澄清"
    )
    clarification_options: list[str] = Field(
        default_factory=list, description="候选对象/选项列表"
    )
