"""boss_aigc.orchestration.scheduler 编排层调度器。

职责：
- run_step_with_retry: 单步执行 + 失败重试（核心辅助函数）
- run_execution: 按 steps 顺序串行执行 TaskExecution → TaskResult，含重试与降级

设计要点：
- 串行执行：多步间 input_refs 依赖必须串行（本阶段不并行）。
- 重试语义：单步 poll 返回 FAILED 时累计 fail_count，未超 retry_max 则继续轮询。
  注：MockAdapter 的状态机通过 poll 推进（fail_then_succeed 模式下 N 次失败后自动转成功），
  因此重试 = 重新 poll 同一 task_id；真实适配器场景下 FAILED 通常是终态，应改为重新 submit，
  后续接入即梦/通义万相时改造此函数。
- 降级：单步重试耗尽后切换到 fallback_adapter；本阶段 MOCK 的备用仍是 MOCK（用 fail_mode="none" 模拟）。
- 进度汇总：progress = 已完成步数 / 总步数 * 100。
- 多步场景：把前序步骤的 Artifact.artifact_id 填入后续步骤 params（如 source_image）。
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from boss_aigc.contracts.enums import TaskStatus
from boss_aigc.contracts.execution import (
    Artifact,
    TaskExecution,
    TaskResult,
)
from boss_aigc.execution.adapter import PlatformAdapter
from boss_aigc.execution.registry import AdapterRegistry
from boss_aigc.logging_setup import get_logger

from boss_aigc.orchestration.planner import ExecutionPlan

logger = get_logger(__name__, layer="orchestration")

# poll 循环最大次数（防止 timeout 模式死循环）
_MAX_POLLS = 100


def run_step_with_retry(
    adapter: PlatformAdapter,
    params: dict[str, Any],
    retry_max: int = 1,
    max_polls: int = _MAX_POLLS,
) -> tuple[TaskStatus, list[Artifact]]:
    """单步执行 + 失败重试。

    策略：
    1. submit 一次 → platform_task_id（同步API如NanoBanana在submit时已完成请求）
    2. poll 一次获取结果：
       - DELIVERED: 返回 (DELIVERED, artifacts)
       - EXECUTING: 继续轮询（异步API场景）
       - FAILED: 直接返回失败（真实API失败不重试，避免重复扣费；Mock场景通过fail_then_succeed模式模拟）

    注：
    - MockAdapter 的状态机通过 poll 推进，需要多次poll
    - 真实适配器（NanoBanana等同步API）submit后直接poll一次即可得到结果
    - 重试策略：真实API默认retry_max=1（不重试），Mock场景可配置多次

    Args:
        adapter: 平台适配器实例。
        params: adapter.submit 调用参数。
        retry_max: 失败重试上限（真实API建议设为1避免重复扣费）。
        max_polls: poll 循环最大次数（防 timeout 模式死循环）。

    Returns:
        (TaskStatus, list[Artifact])：成功时 artifacts 非空；失败时 artifacts 为空列表。
    """
    from boss_aigc.contracts.enums import PlatformKind

    is_mock = getattr(adapter, 'kind', None) == PlatformKind.MOCK
    effective_retry_max = retry_max if is_mock else 1

    for attempt in range(effective_retry_max + 1):
        task_id = adapter.submit(params)
        polls = 0

        while polls < max_polls:
            polls += 1
            status, artifacts = adapter.poll(task_id)

            if status == TaskStatus.DELIVERED:
                return status, list(artifacts or [])

            if status == TaskStatus.EXECUTING:
                if not is_mock and polls <= 2:
                    import time
                    from boss_aigc.config import get_settings
                    time.sleep(get_settings().poll_interval_sec)
                continue

            if status == TaskStatus.FAILED:
                if attempt < effective_retry_max and is_mock:
                    logger.info("step 第%d次尝试失败，准备重试", attempt + 1)
                    break
                logger.warning(
                    "step 执行失败（尝试 %d/%d）",
                    attempt + 1, effective_retry_max + 1,
                )
                return status, []

            logger.warning("step 进入非预期状态 %s，判定失败", status.value)
            return TaskStatus.FAILED, []

        if polls >= max_polls:
            logger.warning("poll 次数达上限 %d，判定失败", max_polls)
            return TaskStatus.FAILED, []

    return TaskStatus.FAILED, []


def _resolve_step_params(
    execution: TaskExecution,
    step_id: str,
    default_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从 ExecutionPlan 取 step 对应的 params；若不是 ExecutionPlan 则返回 default_params。"""
    if isinstance(execution, ExecutionPlan):
        params = execution.step_params.get(step_id, {})
        return dict(params)  # 深拷贝避免污染原 plan
    return dict(default_params or {})


