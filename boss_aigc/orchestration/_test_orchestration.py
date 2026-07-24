"""boss_aigc.orchestration._test_orchestration 编排层 + 执行层验收测试。

覆盖 Task 6 五个子任务（含整合验证）：
    1. plan_execution 单步：IMAGE_GEN → 1 个 step，platform=MOCK，params 含 task_type/quantity
    2. plan_execution 多步：VIDEO_GEN 无 source_image → 2 个 step，step2.input_refs 含 step1.step_id
    3. select_platform：本阶段返回 MOCK
    4. run_execution 单步成功：MockAdapter 默认，artifacts 非空，DELIVERED
    5. run_execution 重试：fail_then_succeed（前2次失败第3次成功），retry_max=3 最终成功
    6. run_execution 降级：主 fail，retry_max=1，降级到 fallback(none) 成功，元数据记录切换
    7. run_execution 全失败：主备都 fail，FAILED
    8. orchestration handler + execution handler 集成：context 状态正确流转

运行：.venv/bin/python -m boss_aigc.orchestration._test_orchestration
不报错即通过。
"""

from __future__ import annotations

from typing import Optional

from boss_aigc.contracts.enums import PlatformKind, TaskStatus, TaskType
from boss_aigc.contracts.execution import (
    ConfirmedTask,
    TaskExecution,
    TaskIntent,
    TaskResult,
    TaskSummary,
)
from boss_aigc.contracts.intent import SlotValue
from boss_aigc.execution.mock_adapter import MockAdapter
from boss_aigc.execution.registry import AdapterRegistry
from boss_aigc.pipeline import SessionContext

from boss_aigc.orchestration import (
    ExecutionPlan,
    build_execution_handler,
    build_orchestration_handler,
    plan_execution,
    run_execution,
    select_platform,
)


# ---------- 测试辅助 ----------


def _make_confirmed(
    task_type: TaskType = TaskType.IMAGE_GEN,
    product: str = "保温杯",
    slots: Optional[dict] = None,
    summary_params: Optional[dict] = None,
) -> ConfirmedTask:
    """构造一个最小可用的 ConfirmedTask。"""
    intent_slots = slots if slots is not None else {
        "quantity": SlotValue(name="quantity", value=3, confidence=0.95)
    }
    summary_p = summary_params if summary_params is not None else {
        "quantity": 3,
        "style": "轻奢暖色调",
    }
    intent = TaskIntent(
        intent_id="i1",
        task_type=task_type,
        product=product,
        slots=intent_slots,
        raw_text=f"给{product}出图",
        confidence=0.9,
    )
    summary = TaskSummary(
        summary_id="s1",
        task_type=task_type,
        product=product,
        params=summary_p,
        platform=PlatformKind.MOCK,
        estimated_duration_sec=120,
        estimated_cost=10,
    )
    return ConfirmedTask(task_id="t1", intent=intent, summary=summary)


def _make_registry(adapter: MockAdapter) -> AdapterRegistry:
    """构建一个只含 MOCK 的注册表。"""
    reg = AdapterRegistry()
    reg.register(PlatformKind.MOCK, adapter)
    return reg


# ---------- 测试用例 ----------


def test_1_plan_single_step() -> None:
    """1. plan_execution 单步：IMAGE_GEN → 1 个 step，platform=MOCK，params 含 task_type/quantity。"""
    confirmed = _make_confirmed(TaskType.IMAGE_GEN)
    plan = plan_execution(confirmed)

    assert isinstance(plan, TaskExecution)
    assert isinstance(plan, ExecutionPlan)
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.platform == PlatformKind.MOCK
    assert step.name == "出主图"
    # 验证 step_params 含 task_type / quantity
    params = plan.step_params[step.step_id]
    assert params["task_type"] == TaskType.IMAGE_GEN
    assert params["quantity"] == 3
    # 也应含 product 与 style
    assert params["product"] == "保温杯"
    assert params["style"] == "轻奢暖色调"
    print("[1/8] plan_execution 单步 OK")


def test_2_plan_multi_step() -> None:
    """2. plan_execution 多步：VIDEO_GEN 无 source_image → 2 个 step，step2.input_refs 含 step1.step_id。"""
    confirmed = _make_confirmed(
        TaskType.VIDEO_GEN,
        slots={"quantity": SlotValue(name="quantity", value=1)},
        summary_params={"quantity": 1, "style": "电影感"},
    )
    # 注意：不传 source_image slot，触发多步拆分
    plan = plan_execution(confirmed)

    assert len(plan.steps) == 2
    step1, step2 = plan.steps
    assert step1.name == "生成主图"
    assert step2.name == "图转视频"
    assert step1.step_id in step2.input_refs
    # step1 params 的 task_type 应该是 IMAGE_GEN
    s1_params = plan.step_params[step1.step_id]
    assert s1_params["task_type"] == TaskType.IMAGE_GEN
    # step2 params 的 task_type 应该是 VIDEO_GEN，source_image 占位
    s2_params = plan.step_params[step2.step_id]
    assert s2_params["task_type"] == TaskType.VIDEO_GEN
    assert "source_image" in s2_params
    print("[2/8] plan_execution 多步 OK")


def test_3_select_platform() -> None:
    """3. select_platform 本阶段返回 MOCK。"""
    summary = TaskSummary(summary_id="s", task_type=TaskType.IMAGE_GEN)
    assert select_platform(TaskType.IMAGE_GEN, summary) == PlatformKind.MOCK
    assert select_platform(TaskType.VIDEO_GEN, summary) == PlatformKind.MOCK
    assert select_platform(TaskType.COPYWRITING, summary) == PlatformKind.MOCK
    assert select_platform(TaskType.DATA_QUERY, summary) == PlatformKind.MOCK
    print("[3/8] select_platform OK")


