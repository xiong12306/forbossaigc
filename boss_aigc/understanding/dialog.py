"""boss_aigc.understanding.dialog 多轮对话补全 + 模糊指令澄清。

- multi_turn_complete: 续接上一轮缺失槽位，把当前回答合并进 intent，
  并针对剩余缺失槽位生成自然语言追问（写入 context.extras 供 TTS 播报）。
- clarify_if_ambiguous: 当意图完全无法识别或指令过于模糊时，
  设置 needs_clarification=True 并提供候选选项让老板二选一。
"""

from __future__ import annotations

import re
from typing import Any

from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.pipeline import SessionContext

from boss_aigc.understanding.recognizer import IntentRecognizer
from boss_aigc.understanding.schemas import get_required_slots

# 各缺失槽位对应的追问模板
_FOLLOW_UP_TEMPLATES: dict[str, str] = {
    "product": "给哪个商品出图？",
    "quantity": "要出几张？",
    "image_type": "要什么类型的图？商品主图、详情图、场景图、海报还是轮播图？",
    "style": "想要什么风格？比如轻奢、暖色调、极简等。",
    "size": "图片尺寸是多少？默认 1024x1024。",
    "reference_image": "有参考图吗？可以直接发一张。",
    "edit_instruction": "想怎么改？比如换背景、换颜色等。",
    "target_image": "改哪张图？可以发图或说编号。",
    "duration_sec": "视频时长多少秒？默认 15 秒。",
    "source_image": "用哪张图作为起始帧？",
    "copy_type": "需要哪种文案？标题 / 详情 / 小红书？",
    "word_count": "文案字数大概多少？",
    "query_target": "想查历史任务还是资产？",
}

# 任务类型澄清选项（无商品候选时让老板选要做什么）
_TASK_TYPE_OPTIONS: list[str] = [
    "出图(生成主图/详情图/封面)",
    "改图(局部修改/换背景)",
    "生视频(图转视频)",
    "写文案(标题/卖点/小红书)",
    "查数据(历史/资产)",
]

# 触发「无任务类型命中」的置信度阈值
_CLARIFY_CONFIDENCE_THRESHOLD = 0.3


def multi_turn_complete(
    text: str,
    context: SessionContext,
    recognizer: IntentRecognizer,
) -> TaskIntent:
    """多轮对话补全：合并上一轮缺失槽位的回答，生成下一轮追问。

    流程：
    1. 若 context.intent 已存在且 missing_slots 非空，把当前 text 当作
       对第一个缺失槽位的回答，合并进 intent.slots，重新检查 missing_slots。
    2. 否则按新一轮调用 recognizer 识别。
    3. 针对剩余的第一个 missing_slots 生成追问文本，写入
       context.extras['follow_up_question'] 供接入层 TTS 播报；
       missing_slots 为空时清除追问标记。

    Returns:
        更新后的 TaskIntent（已写回 context.intent）。
    """
    prev_intent = context.intent

    if prev_intent is not None and prev_intent.missing_slots:
        # 续接：把当前文本作为对第一个缺失槽位的回答
        merged = _merge_answer(prev_intent, text)
        merged.missing_slots = _recompute_missing(merged)
        _emit_follow_up(merged, context)
        context.intent = merged
        return merged

    # 新一轮识别
    intent = recognizer.recognize(text, context)
    _emit_follow_up(intent, context)
    context.intent = intent
    return intent


def clarify_if_ambiguous(
    intent: TaskIntent,
    context: SessionContext,
) -> TaskIntent:
    """模糊指令澄清：无任务类型命中或无对象时让老板二选一。

    触发条件：
    - 任务类型完全无法识别（confidence 低于阈值）。
    - 任务类型识别但商品缺失，且 context.extras['recent_products'] 有候选。

    无候选商品时，提供任务类型选项让老板选要做什么。
    澄清触发时把追问文本覆写为澄清提示，并设置 clarification_options。
    """
    # 1. 完全无法识别任务类型
    if intent.confidence < _CLARIFY_CONFIDENCE_THRESHOLD:
        intent.needs_clarification = True
        recent = _get_recent_products(context)
        if recent:
            intent.clarification_options = list(recent[:3])
            context.extras["follow_up_question"] = "您是要操作哪个商品？"
        else:
            intent.clarification_options = list(_TASK_TYPE_OPTIONS)
            context.extras["follow_up_question"] = "您是想出图、改图、生视频、写文案，还是查数据？"
        return intent

    # 2. 任务类型识别但商品缺失，且有候选商品可让老板选
    if not intent.product and "product" in intent.missing_slots:
        recent = _get_recent_products(context)
        if recent:
            intent.needs_clarification = True
            intent.clarification_options = list(recent[:3])
            context.extras["follow_up_question"] = "给哪个商品？"

    return intent


# ---------- 内部工具 ----------
def _merge_answer(prev_intent: TaskIntent, text: str) -> TaskIntent:
    """把当前回答合并进上一轮 intent 的第一个缺失槽位（原地修改并返回）。"""
    if not prev_intent.missing_slots:
        return prev_intent
    target_slot = prev_intent.missing_slots[0]
    answer = (text or "").strip()
    if not answer:
        return prev_intent

    if target_slot == "product":
        prev_intent.product = answer
        prev_intent.slots["product"] = SlotValue(
            name="product", value=answer, confidence=0.85
        )
    elif target_slot == "quantity":
        # 尝试从回答中解析数字
        m = re.search(r"(\d+)", answer)
        value: Any = int(m.group(1)) if m else answer
        prev_intent.slots["quantity"] = SlotValue(
            name="quantity", value=value, confidence=0.85
        )
    elif target_slot == "size":
        # 尝试解析宽x高，否则原样存
        m = re.search(r"(\d{3,5})\s*[x×*]\s*(\d{3,5})", answer)
        value = f"{m.group(1)}x{m.group(2)}" if m else answer
        prev_intent.slots["size"] = SlotValue(
            name="size", value=value, confidence=0.85
        )
    else:
        # 其余槽位直接当字符串填
        prev_intent.slots[target_slot] = SlotValue(
            name=target_slot, value=answer, confidence=0.85
        )
    return prev_intent


def _recompute_missing(intent: TaskIntent) -> list[str]:
    """根据当前 slots 重新计算缺失的必填槽位。"""
    missing: list[str] = []
    for required in get_required_slots(intent.task_type):
        if required == "product":
            if not intent.product:
                missing.append("product")
        elif required not in intent.slots:
            missing.append(required)
    return missing


def _emit_follow_up(intent: TaskIntent, context: SessionContext) -> None:
    """针对第一个缺失槽位生成追问文本，写入 context.extras。

    missing_slots 为空时清除追问标记（避免上一轮残留）。
    """
    if not intent.missing_slots:
        context.extras.pop("follow_up_question", None)
        context.extras["needs_follow_up"] = False
        return
    first_missing = intent.missing_slots[0]
    question = _FOLLOW_UP_TEMPLATES.get(first_missing, f"请补充 {first_missing}。")
    context.extras["follow_up_question"] = question
    context.extras["needs_follow_up"] = True


def _get_recent_products(context: SessionContext) -> list[str]:
    """从 context.extras['recent_products'] 取最近商品候选（可能为空）。"""
    recent = context.extras.get("recent_products") or []
    if not isinstance(recent, (list, tuple)):
        return []
    return [str(p) for p in recent]
