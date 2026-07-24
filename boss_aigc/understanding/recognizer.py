"""boss_aigc.understanding.recognizer 意图识别 + 槽位抽取。

抽象接口 IntentRecognizer + 规则引擎 Mock 实现 RuleBasedRecognizer。
本阶段不接真实 LLM，规则引擎用关键词 + 正则可正确解析常见老板指令；
后续可通过新增 LLMRecognizer 子类（如 QwenRecognizer）替换实现，
无需改动 dialog.py / handler.py 等上游模块。
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from boss_aigc.contracts.enums import TaskType
from boss_aigc.contracts.intent import SlotValue, TaskIntent
from boss_aigc.pipeline import SessionContext

from boss_aigc.understanding.schemas import get_required_slots, IMAGE_TYPE_NAMES
from boss_aigc.contracts.enums import ImageType

# 任务类型关键词表（按优先级排序：更具体的放前面，避免被宽泛词吞掉）
# 例：IMAGE_EDIT 的「改图」要先于 IMAGE_GEN 的「图」匹配
_TASK_KEYWORDS: list[tuple[TaskType, list[str]]] = [
    (TaskType.IMAGE_EDIT, ["改图", "换背景", "换色", "修图", "调整图", "编辑图", "修改图", "P图", "修一下"]),
    (TaskType.VIDEO_GEN, ["视频", "转视频", "图转视频", "做视频", "生成视频", "剪视频"]),
    (TaskType.COPYWRITING, ["文案", "标题", "卖点", "小红书", "详情文案", "写文案", "写个", "写个标题"]),
    (TaskType.DATA_QUERY, ["历史", "查", "上次", "之前", "查询", "看看", "找一下"]),
    (TaskType.IMAGE_GEN, ["出图", "主图", "详情图", "封面", "出几张", "出张", "生成图", "海报", "轮播图", "场景图",
                          "出图", "做图", "生图", "图给我", "做张图", "出几张图", "几张图", "张图",
                          "生成", "做个", "来一张", "来几张", "搞一张", "搞几张"]),
]

# 图片类型关键词映射
_IMAGE_TYPE_KEYWORDS: list[tuple[ImageType, list[str]]] = [
    (ImageType.DETAIL, ["详情图", "细节图", "卖点图", "细节"]),
    (ImageType.SCENE, ["场景图", "实景图", "使用场景", "场景"]),
    (ImageType.POSTER, ["海报", "营销海报", "促销海报", "活动图"]),
    (ImageType.CAROUSEL, ["轮播图", "首页图", "轮播"]),
    (ImageType.MAIN, ["主图", "商品主图"]),
]

# 风格词库（覆盖常见电商主图风格）
_STYLE_KEYWORDS: list[str] = [
    "轻奢", "暖色调", "暖色", "冷色调", "冷色", "极简", "简约",
    "ins风", "INS风", "国风", "中国风", "复古", "工业风",
    "日系", "韩系", "高级感", "时尚", "活泼", "清新",
]

# 商品抽取模式：覆盖「给 XX 出」「把 XX 改」「XX 图」「生成 XX」等常见句式
# 注意：更具体的模式放前面，避免被宽泛模式误匹配
_PRODUCT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:给|把|帮|为)(.+?)(?:出|改|换|做|生成|写|来|搞|的|$)"),
    re.compile(r"(?:来一张|来几张|搞一张|搞几张|做一张|做几张|出一张|出几张|生成|做|出)(.+?)(?:图|张|个|份|的|主图|详情图|海报|场景图|轮播图|$)"),
    re.compile(r"^(.+?)(?:的图|张图|主图|详情图|海报|场景图|轮播图|图)$"),
]

# 数量抽取：N 张 / N 个 / N 份
_QUANTITY_PATTERN = re.compile(r"(\d+)\s*[张个份]")

# 尺寸抽取：支持 1440x1440 / 1440×1440 / 1440*1440
_SIZE_PATTERN = re.compile(r"(\d{3,5})\s*[x×*]\s*(\d{3,5})")


class IntentRecognizer(ABC):
    """意图识别器抽象基类。

    所有识别器（规则引擎 / LLM）都实现 recognize 方法，
    输入文本 + 上下文，输出 TaskIntent。
    """

    @abstractmethod
    def recognize(self, text: str, context: SessionContext) -> TaskIntent:
        """识别文本意图并抽取槽位。

        Args:
            text: 老板的指令文本（已 ASR 转写）。
            context: 会话上下文（可读 recent_products 等）。

        Returns:
            TaskIntent：含 task_type / slots / missing_slots / confidence。
            若任务类型完全无法识别，task_type 字段保留默认（IMAGE_GEN），
            但 confidence 置 0.0 以供 clarify_if_ambiguous 判定。
        """


class RuleBasedRecognizer(IntentRecognizer):
    """规则引擎 Mock：用关键词 + 正则做意图识别与槽位抽取。

    无需 LLM API key，开箱可用。命中规则越完整，confidence 越高；
    完全无任务类型命中时 confidence=0.0，触发澄清流程。
    """

    def recognize(self, text: str, context: SessionContext) -> TaskIntent:
        text = text or ""

        # 1. 识别任务类型
        task_type, task_confidence = self._match_task_type(text)

        # 2. 抽取槽位（仅抽取文本中显式出现的，默认值由下游填充）
        slots: dict[str, SlotValue] = {}

        product = self._extract_product(text)
        if product:
            slots["product"] = SlotValue(name="product", value=product, confidence=0.9)

        quantity = self._extract_quantity(text)
        if quantity is not None:
            slots["quantity"] = SlotValue(name="quantity", value=quantity, confidence=0.95)

        image_type = self._extract_image_type(text)
        if image_type is not None:
            slots["image_type"] = SlotValue(name="image_type", value=image_type.value, confidence=0.9)

        style = self._extract_style(text)
        if style:
            slots["style"] = SlotValue(name="style", value=style, confidence=0.85)

        size = self._extract_size(text)
        if size:
            slots["size"] = SlotValue(name="size", value=size, confidence=0.95)

        # 3. 检查缺失的必填槽位
        missing_slots = self._compute_missing(task_type, slots, product)

        # 4. 估算整体置信度：命中槽位越多越高；无任务类型命中则压到 0
        hit_count = len(slots)
        if task_confidence == 0.0:
            confidence = 0.0
        else:
            confidence = min(0.5 + 0.1 * hit_count, 0.95)

        return TaskIntent(
            intent_id=uuid.uuid4().hex[:12],
            task_type=task_type,
            product=product,
            slots=slots,
            raw_text=text,
            confidence=confidence,
            missing_slots=missing_slots,
        )

    # ---------- 内部抽取方法 ----------
    def _match_task_type(self, text: str) -> tuple[TaskType, float]:
        """关键词匹配任务类型。无命中返回 (IMAGE_GEN, 0.0) 表示无法识别。"""
        for task_type, keywords in _TASK_KEYWORDS:
            for kw in keywords:
                if kw in text:
                    return task_type, 0.9

        # 兜底1：只要包含"图"且不是其他任务关键词，默认认为是出图（置信度稍低）
        if "图" in text:
            return TaskType.IMAGE_GEN, 0.7

        # 兜底2：短文本（<=6字）没有其他关键词，默认认为是出图任务（老板可能只是说商品名）
        if len(text) <= 6 and not any(kw in text for _, kws in _TASK_KEYWORDS for kw in kws):
            return TaskType.IMAGE_GEN, 0.5

        return TaskType.IMAGE_GEN, 0.0

    def _extract_product(self, text: str) -> Optional[str]:
        """从指令中抽取商品名。匹配不到返回 None。"""
        # 先匹配正则模式
        for pattern in _PRODUCT_PATTERNS:
            m = pattern.search(text)
            if m:
                product = m.group(1).strip()
                # 过滤过短或异常长的误命中，同时过滤掉常见非商品词
                product = self._clean_product(product)
                if product and 1 <= len(product) <= 20:
                    return product

        # 兜底：短文本（<=10字）+ 包含"图"字，假设整个文本去掉"图"就是商品
        if len(text) <= 10 and ("图" in text):
            cleaned = text.replace("图", "").strip()
            cleaned = self._clean_product(cleaned)
            if cleaned and 1 <= len(cleaned) <= 20:
                return cleaned
        return None

    def _clean_product(self, text: str) -> Optional[str]:
        """清理商品名，去掉语气词、量词等干扰"""
        if not text:
            return None
        # 去掉常见虚词和量词
        noise_words = ["给", "把", "帮", "为", "我", "你", "的", "了", "啊", "呢", "吧",
                       "几", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
                       "张", "个", "份", "点", "下"]
        cleaned = text
        for nw in noise_words:
            cleaned = cleaned.replace(nw, "")
        cleaned = cleaned.strip()
        # 过滤掉空或过短（单字且不是中文商品名）
        if len(cleaned) < 1:
            return None
        return cleaned

    def _extract_quantity(self, text: str) -> Optional[int]:
        """抽取数量。「几张」这种无具体数字的返回 None（由追问补全）。"""
        m = _QUANTITY_PATTERN.search(text)
        if m:
            return int(m.group(1))
        return None

    def _extract_image_type(self, text: str) -> Optional[ImageType]:
        """抽取图片类型（主图/详情图/场景图/海报/轮播图）。"""
        for img_type, keywords in _IMAGE_TYPE_KEYWORDS:
            for kw in keywords:
                if kw in text:
                    return img_type
        return None

    def _extract_style(self, text: str) -> Optional[str]:
        """抽取风格词，多个命中时按词库顺序拼接（如「轻奢暖色调」）。"""
        hits = [kw for kw in _STYLE_KEYWORDS if kw in text]
        if not hits:
            return None
        # 过滤被更长词包含的短词（如「暖色」被「暖色调」包含）
        filtered = [
            h for h in hits
            if not any(h != other and h in other for other in hits)
        ]
        # 去重保序
        seen: set[str] = set()
        ordered: list[str] = []
        for h in filtered:
            if h not in seen:
                seen.add(h)
                ordered.append(h)
        return "".join(ordered)

    def _extract_size(self, text: str) -> Optional[str]:
        """抽取尺寸，归一化为「宽x高」格式。"""
        m = _SIZE_PATTERN.search(text)
        if m:
            return f"{m.group(1)}x{m.group(2)}"
        return None

    def _compute_missing(
        self,
        task_type: TaskType,
        slots: dict[str, SlotValue],
        product: Optional[str],
    ) -> list[str]:
        """根据 schema 必填槽位检查缺失项。"""
        missing: list[str] = []
        for required in get_required_slots(task_type):
            if required == "product":
                if not product:
                    missing.append("product")
            elif required not in slots:
                missing.append(required)
        return missing
