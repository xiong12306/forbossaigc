import pytest

import boss_aigc.db as db
from boss_aigc.contracts.enums import TaskStatus, TaskType
from boss_aigc.contracts.execution import Artifact, ConfirmedTask, TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.delivery.acceptance import handle_acceptance, AcceptanceAction
from boss_aigc.pipeline import SessionContext

UT_PRODUCT = "UT接线_归档测试"


def _ctx_delivered():
    intent = TaskIntent(intent_id="i", task_type=TaskType.IMAGE_GEN, product=UT_PRODUCT,
                        raw_text="出图", confidence=0.9)
    summary = TaskSummary(summary_id="s", task_type=TaskType.IMAGE_GEN, product=UT_PRODUCT,
                          params={"quantity": 1}, estimated_cost=3)
    result = TaskResult(result_id="r", task_id="t",
                        artifacts=[Artifact(artifact_id="a", kind="IMAGE",
                                            url_or_path="https://img/a.png",
                                            metadata={"image_type": "main"})],
                        status=TaskStatus.DELIVERED)
    ctx = SessionContext()
    ctx.intent = intent
    ctx.result = result
    ctx.confirmed_task = ConfirmedTask(task_id="ct", intent=intent, summary=summary,
                                       confirmed_at=__import__("datetime").datetime.now())
    ctx.status = TaskStatus.DELIVERED
    return ctx


def test_accept_persists_to_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "ut.db"))
    db.init_db()
    import boss_aigc.asset.db_archive as arch
    monkeypatch.setattr(arch, "get_supabase", lambda: None)
    ctx = _ctx_delivered()
    status, prompt = handle_acceptance(AcceptanceAction.ACCEPT, ctx, asset_store=None)
    assert status == TaskStatus.ACCEPTED
    with db.get_conn() as conn:
        t = conn.execute("SELECT * FROM ai_tasks WHERE product=?", (UT_PRODUCT,)).fetchall()
        a = conn.execute("SELECT * FROM assets WHERE product_name=?", (UT_PRODUCT,)).fetchall()
    assert len(t) == 1 and len(a) == 1


def test_accept_db_failure_keeps_delivered(monkeypatch):
    # 方案 B：DB 失败 → 保持 DELIVERED + 失败提示，不误置 ACCEPTED
    import boss_aigc.delivery.acceptance as acc
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(acc, "archive_accepted_task", boom)
    ctx = _ctx_delivered()
    status, prompt = acc.handle_acceptance(AcceptanceAction.ACCEPT, ctx, asset_store=None)
    assert status == TaskStatus.DELIVERED
    assert ctx.status == TaskStatus.DELIVERED
    assert "归档失败" in prompt
