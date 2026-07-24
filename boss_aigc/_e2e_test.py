"""boss_aigc._e2e_test 全链路 Mock 端到端验收测试（Task 9）。

把七层真实处理器全部注册进 Pipeline，跑通完整旅程，并验证：
    9.1 完整旅程 + 修改闭环 + 取消 + 模糊指令追问
    9.2 响应时效（access+understanding / confirmation / speak_text 写入）
    9.3 确认锁不可被绕过（execution 层在未确认前不被调用）
    9.4 降级路径（主适配器 fail → 切换 fallback 成功；主备都 fail → FAILED）
    9.5 各层 create_default_xxx() 独立可实例化

运行：.venv/bin/python -m boss_aigc._e2e_test
不报错即通过。
"""

from __future__ import annotations

import time
from typing import Any

from boss_aigc.access import create_default_access
from boss_aigc.asset import AssetStore, create_default_asset_store
from boss_aigc.config import configure
from boss_aigc.confirmation import create_default_confirmation
from boss_aigc.contracts.enums import PlatformKind, TaskStatus
from boss_aigc.delivery import create_default_delivery
from boss_aigc.execution.mock_adapter import MockAdapter
from boss_aigc.execution.registry import AdapterRegistry
from boss_aigc.orchestration import (
    build_execution_handler,
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
    LayerHandler,
    Pipeline,
    SessionContext,
)
from boss_aigc.understanding import create_default_understanding

# 各测试用例的宽松时效阈值（秒）—— Mock 下应远低于
_ACCESS_UNDERSTANDING_TIMEOUT = 2.0  # 唤醒+ASR+理解一轮
_CONFIRMATION_TIMEOUT = 5.0          # 任务摘要生成
_SPEAK_TEXT_TIMEOUT = 3.0            # 状态播报写入（含 delivery 整轮）


# ============================================================================
# 装配工厂
# ============================================================================

def build_full_pipeline(asset_store: AssetStore | None = None) -> tuple[Pipeline, SessionContext]:
    """把七层真实处理器全部注册进 Pipeline，共享同一个 asset_store。

    Args:
        asset_store: 可选资产层；不传则新建默认 AssetStore。

    Returns:
        (pipeline, SessionContext)：装配好的 Pipeline 与一个全新的会话上下文。
    """
    if asset_store is None:
        asset_store = create_default_asset_store()

    pipeline = Pipeline()
    pipeline.register_layer(LAYER_ACCESS, create_default_access())
    pipeline.register_layer(LAYER_UNDERSTANDING, create_default_understanding())
    pipeline.register_layer(
        LAYER_CONFIRMATION, create_default_confirmation(asset_store=asset_store)
    )
    pipeline.register_layer(LAYER_ORCHESTRATION, create_default_orchestration())
    pipeline.register_layer(LAYER_EXECUTION, create_default_execution())
    pipeline.register_layer(
        LAYER_DELIVERY, create_default_delivery(asset_store=asset_store)
    )
    return pipeline, SessionContext()


# ============================================================================
# SubTask 9.1: 完整旅程 + 修改闭环 + 取消 + 模糊指令追问
# ============================================================================

