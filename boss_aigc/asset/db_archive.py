"""asset.db_archive 已验收任务的 DB 持久化（打通平台资产库/任务记录）。

验收 ACCEPT 时把任务写入 ai_tasks、把每张生成图写入 assets，
使平台后台"资产/仪表盘"页可见且重启不丢。Supabase 优先，否则 SQLite。

遵「不擅自加兜底」：DB 失败不在此吞错，直接向上抛，由调用方（_handle_accept）按方案 B 处理。

注意 Supabase 与 SQLite 的类型差异：
  - Supabase(Postgres) 的 params/artifacts 列是 JSONB → 直接传 Python 对象，交给 postgrest 序列化；
    若在此处 json.dumps 成字符串再传，会被存成 JSON string 标量（双重编码），破坏平台读取。
  - SQLite 的 params/artifacts 列是 TEXT → 传 json.dumps 后的字符串。
Supabase 多图用一次批量 insert（缩小非事务部分写入窗口）；跨 ai_tasks/assets 两次写入仍非原子，
失败时可能残留 ai_tasks 行（方案 B 会提示重试），当前无 RPC 单事务封装，属已知约束。
"""

from __future__ import annotations

import json
from typing import Any

from boss_aigc.db import get_conn, _now
from boss_aigc.supabase_client import get_supabase
from boss_aigc.contracts.execution import TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="asset")

_VALID_ASSET_TYPES = {"main", "detail", "scene", "poster", "carousel"}


def _enum_value(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _asset_type_of(artifact: Any) -> str:
    meta = getattr(artifact, "metadata", None) or {}
    raw = _enum_value(meta.get("image_type"))
    if raw in _VALID_ASSET_TYPES:
        return raw
    if raw is not None:
        logger.debug("未知 image_type=%r，asset_type 回退 main", raw)
    return "main"


def _is_real_url(url: str | None) -> bool:
    """判断是否为真实可访问的图片URL（排除 mock:// 占位链接）。"""
    if not url:
        return False
    return not url.startswith("mock://")


def _image_artifacts(result: TaskResult) -> list[Any]:
    """只归档真实图片，过滤 mock 占位产物。"""
    return [
        a for a in (result.artifacts or [])
        if getattr(a, "kind", "") == "IMAGE" and _is_real_url(getattr(a, "url_or_path", None))
    ]


def archive_accepted_task(intent: TaskIntent, summary: TaskSummary, result: TaskResult) -> int:
    """把已验收任务写入 DB：ai_tasks 一行 + 每张 IMAGE 一行 assets。返回 ai_tasks 行 id。

    Supabase 已配走 Supabase，否则 SQLite。DB 失败向上抛（不吞错）。
    """
    task_type = _enum_value(intent.task_type)
    product = intent.product or ""
    params_obj = dict(summary.params)
    cost = int(summary.estimated_cost)
    artifacts_obj = [
        {
            "artifact_id": getattr(a, "artifact_id", ""),
            "kind": getattr(a, "kind", ""),
            "url_or_path": getattr(a, "url_or_path", None),
            "thumbnail_path": getattr(a, "thumbnail_path", None),
            "metadata": getattr(a, "metadata", {}) or {},
        }
        for a in (result.artifacts or [])
    ]
    imgs = _image_artifacts(result)
    now = _now()

    def _asset_row(a: Any, task_id: int) -> dict[str, Any]:
        return {
            "asset_type": _asset_type_of(a),
            "product_name": product,
            "url": getattr(a, "url_or_path", "") or "",
            "thumbnail_url": getattr(a, "thumbnail_path", None) or getattr(a, "url_or_path", "") or "",
            "task_id": task_id,
            "created_at": now,
        }

    sb = get_supabase()
    if sb:
        # JSONB 列直接传对象；postgrest 负责序列化
        task_res = (
            sb.table("ai_tasks")
            .insert({
                "task_type": task_type, "product": product, "params": params_obj,
                "status": "done", "artifacts": artifacts_obj, "cost": cost,
                "created_at": now, "completed_at": now,
            })
            .execute()
        )
        if not getattr(task_res, "data", None):
            raise RuntimeError("ai_tasks insert 未返回行 id（Supabase）")
        task_id = int(task_res.data[0]["id"])
        if imgs:
            # 批量单次 insert，缩小非事务部分写入窗口
            sb.table("assets").insert([_asset_row(a, task_id) for a in imgs]).execute()
    else:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO ai_tasks (task_type, product, params, status, artifacts, cost, created_at, completed_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    task_type, product,
                    json.dumps(params_obj, ensure_ascii=False), "done",
                    json.dumps(artifacts_obj, ensure_ascii=False), cost, now, now,
                ),
            )
            task_id = int(cur.lastrowid)
            for a in imgs:
                row = _asset_row(a, task_id)
                conn.execute(
                    "INSERT INTO assets (asset_type, product_name, url, thumbnail_url, task_id, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (row["asset_type"], row["product_name"], row["url"],
                     row["thumbnail_url"], row["task_id"], row["created_at"]),
                )
    logger.info("验收归档落库: task_id=%s, product=%s, 图片 %d 张", task_id, product, len(imgs))
    return task_id
