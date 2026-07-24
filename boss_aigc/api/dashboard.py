"""dashboard.py 仪表盘数据接口。"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter

from boss_aigc.db import get_conn
from boss_aigc.supabase_client import get_supabase

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview():
    """最近7天汇总数据，并与前7天对比计算涨跌幅。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    recent_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    recent_end = today.strftime("%Y-%m-%d")
    prev_start = (today - timedelta(days=13)).strftime("%Y-%m-%d")
    prev_end = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    sb = get_supabase()
    if sb:
        rows = sb.table("daily_stats").select("*").order("stat_date", desc=True).limit(14).execute().data
        recent_rows = [r for r in rows if recent_start <= r.get("stat_date", "") <= recent_end]
        prev_rows = [r for r in rows if prev_start <= r.get("stat_date", "") <= prev_end]

        def _agg(rows_list):
            gmv = sum(float(r.get("gmv") or 0) for r in rows_list)
            orders = sum(int(r.get("orders") or 0) for r in rows_list)
            visitors = sum(int(r.get("visitors") or 0) for r in rows_list)
            cr_vals = [float(r.get("conversion_rate") or 0) for r in rows_list]
            cr = sum(cr_vals) / len(cr_vals) if cr_vals else 0.0
            return {"gmv": gmv, "orders": orders, "visitors": visitors, "cr": cr}

        recent = _agg(recent_rows)
        prev = _agg(prev_rows)
    else:
        with get_conn() as conn:
            recent = conn.execute(
                "SELECT COALESCE(SUM(gmv),0) AS gmv, COALESCE(SUM(orders),0) AS orders, "
                "COALESCE(SUM(visitors),0) AS visitors, COALESCE(AVG(conversion_rate),0) AS cr "
                "FROM daily_stats WHERE stat_date BETWEEN ? AND ?",
                (recent_start, recent_end),
            ).fetchone()
            prev = conn.execute(
                "SELECT COALESCE(SUM(gmv),0) AS gmv, COALESCE(SUM(orders),0) AS orders, "
                "COALESCE(SUM(visitors),0) AS visitors, COALESCE(AVG(conversion_rate),0) AS cr "
                "FROM daily_stats WHERE stat_date BETWEEN ? AND ?",
                (prev_start, prev_end),
            ).fetchone()
            recent = {"gmv": recent["gmv"], "orders": recent["orders"], "visitors": recent["visitors"], "cr": recent["cr"]}
            prev = {"gmv": prev["gmv"], "orders": prev["orders"], "visitors": prev["visitors"], "cr": prev["cr"]}

    def _change(cur: float, old: float) -> float:
        if not old:
            return 0.0
        return round((cur - old) / old * 100, 1)

    return {
        "gmv": recent["gmv"],
        "gmv_change": _change(recent["gmv"], prev["gmv"]),
        "orders": recent["orders"],
        "orders_change": _change(recent["orders"], prev["orders"]),
        "visitors": recent["visitors"],
        "visitors_change": _change(recent["visitors"], prev["visitors"]),
        "conversion_rate": round(recent["cr"], 2),
        "cr_change": _change(recent["cr"], prev["cr"]),
    }


@router.get("/sales-trend")
def sales_trend():
    """最近7天每日 GMV。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    sb = get_supabase()
    if sb:
        rows = sb.table("daily_stats").select("stat_date,gmv").order("stat_date", desc=True).limit(7).execute().data
        rows = list(reversed(rows))
        return [{"date": r.get("stat_date"), "gmv": r.get("gmv")} for r in rows]

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT stat_date AS date, gmv FROM daily_stats "
            "WHERE stat_date BETWEEN ? AND ? ORDER BY stat_date ASC",
            (start, end),
        ).fetchall()
    return [{"date": r["date"], "gmv": r["gmv"]} for r in rows]


@router.get("/top-products")
def top_products():
    """按 price*stock 估算排名取前5。"""
    sb = get_supabase()
    if sb:
        rows = sb.table("products").select("name,price,stock").execute().data
        rows = sorted(rows, key=lambda r: float(r.get("price") or 0) * int(r.get("stock") or 0), reverse=True)[:5]
        result = []
        for idx, r in enumerate(rows, start=1):
            price = float(r.get("price") or 0)
            stock = int(r.get("stock") or 0)
            sales = max(stock - idx * 3, 1)
            result.append({
                "name": r.get("name"),
                "sales": sales,
                "gmv": round(price * sales, 2),
            })
        return result

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name, price, stock FROM products ORDER BY price * stock DESC LIMIT 5"
        ).fetchall()
    result = []
    for idx, r in enumerate(rows, start=1):
        sales = max(r["stock"] - idx * 3, 1)
        result.append({
            "name": r["name"],
            "sales": sales,
            "gmv": round(r["price"] * sales, 2),
        })
    return result


@router.get("/recent-tasks")
def recent_tasks():
    """最近5条 AI 任务。"""
    sb = get_supabase()
    if sb:
        rows = sb.table("ai_tasks").select("id,task_type,product,status,created_at").order("created_at", desc=True).limit(5).execute().data
        return rows

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, task_type, product, status, created_at FROM ai_tasks "
            "ORDER BY id DESC LIMIT 5"
        ).fetchall()
    return [dict(r) for r in rows]
