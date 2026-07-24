"""boss_aigc.delivery._test_delivery 交付层验收测试。

覆盖 Task 7 四个子任务（含整合验证）：
    1.  package_result：3 个 IMAGE artifact → summary_text 含「3 张图」，thumbnails 非空
    2.  DialogChannel.push：写入 context.extras['speak_text']，返回 True
    3.  WechatChannel / WecomChannel：存根不报错
    4.  parse_acceptance：四种动作识别
    5.  handle_acceptance ACCEPT：status=ACCEPTED，asset_store.history 有记录
    6.  handle_acceptance MODIFY：status=AWAITING_CONFIRMATION，pending_summary 非空，intent 是 IMAGE_EDIT
    7.  handle_acceptance REGENERATE：status=CONFIRMED，confirmed_task 非空
    8.  handler 分支 A：传入 TaskResult → package 产出，status 保持 DELIVERED，speak_text 写入
    9.  handler 分支 B：prev_status=DELIVERED 传入「可以了」→ status=ACCEPTED
    10. 集成测试：真实 Pipeline + 真实 access/understanding/confirmation/orchestration/execution/delivery，
        跑两轮：第1轮下任务→确认→执行→交付（DELIVERED）；第2轮「可以了」→ ACCEPTED，资产库有历史记录。

运行：.venv/bin/python -m boss_aigc.delivery._test_delivery
不报错即通过。
"""

from __future__ import annotations

from typing import Any

from boss_aigc.access import create_default_access
from boss_aigc.asset import AssetStore
from boss_aigc.contracts.enums import TaskStatus, TaskType
from boss_aigc.contracts.execution import (
    Artifact,
    ConfirmedTask,
    TaskResult,
)
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.contracts.summary import TaskSummary
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

from boss_aigc.confirmation import create_default_confirmation
from boss_aigc.orchestration import (
    create_default_execution,
    create_default_orchestration,
)
from boss_aigc.understanding import create_default_understanding

from boss_aigc.delivery import (
    AcceptanceAction,
    DeliveryPackage,
    DialogChannel,
    WecomChannel,
    WechatChannel,
    build_delivery_handler,
    create_default_delivery,
    handle_acceptance,
    package_result,
    parse_acceptance,
)


# ---------- 测试辅助 ----------

def _make_image_artifact(idx: int) -> Artifact:
    """构造一个 IMAGE 类型的 Artifact。"""
    return Artifact(
        artifact_id=f"art-{idx}",
        kind="IMAGE",
        url_or_path=f"mock://image/{idx}.png",
        thumbnail_path=f"mock://thumb/{idx}.png",
        metadata={"placeholder": True},
    )


def _make_task_result(artifact_count: int = 3) -> TaskResult:
    """构造一个含 N 个 IMAGE artifact 的 TaskResult。"""
    artifacts = [_make_image_artifact(i + 1) for i in range(artifact_count)]
    return TaskResult(
        result_id="r-test-1",
        task_id="t-test-1",
        artifacts=artifacts,
    )


def _make_context_with_result(artifact_count: int = 3) -> SessionContext:
    """构造一个含已交付 result 的 SessionContext（status=DELIVERED）。"""
    intent = TaskIntent(
        intent_id="i1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        slots={
            "quantity": SlotValue(name="quantity", value=artifact_count, confidence=0.95),
            "style": SlotValue(name="style", value="轻奢暖色调", confidence=0.85),
        },
        raw_text=f"给保温杯出 {artifact_count} 张主图",
        confidence=0.9,
    )
    summary = TaskSummary(
        summary_id="s1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        params={"quantity": artifact_count, "style": "轻奢暖色调"},
    )
    confirmed = ConfirmedTask(task_id="t1", intent=intent, summary=summary)
    result = _make_task_result(artifact_count)

    ctx = SessionContext()
    ctx.intent = intent
    ctx.pending_summary = None  # 已确认
    ctx.confirmed_task = confirmed
    ctx.result = result
    ctx.status = TaskStatus.DELIVERED
    return ctx


# ---------- SubTask 7.1: package_result ----------

def test_1_package_result() -> None:
    """1. package_result：3 个 IMAGE artifact → summary_text 含「3 张图」，thumbnails 非空。"""
    result = _make_task_result(artifact_count=3)
    package = package_result(result)

    # 返回类型正确
    assert isinstance(package, DeliveryPackage), (
        f"应返回 DeliveryPackage，实际 {type(package).__name__}"
    )
    # summary_text 含「3 张图」
    assert "3" in package.summary_text and "张" in package.summary_text and "图" in package.summary_text, (
        f"summary_text 应含「3 张图」，实际: {package.summary_text!r}"
    )
    # thumbnails 非空，且数量等于 artifact 数
    assert len(package.thumbnails) == 3, (
        f"thumbnails 应有 3 个，实际 {len(package.thumbnails)}"
    )
    # artifacts 透传
    assert len(package.artifacts) == 3, (
        f"artifacts 应有 3 个，实际 {len(package.artifacts)}"
    )
    # metadata 含分类统计
    assert package.metadata.get("kind_counts", {}).get("IMAGE") == 3, (
        f"metadata.kind_counts.IMAGE 应为 3，实际 {package.metadata.get('kind_counts')}"
    )
    print("[1/10] package_result OK")


