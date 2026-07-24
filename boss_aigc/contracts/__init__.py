"""boss_aigc.contracts 统一数据契约模块。

各层引用此模块中的契约，而非各自定义，
确保层间数据结构一致、可校验、可演进。
"""

from boss_aigc.contracts.enums import (
    ConfirmationAction,
    DeliveryChannel,
    PlatformKind,
    TaskStatus,
    TaskType,
)
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.contracts.execution import (
    Artifact,
    ConfirmedTask,
    TaskExecution,
    TaskResult,
    TaskStep,
)
from boss_aigc.contracts.asset import BrandStyle, ProductAsset

__all__ = [
    "ConfirmationAction",
    "DeliveryChannel",
    "PlatformKind",
    "TaskStatus",
    "TaskType",
    "SlotValue",
    "TaskIntent",
    "TaskSummary",
    "Artifact",
    "ConfirmedTask",
    "TaskExecution",
    "TaskResult",
    "TaskStep",
    "BrandStyle",
    "ProductAsset",
]
