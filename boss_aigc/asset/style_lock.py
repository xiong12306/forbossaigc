"""asset.style_lock 风格锁定注入点（预留）。

把品牌风格关键词注入到任务参数中，保证跨任务风格一致。

Note:
    本阶段只做参数注入逻辑。真实的「风格一致性校验」需基于
    真实出图后的图像特征比对实现，留待后续阶段接入。
"""

from typing import Any

from boss_aigc.asset.brand_style import BrandStyleStore


# 注入到 params 中的字段名
STYLE_KEY = "style"


def inject_style_lock(
    params: dict[str, Any],
    brand_style_store: BrandStyleStore,
) -> dict[str, Any]:
    """把品牌风格关键词注入任务参数。

    策略：
        - 若 params 已显式指定 style（非空），则保留老板当前选择，不覆盖；
        - 否则用品牌风格关键词填充 params['style']。
        - 返回新 dict，不修改入参。

    Args:
        params: 原始任务参数（可能含 quantity/size/style 等）。
        brand_style_store: 品牌风格库，提供关键词来源。

    Returns:
        注入后的新参数 dict。
    """
    out: dict[str, Any] = dict(params) if params else {}
    existing = out.get(STYLE_KEY)
    if not existing:
        keywords = brand_style_store.get_style_keywords()
        if keywords:
            out[STYLE_KEY] = list(keywords)
    return out
