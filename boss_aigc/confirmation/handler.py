"""boss_aigc.confirmation.handler 确认层处理器。

把 summary_builder + state_machine 串成符合 pipeline LayerHandler 协议的处理器。
职责：
    - 分支 A（首次，context 无 pending_summary）：upstream 是 TaskIntent（来自理解层）。
        build_summary → 存入 context.pending_summary → status=AWAITING_CONFIRMATION
        → 返回 summary（pipeline 早停，Response 提示「请确认」）。
    - 分支 B（context 有 pending_summary）：upstream 是老板的确认回复文本。
        parse_confirmation_action → state_machine.handle_action → 更新 context 状态。
    - 高成本二次确认：is_high_cost=True 时首次 CONFIRM 不放行，要求二次确认。
    - 确认锁日志：放行执行时显式记「确认锁放行」。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from boss_aigc.contracts.enums import ConfirmationAction, TaskStatus
from boss_aigc.contracts.execution import ConfirmedTask
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.logging_setup import get_logger
from boss_aigc.pipeline import LayerHandler, SessionContext

from boss_aigc.confirmation.state_machine import (
    ConfirmationStateMachine,
    parse_confirmation_action,
)
from boss_aigc.confirmation.summary_builder import (
    build_summary,
    format_summary_text,
)

logger = get_logger(__name__, layer="confirmation")

# context.extras 中标记是否等待二次确认的 key
EXTRA_AWAITING_SECONDARY = "awaiting_secondary_confirmation"
# context.extras 中标记 TTS 播报文本的 key
EXTRA_SPEAK_TEXT = "speak_text"


def build_confirmation_handler(asset_store: Optional[Any] = None) -> LayerHandler:
    """构建确认层处理器。

    Args:
        asset_store: 可选的资产层聚合；用于 build_summary 时注入品牌风格。

    Returns:
        LayerHandler：签名 (upstream, context) -> TaskSummary | ConfirmedTask | None。
    """
    # 一个 handler 闭包内共享一个 state machine 实例
    state_machine = ConfirmationStateMachine()

    def handler(upstream: Any, context: SessionContext) -> Any:
        # 路由判断：是否有 pending_summary 决定走分支 A 还是 B
        if context.pending_summary is None:
            return _branch_first_turn(upstream, context, state_machine, asset_store)
        return _branch_reply_turn(upstream, context, state_machine, asset_store)

    return handler


# ---------- 分支 A：首次摘要生成 ----------
def _branch_first_turn(
    upstream: Any,
    context: SessionContext,
    state_machine: ConfirmationStateMachine,
    asset_store: Optional[Any],
) -> Any:
    """首次进入确认层：upstream 是 TaskIntent，构建摘要并等待老板确认。
    对于「一键出图」快速指令（已上传参考图+选了类型），直接自动确认放行。"""
    # 校验上游产出
    if not isinstance(upstream, TaskIntent):
        # 异常路径：upstream 不是 intent，记日志并按 context.intent 兜底
        logger.warning(
            "确认层首次进入但 upstream 非 TaskIntent: %r，尝试用 context.intent 兜底",
            type(upstream).__name__,
        )
        if context.intent is None:
            # 既无 upstream intent 也无 context.intent，无法生成摘要
            context.status = TaskStatus.FAILED
            context.extras[EXTRA_SPEAK_TEXT] = "任务意图缺失，无法生成摘要"
            return TaskSummary(
                summary_id="",
                task_type=context.intent.task_type if context.intent else None,  # type: ignore[arg-type]
            )
        upstream = context.intent

    intent: TaskIntent = upstream

    # 快速通道：检测到「一键出X」指令且有参考图，直接自动确认放行（无需老板点确认）
    raw_text = (intent.raw_text or "").strip()
    has_ref_image = "reference_image" in intent.slots
    is_quick_cmd = raw_text.startswith("一键出")
    if is_quick_cmd and has_ref_image:
        logger.info("检测到一键出图快速指令（有参考图），跳过确认直接放行")
        # 确保有product默认值（一键出指令抽取出的product可能为空或乱码）
        if not intent.product or len(intent.product) < 1:
            intent.product = "参考图商品"
        from boss_aigc.understanding.schemas import SLOT_SCHEMAS
        schema = SLOT_SCHEMAS.get(intent.task_type, {})
        for slot_name, (required, default) in schema.items():
            if not required and default is not None and slot_name not in intent.slots:
                intent.slots[slot_name] = SlotValue(
                    name=slot_name, value=default, confidence=1.0,
                )
                if slot_name == "product" and not intent.product:
                    intent.product = str(default)
        summary = build_summary(intent, asset_store=asset_store)
        confirmed_task = ConfirmedTask(
            task_id=uuid.uuid4().hex[:12],
            intent=intent,
            summary=summary,
            confirmed_at=datetime.now(),
        )
        context.intent = intent
        context.pending_summary = None
        context.confirmed_task = confirmed_task
        context.status = TaskStatus.CONFIRMED
        context.extras[EXTRA_SPEAK_TEXT] = "好的，马上开始生成"
        context.extras["auto_accept"] = True  # 标记快速通道：交付后自动验收归档
        context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
        logger.info("快速指令确认锁放行: task_id=%s", confirmed_task.task_id)
        return confirmed_task

    # 1. 构建摘要
    summary = build_summary(intent, asset_store=asset_store)

    # 2. 写回 context
    # 若上游/前层未把 intent 写入 context（如直接调用 handler 的单元测试场景），
    # 此处兜底写入；正常 pipeline 流程下 understanding 层已写入，不覆盖
    if context.intent is None:
        context.intent = intent
    context.pending_summary = summary
    context.confirmed_task = None  # 清掉旧值（多轮场景兜底）
    context.extras.pop(EXTRA_AWAITING_SECONDARY, None)  # 清掉二次确认标记

    # 3. 进入等待确认状态
    state_machine.awaiting_confirmation(summary)
    context.status = TaskStatus.AWAITING_CONFIRMATION

    # 4. 生成播报文本供 TTS 使用
    speak_text = format_summary_text(summary)
    context.extras[EXTRA_SPEAK_TEXT] = speak_text

    logger.info(
        "已生成任务摘要等待确认: summary_id=%s, cost=%d, high_cost=%s",
        summary.summary_id, summary.estimated_cost, summary.is_high_cost,
    )
    return summary


# ---------- 分支 B：处理老板的确认回复 ----------
def _branch_reply_turn(
    upstream: Any,
    context: SessionContext,
    state_machine: ConfirmationStateMachine,
    asset_store: Optional[Any],
) -> Any:
    """第二+轮：upstream 是老板的确认回复文本，解析并驱动状态机。"""
    # 取老板回复文本
    if isinstance(upstream, str):
        reply_text = upstream
    else:
        reply_text = str(upstream) if upstream is not None else ""

    # 取当前 intent（state machine 修改需要）
    intent = context.intent
    if intent is None:
        logger.warning("确认回复到达但 context.intent 为空，无法处理修改/确认")
        context.status = TaskStatus.FAILED
        context.extras[EXTRA_SPEAK_TEXT] = "任务意图缺失，无法处理确认"
        return None

    # 1. 解析老板回复
    action, modifications = parse_confirmation_action(reply_text)
    logger.info(
        "解析老板确认回复: text=%r, action=%s, modifications=%s",
        reply_text, action.value, modifications,
    )

    # 2. 高成本二次确认特殊处理
    # 仅当 action==CONFIRM 且当前处于二次确认等待中或本次摘要为高成本时触发
    pending_summary = context.pending_summary
    awaiting_secondary = bool(context.extras.get(EXTRA_AWAITING_SECONDARY))

    if action == ConfirmationAction.CONFIRM and pending_summary is not None:
        if awaiting_secondary:
            # 已经在二次确认等待中，本次 CONFIRM 即真正放行
            logger.info("高成本任务二次确认通过，确认锁放行")
            context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
            # 落到下方 state_machine.handle_action 正常 CONFIRM 流程
        elif pending_summary.is_high_cost:
            # 首次 CONFIRM 且为高成本任务：不放行，要求二次确认
            logger.info(
                "高成本任务(cost=%d > 阈值)，触发二次确认",
                pending_summary.estimated_cost,
            )
            secondary_prompt = (
                f"⚠️ 本次预计消耗 {pending_summary.estimated_cost} 积分，较高，"
                f"请再次回复「确认执行」以放行。"
            )
            context.extras[EXTRA_AWAITING_SECONDARY] = True
            context.extras[EXTRA_SPEAK_TEXT] = secondary_prompt
            # 状态保持 AWAITING_CONFIRMATION，等待二次确认
            context.status = TaskStatus.AWAITING_CONFIRMATION
            return pending_summary

    # 3. 处理动作：支持"修改+确认"一步完成
    # 检测是否文本同时包含修改和确认意图（如"类型改成海报，数量4张，确认"）
    has_confirm_intent = any(kw in reply_text for kw in ["确认", "开始", "执行", "好", "行", "可以"])

    if action == ConfirmationAction.MODIFY and modifications and has_confirm_intent:
        # 一步完成：先应用修改更新摘要，再直接放行确认
        logger.info("检测到修改+确认复合指令，一步完成修改并放行")
        # 先应用修改
        for slot_name, new_value in modifications.items():
            intent.slots[slot_name] = SlotValue(
                name=slot_name,
                value=new_value,
                confidence=0.95,
            )
            if slot_name == "product":
                intent.product = str(new_value)
        # 用修改后的intent重新构建摘要
        new_summary = build_summary(intent, asset_store=asset_store)
        context.pending_summary = new_summary
        # 直接放行
        confirmed_task = ConfirmedTask(
            task_id=uuid.uuid4().hex[:12],
            intent=intent,
            summary=new_summary,
            confirmed_at=datetime.now(),
        )
        context.confirmed_task = confirmed_task
        context.pending_summary = None
        context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
        context.extras[EXTRA_SPEAK_TEXT] = "已确认，开始执行"
        context.status = TaskStatus.CONFIRMED
        logger.info(
            "复合指令确认锁放行: task_id=%s", confirmed_task.task_id,
        )
        return confirmed_task

    # 非 CONFIRM 或 已通过二次确认：交给状态机处理
    new_status, new_summary, confirmed_task = state_machine.handle_action(
        action, modifications, intent, asset_store=asset_store
    )

    # 4. 按状态机结果更新 context
    if new_status == TaskStatus.CONFIRMED and confirmed_task is not None:
        # 放行：写 confirmed_task，清掉 pending_summary
        context.confirmed_task = confirmed_task
        context.pending_summary = None
        context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
        context.extras[EXTRA_SPEAK_TEXT] = "已确认，开始执行"
        logger.info(
            "确认锁放行: task_id=%s, intent_id=%s",
            confirmed_task.task_id, intent.intent_id,
        )
    elif new_status == TaskStatus.AWAITING_CONFIRMATION and new_summary is not None:
        # 修改：更新 pending_summary，状态保持等待确认
        context.pending_summary = new_summary
        context.extras[EXTRA_SPEAK_TEXT] = format_summary_text(new_summary)
        # 注意：二次确认标记在 MODIFY 后应清除（任务参数已变，重新评估）
        context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
        # 若新摘要仍为高成本，下次 CONFIRM 会重新触发二次确认
        logger.info("任务已修改，重新生成摘要等待确认")
    elif new_status == TaskStatus.CANCELLED:
        # 取消：清掉 pending_summary
        context.pending_summary = None
        context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
        context.extras[EXTRA_SPEAK_TEXT] = "已取消"
        logger.info("任务已取消")

    context.status = new_status
    # 返回值：CONFIRMED 返回 ConfirmedTask；MODIFY 返回新 summary；CANCEL 返回 None
    if confirmed_task is not None:
        return confirmed_task
    return new_summary


# ---------- 开箱即用工厂 ----------
def create_default_confirmation(asset_store: Optional[Any] = None) -> LayerHandler:
    """构建开箱即用的确认层处理器。

    Args:
        asset_store: 可选资产层；不传则不注入品牌风格。

    Returns:
        LayerHandler 实例。
    """
    return build_confirmation_handler(asset_store=asset_store)
