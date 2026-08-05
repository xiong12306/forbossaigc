"""boss_aigc.confirmation._test_confirmation 确认层验收测试。

覆盖 Task 5 四个子任务的端到端验证：
    1-2.  摘要构建 + 自然语言播报
    3.    parse_confirmation_action 三种动作识别
    4-6.  状态机 CONFIRM / MODIFY / CANCEL
    7-10. handler 首次 / 确认 / 修改 / 取消
    11.   高成本任务二次确认
    12.   确认锁：真实 Pipeline + 真实 access/understanding/confirmation，
          占位 orchestration/execution/delivery；验证未确认时 execution 未被调用。

运行：.venv/bin/python -m boss_aigc.confirmation._test_confirmation
不报错即通过。
"""

from __future__ import annotations

from typing import Any

from boss_aigc.access import create_default_access
from boss_aigc.asset import AssetStore
from boss_aigc.config import configure
from boss_aigc.contracts.enums import (
    ConfirmationAction,
    TaskStatus,
    TaskType,
)
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.delivery import create_default_delivery
from boss_aigc.orchestration import (
    create_default_execution,
    create_default_orchestration,
)
from boss_aigc.pipeline import (
    LAYER_ACCESS,
    LAYER_CONFIRMATION,
    LAYER_DELIVERY,
    LAYER_EXECUTION,
    LAYER_ORCHESTRATION,
    LAYER_UNDERSTANDING,
    Pipeline,
    SessionContext,
)
from boss_aigc.understanding import create_default_understanding

from boss_aigc.confirmation import (
    ConfirmationStateMachine,
    build_confirmation_handler,
    build_summary,
    create_default_confirmation,
    format_summary_text,
    parse_confirmation_action,
)


def _make_image_intent(quantity: int = 3, style: str = "轻奢暖色调") -> TaskIntent:
    """构造一个 IMAGE_GEN 测试意图。"""
    slots: dict[str, SlotValue] = {
        "quantity": SlotValue(name="quantity", value=quantity, confidence=0.95),
    }
    if style:
        slots["style"] = SlotValue(name="style", value=style, confidence=0.85)
    return TaskIntent(
        intent_id="test-intent-1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        slots=slots,
        raw_text=f"给保温杯出 {quantity} 张主图，{style}",
        confidence=0.9,
    )


# ---------- SubTask 5.1: 摘要构建 ----------
def test_build_summary() -> None:
    """1. build_summary：IMAGE_GEN, product=保温杯, quantity=3, style=轻奢暖色调。"""
    intent = _make_image_intent(quantity=3, style="轻奢暖色调")
    summary = build_summary(intent)

    assert summary.task_type == TaskType.IMAGE_GEN, (
        f"task_type 应为 IMAGE_GEN，实际 {summary.task_type}"
    )
    assert summary.product == "保温杯", f"product 应为保温杯，实际 {summary.product}"
    assert summary.params.get("quantity") == 3, (
        f"params.quantity 应为 3，实际 {summary.params.get('quantity')}"
    )
    # 风格应被填入 params
    assert summary.params.get("style") == "轻奢暖色调", (
        f"params.style 应为轻奢暖色调，实际 {summary.params.get('style')}"
    )
    # 平台固定 MOCK
    from boss_aigc.contracts.enums import PlatformKind
    assert summary.platform == PlatformKind.MOCK, (
        f"platform 应为 MOCK，实际 {summary.platform}"
    )
    # IMAGE_GEN: 30 秒/张 * 3 = 90 秒
    assert summary.estimated_duration_sec == 90, (
        f"estimated_duration_sec 应为 90，实际 {summary.estimated_duration_sec}"
    )
    # IMAGE_GEN: 2 积分/张 * 3 = 6 积分
    assert summary.estimated_cost == 6, (
        f"estimated_cost 应为 6，实际 {summary.estimated_cost}"
    )
    # 6 不超过阈值 20，应非高成本
    assert summary.is_high_cost is False, (
        f"is_high_cost 应为 False，实际 {summary.is_high_cost}"
    )
    print("[1/12] build_summary OK")


