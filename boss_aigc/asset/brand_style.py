"""asset.brand_style 品牌风格库。

保存老板首次设定的品牌风格关键词，所有出图任务默认注入，
保证跨任务风格一致。本阶段为内存存储。
"""

import uuid
from typing import Callable, Optional

from boss_aigc.contracts.asset import BrandStyle


# 默认品牌风格关键词（demo 中 onboarding_callback 未提供时兜底使用）
DEFAULT_BRAND_STYLE_KEYWORDS: list[str] = ["轻奢", "暖色调", "大面积留白"]


class BrandStyleStore:
    """品牌风格库：内存存储（单条全局风格）。

    职责：
        - get_or_prompt：首次访问时通过回调引导老板设定风格；
        - set_style / get_style：读写品牌风格；
        - get_style_keywords：返回关键词列表，供执行层风格锁定注入。
    """

    def __init__(self) -> None:
        self._style: Optional[BrandStyle] = None

    def get_or_prompt(
        self,
        onboarding_callback: Optional[Callable[[], list[str]]] = None,
    ) -> BrandStyle:
        """获取品牌风格；若未设定则通过 onboarding_callback 引导老板设定。

        Args:
            onboarding_callback: 引导回调，返回风格关键词列表。
                demo 中可返回默认风格「轻奢、暖色调、大面积留白」。
                若不传回调，则使用内置默认关键词。
        """
        if self._style is not None:
            return self._style
        if onboarding_callback is None:
            keywords = list(DEFAULT_BRAND_STYLE_KEYWORDS)
        else:
            keywords = list(onboarding_callback())
        return self.set_style(keywords)

    def set_style(self, keywords: list[str]) -> BrandStyle:
        """设定/覆盖品牌风格。"""
        self._style = BrandStyle(
            style_id=uuid.uuid4().hex[:12],
            keywords=list(keywords),
        )
        return self._style

    def get_style(self) -> Optional[BrandStyle]:
        """获取品牌风格，未设定返回 None。"""
        return self._style

    def get_style_keywords(self) -> list[str]:
        """返回风格关键词列表，供执行层注入（风格锁定）。

        若尚未设定返回空列表。
        """
        if self._style is None:
            return []
        return list(self._style.keywords)
