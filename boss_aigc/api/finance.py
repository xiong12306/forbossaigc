"""finance.py 财务统计与明细接口。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter

from boss_aigc.db import get_conn
from boss_aigc.supabase_client import get_supabase

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/summary")
def summary():
    """本月收入、支出、利润。"""
    now = datetime.now()
    month_str = f"{now.year:04d}-{now.month:02d}"

    sb = get_supabase()
    if sb:
        rows = sb.table("finance_records").select("*").execute().data
        income = sum(
            float(r.get("amount") or 0)
            for r in rows
            if r.get("record_type") == "income" and (r.get("record_date") or "").startswith(month_str)
        )
        expense = sum(
            float(r.get("amount") or 0)
            for r in rows
            if r.get("record_type") == "expense" and (r.get("record_date") or "").startswith(month_str)
        )
    else:
        with get_conn() as conn:
            income_row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM finance_records "
                "WHERE record_type='income' AND record_date LIKE ?",
                (f"{month_str}%",),
            ).fetchone()
            expense_row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM finance_records "
                "WHERE record_type='expense' AND record_date LIKE ?",
                (f"{month_str}%",),
            ).fetchone()
        income = income_row["total"]
        expense = expense_row["total"]

    return {
        "income": income,
        "expense": expense,
        "profit": round(income - expense, 2),
        "month": month_str,
    }


@router.get("/records")
def list_records(record_type: Optional[str] = None):
    """收支明细列表，支持按 record_type 过滤。"""
    sb = get_supabase()
    if sb:
        query = sb.table("finance_records").select("*")
        if record_type:
            query = query.eq("record_type", record_type)
        rows = query.order("record_date", desc=True).order("id", desc=True).execute().data
        return rows

    with get_conn() as conn:
        if record_type:
            rows = conn.execute(
                "SELECT * FROM finance_records WHERE record_type=? ORDER BY record_date DESC, id DESC",
                (record_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM finance_records ORDER BY record_date DESC, id DESC"
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/monthly-comparison")
def monthly_comparison():
    """最近4个月收入/支出对比。"""
    now = datetime.now()
    months = []
    for i in range(3, -1, -1):
        d = datetime(now.year, now.month, 1)
        # 回退 i 个月
        year = d.year - (d.month - i - 1) // 12
        month = (d.month - i - 1) % 12 + 1
        months.append((year, month))

    sb = get_supabase()
    if sb:
        rows = sb.table("finance_records").select("*").execute().data
        result = []
        for year, month in months:
            prefix = f"{year:04d}-{month:02d}"
            income = sum(
                float(r.get("amount") or 0)
                for r in rows
                if r.get("record_type") == "income" and (r.get("record_date") or "").startswith(prefix)
            )
            expense = sum(
                float(r.get("amount") or 0)
                for r in rows
                if r.get("record_type") == "expense" and (r.get("record_date") or "").startswith(prefix)
            )
            result.append({
                "month": f"{year:04d}-{month:02d}",
                "income": income,
                "expense": expense,
            })
        return result

    result = []
    with get_conn() as conn:
        for year, month in months:
            prefix = f"{year:04d}-{month:02d}"
            income_row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM finance_records "
                "WHERE record_type='income' AND record_date LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
            expense_row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM finance_records "
                "WHERE record_type='expense' AND record_date LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
            result.append({
                "month": f"{year:04d}-{month:02d}",
                "income": income_row["total"],
                "expense": expense_row["total"],
            })
    return result
