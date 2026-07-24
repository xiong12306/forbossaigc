"""products.py 商品管理接口。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from boss_aigc.db import get_conn, _now
from boss_aigc.supabase_client import get_supabase

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductCreate(BaseModel):
    name: str
    category: str = ""
    price: float = 0
    cost: float = 0
    stock: int = 0
    status: str = "on_sale"
    image_url: str = ""
    description: str = ""


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    cost: Optional[float] = None
    stock: Optional[int] = None
    status: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


class ProductStatusUpdate(BaseModel):
    status: str


@router.get("")
def list_products(search: Optional[str] = None):
    """商品列表，支持按名称搜索。"""
    sb = get_supabase()
    if sb:
        query = sb.table("products").select("*")
        if search:
            query = query.ilike("name", f"%{search}%")
        data = query.order("id", desc=True).execute().data
        return data
    else:
        with get_conn() as conn:
            if search:
                rows = conn.execute(
                    "SELECT * FROM products WHERE name LIKE ? ORDER BY id DESC",
                    (f"%{search}%",),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


@router.post("")
def create_product(body: ProductCreate):
    """创建商品。"""
    now = _now()
    payload = {
        "name": body.name,
        "category": body.category,
        "price": body.price,
        "cost": body.cost,
        "stock": body.stock,
        "status": body.status,
        "image_url": body.image_url,
        "description": body.description,
        "created_at": now,
        "updated_at": now,
    }
    sb = get_supabase()
    if sb:
        data = sb.table("products").insert(payload).execute().data
        return data[0] if data else payload
    else:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO products (name, category, price, cost, stock, status, image_url, description, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    body.name,
                    body.category,
                    body.price,
                    body.cost,
                    body.stock,
                    body.status,
                    body.image_url,
                    body.description,
                    now,
                    now,
                ),
            )
            new_id = cur.lastrowid
            row = conn.execute("SELECT * FROM products WHERE id=?", (new_id,)).fetchone()
        return dict(row)


@router.put("/{product_id}")
def update_product(product_id: int, body: ProductUpdate):
    """更新商品，仅更新传入字段。"""
    updates = {}
    for field in ("name", "category", "price", "cost", "stock", "status", "image_url", "description"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
    if not updates:
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    updates["updated_at"] = _now()

    sb = get_supabase()
    if sb:
        data = sb.table("products").update(updates).eq("id", product_id).execute().data
        if not data:
            raise HTTPException(status_code=404, detail="商品不存在")
        return data[0]
    else:
        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(product_id)
        with get_conn() as conn:
            cur = conn.execute(
                f"UPDATE products SET {', '.join(fields)} WHERE id=?", values
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="商品不存在")
            row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        return dict(row)


@router.delete("/{product_id}")
def delete_product(product_id: int):
    """删除商品。"""
    sb = get_supabase()
    if sb:
        sb.table("products").delete().eq("id", product_id).execute()
        return {"ok": True, "id": product_id}
    else:
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM products WHERE id=?", (product_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="商品不存在")
        return {"ok": True, "id": product_id}


@router.put("/{product_id}/status")
def update_product_status(product_id: int, body: ProductStatusUpdate):
    """更新商品状态。"""
    now = _now()
    sb = get_supabase()
    if sb:
        data = (
            sb.table("products")
            .update({"status": body.status, "updated_at": now})
            .eq("id", product_id)
            .execute()
            .data
        )
        if not data:
            raise HTTPException(status_code=404, detail="商品不存在")
        return data[0]
    else:
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE products SET status=?, updated_at=? WHERE id=?",
                (body.status, now, product_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="商品不存在")
            row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        return dict(row)
