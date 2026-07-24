"""asset.history 任务历史持久化与检索。

记录每次任务的原始意图、确认摘要、执行结果摘要，供老板回查
与后续模板沉淀。本阶段为内存存储。
"""

from datetime import datetime
from typing import Any, Optional

from boss_aigc.contracts.execution import TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary


def _enum_value(v: Any) -> Any:
    """统一取枚举的 value，非枚举原样返回。"""
    return v.value if hasattr(v, "value") else v


class TaskHistoryStore:
    """任务历史存储：内存存储（list 实现）。"""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        intent: TaskIntent,
        summary: TaskSummary,
        result: TaskResult,
    ) -> None:
        """记录一次任务。

        存为简单 dict，含 task_id / task_type / product / raw_text /
        summary 摘要 / result 摘要 / timestamp 等字段。
        """
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
        self._records.append(record)

    def search(
        self,
        product: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """按商品名 / 任务类型搜索历史，最多返回 limit 条（按时间倒序）。

        任一过滤条件为 None 表示不过滤该字段。
        """
        out: list[dict[str, Any]] = []
        for r in reversed(self._records):
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
        return list(reversed(self._records))[:n]
