"""contracts.asset 资产与记忆层数据契约。

BrandStyle 与 ProductAsset 是「资产层」的核心实体，
被理解/确认/执行/交付各层查询或写入，用于风格锁定与商品关联。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BrandStyle(BaseModel):
    """品牌风格：老板首次设定的全局风格约束。

    所有出图任务默认注入该风格关键词，保证跨任务风格一致。

    Attributes:
        style_id: 风格设定唯一 ID。
        keywords: 风格关键词列表（如 ["轻奢","暖色调","大面积留白"]）。
        created_at: 创建时间。
    """

    style_id: str = Field(..., description="风格设定唯一 ID")
    keywords: list[str] = Field(
        default_factory=list, description="风格关键词列表"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间"
    )


class ProductAsset(BaseModel):
    """商品资产：单个商品的入库记录（白底原图 + SKU 关联）。

    老板提及该商品时，执行层可自动取用参考图。

    Attributes:
        asset_id: 资产唯一 ID。
        product_name: 商品名。
        sku: 商品 SKU（可选）。
        reference_image_path: 白底原图路径。
        created_at: 创建时间。
    """

    asset_id: str = Field(..., description="资产唯一 ID")
    product_name: str = Field(..., description="商品名")
    sku: Optional[str] = Field(default=None, description="商品 SKU")
    reference_image_path: Optional[str] = Field(
        default=None, description="白底原图路径"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间"
    )
