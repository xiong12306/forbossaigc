"""assets.py 素材库接口。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from boss_aigc.db import get_conn
from boss_aigc.supabase_client import get_supabase

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("")
def list_assets(asset_type: Optional[str] = None):
    """素材列表，支持按 asset_type 过滤。"""
    sb = get_supabase()
    if sb:
        query = sb.table("assets").select("*")
        if asset_type:
            query = query.eq("asset_type", asset_type)
        data = query.order("id", desc=True).execute().data
        return data
    else:
        with get_conn() as conn:
            if asset_type:
                rows = conn.execute(
                    "SELECT * FROM assets WHERE asset_type=? ORDER BY id DESC",
                    (asset_type,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM assets ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


@router.delete("/{asset_id}")
def delete_asset(asset_id: int):
    """删除素材。"""
    sb = get_supabase()
    if sb:
        sb.table("assets").delete().eq("id", asset_id).execute()
        return {"ok": True, "id": asset_id}
    else:
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM assets WHERE id=?", (asset_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="素材不存在")
        return {"ok": True, "id": asset_id}
