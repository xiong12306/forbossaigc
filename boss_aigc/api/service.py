"""service.py 客服消息与 FAQ 接口。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from boss_aigc.db import get_conn, _now
from boss_aigc.supabase_client import get_supabase

router = APIRouter(prefix="/api/service", tags=["service"])


@router.get("/messages")
def list_messages():
    """待处理消息列表。"""
    sb = get_supabase()
    if sb:
        data = (
            sb.table("customer_messages")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
            .data
        )
        return data
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM customer_messages WHERE status='pending' ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.put("/messages/{message_id}/resolve")
def resolve_message(message_id: int):
    """标记消息为已处理。"""
    sb = get_supabase()
    if sb:
        data = (
            sb.table("customer_messages")
            .update(
                {"status": "resolved", "updated_at": datetime.now().isoformat()}
            )
            .eq("id", message_id)
            .execute()
            .data
        )
        if not data:
            raise HTTPException(status_code=404, detail="消息不存在")
        return data[0]
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE customer_messages SET status='resolved', updated_at=? WHERE id=?",
            (now, message_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="消息不存在")
        row = conn.execute(
            "SELECT * FROM customer_messages WHERE id=?", (message_id,)
        ).fetchone()
    return dict(row)


@router.get("/faq")
def list_faq():
    """FAQ 列表，按 sort_order 排序。"""
    sb = get_supabase()
    if sb:
        data = sb.table("faq").select("*").order("sort_order").execute().data
        return data
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM faq ORDER BY sort_order ASC, id ASC"
        ).fetchall()
    return [dict(r) for r in rows]
