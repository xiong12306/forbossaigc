"""boss_aigc.delivery.handler 交付层处理器（LayerHandler 实现）。

把 packager + channels + acceptance 串成符合 pipeline LayerHandler 协议的处理器。

两个分支：
    - 分支 A（首次交付）：upstream 是 TaskResult（来自执行层）。
        package_result → pusher.push(dialog) → 把 speak_text 写 context.extras
        → 保持 status=DELIVERED（等验收）→ 返回 DeliveryPackage
    - 分支 B（验收反馈轮）：upstream 是老板文本（来自接入层，prev_status=DELIVERED）。
        parse_acceptance → handle_acceptance → 按结果更新 context/status → 返回提示文本
"""

from __future__ import annotations

from typing import Any, Optional

from boss_aigc.contracts.enums import TaskStatus
from boss_aigc.contracts.execution import TaskResult
from boss_aigc.logging_setup import get_logger
from boss_aigc.pipeline import LayerHandler, SessionContext

from boss_aigc.delivery.acceptance import (
    handle_acceptance,
    parse_acceptance,
)
from boss_aigc.delivery.channels import DeliveryPusher, create_default_pusher
from boss_aigc.delivery.packager import DeliveryPackage, package_result

logger = get_logger(__name__, layer="delivery")


def build_delivery_handler(
    asset_store: Optional[Any] = None,
    pusher: Optional[DeliveryPusher] = None,
) -> LayerHandler:
    """构建交付层处理器。

    Args:
        asset_store: 可选的资产层聚合；ACCEPT 时用于归档。
        pusher: 可选的推送器；None 时使用默认 DeliveryPusher（含 dialog/wechat/wecom）。

    Returns:
        LayerHandler：签名 (upstream, context) -> DeliveryPackage | str。
        - 分支 A 返回 DeliveryPackage
        - 分支 B 返回给老板的提示文本（str）
    """
    if pusher is None:
        pusher = create_default_pusher()

    def handler(upstream: Any, context: SessionContext) -> Any:
        # 区分 A/B：TaskResult → 分支 A；str → 分支 B
        if isinstance(upstream, TaskResult):
            return _branch_a_deliver(upstream, context, pusher)
        if isinstance(upstream, str):
            return _branch_b_acceptance(upstream, context, asset_store)
        # 兜底：upstream 既非 TaskResult 也非 str，尝试用 context.result 走分支 A
        logger.warning(
            "交付层收到非 TaskResult/str 的 upstream: %r，尝试用 context.result 兜底",
            type(upstream).__name__,
        )
        if context.result is not None:
            return _branch_a_deliver(context.result, context, pusher)
        # 实在没有 result，按 OTHER 验收反馈处理
        text = str(upstream) if upstream is not None else ""
        return _branch_b_acceptance(text, context, asset_store)

    return handler


# ---------- 分支 A：首次交付 ----------
def _branch_a_deliver(
    task_result: TaskResult,
    context: SessionContext,
    pusher: DeliveryPusher,
) -> DeliveryPackage:
    """分支 A：打包结果 + 默认 dialog 通道推送，保持 status=DELIVERED 等验收。"""
    # 1. 打包
    package = package_result(task_result)
    # 2. 推送（默认 dialog 通道，把 summary_text 写入 context.extras['speak_text']）
    pusher.push(package, channel="dialog", context=context)
    # 3. 写回 context.result 兜底（执行层应已写入，此处幂等）
    context.result = task_result
    # 4. 保持 status=DELIVERED，等老板验收（不主动改为 ACCEPTED）
    context.status = TaskStatus.DELIVERED
    logger.info(
        "分支 A 交付完成: result_id=%s, artifacts=%d, 等老板验收",
        package.result_id, len(package.artifacts),
    )
    return package


# ---------- 分支 B：验收反馈 ----------
def _branch_b_acceptance(
    text: str,
    context: SessionContext,
    asset_store: Optional[Any],
) -> str:
    """分支 B：解析老板验收反馈，驱动 acceptance 状态机。"""
    # 把老板文本写入 context.user_input（供 MODIFY 构造 edit_instruction 用）
    if text:
        context.user_input = text

    action = parse_acceptance(text)
    logger.info(
        "解析老板验收反馈: text=%r, action=%s", text, action.value,
    )

    new_status, prompt = handle_acceptance(action, context, asset_store)
    logger.info(
        "验收反馈处理完成: action=%s, new_status=%s, prompt=%r",
        action.value, new_status.value, prompt,
    )
    return prompt


# ---------- 开箱即用工厂 ----------
def create_default_delivery(asset_store: Optional[Any] = None) -> LayerHandler:
    """构建开箱即用的交付层处理器。

    Args:
        asset_store: 可选资产层；ACCEPT 时用于归档到 history / product_asset。

    Returns:
        LayerHandler 实例（默认 DialogChannel 推送）。
    """
    return build_delivery_handler(asset_store=asset_store)
