"""boss_aigc 确认层包。

职责：任务摘要生成 / 老板确认-修改-取消状态机 / 确认锁 / 高成本二次确认。

主链第三层，是 Human-in-the-Loop 的核心：
    - 第 1 轮：理解层产出 TaskIntent → 确认层生成 TaskSummary 摘要卡片
      → 等老板确认（pipeline 早停，不进入执行层）
    - 第 2 轮：老板回复「确认/取消/改成XX」→ 确认层解析回复
      → 放行（CONFIRMED）或取消或修改后重新摘要
"""

from boss_aigc.confirmation.handler import (
    build_confirmation_handler,
    create_default_confirmation,
)
from boss_aigc.confirmation.state_machine import (
    ConfirmationStateMachine,
    parse_confirmation_action,
)
from boss_aigc.confirmation.summary_builder import (
    build_summary,
    format_summary_text,
)

__all__ = [
    # 摘要构建
    "build_summary",
    "format_summary_text",
    # 状态机
    "parse_confirmation_action",
    "ConfirmationStateMachine",
    # 处理器
    "build_confirmation_handler",
    "create_default_confirmation",
]
