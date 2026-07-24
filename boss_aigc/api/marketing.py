"""marketing.py 营销活动与优惠券接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from boss_aigc.db import get_conn, _now
from boss_aigc.supabase_client import get_supabase

router = APIRouter(prefix="/api/marketing", tags=["marketing"])


class CampaignCreate(BaseModel):
    name: str
    type: str
    start_date: str
    end_date: str
    status: str = "active"
    discount_value: float = 0
    conditions: str = ""


class CouponCreate(BaseModel):
    name: str
    type: str
    value: float
    condition_amount: float = 0
    claimed_count: int = 0
    total_count: int = 100
    status: str = "active"


@router.get("/campaigns")
def list_campaigns():
    """活动列表。"""
    sb = get_supabase()
    if sb:
        data = (
            sb.table("campaigns")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data
        )
        return data
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/campaigns")
def create_campaign(body: CampaignCreate):
    """创建活动。"""
    now = _now()
    sb = get_supabase()
    if sb:
        data = (
            sb.table("campaigns")
            .insert(
                {
                    "name": body.name,
                    "type": body.type,
                    "start_date": body.start_date,
                    "end_date": body.end_date,
                    "status": body.status,
                    "discount_value": body.discount_value,
                    "conditions": body.conditions,
                    "created_at": now,
                }
            )
            .execute()
            .data
        )
        return data[0] if data else {}
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO campaigns (name, type, start_date, end_date, status, discount_value, conditions, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                body.name,
                body.type,
                body.start_date,
                body.end_date,
                body.status,
                body.discount_value,
                body.conditions,
                now,
            ),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM campaigns WHERE id=?", (new_id,)).fetchone()
    return dict(row)


@router.get("/coupons")
def list_coupons():
    """优惠券列表。"""
    sb = get_supabase()
    if sb:
        data = (
            sb.table("coupons")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data
        )
        return data
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/coupons")
def create_coupon(body: CouponCreate):
    """创建优惠券。"""
    now = _now()
    sb = get_supabase()
    if sb:
        data = (
            sb.table("coupons")
            .insert(
                {
                    "name": body.name,
                    "type": body.type,
                    "value": body.value,
                    "condition_amount": body.condition_amount,
                    "claimed_count": body.claimed_count,
                    "total_count": body.total_count,
                    "status": body.status,
                    "created_at": now,
                }
            )
            .execute()
            .data
        )
        return data[0] if data else {}
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO coupons (name, type, value, condition_amount, claimed_count, total_count, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                body.name,
                body.type,
                body.value,
                body.condition_amount,
                body.claimed_count,
                body.total_count,
                body.status,
                now,
            ),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM coupons WHERE id=?", (new_id,)).fetchone()
    return dict(row)
