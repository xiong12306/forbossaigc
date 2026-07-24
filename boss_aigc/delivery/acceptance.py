"""boss_aigc.delivery.acceptance 验收/修改/重新生成闭环。

老板对交付结果的反馈（验收反馈）解析与处理：
- parse_acceptance: 把老板的口语化反馈解析为 AcceptanceAction
- handle_acceptance: 按动作驱动状态流转，含归档/构造修改任务/重新执行

AcceptanceAction 四种：
    ACCEPT     -> 验收通过：归档到资产库（history + product_asset），status=ACCEPTED
    MODIFY     -> 要求修改：构造 IMAGE_EDIT 意图，重新走 confirmation 流程
    REGENERATE -> 重新生成：复用原 intent+summary，status=CONFIRMED 直接重新执行
    OTHER      -> 无法识别：保持 DELIVERED，提示老板再说一次
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from boss_aigc.contracts.enums import TaskStatus, TaskType
from boss_aigc.contracts.execution import ConfirmedTask
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.logging_setup import get_logger
from boss_aigc.pipeline import SessionContext

logger = get_logger(__name__, layer="delivery")

# context.extras 中标记 TTS 播报文本的 key（与 confirmation 层保持一致）
EXTRA_SPEAK_TEXT = "speak_text"
# context.extras 中标记是否等待二次确认的 key（与 confirmation 层保持一致）
EXTRA_AWAITING_SECONDARY = "awaiting_secondary_confirmation"


class AcceptanceAction(str, Enum):
    """验收动作：老板对交付结果的反馈分类。"""

    ACCEPT = "accept"            # 验收通过
    MODIFY = "modify"            # 要求修改（局部调整）
    REGENERATE = "regenerate"    # 重新生成（整体重做）
    OTHER = "other"              # 无法识别


# 重新生成关键词（优先判定，避免「重新改」类歧义）
_REGENERATE_KEYWORDS: tuple[str, ...] = (
    "重做", "重新生成", "再来一版", "重新来", "再生成", "重新做",
    "重新出一版", "再来一次", "重新出",
)

# 修改关键词
_MODIFY_KEYWORDS: tuple[str, ...] = (
    "改", "换", "修改", "调整", "替换", "改成", "换成", "改为", "换为",
)

# 第 N 张 触发修改（如「第2张换纯白」）
_MODIFY_INDEX_PATTERN: re.Pattern[str] = re.compile(r"第\s*\d+\s*[张个份]")

# 验收通过关键词
_ACCEPT_KEYWORDS: tuple[str, ...] = (
    "可以了", "可以", "就这版", "通过", "好了", "没问题",
    "行", "好的", "ok", "accept", "完美", "不错", "满意",
)


def parse_acceptance(text: str) -> AcceptanceAction:
    """解析老板对交付结果的反馈文本，返回验收动作。

    解析优先级：REGENERATE > MODIFY > ACCEPT > OTHER。
    优先判定 REGENERATE 是为了避免「重新改」「重新换」类输入被误判为 MODIFY。

    Args:
        text: 老板的反馈文本（如「可以了」/「第2张换纯白」/「重做」）。

    Returns:
        AcceptanceAction：ACCEPT / MODIFY / REGENERATE / OTHER。
    """
    if not text:
        return AcceptanceAction.OTHER

    text = text.strip()
    if not text:
        return AcceptanceAction.OTHER

    text_lower = text.lower()

    # 1. 优先判定 REGENERATE（语义最强）
    for kw in _REGENERATE_KEYWORDS:
        if kw in text or kw in text_lower:
            return AcceptanceAction.REGENERATE

    # 2. 判定 MODIFY（含修改关键词或「第N张」模式）
    if _MODIFY_INDEX_PATTERN.search(text):
        return AcceptanceAction.MODIFY
    for kw in _MODIFY_KEYWORDS:
        if kw in text:
            return AcceptanceAction.MODIFY

    # 3. 判定 ACCEPT
    for kw in _ACCEPT_KEYWORDS:
        if kw in text or kw in text_lower:
            return AcceptanceAction.ACCEPT

    # 4. 无法识别
    return AcceptanceAction.OTHER


def handle_acceptance(
    action: AcceptanceAction,
    context: SessionContext,
    asset_store: Optional[Any] = None,
) -> tuple[TaskStatus, str]:
    """按验收动作驱动状态流转，返回新状态与给老板的提示文本。

    四种动作的处理：
        - ACCEPT: 归档到资产库（history + product_asset），status=ACCEPTED
        - MODIFY: 构造 IMAGE_EDIT 意图，写入 context.intent/pending_summary，
                  status=AWAITING_CONFIRMATION（下一轮走 confirmation 路由）
        - REGENERATE: 复用原 intent+summary 重建 confirmed_task，
                  status=CONFIRMED（直接重新执行，不再确认）
        - OTHER: 保持 DELIVERED，提示老板再说一次

    Args:
        action: 验收动作。
        context: 当前会话上下文（读取 intent/result/confirmed_task，写入新状态）。
        asset_store: 可选的资产层聚合；ACCEPT 时用于归档。

    Returns:
        (new_status, prompt_text)：新状态与给老板的提示文本。
    """
    if action == AcceptanceAction.ACCEPT:
        return _handle_accept(context, asset_store)
    if action == AcceptanceAction.MODIFY:
        return _handle_modify(context)
    if action == AcceptanceAction.REGENERATE:
        return _handle_regenerate(context)
    return _handle_other(context)


# ---------- 内部分支 ----------

def _handle_accept(
    context: SessionContext,
    asset_store: Optional[Any],
) -> tuple[TaskStatus, str]:
    """ACCEPT：归档到资产库（任务历史 + 商品资产），status=ACCEPTED。"""
    intent = context.intent
    result = context.result
    summary = (
        context.confirmed_task.summary
        if context.confirmed_task is not None
        else context.pending_summary
    )

    # 归档到任务历史
    if asset_store is not None and intent is not None and summary is not None and result is not None:
        try:
            asset_store.history.record(intent, summary, result)
            logger.info(
                "ACCEPT 已归档任务历史: task_id=%s, product=%s",
                result.task_id, intent.product,
            )
        except Exception as e:
            logger.warning("归档任务历史失败: %s", e)

        # 商品资产入库：product 非空且资产库无该商品时，用首个 IMAGE artifact 占位
        product = intent.product
        if product:
            try:
                existing = asset_store.product_asset.get(product)
                if existing is None:
                    ref_image = _find_first_image_path(result.artifacts)
                    asset_store.product_asset.add(
                        product_name=product,
                        reference_image_path=ref_image,
                    )
                    logger.info(
                        "ACCEPT 已入库商品资产: product=%s, ref_image=%s",
                        product, ref_image,
                    )
            except Exception as e:
                logger.warning("入库商品资产失败: %s", e)

        # 模板沉淀（本阶段简单跳过，留待后续阶段完善推荐策略）
    else:
        logger.warning(
            "ACCEPT 缺少 intent/summary/result 或 asset_store，跳过归档: "
            "intent=%s, summary=%s, result=%s, asset_store=%s",
            intent is not None, summary is not None, result is not None,
            asset_store is not None,
        )

    context.status = TaskStatus.ACCEPTED
    # 清掉交付阶段标记，避免残留影响下一轮
    context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
    prompt = "已归档到资产库"
    context.extras[EXTRA_SPEAK_TEXT] = prompt
    return TaskStatus.ACCEPTED, prompt


def _handle_modify(context: SessionContext) -> tuple[TaskStatus, str]:
    """MODIFY：构造 IMAGE_EDIT 意图，写入 pending_summary，等老板确认修改任务。

    基于老板的修改文本（context.user_input）+ 原 intent 的 product 构造一个新的
    IMAGE_EDIT 意图，让老板确认修改任务后再进入执行层。
    """
    modify_text = (context.user_input or "").strip()
    original_product: Optional[str] = None
    if context.intent is not None:
        original_product = context.intent.product

    # 构造 IMAGE_EDIT 意图
    slots: dict[str, SlotValue] = {
        "edit_instruction": SlotValue(
            name="edit_instruction",
            value=modify_text,
            confidence=0.95,
        ),
    }
    # 「第N张」类输入解析出 target_image 槽位
    m = _MODIFY_INDEX_PATTERN.search(modify_text)
    if m:
        idx_match = re.search(r"\d+", m.group(0))
        if idx_match:
            slots["target_image"] = SlotValue(
                name="target_image",
                value=f"#{idx_match.group(0)}",
                confidence=0.9,
            )

    new_intent = TaskIntent(
        intent_id=uuid.uuid4().hex[:12],
        task_type=TaskType.IMAGE_EDIT,
        product=original_product,
        slots=slots,
        raw_text=modify_text,
        confidence=0.9,
        missing_slots=[],  # edit_instruction 已填，product 复用原值
    )
    context.intent = new_intent

    # 简单构造一个 TaskSummary（避免循环依赖，不调用 confirmation.build_summary）
    new_summary = TaskSummary(
        summary_id=uuid.uuid4().hex[:12],
        task_type=TaskType.IMAGE_EDIT,
        product=original_product,
        params={"edit_instruction": modify_text},
    )
    context.pending_summary = new_summary
    context.confirmed_task = None  # 清掉旧值，等老板确认后重新生成

    # 状态：等老板确认修改任务
    context.status = TaskStatus.AWAITING_CONFIRMATION
    context.extras[EXTRA_AWAITING_SECONDARY] = False

    prompt = f"好的，改为「{modify_text}」，确认吗？"
    context.extras[EXTRA_SPEAK_TEXT] = prompt
    logger.info(
        "MODIFY 已构造修改任务: product=%s, edit_instruction=%r",
        original_product, modify_text,
    )
    return TaskStatus.AWAITING_CONFIRMATION, prompt


def _handle_regenerate(context: SessionContext) -> tuple[TaskStatus, str]:
    """REGENERATE：复用原 intent+summary 重建 confirmed_task，直接重新执行。

    从 context.confirmed_task 取原 intent 与 summary，重建一个新的 ConfirmedTask
    （新 task_id），status=CONFIRMED 让下游 orchestration/execution 重新跑。
    本阶段不立即触发重新执行（pipeline 下一轮按 CONFIRMED 路由续跑）。
    """
    original = context.confirmed_task
    if original is None:
        # 兜底：从 context.intent 重建 summary
        logger.warning(
            "REGENERATE 时 context.confirmed_task 为空，尝试用 context.intent 兜底"
        )
        intent = context.intent
        if intent is None:
            logger.error("REGENERATE 时 intent 与 confirmed_task 都为空，无法重做")
            context.status = TaskStatus.DELIVERED
            prompt = "没找到原任务，无法重做"
            context.extras[EXTRA_SPEAK_TEXT] = prompt
            return TaskStatus.DELIVERED, prompt
        summary = context.pending_summary or TaskSummary(
            summary_id=uuid.uuid4().hex[:12],
            task_type=intent.task_type,
            product=intent.product,
        )
    else:
        intent = original.intent
        summary = original.summary

    # 重建 confirmed_task（新 task_id）
    new_confirmed = ConfirmedTask(
        task_id=uuid.uuid4().hex[:12],
        intent=intent,
        summary=summary,
        confirmed_at=datetime.now(),
    )
    context.confirmed_task = new_confirmed
    context.pending_summary = None  # 已确认，清掉待确认摘要
    context.extras.pop(EXTRA_AWAITING_SECONDARY, None)

    context.status = TaskStatus.CONFIRMED
    prompt = "好的，重新生成一版"
    context.extras[EXTRA_SPEAK_TEXT] = prompt
    logger.info(
        "REGENERATE 已重建 confirmed_task: task_id=%s",
        new_confirmed.task_id,
    )
    return TaskStatus.CONFIRMED, prompt


def _handle_other(context: SessionContext) -> tuple[TaskStatus, str]:
    """OTHER：无法识别，保持 DELIVERED，提示老板再说一次。"""
    context.status = TaskStatus.DELIVERED
    prompt = "没听清，您是说可以了还是要改？"
    context.extras[EXTRA_SPEAK_TEXT] = prompt
    return TaskStatus.DELIVERED, prompt


# ---------- 内部工具 ----------

def _find_first_image_path(artifacts: list[Any]) -> Optional[str]:
    """从 artifact 列表中找第一个 IMAGE 类型，返回其 url_or_path 作占位参考图。"""
    for art in artifacts or []:
        kind = getattr(art, "kind", "")
        if kind == "IMAGE":
            url = getattr(art, "url_or_path", None)
            if url:
                return url
    return None