# ---------- SubTask 7.2: 多通道推送 ----------

def test_2_dialog_channel_push() -> None:
    """2. DialogChannel.push：写入 context.extras['speak_text']，返回 True。"""
    package = package_result(_make_task_result(3))
    ctx = SessionContext()
    ch = DialogChannel()

    ok = ch.push(package, ctx)

    assert ok is True, "DialogChannel.push 应返回 True"
    assert ctx.extras.get("speak_text") == package.summary_text, (
        "context.extras['speak_text'] 应等于 package.summary_text"
    )
    print("[2/10] DialogChannel.push OK")


def test_3_stub_channels() -> None:
    """3. WechatChannel / WecomChannel：存根不报错，返回 True。"""
    package = package_result(_make_task_result(2))
    ctx = SessionContext()

    wx_ok = WechatChannel().push(package, ctx)
    wecom_ok = WecomChannel().push(package, ctx)

    assert wx_ok is True, "WechatChannel.push 应返回 True"
    assert wecom_ok is True, "WecomChannel.push 应返回 True"
    print("[3/10] WechatChannel/WecomChannel 存根 OK")


# ---------- SubTask 7.3: parse_acceptance ----------

def test_4_parse_acceptance() -> None:
    """4. parse_acceptance：四种动作识别。"""
    # ACCEPT
    for text in ["可以了", "就这版", "通过", "好了", "可以"]:
        action = parse_acceptance(text)
        assert action == AcceptanceAction.ACCEPT, (
            f"{text!r} 应识别为 ACCEPT，实际 {action}"
        )

    # MODIFY
    for text in ["第2张换纯白", "改成红色", "换一张", "修改第1张"]:
        action = parse_acceptance(text)
        assert action == AcceptanceAction.MODIFY, (
            f"{text!r} 应识别为 MODIFY，实际 {action}"
        )

    # REGENERATE
    for text in ["重做", "重新生成", "再来一版"]:
        action = parse_acceptance(text)
        assert action == AcceptanceAction.REGENERATE, (
            f"{text!r} 应识别为 REGENERATE，实际 {action}"
        )

    # OTHER
    for text in ["啊", "嗯嗯", "？？？"]:
        action = parse_acceptance(text)
        assert action == AcceptanceAction.OTHER, (
            f"{text!r} 应识别为 OTHER，实际 {action}"
        )

    print("[4/10] parse_acceptance OK")


# ---------- SubTask 7.3+7.4: handle_acceptance ----------

def test_5_handle_acceptance_accept() -> None:
    """5. handle_acceptance ACCEPT：status=ACCEPTED，asset_store.history 有记录。"""
    asset_store = AssetStore()
    ctx = _make_context_with_result(artifact_count=3)
    assert len(asset_store.history.get_recent(10)) == 0, "初始 history 应为空"

    new_status, prompt = handle_acceptance(
        AcceptanceAction.ACCEPT, ctx, asset_store=asset_store
    )

    assert new_status == TaskStatus.ACCEPTED, (
        f"ACCEPT 后 status 应为 ACCEPTED，实际 {new_status}"
    )
    assert ctx.status == TaskStatus.ACCEPTED, (
        f"context.status 应为 ACCEPTED，实际 {ctx.status}"
    )
    # history 应有 1 条记录
    records = asset_store.history.get_recent(10)
    assert len(records) == 1, (
        f"history 应有 1 条记录，实际 {len(records)}"
    )
    # 记录的 task_id 应匹配
    assert records[0]["task_id"] == ctx.result.task_id, (
        f"history 记录 task_id 应为 {ctx.result.task_id}，实际 {records[0]['task_id']}"
    )
    # 商品资产库应自动入库
    product_asset = asset_store.product_asset.get("保温杯")
    assert product_asset is not None, "ACCEPT 后商品资产库应有「保温杯」记录"
    # 提示文本应提到归档
    assert "归档" in prompt or "资产库" in prompt, (
        f"提示文本应含「归档/资产库」，实际: {prompt!r}"
    )
    print("[5/10] handle_acceptance ACCEPT OK")