def test_format_summary_text() -> None:
    """2. format_summary_text：输出含「保温杯」「3 张」「确认」自然语言。"""
    intent = _make_image_intent(quantity=3, style="轻奢暖色调")
    summary = build_summary(intent)
    text = format_summary_text(summary)

    assert "保温杯" in text, f"播报文本应含商品名「保温杯」，实际: {text!r}"
    assert "3" in text and "张" in text, (
        f"播报文本应含「3 张」，实际: {text!r}"
    )
    assert "确认" in text, f"播报文本应以「确认」结尾，实际: {text!r}"
    # 应含积分提示
    assert "6" in text, f"播报文本应含积分 6，实际: {text!r}"
    # 非高成本不应有 ⚠️ 提示
    assert "⚠️" not in text, f"非高成本不应有 ⚠️ 提示，实际: {text!r}"
    print("[2/12] format_summary_text OK")


# ---------- SubTask 5.2: parse_confirmation_action ----------
def test_parse_confirmation_action() -> None:
    """3. parse_confirmation_action：三种动作识别。"""
    # CONFIRM
    for text in ["确认", "确认执行", "开始", "可以", "好的"]:
        action, mods = parse_confirmation_action(text)
        assert action == ConfirmationAction.CONFIRM, (
            f"{text!r} 应识别为 CONFIRM，实际 {action}"
        )
        assert mods == {}, f"CONFIRM 的 modifications 应为空，实际 {mods}"

    # CANCEL
    for text in ["取消", "算了", "不要了"]:
        action, mods = parse_confirmation_action(text)
        assert action == ConfirmationAction.CANCEL, (
            f"{text!r} 应识别为 CANCEL，实际 {action}"
        )
        assert mods == {}

    # MODIFY：数量改成5张
    action, mods = parse_confirmation_action("数量改成5张")
    assert action == ConfirmationAction.MODIFY, (
        f"'数量改成5张' 应识别为 MODIFY，实际 {action}"
    )
    assert mods.get("quantity") == 5, (
        f"应解析出 quantity=5，实际 {mods}"
    )

    # MODIFY：风格换成极简
    action, mods = parse_confirmation_action("风格换成极简")
    assert action == ConfirmationAction.MODIFY, (
        f"'风格换成极简' 应识别为 MODIFY，实际 {action}"
    )
    assert mods.get("style") == "极简", f"应解析出 style=极简，实际 {mods}"

    print("[3/12] parse_confirmation_action OK")


# ---------- SubTask 5.2: 状态机 ----------
def test_state_machine_confirm() -> None:
    """4. 状态机 CONFIRM：返回 CONFIRMED + ConfirmedTask。"""
    intent = _make_image_intent()
    summary = build_summary(intent)

    sm = ConfirmationStateMachine()
    sm.awaiting_confirmation(summary)
    status, new_summary, confirmed = sm.handle_action(
        ConfirmationAction.CONFIRM, {}, intent
    )

    assert status == TaskStatus.CONFIRMED, f"应返回 CONFIRMED，实际 {status}"
    assert new_summary is None, "CONFIRM 不应返回新摘要"
    assert confirmed is not None, "CONFIRM 应返回 ConfirmedTask"
    assert confirmed.intent is intent, "ConfirmedTask 应携带原 intent"
    assert confirmed.summary is summary, "ConfirmedTask 应携带当前 summary"
    print("[4/12] 状态机 CONFIRM OK")


