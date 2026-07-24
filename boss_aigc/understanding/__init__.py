"""boss_aigc 理解层包。

职责：意图识别 / 槽位抽取 / 多轮追问补全 / 模糊指令澄清。
本阶段用规则引擎 Mock，无需 LLM API key 即可跑通；
后续可通过新增 IntentRecognizer 子类（如 QwenRecognizer）替换为真实 LLM，
dialog.py / handler.py 等上游模块无需改动。
"""

from boss_aigc.understanding.dialog import (
    clarify_if_ambiguous,
    multi_turn_complete,
)
from boss_aigc.understanding.handler import (
    build_understanding_handler,
    create_default_understanding,
)
from boss_aigc.understanding.recognizer import (
    IntentRecognizer,
    RuleBasedRecognizer,
)
from boss_aigc.understanding.schemas import (
    SLOT_ENUMS,
    SLOT_SCHEMAS,
    get_default,
    get_optional_slots,
    get_required_slots,
)

__all__ = [
    # 识别器
    "IntentRecognizer",
    "RuleBasedRecognizer",
    # 处理器
    "build_understanding_handler",
    "create_default_understanding",
    # 对话工具
    "clarify_if_ambiguous",
    "multi_turn_complete",
    # Schema 查询
    "get_required_slots",
    "get_optional_slots",
    "get_default",
    "SLOT_SCHEMAS",
    "SLOT_ENUMS",
]
