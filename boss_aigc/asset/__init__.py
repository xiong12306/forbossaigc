"""boss_aigc 资产与记忆层包。

职责：品牌风格库 / 商品资产库 / 任务历史 / 常用模板。
作为横切关注点，被各层查询或写入，不进入主链线性顺序。
本阶段为内存存储实现。
"""

from boss_aigc.asset.brand_style import BrandStyleStore
from boss_aigc.asset.history import TaskHistoryStore
from boss_aigc.asset.product_asset import ProductAssetStore
from boss_aigc.asset.store import AssetStore, create_default_asset_store
from boss_aigc.asset.style_lock import inject_style_lock
from boss_aigc.asset.template import TaskTemplateStore

__all__ = [
    "BrandStyleStore",
    "ProductAssetStore",
    "TaskHistoryStore",
    "TaskTemplateStore",
    "inject_style_lock",
    "AssetStore",
    "create_default_asset_store",
]