def _fill_input_refs(
    execution: TaskExecution,
    step,
    params: dict[str, Any],
) -> None:
    """多步场景：把前序步骤的产出填入当前步骤的 params（如 source_image）。"""
    for ref_id in step.input_refs:
        # 找到 ref_id 对应的前序 step
        for prev_step in execution.steps:
            if prev_step.step_id == ref_id and prev_step.result is not None:
                # 把产出 artifact_id 填入 source_image（执行时引用前序产出）
                params["source_image"] = prev_step.result.artifact_id
                params["source_url"] = prev_step.result.url_or_path
                break


def run_execution(
    execution: TaskExecution,
    registry: AdapterRegistry,
    retry_max: int = 3,
    fallback_adapter: Optional[PlatformAdapter] = None,
) -> TaskResult:
    """按步骤顺序执行 TaskExecution → TaskResult。

    流程：
    1. 取 step_params（若 execution 是 ExecutionPlan）
    2. 串行执行每个 step：
       a. 取 adapter = registry.get(step.platform)
       b. 组装 params（step_params + input_refs 填入前序产出）
       c. run_step_with_retry 执行
       d. 失败 → 切换到 fallback_adapter 重试；仍失败 → 整个任务 FAILED
       e. 成功 → 收集 artifacts，更新 step.result / step.status，更新 progress
    3. 全部成功 → TaskResult(status=DELIVERED, artifacts=[...])；任一失败 → FAILED

    Args:
        execution: 任务执行体（含 steps）。
        registry: 适配器注册表。
        retry_max: 单步失败重试上限。
        fallback_adapter: 备用适配器；None 表示不降级。

    Returns:
        TaskResult：成功时 artifacts 非空；失败时 artifacts 为空。
    """
    total_steps = len(execution.steps)
    if total_steps == 0:
        logger.warning("execution 无 steps，直接返回 FAILED")
        return TaskResult(
            result_id=f"res-{uuid.uuid4().hex[:12]}",
            task_id=execution.task_id,
            artifacts=[],
            status=TaskStatus.FAILED,
        )

    all_artifacts: list[Artifact] = []
    completed = 0

    for step in execution.steps:
        # 1. 组装 params
        params = _resolve_step_params(execution, step.step_id)
        _fill_input_refs(execution, step, params)

        # 2. 取适配器
        adapter = registry.get(step.platform)
        if adapter is None:
            logger.error(
                "找不到适配器: platform=%s, step=%s",
                step.platform.value, step.step_id,
            )
            _mark_execution_failed(execution, completed, total_steps)
            return _build_failed_result(execution)

        # 3. 执行 + 重试
        step.status = TaskStatus.EXECUTING
        status, artifacts = run_step_with_retry(adapter, params, retry_max)

        # 4. 失败：尝试降级到 fallback_adapter
        if status != TaskStatus.DELIVERED and fallback_adapter is not None:
            logger.info(
                "step %s 主适配器失败，降级到备用适配器", step.step_id,
            )
            _record_fallback(execution, step.step_id)
            status, artifacts = run_step_with_retry(
                fallback_adapter, params, retry_max
            )

        # 5. 仍失败：整个任务失败
        if status != TaskStatus.DELIVERED:
            step.status = TaskStatus.FAILED
            _mark_execution_failed(execution, completed, total_steps)
            return _build_failed_result(execution)

        # 6. 成功：收集产出，更新 step 状态
        step.status = TaskStatus.DELIVERED
        if artifacts:
            step.result = artifacts[0]  # 取首个作为该 step 的代表产出
            all_artifacts.extend(artifacts)
        completed += 1
        execution.progress = int(completed / total_steps * 100)

    execution.status = TaskStatus.DELIVERED
    logger.info(
        "execution 完成: exec_id=%s, artifacts=%d",
        execution.execution_id, len(all_artifacts),
    )
    return TaskResult(
        result_id=f"res-{uuid.uuid4().hex[:12]}",
        task_id=execution.task_id,
        artifacts=all_artifacts,
        status=TaskStatus.DELIVERED,
    )


# ---------- 内部辅助 ----------


def _mark_execution_failed(execution: TaskExecution, completed: int, total: int) -> None:
    """标记 execution 为失败状态并更新进度。"""
    execution.status = TaskStatus.FAILED
    execution.progress = int(completed / total * 100) if total > 0 else 0


def _build_failed_result(execution: TaskExecution) -> TaskResult:
    """构造失败结果。"""
    return TaskResult(
        result_id=f"res-{uuid.uuid4().hex[:12]}",
        task_id=execution.task_id,
        artifacts=[],
        status=TaskStatus.FAILED,
    )


def _record_fallback(execution: TaskExecution, step_id: str) -> None:
    """在 execution 元数据记录「已切换到备用平台」。

    若 execution 不是 ExecutionPlan（无 metadata 字段），则跳过（不影响主流程）。
    """
    if isinstance(execution, ExecutionPlan):
        execution.metadata["switched_to_fallback"] = True
        execution.metadata.setdefault("fallback_steps", []).append(step_id)
