"""boss_aigc 编排层包。

职责：任务规划 / 平台选择 / DAG 工作流 / 串行调度 / 失败重试降级。
本层同时承载编排层与执行层处理器（派发/重试/降级跨两层，强耦合）。

主链第四层（orchestration）：ConfirmedTask → plan_execution → TaskExecution
主链第五层（execution）：TaskExecution → run_execution → TaskResult
"""

from boss_aigc.orchestration.planner import (
    ExecutionPlan,
    plan_execution,
    select_platform,
)
from boss_aigc.orchestration.scheduler import (
    run_execution,
    run_step_with_retry,
)
from boss_aigc.orchestration.handler import (
    build_execution_handler,
    build_orchestration_handler,
    create_default_execution,
    create_default_orchestration,
)

__all__ = [
    # 规划器
    "ExecutionPlan",
    "plan_execution",
    "select_platform",
    # 调度器
    "run_execution",
    "run_step_with_retry",
    # 处理器
    "build_orchestration_handler",
    "build_execution_handler",
    "create_default_orchestration",
    "create_default_execution",
]
