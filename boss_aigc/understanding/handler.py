"""boss_aigc.understanding.handler 理解层处理器。

把 multi_turn_complete + clarify_if_ambiguous 串成 LayerHandler，
供 Pipeline.register_layer(LAYER_UNDERSTANDING, handler) 注册使用。

处理器职责：
1. 接收接入层返回的纯指令文本 + 会话上下文。
2. 调用 multi_turn_complete 完成意图识别 + 多轮追问续接。
3. 调用 clarify_if_ambiguous 处理模糊指令。
4. 把最终 intent 写回 context.intent，并设置 context.status。
5. 若仍有缺失槽位或需要澄清：保持 UNDERSTANDING 状态，
   extras['needs_follow_up']=True，返回带追问的 intent。
   否则进入 AWAITING_CONFIRMATION，移交确认层。
"""

from __future__ import annotations

from typing import Any

from boss_aigc.contracts.enums import TaskStatus
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.pipeline import LayerHandler, SessionContext

from boss_aigc.understanding.dialog import clarify_if_ambiguous, multi_turn_complete
from boss_aigc.understanding.recognizer import IntentRecognizer, RuleBasedRecognizer


def build_understanding_handler(recognizer: IntentRecognizer) -> LayerHandler:
    """构建理解层处理器。

    Args:
        recognizer: 意图识别器（规则引擎或后续 LLM 实现）。

    Returns:
        LayerHandler：签名 (upstream, context) -> TaskIntent。
    """

    def handler(upstream: Any, context: SessionContext) -> TaskIntent:
        text = upstream if isinstance(upstream, str) else str(upstream)

        # 1. 多轮补全 + 槽位抽取（含追问生成）
        intent = multi_turn_complete(text, context, recognizer)
        # 2. 模糊指令澄清（可能覆写追问为澄清提示）
        intent = clarify_if_ambiguous(intent, context)
        # 3. 写回上下文
        context.intent = intent

        # 4. 状态决策：是否进入确认层
        if intent.missing_slots or intent.needs_clarification:
            # 仍需追问/澄清，停留在理解层
            context.status = TaskStatus.UNDERSTANDING
            context.extras["needs_follow_up"] = True
        else:
            # 槽位齐全且无澄清需求，移交确认层
            context.status = TaskStatus.AWAITING_CONFIRMATION
            context.extras["needs_follow_up"] = False
            context.extras.pop("follow_up_question", None)

        return intent

    return handler


def create_default_understanding() -> LayerHandler:
    """用 config 默认 provider 构建开箱即用的理解层处理器。

    本阶段只实现了 RuleBasedRecognizer（provider="rule"），
    后续接入真实 LLM 时新增 QwenRecognizer / GlmRecognizer 子类，
    并在此按 settings.llm_provider 选择即可。
    """
    from boss_aigc.config import get_settings

    settings = get_settings()
    provider = settings.llm_provider

    if provider == "rule":
        recognizer: IntentRecognizer = RuleBasedRecognizer()
    else:
        # 未实现的 provider 暂时回退到规则引擎，保证可跑通
        recognizer = RuleBasedRecognizer()

    return build_understanding_handler(recognizer)