def test_state_machine_modify() -> None:
    """5. 状态机 MODIFY：返回 AWAITING_CONFIRMATION + 新 summary（quantity=5）。"""
    intent = _make_image_intent(quantity=3)
    summary = build_summary(intent)

    sm = ConfirmationStateMachine()
    sm.awaiting_confirmation(summary)
    status, new_summary, confirmed = sm.handle_action(
        ConfirmationAction.MODIFY, {"quantity": 5}, intent
    )

    assert status == TaskStatus.AWAITING_CONFIRMATION, (
        f"应返回 AWAITING_CONFIRMATION，实际 {status}"
    )
    assert new_summary is not None, "MODIFY 应返回新 summary"
    assert confirmed is None, "MODIFY 不应返回 ConfirmedTask"
    # intent.slots 应被更新
    assert intent.slots["quantity"].value == 5, (
        f"intent.slots.quantity 应为 5，实际 {intent.slots['quantity'].value}"
    )
    # 新 summary 应反映 quantity=5
    assert new_summary.params.get("quantity") == 5, (
        f"新 summary.params.quantity 应为 5，实际 {new_summary.params.get('quantity')}"
    )
    # 新 summary 的积分应为 2*5=10
    assert new_summary.estimated_cost == 10, (
        f"新 summary.estimated_cost 应为 10，实际 {new_summary.estimated_cost}"
    )
    print("[5/12] 状态机 MODIFY OK")


def test_state_machine_cancel() -> None:
    """6. 状态机 CANCEL：返回 CANCELLED。"""
    intent = _make_image_intent()
    summary = build_summary(intent)

    sm = ConfirmationStateMachine()
    sm.awaiting_confirmation(summary)
    status, new_summary, confirmed = sm.handle_action(
        ConfirmationAction.CANCEL, {}, intent
    )

    assert status == TaskStatus.CANCELLED, f"应返回 CANCELLED，实际 {status}"
    assert new_summary is None, "CANCEL 不应返回新摘要"
    assert confirmed is None, "CANCEL 不应返回 ConfirmedTask"
    print("[6/12] 状态机 CANCEL OK")


# ---------- SubTask 5.3+5.4: handler ----------
def test_handler_first_turn() -> None:
    """7. handler 首次：传入 intent，context 出现 pending_summary，status=AWAITING_CONFIRMATION。"""
    handler = create_default_confirmation()
    intent = _make_image_intent()
    ctx = SessionContext()

    result = handler(intent, ctx)

    # 返回值应为 TaskSummary
    from boss_aigc.contracts.summary import TaskSummary
    assert isinstance(result, TaskSummary), (
        f"首次应返回 TaskSummary，实际 {type(result).__name__}"
    )
    # context 应有 pending_summary
    assert ctx.pending_summary is not None, "context.pending_summary 应非空"
    assert ctx.pending_summary is result, "context.pending_summary 应与返回值一致"
    # status 应为 AWAITING_CONFIRMATION
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    # confirmed_task 应为 None（未放行）
    assert ctx.confirmed_task is None, "首次不应生成 confirmed_task"
    # extras 应有 speak_text
    assert ctx.extras.get("speak_text"), "extras 应有 speak_text"
    print("[7/12] handler 首次 OK")