def test_6_handle_acceptance_modify() -> None:
    """6. handle_acceptance MODIFY：status=AWAITING_CONFIRMATION，pending_summary 非空，intent 是 IMAGE_EDIT。"""
    asset_store = AssetStore()
    ctx = _make_context_with_result(artifact_count=3)
    # 模拟老板说「第2张换纯白」
    ctx.user_input = "第2张换纯白"

    new_status, prompt = handle_acceptance(
        AcceptanceAction.MODIFY, ctx, asset_store=asset_store
    )

    assert new_status == TaskStatus.AWAITING_CONFIRMATION, (
        f"MODIFY 后 status 应为 AWAITING_CONFIRMATION，实际 {new_status}"
    )
    # pending_summary 应非空
    assert ctx.pending_summary is not None, "MODIFY 后 pending_summary 应非空"
    # intent 应是 IMAGE_EDIT
    assert ctx.intent is not None, "MODIFY 后 intent 应非空"
    assert ctx.intent.task_type == TaskType.IMAGE_EDIT, (
        f"intent.task_type 应为 IMAGE_EDIT，实际 {ctx.intent.task_type}"
    )
    # 应保留原 product
    assert ctx.intent.product == "保温杯", (
        f"intent.product 应仍为「保温杯」，实际 {ctx.intent.product}"
    )
    # edit_instruction 槽位应填入老板文本
    edit_slot = ctx.intent.slots.get("edit_instruction")
    assert edit_slot is not None and "第2张换纯白" in str(edit_slot.value), (
        f"edit_instruction 槽位应含「第2张换纯白」，实际 {edit_slot}"
    )
    # 提示文本应包含「确认」
    assert "确认" in prompt, f"提示文本应含「确认」，实际: {prompt!r}"
    print("[6/10] handle_acceptance MODIFY OK")


def test_7_handle_acceptance_regenerate() -> None:
    """7. handle_acceptance REGENERATE：status=CONFIRMED，confirmed_task 非空。"""
    asset_store = AssetStore()
    ctx = _make_context_with_result(artifact_count=3)
    original_task_id = ctx.confirmed_task.task_id if ctx.confirmed_task else ""

    new_status, prompt = handle_acceptance(
        AcceptanceAction.REGENERATE, ctx, asset_store=asset_store
    )

    assert new_status == TaskStatus.CONFIRMED, (
        f"REGENERATE 后 status 应为 CONFIRMED，实际 {new_status}"
    )
    # confirmed_task 应非空，且应是新建的（task_id 不同于原）
    assert ctx.confirmed_task is not None, "REGENERATE 后 confirmed_task 应非空"
    assert ctx.confirmed_task.task_id != original_task_id, (
        "REGENERATE 应重建 confirmed_task（task_id 不同）"
    )
    # 提示文本应含「重新生成」
    assert "重新生成" in prompt or "重做" in prompt or "重新" in prompt, (
        f"提示文本应含「重新生成」，实际: {prompt!r}"
    )
    print("[7/10] handle_acceptance REGENERATE OK")


# ---------- 整合：handler 分支 A / B ----------

def test_8_handler_branch_a() -> None:
    """8. handler 分支 A：传入 TaskResult → package 产出，status 保持 DELIVERED，speak_text 写入。"""
    handler = create_default_delivery()
    ctx = SessionContext()
    ctx.status = TaskStatus.EXECUTING  # 模拟执行层刚跑完（未设 DELIVERED）
    result = _make_task_result(3)

    package = handler(result, ctx)

    # 应返回 DeliveryPackage
    assert isinstance(package, DeliveryPackage), (
        f"分支 A 应返回 DeliveryPackage，实际 {type(package).__name__}"
    )
    # status 应保持 DELIVERED（等老板验收）
    assert ctx.status == TaskStatus.DELIVERED, (
        f"分支 A 后 status 应为 DELIVERED，实际 {ctx.status}"
    )
    # context.extras['speak_text'] 应写入
    assert ctx.extras.get("speak_text") == package.summary_text, (
        "extras['speak_text'] 应等于 package.summary_text"
    )
    # context.result 应被写回
    assert ctx.result is result, "context.result 应与传入的 TaskResult 一致"
    print("[8/10] handler 分支 A OK")


def test_9_handler_branch_b() -> None:
    """9. handler 分支 B：prev_status=DELIVERED 传入「可以了」→ status=ACCEPTED。"""
    asset_store = AssetStore()
    handler = build_delivery_handler(asset_store=asset_store)
    ctx = _make_context_with_result(artifact_count=3)
    # prev_status 已是 DELIVERED（_make_context_with_result 设置）

    prompt = handler("可以了", ctx)

    # 应返回 str（提示文本）
    assert isinstance(prompt, str), f"分支 B 应返回 str，实际 {type(prompt).__name__}"
    # status 应变为 ACCEPTED
    assert ctx.status == TaskStatus.ACCEPTED, (
        f"分支 B 「可以了」后 status 应为 ACCEPTED，实际 {ctx.status}"
    )
    # asset_store.history 应有记录
    assert len(asset_store.history.get_recent(10)) == 1, (
        "ACCEPT 后 history 应有 1 条记录"
    )
    print("[9/10] handler 分支 B OK")


