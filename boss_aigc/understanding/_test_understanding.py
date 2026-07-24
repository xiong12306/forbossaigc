"""boss_aigc.understanding._test_understanding 理解层验收测试。

覆盖 Task 4 四个子任务的端到端验证：
1. 完整指令解析（schema + 识别器）
2. 缺商品时生成追问（多轮补全）
3. 多轮合并：第一轮缺商品，第二轮补充
4. 模糊指令无候选时触发澄清

运行：.venv/bin/python -m boss_aigc.understanding._test_understanding
不报错即通过。
"""

from __future__ import annotations

from boss_aigc.contracts.enums import TaskStatus, TaskType
from boss_aigc.pipeline import SessionContext

from boss_aigc.understanding import (
    RuleBasedRecognizer,
    build_understanding_handler,
    create_default_understanding,
    get_optional_slots,
    get_required_slots,
)
from boss_aigc.understanding.dialog import clarify_if_ambiguous, multi_turn_complete


def test_full_parse() -> None:
    """1. 完整指令解析：所有槽位齐全。"""
    recognizer = RuleBasedRecognizer()
    ctx = SessionContext()
    intent = recognizer.recognize(
        "给保温杯出 3 张主图，轻奢暖色调，1440x1440", ctx
    )

    assert intent.task_type == TaskType.IMAGE_GEN, (
        f"task_type 应为 IMAGE_GEN，实际 {intent.task_type}"
    )
    assert intent.product == "保温杯", f"product 应为保温杯，实际 {intent.product}"
    assert intent.slots["quantity"].value == 3, (
        f"quantity 应为 3，实际 {intent.slots['quantity'].value}"
    )
    style = intent.slots["style"].value
    assert "轻奢" in style and "暖色调" in style, f"style 应含轻奢暖色调，实际 {style}"
    assert intent.slots["size"].value == "1440x1440", (
        f"size 应为 1440x1440，实际 {intent.slots['size'].value}"
    )
    assert intent.missing_slots == [], (
        f"missing_slots 应为空，实际 {intent.missing_slots}"
    )
    print("[1/4] 完整指令解析 OK")


def test_missing_product_followup() -> None:
    """2. 缺商品时生成追问。"""
    recognizer = RuleBasedRecognizer()
    ctx = SessionContext()
    intent = multi_turn_complete("出几张图", ctx, recognizer)

    assert "product" in intent.missing_slots, (
        f"missing_slots 应含 product，实际 {intent.missing_slots}"
    )
    follow_up = ctx.extras.get("follow_up_question", "")
    assert follow_up, f"应生成追问文本，实际 {follow_up!r}"
    assert "商品" in follow_up or "产品" in follow_up, (
        f"追问应问商品，实际 {follow_up!r}"
    )
    assert ctx.extras.get("needs_follow_up") is True, "needs_follow_up 应为 True"
    print("[2/4] 缺商品追问 OK")


def test_multi_turn_merge() -> None:
    """3. 多轮合并：第一轮缺商品，第二轮补充。"""
    recognizer = RuleBasedRecognizer()
    ctx = SessionContext()

    # 第一轮：缺商品
    intent1 = multi_turn_complete("出 3 张主图", ctx, recognizer)
    assert "product" in intent1.missing_slots, (
        f"第一轮 missing_slots 应含 product，实际 {intent1.missing_slots}"
    )
    assert intent1.slots["quantity"].value == 3, "第一轮应抽出 quantity=3"

    # 第二轮：补充商品
    intent2 = multi_turn_complete("保温杯", ctx, recognizer)
    assert intent2.product == "保温杯", (
        f"合并后 product 应为保温杯，实际 {intent2.product}"
    )
    assert "product" not in intent2.missing_slots, (
        f"合并后 missing_slots 不应含 product，实际 {intent2.missing_slots}"
    )
    # 第二轮 quantity 应保留
    assert intent2.slots["quantity"].value == 3, "合并后 quantity 应保留为 3"
    print("[3/4] 多轮合并 OK")


def test_ambiguous_clarification() -> None:
    """4. 模糊指令无候选时触发澄清。"""
    recognizer = RuleBasedRecognizer()
    ctx = SessionContext()
    # 不设置 recent_products，模拟无候选场景
    intent = recognizer.recognize("把这个弄好看点", ctx)
    intent = clarify_if_ambiguous(intent, ctx)

    assert intent.needs_clarification is True, "needs_clarification 应为 True"
    assert intent.clarification_options, "应提供澄清候选选项"
    # 无候选时应提供任务类型选项
    assert any("出图" in opt or "改图" in opt for opt in intent.clarification_options), (
        f"无候选时应有任务类型选项，实际 {intent.clarification_options}"
    )
    print("[4/4] 模糊指令澄清 OK")


def test_handler_integration() -> None:
    """额外：处理器端到端集成（验收 spec 之外，保证 handler 可用）。"""
    handler = create_default_understanding()
    ctx = SessionContext()
    intent = handler("给保温杯出 3 张主图，轻奢暖色调，1440x1440", ctx)
    assert intent.task_type == TaskType.IMAGE_GEN
    assert intent.product == "保温杯"
    assert ctx.intent is intent, "应写回 context.intent"
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"完整指令应进入 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )

    # 缺商品场景：状态停留在 UNDERSTANDING
    ctx2 = SessionContext()
    intent2 = handler("出几张图", ctx2)
    assert ctx2.status == TaskStatus.UNDERSTANDING, (
        f"缺商品应停留在 UNDERSTANDING，实际 {ctx2.status}"
    )
    assert ctx2.extras.get("needs_follow_up") is True
    print("[5/5] 处理器集成 OK")


def test_schema_helpers() -> None:
    """额外：schema 查询辅助函数（验收 spec 之外，保证 API 完整）。"""
    required = get_required_slots(TaskType.IMAGE_GEN)
    assert "product" in required, "IMAGE_GEN 必填应含 product"
    optional = get_optional_slots(TaskType.IMAGE_GEN)
    assert "quantity" in optional, "IMAGE_GEN 可选应含 quantity"
    assert "style" in optional, "IMAGE_GEN 可选应含 style"

    # COPYWRITING 必填应含 product + copy_type
    cw_required = get_required_slots(TaskType.COPYWRITING)
    assert "product" in cw_required and "copy_type" in cw_required

    # DATA_QUERY 必填应含 query_target
    dq_required = get_required_slots(TaskType.DATA_QUERY)
    assert dq_required == ["query_target"]
    print("[6/6] Schema 查询 OK")


def main() -> None:
    test_full_parse()
    test_missing_product_followup()
    test_multi_turn_merge()
    test_ambiguous_clarification()
    test_handler_integration()
    test_schema_helpers()
    print("\n理解层验收测试全部通过 ✅")


if __name__ == "__main__":
    main()
