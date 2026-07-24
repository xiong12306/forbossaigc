"""boss_aigc.orchestration.handler 编排层 + 执行层处理器（LayerHandler 实现）。

由于编排与执行调度逻辑强耦合（派发/重试/降级跨两层），且 execution/ 目录只放适配器实现，
故执行层处理器也放在 orchestration/handler.py 中。

提供四个工厂：
- build_orchestration_handler: 编排层处理器（ConfirmedTask → TaskExecution）
- build_execution_handler: 执行层处理器（TaskExecution → TaskResult）
- create_default_orchestration: 开箱即用编排层处理器
- create_default_execution: 开箱即用执行层处理器（用 get_registry + register_default_adapters）
"""

from __future__ import annotations

from typing import Any, Optional

from boss_aigc.config import get_settings
from boss_aigc.contracts.enums import TaskStatus
from boss_aigc.contracts.execution import (
    ConfirmedTask,
    TaskExecution,
    TaskResult,
)
from boss_aigc.execution.adapter import PlatformAdapter
from boss_aigc.execution.registry import (
    AdapterRegistry,
    get_registry,
    register_default_adapters,
)
from boss_aigc.logging_setup import get_logger
from boss_aigc.pipeline import LayerHandler, SessionContext

from boss_aigc.orchestration.planner import plan_execution
from boss_aigc.orchestration.scheduler import run_execution

logger = get_logger(__name__, layer="orchestration")


def build_orchestration_handler() -> LayerHandler:
    """构建编排层处理器。

    输入：upstream 是 ConfirmedTask（来自确认层），context.confirmed_task 作为兜底。
    处理：
        1. plan_execution(confirmed) → ExecutionPlan
        2. 写入 context.execution
        3. context.status = EXECUTING
    输出：ExecutionPlan（也是 TaskExecution 子类，给 execution 层消费）。
    """

    def handler(upstream: Any, context: SessionContext) -> TaskExecution:
        # 取 ConfirmedTask：优先 upstream，回退 context.confirmed_task
        confirmed: Optional[ConfirmedTask] = (
            upstream if isinstance(upstream, ConfirmedTask) else None
        )
        if confirmed is None:
            confirmed = context.confirmed_task

        if confirmed is None:
            logger.error("编排层未收到 ConfirmedTask，无法规划执行")
            context.status = TaskStatus.FAILED
            return TaskExecution(execution_id="", task_id="")

        # 规划执行
        plan = plan_execution(confirmed)
        context.execution = plan
        context.status = TaskStatus.EXECUTING
        logger.info(
            "编排层产出 ExecutionPlan: exec_id=%s, steps=%d",
            plan.execution_id, len(plan.steps),
        )
        return plan

    return handler


def build_execution_handler(
    registry: AdapterRegistry,
    retry_max: int = 3,
    fallback_adapter: Optional[PlatformAdapter] = None,
) -> LayerHandler:
    """构建执行层处理器。

    输入：upstream 是 TaskExecution（来自编排层），context.execution 作为兜底。
    处理：
        1. run_execution(execution, registry, retry_max, fallback_adapter) → TaskResult
        2. 写入 context.result
        3. context.status = DELIVERED（成功）或 FAILED（失败）
    输出：TaskResult。

    Args:
        registry: 适配器注册表。
        retry_max: 单步失败重试上限。
        fallback_adapter: 备用适配器；None 时默认用 MockAdapter(fail_mode="none")
            模拟「切换到备用平台」（本阶段 MOCK 的备用仍是 MOCK）。
    """
    # 默认 fallback：本阶段用 MockAdapter(none) 模拟切换备用平台
    if fallback_adapter is None:
        # 局部导入避免循环依赖
        from boss_aigc.execution.mock_adapter import MockAdapter

        fallback_adapter = MockAdapter(fail_mode="none")

    def handler(upstream: Any, context: SessionContext) -> TaskResult:
        # 取 TaskExecution：优先 upstream，回退 context.execution
        execution: Optional[TaskExecution] = (
            upstream if isinstance(upstream, TaskExecution) else None
        )
        if execution is None:
            execution = context.execution

        if execution is None:
            logger.error("执行层未收到 TaskExecution，无法执行")
            context.status = TaskStatus.FAILED
            return TaskResult(result_id="", task_id="")

        result = run_execution(
            execution,
            registry,
            retry_max=retry_max,
            fallback_adapter=fallback_adapter,
        )
        context.result = result
        context.status = result.status
        logger.info(
            "执行层产出 TaskResult: result_id=%s, status=%s, artifacts=%d",
            result.result_id, result.status.value, len(result.artifacts),
        )
        return result

    return handler


# ---------- 开箱即用工厂 ----------


def create_default_orchestration() -> LayerHandler:
    """构建开箱即用的编排层处理器（无外部依赖，纯函数式规划）。"""
    return build_orchestration_handler()


def create_default_execution() -> LayerHandler:
    """构建开箱即用的执行层处理器。

    使用全局 registry + register_default_adapters() 注册默认 Mock 适配器；
    retry_max 从全局 config 取；fallback 用 MockAdapter(none) 默认实例。
    """
    registry = register_default_adapters()
    settings = get_settings()
    return build_execution_handler(
        registry,
        retry_max=settings.retry_max,
    )
