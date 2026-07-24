"""asset.store AssetStore 聚合。

把品牌风格库 / 商品资产库 / 任务历史 / 模板四个 store 组合在一起，
作为资产层的横切关注点统一入口；并提供 inject_style 便捷方法。
"""

from typing import Any

from boss_aigc.asset.brand_style import BrandStyleStore
from boss_aigc.asset.history import TaskHistoryStore
from boss_aigc.asset.product_asset import ProductAssetStore
from boss_aigc.asset.style_lock import inject_style_lock
from boss_aigc.asset.template import TaskTemplateStore


class AssetStore:
    """资产层聚合：组合所有子 store，提供统一访问入口。

    Attributes:
        brand_style: 品牌风格库。
        product_asset: 商品资产库。
        history: 任务历史。
        template: 常用模板。
    """

    def __init__(self) -> None:
        self.brand_style: BrandStyleStore = BrandStyleStore()
        self.product_asset: ProductAssetStore = ProductAssetStore()
        self.history: TaskHistoryStore = TaskHistoryStore()
        self.template: TaskTemplateStore = TaskTemplateStore()

    def inject_style(self, params: dict[str, Any]) -> dict[str, Any]:
        """便捷调用 style_lock.inject_style_lock，注入品牌风格到参数。"""
        return inject_style_lock(params, self.brand_style)


def create_default_asset_store() -> AssetStore:
    """构造一个默认的 AssetStore 实例。"""
    return AssetStore()
