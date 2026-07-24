"""boss_aigc.confirmation.state_machine 确认/修改/取消状态机。

解析老板对任务摘要的回复，驱动确认层状态流转：
    CONFIRM  -> 放行（生成 ConfirmedTask）
    MODIFY   -> 用修改项更新 intent，重新生成摘要，仍等待确认
    CANCEL   -> 取消任务
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Optional

from boss_aigc.contracts.enums import ConfirmationAction, TaskStatus
from boss_aigc.contracts.execution import ConfirmedTask
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.logging_setup import get_logger

from boss_aigc.confirmation.summary_builder import build_summary

logger = get_logger(__name__, layer="confirmation")


# 确认关键词：老板回复中含任意一个即判定为 CONFIRM
_CONFIRM_KEYWORDS: tuple[str, ...] = (
    "确认", "确认执行", "开始", "开始执行", "可以", "好的",
    "好", "行", "没问题", "对的", "是的", "yes", "ok",
)

# 取消关键词
_CANCEL_KEYWORDS: tuple[str, ...] = (
    "取消", "算了", "不要了", "不做了", "放弃", "关闭", "取消执行",
)

# 修改关键词：触发 MODIFY 分支
_MODIFY_KEYWORDS: tuple[str, ...] = (
    "改成", "换成", "改为", "换为", "调整", "修改",
    "数量改", "风格改", "尺寸改", "改一下", "换一下",
)


# 图片类型关键词映射（用于修改解析）
_IMAGE_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("detail", ["详情图", "细节图", "卖点图"]),
    ("scene", ["场景图", "实景图", "使用场景"]),
    ("poster", ["海报", "营销海报", "促销海报"]),
    ("carousel", ["轮播图", "首页图"]),
    ("main", ["主图", "商品主图"]),
]

# 各槽位的修改解析规则：(槽位名, 正则模式, 转换函数)
# 正则中用 group(1) 捕获要修改的值
_MODIFY_PATTERNS: list[tuple[str, re.Pattern[str], Any]] = [
    # 数量：N 张 / N 个 / N 份
    (
        "quantity",
        re.compile(r"(?:数量)?\s*(?:改成|换成|改为|换为|调整(?:为|到)?|改一下)?\s*(\d+)\s*[张个份]"),
        lambda m: int(m.group(1)),
    ),
    # 图片类型：改成主图/详情图/场景图/海报/轮播图
    (
        "image_type",
        re.compile(r"(?:类型|图类型|图片类型)?\s*(?:改成|换成|改为|换为|调整(?:为|到)?|要|出)\s*(主图|商品主图|详情图|细节图|卖点图|场景图|实景图|海报|营销海报|轮播图|首页图)"),
        lambda m: _parse_image_type(m.group(1)),
    ),
    # 尺寸：1440x1440 / 1440×1440
    (
        "size",
        re.compile(r"尺寸?\s*(?:改成|换成|改为|换为|调整(?:为|到)?)\s*(\d{3,5})\s*[x×*]\s*(\d{3,5})"),
        lambda m: f"{m.group(1)}x{m.group(2)}",
    ),
    # 风格：风格改成XX / 换成XX风格
    (
        "style",
        re.compile(r"风格?\s*(?:改成|换成|改为|换为|调整(?:为|到)?)\s*([^\s,，。\.]+?)(?:风格)?(?:[，,。\s]|$)"),
        lambda m: m.group(1),
    ),
]


def _parse_image_type(text: str) -> str:
    """从文本解析图片类型value。"""
    for value, keywords in _IMAGE_TYPE_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return value
    return "main"


def parse_confirmation_action(text: str) -> tuple[ConfirmationAction, dict[str, Any]]:
    """解析老板对任务摘要的回复文本，返回动作与修改项。

    Args:
        text: 老板的回复文本（如「确认」/「数量改成5张」/「取消」）。
        支持复合指令：如「类型改成海报，数量改成4张，确认」会同时解析修改并确认。

    Returns:
        (action, modifications):
            - CONFIRM  -> modifications 包含修改项（若有），状态机处理完修改后放行
            - CANCEL   -> modifications 为空 dict
            - MODIFY   -> modifications 为 {slot_name: new_value} 字典
    """
    if not text:
        return ConfirmationAction.CONFIRM, {}

    text = text.strip()
    text_lower = text.lower()

    # 1. 优先判定 CANCEL（取消语义最强，避免「不要了改成XX」被误判）
    for kw in _CANCEL_KEYWORDS:
        if kw in text:
            return ConfirmationAction.CANCEL, {}

    # 2. 解析所有修改项（无论关键词，只要正则命中就提取）
    modifications: dict[str, Any] = {}
    for slot_name, pattern, converter in _MODIFY_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                modifications[slot_name] = converter(m)
            except (ValueError, IndexError):
                continue

    # 3. 检查是否包含确认关键词
    has_confirm = any(kw in text or kw in text_lower for kw in _CONFIRM_KEYWORDS)
    has_modify_keyword = any(kw in text for kw in _MODIFY_KEYWORDS)

    # 如果同时有修改和确认关键词：先应用修改再确认（状态机会处理）
    if modifications and has_confirm:
        return ConfirmationAction.MODIFY, modifications  # 先MODIFY，下一轮自动确认？
        # 注意：这里返回MODIFY，修改后摘要更新，需要用户再次确认。
        # 如果希望支持"改完直接确认"，需要扩展状态机支持MODIFY_AND_CONFIRM，
        # 本阶段为安全起见，改完仍需再确认一次（避免误操作）

    # 如果只有修改，返回 MODIFY
    if modifications or has_modify_keyword:
        return ConfirmationAction.MODIFY, modifications

    # 4. 判定 CONFIRM
    if has_confirm:
        return ConfirmationAction.CONFIRM, modifications

    # 5. 默认按 CONFIRM 处理（短回复通常是肯定）
    # 兜底：长度 ≤ 6 的短文本视为确认
    if len(text) <= 6:
        return ConfirmationAction.CONFIRM, modifications

    # 其余模糊回复也按 CONFIRM 兜底（保守放行，由老板后续纠正）
    return ConfirmationAction.CONFIRM, modifications


class ConfirmationStateMachine:
    """确认层状态机：维护等待确认状态，处理 CONFIRM/MODIFY/CANCEL 动作。

    一次会话内通常使用同一个 state machine 实例，
    由 confirmation handler 在 awaiting_confirmation 与 handle_action 之间驱动。
    """

    def __init__(self) -> None:
        # 当前是否处于等待确认状态；以及当前等待确认的 summary
        self._awaiting: bool = False
        self._current_summary: Optional[TaskSummary] = None

    def awaiting_confirmation(self, summary: TaskSummary) -> None:
        """进入等待确认状态，记录待确认摘要。"""
        self._awaiting = True
        self._current_summary = summary

    def handle_action(
        self,
        action: ConfirmationAction,
        modifications: dict[str, Any],
        intent: TaskIntent,
        asset_store: Optional[Any] = None,
    ) -> tuple[TaskStatus, Optional[TaskSummary], Optional[ConfirmedTask]]:
        """根据确认动作驱动状态流转。

        Args:
            action: 老板的确认动作（CONFIRM/MODIFY/CANCEL）。
            modifications: MODIFY 时的修改项字典。
            intent: 当前任务意图（MODIFY 时会被原地更新 slots）。
            asset_store: 可选资产层，用于重新构建摘要时注入风格。

        Returns:
            (new_status, new_summary, confirmed_task):
                - CONFIRM  -> (CONFIRMED, None, ConfirmedTask)
                - MODIFY   -> (AWAITING_CONFIRMATION, new_summary, None)
                - CANCEL   -> (CANCELLED, None, None)
        """
        if action == ConfirmationAction.CONFIRM:
            return self._handle_confirm(intent)

        if action == ConfirmationAction.MODIFY:
            return self._handle_modify(modifications, intent, asset_store)

        if action == ConfirmationAction.CANCEL:
            return self._handle_cancel()

        # 未知动作兜底为 CANCEL
        logger.warning("未知确认动作 %s，按取消处理", action)
        return self._handle_cancel()

    # ---------- 内部分支 ----------
    def _handle_confirm(
        self, intent: TaskIntent
    ) -> tuple[TaskStatus, Optional[TaskSummary], Optional[ConfirmedTask]]:
        """CONFIRM：放行，生成 ConfirmedTask。"""
        summary = self._current_summary
        if summary is None:
            # 兜底：若 state machine 未保存 summary，从 intent 重建
            summary = build_summary(intent)

        confirmed = ConfirmedTask(
            task_id=uuid.uuid4().hex[:12],
            intent=intent,
            summary=summary,
            confirmed_at=datetime.now(),
        )
        self._awaiting = False
        self._current_summary = None
        logger.info(
            "确认锁放行：task_id=%s, cost=%d",
            confirmed.task_id, summary.estimated_cost,
        )
        return TaskStatus.CONFIRMED, None, confirmed

    def _handle_modify(
        self,
        modifications: dict[str, Any],
        intent: TaskIntent,
        asset_store: Optional[Any],
    ) -> tuple[TaskStatus, Optional[TaskSummary], Optional[ConfirmedTask]]:
        """MODIFY：用 modifications 更新 intent.slots，重新 build_summary。"""
        for slot_name, new_value in modifications.items():
            intent.slots[slot_name] = SlotValue(
                name=slot_name,
                value=new_value,
                confidence=0.95,  # 老板显式修改，置信度高
            )
            # product 同步到 intent.product
            if slot_name == "product":
                intent.product = str(new_value)
            logger.info(
                "修改槽位 %s = %r", slot_name, new_value,
            )

        new_summary = build_summary(intent, asset_store=asset_store)
        self._current_summary = new_summary
        self._awaiting = True
        return TaskStatus.AWAITING_CONFIRMATION, new_summary, None

    def _handle_cancel(
        self,
    ) -> tuple[TaskStatus, Optional[TaskSummary], Optional[ConfirmedTask]]:
        """CANCEL：取消任务。"""
        self._awaiting = False
        self._current_summary = None
        logger.info("任务已取消")
        return TaskStatus.CANCELLED, None, None
