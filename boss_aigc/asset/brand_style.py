"""asset.brand_style 品牌风格库。

保存老板首次设定的品牌风格关键词，所有出图任务默认注入，
保证跨任务风格一致。持久化到 DB（Supabase 优先，SQLite 回退）。
"""

import json
import uuid
from typing import Callable, Optional

from boss_aigc.contracts.asset import BrandStyle
from boss_aigc.db import get_conn
from boss_aigc.supabase_client import get_supabase


# 默认品牌风格关键词（demo 中 onboarding_callback 未提供时兜底使用）
DEFAULT_BRAND_STYLE_KEYWORDS: list[str] = ["轻奢", "暖色调", "大面积留白"]


def _row_to_style(row: dict) -> Optional[BrandStyle]:
    """把 DB 行还原为 BrandStyle。"""
    try:
        keywords = json.loads(row.get("keywords") or "[]")
    except (json.JSONDecodeError, TypeError):
        keywords = []
    return BrandStyle(
        style_id=row.get("style_id") or "",
        keywords=keywords,
    )


class BrandStyleStore:
    """品牌风格库：DB 持久化（单条全局风格）。

    职责：
        - get_or_prompt：首次访问时通过回调引导老板设定风格；
        - set_style / get_style：读写品牌风格；
        - get_style_keywords：返回关键词列表，供执行层风格锁定注入。
    """

    def __init__(self) -> None:
        self._cache: Optional[BrandStyle] = None
        self._cache_loaded: bool = False

    def _load_cache(self) -> None:
        """从 DB 加载当前激活风格到缓存（懒加载，仅一次）。"""
        if self._cache_loaded:
            return
        self._cache = self._fetch_active_from_db()
        self._cache_loaded = True

    @staticmethod
    def _fetch_active_from_db() -> Optional[BrandStyle]:
        """从 DB 读取当前激活的品牌风格。"""
        sb = get_supabase()
        if sb:
            try:
                data = (
                    sb.table("brand_styles")
                    .select("*")
                    .eq("is_active", 1)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                    .data
                )
                if data:
                    return _row_to_style(data[0])
                return None
            except Exception:
                pass
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM brand_styles WHERE is_active=1 "
                    "ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
            if row:
                return _row_to_style(dict(row))
            return None
        except Exception:
            return None

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
        self._load_cache()
        if self._cache is not None:
            return self._cache
        if onboarding_callback is None:
            keywords = list(DEFAULT_BRAND_STYLE_KEYWORDS)
        else:
            keywords = list(onboarding_callback())
        return self.set_style(keywords)

    def set_style(self, keywords: list[str]) -> BrandStyle:
        """设定/覆盖品牌风格，持久化到 DB。"""
        style = BrandStyle(
            style_id=uuid.uuid4().hex[:12],
            keywords=list(keywords),
        )

        # 写 DB：先将旧记录置为 inactive，再插入新记录
        created_at_str = style.created_at.isoformat()
        sb = get_supabase()
        if sb:
            try:
                sb.table("brand_styles").update(
                    {"is_active": 0}
                ).eq("is_active", 1).execute()
                sb.table("brand_styles").insert(
                    {
                        "style_id": style.style_id,
                        "keywords": json.dumps(style.keywords, ensure_ascii=False),
                        "is_active": 1,
                        "created_at": created_at_str,
                    }
                ).execute()
            except Exception:
                pass
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE brand_styles SET is_active=0 WHERE is_active=1"
                )
                conn.execute(
                    "INSERT INTO brand_styles (style_id, keywords, is_active, created_at) "
                    "VALUES (?,?,?,?)",
                    (
                        style.style_id,
                        json.dumps(style.keywords, ensure_ascii=False),
                        1,
                        created_at_str,
                    ),
                )
        except Exception:
            pass

        self._cache = style
        self._cache_loaded = True
        return style

    def get_style(self) -> Optional[BrandStyle]:
        """获取品牌风格，未设定返回 None。"""
        self._load_cache()
        return self._cache

    def get_style_keywords(self) -> list[str]:
        """返回风格关键词列表，供执行层注入（风格锁定）。

        若尚未设定返回空列表。
        """
        self._load_cache()
        if self._cache is None:
            return []
        return list(self._cache.keywords)
