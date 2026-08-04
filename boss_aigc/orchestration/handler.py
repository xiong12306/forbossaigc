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


# 哨兵值：明确表示不使用fallback适配器（真实平台配置时使用，失败直接报错）
_NO_FALLBACK = object()


def build_execution_handler(
    registry: AdapterRegistry,
    retry_max: int = 3,
    fallback_adapter: Optional[PlatformAdapter] = _NO_FALLBACK,
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
        fallback_adapter: 备用适配器；
            - 不传（默认）：开发模式，自动用 MockAdapter(fail_mode="none")
            - 显式传入 None：**禁止降级**，真实平台失败直接返回错误，不静默出mock图
            - 传入具体适配器实例：使用指定适配器作为fallback
    """
    # 默认 fallback：开发模式用 MockAdapter(none) 模拟切换备用平台；显式传None则不使用任何fallback
    if fallback_adapter is _NO_FALLBACK:
        # 局部导入避免循环依赖
        from boss_aigc.execution.mock_adapter import MockAdapter
        fallback_adapter = MockAdapter(fail_mode="none")
    # 当 fallback_adapter is None 时：保持None，run_execution中判断为None表示不降级

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

    使用全局 registry + register_default_adapters() 注册默认适配器；
    retry_max 从全局 config 取；
    fallback 策略：
    - 若配置了真实平台（modelscope/nanobanana）：**不设置任何fallback**，失败直接返回错误，
      避免静默降级到Mock生成假图
    - 若仅注册了mock（未配置任何真实平台，纯开发模式）：保持默认Mock fallback，方便开发测试
    """
    from boss_aigc.contracts.enums import PlatformKind
    registry = register_default_adapters()
    settings = get_settings()

    # 检查是否配置了真实平台适配器
    has_real_platform = any(
        kind != PlatformKind.MOCK
        for kind in registry.list_kinds()
    )

    if has_real_platform:
        # 配置了真实平台：显式传 None，**禁止**降级到mock，失败就报错给用户
        logger.info("检测到真实平台适配器，已禁用Mock降级，失败将直接返回错误")
        return build_execution_handler(
            registry,
            retry_max=settings.retry_max,
            fallback_adapter=None,
        )
    else:
        # 仅mock模式：使用默认fallback（保持原开发体验）
        return build_execution_handler(
            registry,
            retry_max=settings.retry_max,
        )