def test_full_journey() -> None:
    """完整旅程：下任务→确认→收图→可以了，验证 3 轮状态流转与归档。"""
    asset_store = create_default_asset_store()
    pipeline, ctx = build_full_pipeline(asset_store=asset_store)

    # ---------- Turn 1：下任务 ----------
    resp1 = pipeline.handle_user_input(
        "小帮小帮，给保温杯出 3 张主图，轻奢暖色调", ctx
    )
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"Turn 1 后 status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    assert ctx.pending_summary is not None, "Turn 1 应生成 pending_summary"
    summary_text = ctx.pending_summary.params.get("quantity")
    assert summary_text == 3, (
        f"pending_summary.params.quantity 应为 3，实际 {summary_text}"
    )
    # 摘要含「保温杯」「3 张」
    speak_text_1 = ctx.extras.get("speak_text", "")
    assert "保温杯" in speak_text_1, f"摘要应含「保温杯」，实际: {speak_text_1!r}"
    assert "3" in speak_text_1 and "张" in speak_text_1, (
        f"摘要应含「3 张」，实际: {speak_text_1!r}"
    )
    # speak_text 含「确认」
    assert "确认" in speak_text_1, f"speak_text 应含「确认」，实际: {speak_text_1!r}"
    print("[1/4] Turn 1 下任务 → AWAITING_CONFIRMATION OK")

    # ---------- Turn 2：确认 → 执行 → 交付 ----------
    resp2 = pipeline.handle_user_input("确认", ctx)
    assert ctx.status == TaskStatus.DELIVERED, (
        f"Turn 2 后 status 应为 DELIVERED，实际 {ctx.status}"
    )
    assert ctx.result is not None, "Turn 2 应已生成 result"
    image_artifacts = [
        a for a in ctx.result.artifacts if a.kind == "IMAGE"
    ]
    assert len(image_artifacts) == 3, (
        f"应产出 3 个 IMAGE，实际 {len(image_artifacts)}"
    )
    speak_text_2 = ctx.extras.get("speak_text", "")
    assert "出好了" in speak_text_2, (
        f"交付 speak_text 应含「出好了」，实际: {speak_text_2!r}"
    )
    print("[2/4] Turn 2 确认 → DELIVERED（3 张 IMAGE）OK")

    # ---------- Turn 3：可以了 → ACCEPTED + 归档 ----------
    resp3 = pipeline.handle_user_input("可以了", ctx)
    assert ctx.status == TaskStatus.ACCEPTED, (
        f"Turn 3 后 status 应为 ACCEPTED，实际 {ctx.status}"
    )
    history = asset_store.history.get_recent(10)
    assert len(history) >= 1, "ACCEPT 后 asset_store.history 应有记录"
    print("[3/4] Turn 3 可以了 → ACCEPTED + 归档 OK")
    print(f"      最终 message: {resp3.message!r}")