# ---------- 集成测试 ----------

def test_10_integration() -> None:
    """10. 集成测试：真实 Pipeline + 全真实层处理器。

    跑两轮（共 3 个 turn）：
        Turn 1：老板下任务「给保温杯出 3 张主图」→ status=AWAITING_CONFIRMATION
        Turn 2：老板「确认」→ 经 confirmation/orchestration/execution/delivery
                → status=DELIVERED（交付层不主动 ACCEPTED，等老板验收）
        Turn 3：老板「可以了」→ 仅走 delivery 路由 → status=ACCEPTED，资产库有历史记录
    """
    asset_store = AssetStore()

    # 构造 Pipeline：注册全部真实层处理器
    pipeline = Pipeline()
    pipeline.register_layer(LAYER_ACCESS, create_default_access())
    pipeline.register_layer(LAYER_UNDERSTANDING, create_default_understanding())
    pipeline.register_layer(LAYER_CONFIRMATION, create_default_confirmation())
    pipeline.register_layer(LAYER_ORCHESTRATION, create_default_orchestration())
    pipeline.register_layer(LAYER_EXECUTION, create_default_execution())
    pipeline.register_layer(LAYER_DELIVERY, create_default_delivery(asset_store=asset_store))

    ctx = SessionContext()

    # ---------- Turn 1：老板下任务 ----------
    resp1 = pipeline.handle_user_input(
        "给保温杯出 3 张主图，轻奢暖色调，1440x1440", ctx
    )
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"Turn 1 后 status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    assert ctx.pending_summary is not None, "Turn 1 应生成 pending_summary"
    assert ctx.confirmed_task is None, "Turn 1 不应生成 confirmed_task"
    # 此时尚未交付
    assert ctx.result is None, "Turn 1 不应有 result"
    assert "确认" in resp1.message, (
        f"Turn 1 message 应含「确认」，实际: {resp1.message!r}"
    )

    # ---------- Turn 2：老板「确认」→ 执行 → 交付 ----------
    resp2 = pipeline.handle_user_input("确认", ctx)
    # 应已通过 confirmation → orchestration → execution → delivery
    assert ctx.status == TaskStatus.DELIVERED, (
        f"Turn 2 后 status 应为 DELIVERED（交付层等老板验收），实际 {ctx.status}"
    )
    assert ctx.confirmed_task is not None, "Turn 2 应已生成 confirmed_task"
    assert ctx.result is not None, "Turn 2 应已生成 result"
    # 执行层产出 artifacts 应非空（MockAdapter 默认 quantity=3 出 3 张图）
    assert len(ctx.result.artifacts) >= 1, (
        f"result.artifacts 应非空，实际 {len(ctx.result.artifacts)}"
    )
    # 交付层应写入 speak_text
    speak_text = ctx.extras.get("speak_text")
    assert speak_text, "Turn 2 后 extras['speak_text'] 应非空"
    # 资产库此时不应有历史记录（还未验收）
    assert len(asset_store.history.get_recent(10)) == 0, (
        "Turn 2 后 history 应仍为空（未验收）"
    )

    # ---------- Turn 3：老板「可以了」→ ACCEPTED + 归档 ----------
    resp3 = pipeline.handle_user_input("可以了", ctx)
    assert ctx.status == TaskStatus.ACCEPTED, (
        f"Turn 3 后 status 应为 ACCEPTED，实际 {ctx.status}"
    )
    # 资产库应有 1 条历史记录
    records = asset_store.history.get_recent(10)
    assert len(records) == 1, (
        f"Turn 3 后 history 应有 1 条记录，实际 {len(records)}"
    )
    # 历史记录的 task_id 应匹配 confirmed_task.task_id
    assert records[0]["task_id"] == ctx.confirmed_task.task_id, (
        f"history 记录 task_id 应为 {ctx.confirmed_task.task_id}，"
        f"实际 {records[0]['task_id']}"
    )
    # 商品资产库应自动入库「保温杯」
    product_asset = asset_store.product_asset.get("保温杯")
    assert product_asset is not None, "Turn 3 后商品资产库应有「保温杯」记录"
    print("[10/10] 集成测试 OK")


def main() -> None:
    test_1_package_result()
    test_2_dialog_channel_push()
    test_3_stub_channels()
    test_4_parse_acceptance()
    test_5_handle_acceptance_accept()
    test_6_handle_acceptance_modify()
    test_7_handle_acceptance_regenerate()
    test_8_handler_branch_a()
    test_9_handler_branch_b()
    test_10_integration()
    print("\n交付层验收测试全部通过 ✅")


if __name__ == "__main__":
    main()
