"""boss_aigc.confirmation.summary_builder 任务摘要卡片生成。

把理解层产出的 TaskIntent 转成老板可读的 TaskSummary 摘要卡片，
作为确认/修改/取消的依据；并提供自然语言播报文本生成。
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from boss_aigc.contracts.enums import (
    DeliveryChannel,
    ImageType,
    PlatformKind,
    TaskType,
)
from boss_aigc.contracts.intent import TaskIntent, SlotValue
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.config import get_settings
from boss_aigc.orchestration.planner import select_platform
from boss_aigc.understanding.schemas import SLOT_SCHEMAS, IMAGE_TYPE_NAMES, get_default


# 各任务类型的预估耗时（秒）与积分消耗系数
# IMAGE_GEN: 30 秒/张、2 积分/张；VIDEO_GEN: 固定 180 秒、20 积分；
# COPYWRITING: 10 秒、1 积分；其余 30 秒、1 积分。
_DURATION_TABLE: dict[TaskType, int] = {
    TaskType.IMAGE_GEN: 30,
    TaskType.VIDEO_GEN: 180,
    TaskType.COPYWRITING: 10,
}
_COST_TABLE: dict[TaskType, int] = {
    TaskType.IMAGE_GEN: 2,
    TaskType.VIDEO_GEN: 20,
    TaskType.COPYWRITING: 1,
}


def build_summary(
    intent: TaskIntent,
    asset_store: Optional[Any] = None,
) -> TaskSummary:
    """根据 TaskIntent 构建任务摘要卡片。

    Args:
        intent: 理解层产出的任务意图。
        asset_store: 可选的资产层聚合；若提供且 intent 未指定 style，
            会调用 inject_style 注入品牌风格到 params。

    Returns:
        TaskSummary：含参数 / 平台 / 预估耗时 / 预估积分 / 是否高成本。
    """
    # 1. 从 intent.slots 提取参数（quantity/style/size/reference_image 等）
    params: dict[str, Any] = {}
    for name, slot in intent.slots.items():
        # product 已单独存到 summary.product，避免重复
        if name == "product":
            continue
        params[name] = slot.value

    # 2. 为可选槽位填充默认值
    schema = SLOT_SCHEMAS.get(intent.task_type, {})
    for slot_name, (required, default_val) in schema.items():
        if slot_name == "product":
            continue
        if slot_name not in params and default_val is not None:
            params[slot_name] = default_val

    # 3. 注入品牌风格（若 intent 未指定 style 且提供了 asset_store）
    if asset_store is not None and not params.get("style"):
        try:
            params = asset_store.inject_style(params)
        except Exception:
            # asset_store 注入失败不影响摘要生成，保留原 params
            pass

    # 4. 估算耗时与积分
    quantity = _safe_int(params.get("quantity"), default=1)
    base_duration = _DURATION_TABLE.get(intent.task_type, 30)
    base_cost = _COST_TABLE.get(intent.task_type, 1)

    if intent.task_type == TaskType.IMAGE_GEN:
        # IMAGE_GEN 按张数线性扩展
        estimated_duration_sec = base_duration * max(quantity, 1)
        estimated_cost = base_cost * max(quantity, 1)
    else:
        # 其余任务类型用固定估值（数量影响不大）
        estimated_duration_sec = base_duration
        estimated_cost = base_cost

    # 5. 构建临时summary用于平台选择
    temp_summary = TaskSummary(
        summary_id="temp",
        task_type=intent.task_type,
        product=intent.product,
        params=params,
        platform=PlatformKind.MOCK,
        estimated_duration_sec=estimated_duration_sec,
        estimated_cost=estimated_cost,
    )
    platform = select_platform(intent.task_type, temp_summary)

    # 6. 高成本判定：从 config 读阈值
    settings = get_settings()
    high_cost_threshold = getattr(settings, "high_cost_threshold", 20)
    is_high_cost = estimated_cost > high_cost_threshold

    return TaskSummary(
        summary_id=uuid.uuid4().hex[:12],
        task_type=intent.task_type,
        product=intent.product,
        params=params,
        platform=platform,
        estimated_duration_sec=estimated_duration_sec,
        estimated_cost=estimated_cost,
        delivery_channel=DeliveryChannel.DIALOG,
        is_high_cost=is_high_cost,
    )


def format_summary_text(summary: TaskSummary) -> str:
    """把 TaskSummary 转成给老板听的自然语言播报文本。

    示例：「给保温杯出 3 张商品主图，轻奢暖色调风格，1024x1024，预计 90 秒，消耗 6 积分。确认开始吗？」
    高成本时追加「⚠️ 本次消耗较高」提示。
    """
    parts: list[str] = []

    # 商品 + 数量 + 图片类型
    product = summary.product or "当前商品"
    quantity = _safe_int(summary.params.get("quantity"), default=None)
    image_type_raw = summary.params.get("image_type")
    image_type_name = IMAGE_TYPE_NAMES.get(str(image_type_raw), "主图") if image_type_raw else _task_verb(summary.task_type)

    if quantity is not None and quantity > 1:
        parts.append(f"给{product}出 {quantity} 张{image_type_name}")
    else:
        parts.append(f"给{product}出{image_type_name}")

    # 风格
    style = summary.params.get("style")
    if style:
        style_text = "".join(style) if isinstance(style, (list, tuple)) else str(style)
        if style_text:
            parts.append(f"{style_text}风格")

    # 尺寸
    size = summary.params.get("size")
    if size:
        parts.append(str(size))

    # 拼接主句
    main_sentence = "，".join(parts)

    # 预估耗时 + 积分
    cost_sentence = (
        f"预计 {summary.estimated_duration_sec} 秒，"
        f"消耗 {summary.estimated_cost} 积分"
    )

    # 高成本提示
    high_cost_hint = "。⚠️ 本次消耗较高" if summary.is_high_cost else ""

    # 确认提示
    confirm_prompt = "。确认开始吗？"

    return f"{main_sentence}，{cost_sentence}{high_cost_hint}{confirm_prompt}"


# ---------- 内部工具 ----------
def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """把任意值安全转为 int，失败返回 default。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def _task_verb(task_type: TaskType) -> str:
    """根据任务类型返回动作描述。"""
    if task_type == TaskType.IMAGE_GEN:
        return "主图"
    if task_type == TaskType.IMAGE_EDIT:
        return "改图"
    if task_type == TaskType.VIDEO_GEN:
        return "视频"
    if task_type == TaskType.COPYWRITING:
        return "文案"
    if task_type == TaskType.DATA_QUERY:
        return "查询"
    return "任务"