def test_4_run_execution_single_success() -> None:
    """4. run_execution 单步成功：MockAdapter 默认，artifacts 非空，DELIVERED。"""
    confirmed = _make_confirmed(
        TaskType.IMAGE_GEN,
        slots={"quantity": SlotValue(name="quantity", value=3)},
        summary_params={"quantity": 3},
    )
    plan = plan_execution(confirmed)
    adapter = MockAdapter()  # 默认 fail_mode=none, polls_to_complete=2
    registry = _make_registry(adapter)

    result = run_execution(plan, registry, retry_max=3)

    assert result.status == TaskStatus.DELIVERED
    assert len(result.artifacts) == 3  # quantity=3
    # 验证 execution 状态/进度被更新
    assert plan.status == TaskStatus.DELIVERED
    assert plan.progress == 100
    # step 状态被更新
    assert plan.steps[0].status == TaskStatus.DELIVERED
    assert plan.steps[0].result is not None
    print(f"[4/8] run_execution 单步成功 OK，artifacts={len(result.artifacts)}")


def test_5_run_execution_retry() -> None:
    """5. run_execution 重试：fail_then_succeed 前2次失败第3次成功，retry_max=3 最终成功。"""
    confirmed = _make_confirmed(
        TaskType.IMAGE_GEN,
        slots={"quantity": SlotValue(name="quantity", value=1)},
        summary_params={"quantity": 1},
    )
    plan = plan_execution(confirmed)
    # fail_then_succeed_n=2: 前 2 次 poll FAILED；polls_to_complete=1: 第 3 次 poll DELIVERED
    adapter = MockAdapter(
        fail_mode="fail_then_succeed",
        fail_then_succeed_n=2,
        polls_to_complete=1,
    )
    registry = _make_registry(adapter)

    result = run_execution(plan, registry, retry_max=3)

    assert result.status == TaskStatus.DELIVERED
    assert len(result.artifacts) == 1
    # 没有切换备用（因为重试已成功）
    assert plan.metadata.get("switched_to_fallback") is not True
    print("[5/8] run_execution 重试成功 OK")


def test_6_run_execution_fallback() -> None:
    """6. run_execution 降级：主 fail，retry_max=1，降级到 fallback(none) 成功，元数据记录切换。"""
    confirmed = _make_confirmed(
        TaskType.IMAGE_GEN,
        slots={"quantity": SlotValue(name="quantity", value=1)},
        summary_params={"quantity": 1},
    )
    plan = plan_execution(confirmed)
    primary = MockAdapter(fail_mode="fail")
    registry = _make_registry(primary)
    fallback = MockAdapter(fail_mode="none")  # 备用：正常完成

    result = run_execution(
        plan, registry, retry_max=1, fallback_adapter=fallback
    )

    assert result.status == TaskStatus.DELIVERED
    assert len(result.artifacts) == 1
    # 元数据记录已切换
    assert plan.metadata.get("switched_to_fallback") is True
    assert plan.steps[0].step_id in plan.metadata.get("fallback_steps", [])
    print("[6/8] run_execution 降级成功 OK")


def test_7_run_execution_all_fail() -> None:
    """7. run_execution 全失败：主备都 fail，FAILED，artifacts 为空。"""
    confirmed = _make_confirmed(
        TaskType.IMAGE_GEN,
        slots={"quantity": SlotValue(name="quantity", value=1)},
        summary_params={"quantity": 1},
    )
    plan = plan_execution(confirmed)
    primary = MockAdapter(fail_mode="fail")
    registry = _make_registry(primary)
    fallback = MockAdapter(fail_mode="fail")  # 备用也失败

    result = run_execution(
        plan, registry, retry_max=1, fallback_adapter=fallback
    )

    assert result.status == TaskStatus.FAILED
    assert len(result.artifacts) == 0
    # execution 也被标记为 FAILED
    assert plan.status == TaskStatus.FAILED
    assert plan.steps[0].status == TaskStatus.FAILED
    # 元数据仍记录了降级尝试
    assert plan.metadata.get("switched_to_fallback") is True
    print("[7/8] run_execution 全失败 OK")


def test_8_handler_integration() -> None:
    """8. orchestration handler + execution handler 集成：context 状态正确流转。"""
    confirmed = _make_confirmed(
        TaskType.IMAGE_GEN,
        slots={"quantity": SlotValue(name="quantity", value=2)},
        summary_params={"quantity": 2},
    )
    context = SessionContext()
    context.confirmed_task = confirmed

    # ---- orchestration handler ----
    orch_handler = build_orchestration_handler()
    execution = orch_handler(confirmed, context)

    assert isinstance(execution, TaskExecution)
    assert context.execution is execution
    assert context.status == TaskStatus.EXECUTING
    assert len(execution.steps) == 1

    # ---- execution handler ----
    adapter = MockAdapter()
    registry = _make_registry(adapter)
    exec_handler = build_execution_handler(registry, retry_max=3)
    result = exec_handler(execution, context)

    assert isinstance(result, TaskResult)
    assert context.result is result
    assert context.status == TaskStatus.DELIVERED
    assert len(result.artifacts) == 2  # quantity=2
    print("[8/8] handler 集成 OK")


def main() -> None:
    test_1_plan_single_step()
    test_2_plan_multi_step()
    test_3_select_platform()
    test_4_run_execution_single_success()
    test_5_run_execution_retry()
    test_6_run_execution_fallback()
    test_7_run_execution_all_fail()
    test_8_handler_integration()
    print("\n全部编排层测试通过 ✅")


if __name__ == "__main__":
    main()
