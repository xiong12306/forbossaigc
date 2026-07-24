"""asset.product_asset 商品资产库。

保存老板上传/入库的商品白底原图与 SKU 关联，
供执行层自动取用参考图、理解层做模糊指令澄清。本阶段为内存存储。
"""

import uuid
from typing import Optional

from boss_aigc.contracts.asset import ProductAsset


class ProductAssetStore:
    """商品资产库：内存存储（dict 实现，按商品名去重并保留插入顺序）。"""

    def __init__(self) -> None:
        self._assets: dict[str, ProductAsset] = {}

    def add(
        self,
        product_name: str,
        sku: Optional[str] = None,
        reference_image_path: Optional[str] = None,
    ) -> ProductAsset:
        """新增/更新商品资产（同名商品将被覆盖）。"""
        asset = ProductAsset(
            asset_id=uuid.uuid4().hex[:12],
            product_name=product_name,
            sku=sku,
            reference_image_path=reference_image_path,
        )
        self._assets[product_name] = asset
        return asset

    def get(self, product_name: str) -> Optional[ProductAsset]:
        """按商品名查询资产；未找到返回 None。"""
        return self._assets.get(product_name)

    def list_recent(self, n: int = 3) -> list[ProductAsset]:
        """返回最近 n 个商品（按插入顺序的尾部，供理解层模糊指令澄清用）。"""
        items = list(self._assets.values())
        if n <= 0:
            return []
        return items[-n:]

    def list_all(self) -> list[ProductAsset]:
        """返回所有商品资产（按插入顺序）。"""
        return list(self._assets.values())