def test_handler_confirm_reply() -> None:
    """8. handler 确认回复：context 有 pending_summary 时传入「确认」，status 变 CONFIRMED。"""
    handler = create_default_confirmation()
    intent = _make_image_intent()
    ctx = SessionContext()

    # 第一步：首次生成摘要
    handler(intent, ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION

    # 第二步：老板回复「确认」
    result = handler("确认", ctx)

    # 返回值应为 ConfirmedTask
    from boss_aigc.contracts.execution import ConfirmedTask
    assert isinstance(result, ConfirmedTask), (
        f"确认回复应返回 ConfirmedTask，实际 {type(result).__name__}"
    )
    # status 应变为 CONFIRMED
    assert ctx.status == TaskStatus.CONFIRMED, (
        f"status 应为 CONFIRMED，实际 {ctx.status}"
    )
    # context.confirmed_task 应非空
    assert ctx.confirmed_task is not None, "context.confirmed_task 应非空"
    assert ctx.confirmed_task is result, "context.confirmed_task 应与返回值一致"
    # pending_summary 应被清掉
    assert ctx.pending_summary is None, "确认后 pending_summary 应清空"
    print("[8/12] handler 确认回复 OK")


def test_handler_modify_reply() -> None:
    """9. handler 修改回复：「数量改成5张」→ pending_summary.params.quantity=5，status 仍 AWAITING_CONFIRMATION。"""
    handler = create_default_confirmation()
    intent = _make_image_intent(quantity=3)
    ctx = SessionContext()

    # 首次生成摘要
    handler(intent, ctx)
    assert ctx.pending_summary.params.get("quantity") == 3

    # 老板回复修改
    result = handler("数量改成5张", ctx)

    # status 应仍为 AWAITING_CONFIRMATION
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"修改后 status 应仍为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    # pending_summary 应被更新（quantity=5）
    assert ctx.pending_summary is not None, "修改后 pending_summary 应非空"
    assert ctx.pending_summary.params.get("quantity") == 5, (
        f"修改后 quantity 应为 5，实际 {ctx.pending_summary.params.get('quantity')}"
    )
    # confirmed_task 应为 None
    assert ctx.confirmed_task is None, "修改不应生成 confirmed_task"
    print("[9/12] handler 修改回复 OK")


def test_handler_cancel_reply() -> None:
    """10. handler 取消：「取消」→ status=CANCELLED。"""
    handler = create_default_confirmation()
    intent = _make_image_intent()
    ctx = SessionContext()

    # 首次生成摘要
    handler(intent, ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION

    # 老板回复取消
    result = handler("取消", ctx)

    assert ctx.status == TaskStatus.CANCELLED, (
        f"取消后 status 应为 CANCELLED，实际 {ctx.status}"
    )
    # pending_summary 应被清掉
    assert ctx.pending_summary is None, "取消后 pending_summary 应清空"
    # confirmed_task 应为 None
    assert ctx.confirmed_task is None, "取消不应生成 confirmed_task"
    print("[10/12] handler 取消回复 OK")


def test_high_cost_secondary_confirmation() -> None:
    """11. 高成本二次确认：首次「确认」不放行，再次「确认」才 CONFIRMED。"""
    handler = create_default_confirmation()
    # 构造一个高成本 intent：quantity=15，cost=2*15=30 > 阈值 20
    intent = _make_image_intent(quantity=15, style="轻奢暖色调")
    ctx = SessionContext()

    # 首次生成摘要
    handler(intent, ctx)
    summary = ctx.pending_summary
    assert summary is not None, "首次应生成 pending_summary"
    assert summary.is_high_cost is True, (
        f"quantity=15 时 is_high_cost 应为 True，实际 {summary.is_high_cost} "
        f"(cost={summary.estimated_cost})"
    )
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION

    # 老板第一次「确认」：应触发二次确认，不放行
    handler("确认", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        "高成本首次「确认」后 status 应保持 AWAITING_CONFIRMATION"
    )
    assert ctx.extras.get("awaiting_secondary_confirmation") is True, (
        "高成本首次「确认」后应标记 awaiting_secondary_confirmation=True"
    )
    assert ctx.confirmed_task is None, "高成本首次「确认」不应放行"

    # 老板第二次「确认」：才真正放行
    handler("确认", ctx)
    assert ctx.status == TaskStatus.CONFIRMED, (
        f"高成本二次「确认」后 status 应为 CONFIRMED，实际 {ctx.status}"
    )
    assert ctx.confirmed_task is not None, "高成本二次「确认」应放行"
    # 二次确认标记应被清掉
    assert ctx.extras.get("awaiting_secondary_confirmation") is None, (
        "放行后 awaiting_secondary_confirmation 应被清除"
    )
    print("[11/12] 高成本二次确认 OK")


# ---------- 确认锁集成测试 ----------
def test_confirmation_lock_integration() -> None:
    """12. 确认锁：真实 Pipeline + 真实 access/understanding/confirmation。

    验证：
        - 第 1 轮下任务后 status=AWAITING_CONFIRMATION 且 execution 层未被调用
        - 第 2 轮「确认」后才触发 execution
    """
    # 用计数器包裹真实 execution 处理器，验证是否被调用
    execution_call_count = [0]
    real_exec = create_default_execution()

    def counting_execution(upstream: Any, context: SessionContext) -> Any:
        execution_call_count[0] += 1
        return real_exec(upstream, context)

    # 同样包裹 orchestration 真实处理器
    orchestration_call_count = [0]
    real_orch = create_default_orchestration()

    def counting_orchestration(upstream: Any, context: SessionContext) -> Any:
        orchestration_call_count[0] += 1
        return real_orch(upstream, context)

    # 构造 Pipeline：注册全部真实层处理器
    pipeline = Pipeline()
    pipeline.register_layer(LAYER_ACCESS, create_default_access())
    pipeline.register_layer(LAYER_UNDERSTANDING, create_default_understanding())
    pipeline.register_layer(LAYER_CONFIRMATION, create_default_confirmation())
    pipeline.register_layer(LAYER_ORCHESTRATION, counting_orchestration)
    pipeline.register_layer(LAYER_EXECUTION, counting_execution)
    pipeline.register_layer(
        LAYER_DELIVERY, create_default_delivery(asset_store=AssetStore())
    )

    # 第 1 轮：老板下任务
    ctx = SessionContext()
    resp1 = pipeline.handle_user_input(
        "给保温杯出 3 张主图，轻奢暖色调，1440x1440", ctx
    )

    # 验证：status 应为 AWAITING_CONFIRMATION
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"第 1 轮后 status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    # pending_summary 应非空
    assert ctx.pending_summary is not None, "第 1 轮应生成 pending_summary"
    # confirmed_task 应为 None（未放行）
    assert ctx.confirmed_task is None, "第 1 轮不应生成 confirmed_task"
    # 关键断言：execution 与 orchestration 应未被调用（确认锁生效）
    assert execution_call_count[0] == 0, (
        f"未确认时 execution 不应被调用，实际调用 {execution_call_count[0]} 次"
    )
    assert orchestration_call_count[0] == 0, (
        f"未确认时 orchestration 不应被调用，实际调用 {orchestration_call_count[0]} 次"
    )
    # Response.message 应提示确认
    assert "确认" in resp1.message, (
        f"第 1 轮 Response.message 应含「确认」，实际: {resp1.message!r}"
    )

    # 第 2 轮：老板回复「确认」
    resp2 = pipeline.handle_user_input("确认", ctx)

    # 验证：status 应为 DELIVERED（经 CONFIRMED → EXECUTING → DELIVERED，等老板验收）
    assert ctx.status == TaskStatus.DELIVERED, (
        f"第 2 轮确认后 status 应为 DELIVERED，实际 {ctx.status}"
    )
    # confirmed_task 应非空
    assert ctx.confirmed_task is not None, "第 2 轮应生成 confirmed_task"
    # 关键断言：execution 与 orchestration 应被调用各 1 次
    assert orchestration_call_count[0] == 1, (
        f"确认后 orchestration 应被调用 1 次，实际 {orchestration_call_count[0]} 次"
    )
    assert execution_call_count[0] == 1, (
        f"确认后 execution 应被调用 1 次，实际 {execution_call_count[0]} 次"
    )
    print("[12/12] 确认锁集成测试 OK")


def main() -> None:
    # 确保 high_cost_threshold 是默认值 20（防止被其他测试污染）
    configure(high_cost_threshold=20)

    test_build_summary()
    test_format_summary_text()
    test_parse_confirmation_action()
    test_state_machine_confirm()
    test_state_machine_modify()
    test_state_machine_cancel()
    test_handler_first_turn()
    test_handler_confirm_reply()
    test_handler_modify_reply()
    test_handler_cancel_reply()
    test_high_cost_secondary_confirmation()
    test_confirmation_lock_integration()
    print("\n确认层验收测试全部通过 ✅")


if __name__ == "__main__":
    main()
