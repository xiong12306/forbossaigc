"""asset.history 任务历史持久化与检索。

记录每次任务的原始意图、确认摘要、执行结果摘要，供老板回查
与后续模板沉淀。持久化到 DB（Supabase 优先，SQLite 回退），
内存缓存保留以便高频读取。
"""

import json
from datetime import datetime
from typing import Any, Optional

from boss_aigc.contracts.execution import TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.db import get_conn
from boss_aigc.supabase_client import get_supabase


def _enum_value(v: Any) -> Any:
    """统一取枚举的 value，非枚举原样返回。"""
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: dict) -> dict[str, Any]:
    """把 DB 行还原为 record dict（与原内存结构对齐）。"""
    try:
        params = json.loads(row.get("params") or "{}")
    except (json.JSONDecodeError, TypeError):
        params = {}
    return {
        "task_id": row.get("task_id"),
        "task_type": row.get("task_type"),
        "product": row.get("product") or "",
        "raw_text": row.get("raw_text") or "",
        "summary": {
            "summary_id": row.get("summary_id") or "",
            "params": params,
            "platform": row.get("platform") or "",
        },
        "result_artifacts_count": row.get("result_artifacts_count") or 0,
        "result_status": row.get("result_status") or "",
        "timestamp": row.get("timestamp") or "",
    }


class TaskHistoryStore:
    """任务历史存储：DB 持久化（Supabase 优先，SQLite 回退）+ 内存缓存。"""

    def __init__(self) -> None:
        # 内存缓存仅用于加速高频读取，权威数据在 DB
        self._cache: list[dict[str, Any]] = []
        self._cache_loaded: bool = False

    def _load_cache(self) -> None:
        """从 DB 加载全部历史到内存缓存（懒加载，仅一次）。"""
        if self._cache_loaded:
            return
        self._cache = self._fetch_all_from_db()
        self._cache_loaded = True

    @staticmethod
    def _fetch_all_from_db() -> list[dict[str, Any]]:
        """从 DB 读取全部历史（按时间倒序）。"""
        sb = get_supabase()
        if sb:
            try:
                data = (
                    sb.table("task_history")
                    .select("*")
                    .order("timestamp", desc=True)
                    .execute()
                    .data
                )
                return [_row_to_record(r) for r in data]
            except Exception:
                pass
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM task_history ORDER BY id DESC"
                ).fetchall()
            return [_row_to_record(dict(r)) for r in rows]
        except Exception:
            return []

    def record(
        self,
        intent: TaskIntent,
        summary: TaskSummary,
        result: TaskResult,
    ) -> None:
        """记录一次任务，持久化到 DB 并更新内存缓存。"""
        record: dict[str, Any] = {
            "task_id": result.task_id,
            "task_type": _enum_value(intent.task_type),
            "product": intent.product,
            "raw_text": intent.raw_text,
            "summary": {
                "summary_id": summary.summary_id,
                "params": dict(summary.params),
                "platform": _enum_value(summary.platform),
            },
            "result_artifacts_count": len(result.artifacts),
            "result_status": _enum_value(result.status),
            "timestamp": datetime.now().isoformat(),
        }

        # 写 DB
        sb = get_supabase()
        if sb:
            try:
                sb.table("task_history").upsert(
                    {
                        "task_id": record["task_id"],
                        "task_type": record["task_type"],
                        "product": record["product"] or "",
                        "raw_text": record["raw_text"] or "",
                        "summary_id": record["summary"]["summary_id"] or "",
                        "params": json.dumps(
                            record["summary"]["params"], ensure_ascii=False
                        ),
                        "platform": record["summary"]["platform"] or "",
                        "result_artifacts_count": record["result_artifacts_count"],
                        "result_status": record["result_status"] or "",
                        "timestamp": record["timestamp"],
                    }
                ).execute()
            except Exception:
                pass
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO task_history "
                    "(task_id, task_type, product, raw_text, summary_id, params, "
                    "platform, result_artifacts_count, result_status, timestamp) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        record["task_id"],
                        record["task_type"],
                        record["product"] or "",
                        record["raw_text"] or "",
                        record["summary"]["summary_id"] or "",
                        json.dumps(
                            record["summary"]["params"], ensure_ascii=False
                        ),
                        record["summary"]["platform"] or "",
                        record["result_artifacts_count"],
                        record["result_status"] or "",
                        record["timestamp"],
                    ),
                )
        except Exception:
            pass

        # 更新内存缓存
        if not self._cache_loaded:
            self._cache = self._fetch_all_from_db()
            self._cache_loaded = True
        # 避免重复插入相同 task_id
        self._cache = [r for r in self._cache if r.get("task_id") != record["task_id"]]
        self._cache.insert(0, record)

    def search(
        self,
        product: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """按商品名 / 任务类型搜索历史，最多返回 limit 条（按时间倒序）。

        任一过滤条件为 None 表示不过滤该字段。
        """
        self._load_cache()
        out: list[dict[str, Any]] = []
        for r in self._cache:
            if product is not None and r.get("product") != product:
                continue
            if task_type is not None and r.get("task_type") != task_type:
                continue
            out.append(r)
            if len(out) >= limit:
                break
        return out

    def get_recent(self, n: int = 5) -> list[dict[str, Any]]:
        """返回最近 n 条历史（按时间倒序）。"""
        if n <= 0:
            return []
        self._load_cache()
        return self._cache[:n]