def test_modify_loop() -> None:
    """修改闭环：下任务→修改数量→确认，验证 pending_summary 与 artifacts 数量更新。"""
    asset_store = create_default_asset_store()
    pipeline, ctx = build_full_pipeline(asset_store=asset_store)

    # Turn 1：下任务「给马克杯出 1 张主图」
    pipeline.handle_user_input("给马克杯出 1 张主图", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"Turn 1 后 status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    assert ctx.pending_summary.params.get("quantity") == 1, (
        f"Turn 1 quantity 应为 1，实际 {ctx.pending_summary.params.get('quantity')}"
    )
    print("[1/3] Turn 1 给马克杯出 1 张主图 → AWAITING_CONFIRMATION OK")

    # Turn 2：修改「数量改成 2 张」
    pipeline.handle_user_input("数量改成 2 张", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"Turn 2 修改后 status 应仍为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    assert ctx.pending_summary is not None, "Turn 2 修改后 pending_summary 应非空"
    assert ctx.pending_summary.params.get("quantity") == 2, (
        f"Turn 2 修改后 quantity 应为 2，实际 "
        f"{ctx.pending_summary.params.get('quantity')}"
    )
    print("[2/3] Turn 2 数量改成 2 张 → 仍 AWAITING_CONFIRMATION（quantity=2）OK")

    # Turn 3：确认 → DELIVERED，artifacts 有 2 个
    pipeline.handle_user_input("确认", ctx)
    assert ctx.status == TaskStatus.DELIVERED, (
        f"Turn 3 后 status 应为 DELIVERED，实际 {ctx.status}"
    )
    image_count = len([
        a for a in ctx.result.artifacts if a.kind == "IMAGE"
    ])
    assert image_count == 2, (
        f"修改后应产出 2 个 IMAGE，实际 {image_count}"
    )
    print("[3/3] Turn 3 确认 → DELIVERED（2 张 IMAGE）OK")


def test_cancel() -> None:
    """取消路径：下任务→取消，验证 status=CANCELLED。"""
    pipeline, ctx = build_full_pipeline()

    # Turn 1：下任务
    pipeline.handle_user_input("给水杯出图", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"Turn 1 后 status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    print("[1/2] Turn 1 给水杯出图 → AWAITING_CONFIRMATION OK")

    # Turn 2：取消
    pipeline.handle_user_input("取消", ctx)
    assert ctx.status == TaskStatus.CANCELLED, (
        f"Turn 2 后 status 应为 CANCELLED，实际 {ctx.status}"
    )
    assert ctx.pending_summary is None, "取消后 pending_summary 应被清空"
    print("[2/2] Turn 2 取消 → CANCELLED OK")


def test_fuzzy_follow_up() -> None:
    """模糊指令追问：缺商品时进入 UNDERSTANDING，补全后进入 AWAITING_CONFIRMATION。"""
    pipeline, ctx = build_full_pipeline()

    # Turn 1：「出几张图」缺商品，应触发追问
    pipeline.handle_user_input("出几张图", ctx)
    assert ctx.status == TaskStatus.UNDERSTANDING, (
        f"Turn 1 后 status 应为 UNDERSTANDING，实际 {ctx.status}"
    )
    assert ctx.extras.get("needs_follow_up") is True, "应标记 needs_follow_up=True"
    follow_up = ctx.extras.get("follow_up_question", "")
    assert follow_up, "应生成追问文本"
    print(f"[1/2] Turn 1 出几张图 → UNDERSTANDING（追问: {follow_up!r}）OK")

    # Turn 2：补全「给保温杯出 3 张」→ AWAITING_CONFIRMATION
    pipeline.handle_user_input("给保温杯出 3 张", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION, (
        f"Turn 2 后 status 应为 AWAITING_CONFIRMATION，实际 {ctx.status}"
    )
    print("[2/2] Turn 2 给保温杯出 3 张 → AWAITING_CONFIRMATION OK")


# ============================================================================
# SubTask 9.2: 响应时效验证
# ============================================================================

def test_response_timing() -> None:
    """时效：access+understanding < 2s；confirmation 一轮 < 5s；speak_text 写入 < 3s。

    注：Mock 下应远低于阈值，断言仅作为架构开销回归保护。
    """
    pipeline, ctx = build_full_pipeline()

    # 1. access + understanding 一轮（输入「出几张图」缺商品，停在 UNDERSTANDING）
    start = time.perf_counter()
    pipeline.handle_user_input("出几张图", ctx)
    elapsed_au = time.perf_counter() - start
    assert elapsed_au < _ACCESS_UNDERSTANDING_TIMEOUT, (
        f"access+understanding 耗时 {elapsed_au:.3f}s 超过 "
        f"{_ACCESS_UNDERSTANDING_TIMEOUT}s 阈值"
    )
    print(
        f"[1/3] access+understanding 耗时 {elapsed_au * 1000:.2f}ms "
        f"(< {_ACCESS_UNDERSTANDING_TIMEOUT}s) OK"
    )

    # 2. 任务摘要生成（confirmation 一轮）：新会话，下任务到 AWAITING_CONFIRMATION
    ctx2 = SessionContext()
    start = time.perf_counter()
    pipeline.handle_user_input("给保温杯出 3 张主图，轻奢暖色调", ctx2)
    elapsed_conf = time.perf_counter() - start
    assert elapsed_conf < _CONFIRMATION_TIMEOUT, (
        f"confirmation 一轮耗时 {elapsed_conf:.3f}s 超过 "
        f"{_CONFIRMATION_TIMEOUT}s 阈值"
    )
    assert ctx2.status == TaskStatus.AWAITING_CONFIRMATION
    print(
        f"[2/3] confirmation 一轮耗时 {elapsed_conf * 1000:.2f}ms "
        f"(< {_CONFIRMATION_TIMEOUT}s) OK"
    )

    # 3. 状态播报写入（speak_text 设置）：第 2 轮「确认」整轮，delivery 写入 speak_text
    start = time.perf_counter()
    pipeline.handle_user_input("确认", ctx2)
    elapsed_speak = time.perf_counter() - start
    assert elapsed_speak < _SPEAK_TEXT_TIMEOUT, (
        f"speak_text 写入轮耗时 {elapsed_speak:.3f}s 超过 "
        f"{_SPEAK_TEXT_TIMEOUT}s 阈值"
    )
    assert ctx2.status == TaskStatus.DELIVERED
    assert ctx2.extras.get("speak_text"), "DELIVERED 后 speak_text 应非空"
    print(
        f"[3/3] speak_text 写入轮耗时 {elapsed_speak * 1000:.2f}ms "
        f"(< {_SPEAK_TEXT_TIMEOUT}s) OK"
    )


# ============================================================================
# SubTask 9.3: 确认锁不可被绕过
# ============================================================================

def _build_pipeline_with_counting_execution(
    asset_store: AssetStore,
) -> tuple[Pipeline, list[int]]:
    """构造 Pipeline，把 execution 层换成计数包装版本。

    Returns:
        (pipeline, [counter])：counter[0] 记录 execution handler 被调用次数。
    """
    counter = [0]
    real_exec = create_default_execution()

    def counting_execution(upstream: Any, context: SessionContext) -> Any:
        counter[0] += 1
        return real_exec(upstream, context)

    pipeline = Pipeline()
    pipeline.register_layer(LAYER_ACCESS, create_default_access())
    pipeline.register_layer(LAYER_UNDERSTANDING, create_default_understanding())
    pipeline.register_layer(
        LAYER_CONFIRMATION, create_default_confirmation(asset_store=asset_store)
    )
    pipeline.register_layer(LAYER_ORCHESTRATION, create_default_orchestration())
    pipeline.register_layer(LAYER_EXECUTION, counting_execution)
    pipeline.register_layer(
        LAYER_DELIVERY, create_default_delivery(asset_store=asset_store)
    )
    return pipeline, counter


def test_confirmation_lock_not_bypassed() -> None:
    """确认锁：未确认时 execution 不被调用；确认后调用 1 次。"""
    asset_store = create_default_asset_store()
    pipeline, counter = _build_pipeline_with_counting_execution(asset_store)
    ctx = SessionContext()

    # Turn 1：下任务 → AWAITING_CONFIRMATION，execution 调用次数应为 0
    pipeline.handle_user_input("给保温杯出 3 张主图", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION
    assert counter[0] == 0, (
        f"未确认时 execution 不应被调用，实际 {counter[0]} 次"
    )
    print("[1/2] 下任务后 status=AWAITING_CONFIRMATION，execution 调用 0 次 OK")

    # Turn 2：确认 → execution 调用 1 次
    pipeline.handle_user_input("确认", ctx)
    assert counter[0] == 1, (
        f"确认后 execution 应被调用 1 次，实际 {counter[0]} 次"
    )
    assert ctx.status == TaskStatus.DELIVERED
    print("[2/2] 确认后 execution 调用 1 次 OK")


def test_confirmation_lock_cancel_keeps_zero() -> None:
    """确认锁：下任务→取消，execution 调用次数仍为 0。"""
    asset_store = create_default_asset_store()
    pipeline, counter = _build_pipeline_with_counting_execution(asset_store)
    ctx = SessionContext()

    pipeline.handle_user_input("给水杯出图", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION
    assert counter[0] == 0

    pipeline.handle_user_input("取消", ctx)
    assert ctx.status == TaskStatus.CANCELLED
    assert counter[0] == 0, (
        f"取消后 execution 不应被调用，实际 {counter[0]} 次"
    )
    print("取消路径 execution 调用 0 次 OK")


# ============================================================================
# SubTask 9.4: 降级路径验证
# ============================================================================

def _build_failing_pipeline(
    asset_store: AssetStore,
    primary_fail: bool = True,
    fallback_fail: bool = False,
) -> Pipeline:
    """构造一个主适配器故障的 Pipeline。

    Args:
        asset_store: 资产层。
        primary_fail: 主适配器是否故障（True=fail）。
        fallback_fail: 备用适配器是否故障（True=fail）。
    """
    primary_mode = "fail" if primary_fail else "none"
    fallback_mode = "fail" if fallback_fail else "none"

    registry = AdapterRegistry()
    registry.register(PlatformKind.MOCK, MockAdapter(fail_mode=primary_mode))

    execution_handler = build_execution_handler(
        registry,
        retry_max=1,
        fallback_adapter=MockAdapter(fail_mode=fallback_mode),
    )

    pipeline = Pipeline()
    pipeline.register_layer(LAYER_ACCESS, create_default_access())
    pipeline.register_layer(LAYER_UNDERSTANDING, create_default_understanding())
    pipeline.register_layer(
        LAYER_CONFIRMATION, create_default_confirmation(asset_store=asset_store)
    )
    pipeline.register_layer(LAYER_ORCHESTRATION, create_default_orchestration())
    pipeline.register_layer(LAYER_EXECUTION, execution_handler)
    pipeline.register_layer(
        LAYER_DELIVERY, create_default_delivery(asset_store=asset_store)
    )
    return pipeline


def test_fallback_success() -> None:
    """降级成功：主适配器 fail → 切换 fallback(none) 成功，metadata 记 switched_to_fallback。"""
    asset_store = create_default_asset_store()
    pipeline = _build_failing_pipeline(
        asset_store, primary_fail=True, fallback_fail=False
    )
    ctx = SessionContext()

    # Turn 1：下任务 → AWAITING_CONFIRMATION
    pipeline.handle_user_input("给保温杯出 1 张主图", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION

    # Turn 2：确认 → 主适配器失败，降级到备用成功 → DELIVERED
    pipeline.handle_user_input("确认", ctx)
    assert ctx.status == TaskStatus.DELIVERED, (
        f"降级成功后 status 应为 DELIVERED，实际 {ctx.status}"
    )
    assert ctx.result is not None and len(ctx.result.artifacts) >= 1, (
        "降级成功后 result.artifacts 应非空"
    )
    # execution 元数据记录 switched_to_fallback=True
    execution = ctx.execution
    assert execution is not None, "execution 应非空"
    metadata = getattr(execution, "metadata", {}) or {}
    assert metadata.get("switched_to_fallback") is True, (
        f"execution.metadata.switched_to_fallback 应为 True，实际 {metadata}"
    )
    print(
        "[1/2] 主适配器 fail → 降级 fallback 成功 → DELIVERED，"
        "metadata.switched_to_fallback=True OK"
    )


def test_fallback_all_fail() -> None:
    """降级全失败：主备都 fail → TaskResult.status=FAILED。"""
    asset_store = create_default_asset_store()
    pipeline = _build_failing_pipeline(
        asset_store, primary_fail=True, fallback_fail=True
    )
    ctx = SessionContext()

    # Turn 1：下任务 → AWAITING_CONFIRMATION
    pipeline.handle_user_input("给保温杯出 1 张主图", ctx)
    assert ctx.status == TaskStatus.AWAITING_CONFIRMATION

    # Turn 2：确认 → 主备都 fail → FAILED
    pipeline.handle_user_input("确认", ctx)
    assert ctx.status == TaskStatus.FAILED, (
        f"主备都失败后 status 应为 FAILED，实际 {ctx.status}"
    )
    assert ctx.result is not None and ctx.result.status == TaskStatus.FAILED, (
        f"TaskResult.status 应为 FAILED，实际 {ctx.result.status if ctx.result else None}"
    )
    print("[2/2] 主备都 fail → TaskResult.status=FAILED OK")


# ============================================================================
# SubTask 9.5: 各层可独立实例化
# ============================================================================

def test_default_factories_instantiate() -> None:
    """各层 create_default_xxx() 都能独立实例化且返回可调用对象（LayerHandler）。"""
    asset_store = create_default_asset_store()

    handlers: list[tuple[str, LayerHandler]] = [
        ("access", create_default_access()),
        ("understanding", create_default_understanding()),
        ("confirmation", create_default_confirmation(asset_store=asset_store)),
        ("orchestration", create_default_orchestration()),
        ("execution", create_default_execution()),
        ("delivery", create_default_delivery(asset_store=asset_store)),
    ]

    for name, handler in handlers:
        assert callable(handler), (
            f"{name} 工厂返回的对象不可调用，不是 LayerHandler"
        )
        # 实际调用一下确保不抛异常（用最小输入）
        ctx = SessionContext()
        try:
            if name == "access":
                handler("测试输入", ctx)
            elif name == "understanding":
                handler("给保温杯出 1 张主图", ctx)
            elif name == "confirmation":
                # 先放一个 intent 进 ctx 让 confirmation 走首次分支
                from boss_aigc.contracts.enums import TaskType
                from boss_aigc.contracts.intent import SlotValue, TaskIntent

                ctx.intent = TaskIntent(
                    intent_id="i1",
                    task_type=TaskType.IMAGE_GEN,
                    product="保温杯",
                    slots={
                        "quantity": SlotValue(
                            name="quantity", value=1, confidence=0.95
                        )
                    },
                    raw_text="给保温杯出 1 张主图",
                    confidence=0.9,
                )
                handler(ctx.intent, ctx)
            elif name == "orchestration":
                # orchestration 需要 ConfirmedTask，但独立调用应至少不抛异常
                # 此处用空 upstream 触发兜底分支（返回空 Execution，status=FAILED）
                handler(None, ctx)
            elif name == "execution":
                handler(None, ctx)  # 兜底分支
            elif name == "delivery":
                handler("可以了", ctx)  # 走分支 B（OTHER）
        except Exception as e:
            raise AssertionError(
                f"{name} 工厂返回的 handler 调用抛异常: {e!r}"
            ) from e

    print(f"各层 create_default_xxx() 独立实例化 OK（共 {len(handlers)} 层）")


# ============================================================================
# 主入口
# ============================================================================

def main() -> None:
    # 确保 high_cost_threshold 是默认值 20（防止被其他测试污染）
    configure(high_cost_threshold=20)

    print("=" * 60)
    print("SubTask 9.1: 完整旅程 + 修改闭环 + 取消 + 模糊指令追问")
    print("=" * 60)
    test_full_journey()
    test_modify_loop()
    test_cancel()
    test_fuzzy_follow_up()

    print("\n" + "=" * 60)
    print("SubTask 9.2: 响应时效验证")
    print("=" * 60)
    test_response_timing()

    print("\n" + "=" * 60)
    print("SubTask 9.3: 确认锁不可被绕过")
    print("=" * 60)
    test_confirmation_lock_not_bypassed()
    test_confirmation_lock_cancel_keeps_zero()

    print("\n" + "=" * 60)
    print("SubTask 9.4: 降级路径验证")
    print("=" * 60)
    test_fallback_success()
    test_fallback_all_fail()

    print("\n" + "=" * 60)
    print("SubTask 9.5: 各层可独立实例化")
    print("=" * 60)
    test_default_factories_instantiate()

    print("\n" + "=" * 60)
    print("全部 E2E 测试通过 ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
