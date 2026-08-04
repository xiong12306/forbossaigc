import json
import pytest

import boss_aigc.db as db
from boss_aigc.contracts.enums import TaskStatus, TaskType
from boss_aigc.contracts.execution import Artifact, TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary

UT_PRODUCT = "UT保温杯_归档测试"


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """临时 SQLite 并强制走 SQLite（get_supabase→None）。"""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "ut.db"))
    db.init_db()  # 建表（含种子数据，故测试按 UT_PRODUCT 过滤避免干扰）
    import boss_aigc.asset.db_archive as arch
    monkeypatch.setattr(arch, "get_supabase", lambda: None)
    return db


def _make(intent_product=UT_PRODUCT, artifacts=None, image_type="main"):
    intent = TaskIntent(
        intent_id="i1", task_type=TaskType.IMAGE_GEN, product=intent_product,
        raw_text="给保温杯出2张主图", confidence=0.9,
    )
    summary = TaskSummary(
        summary_id="s1", task_type=TaskType.IMAGE_GEN, product=intent_product,
        params={"quantity": 2, "image_type": image_type}, estimated_cost=6,
    )
    if artifacts is None:
        artifacts = [
            Artifact(artifact_id=f"a{i}", kind="IMAGE",
                     url_or_path=f"https://img/{i}.png", thumbnail_path=f"https://img/{i}.png",
                     metadata={"image_type": image_type, "source": "modelscope"})
            for i in range(2)
        ]
    result = TaskResult(result_id="r1", task_id="t1", artifacts=artifacts, status=TaskStatus.DELIVERED)
    return intent, summary, result


def test_archive_writes_task_and_assets(sqlite_db):
    from boss_aigc.asset.db_archive import archive_accepted_task
    intent, summary, result = _make()
    task_id = archive_accepted_task(intent, summary, result)
    assert isinstance(task_id, int) and task_id > 0
    with db.get_conn() as conn:
        trows = conn.execute("SELECT * FROM ai_tasks WHERE product=?", (UT_PRODUCT,)).fetchall()
        arows = conn.execute("SELECT * FROM assets WHERE product_name=? ORDER BY id", (UT_PRODUCT,)).fetchall()
    assert len(trows) == 1
    assert trows[0]["status"] == "done"
    assert trows[0]["task_type"] == "image_gen"
    assert json.loads(trows[0]["artifacts"]) and len(json.loads(trows[0]["artifacts"])) == 2
    assert len(arows) == 2
    assert arows[0]["asset_type"] == "main"
    assert arows[0]["url"] == "https://img/0.png"
    assert arows[0]["task_id"] == task_id


def test_archive_only_image_artifacts(sqlite_db):
    from boss_aigc.asset.db_archive import archive_accepted_task
    from boss_aigc.contracts.enums import TaskStatus
    arts = [
        Artifact(artifact_id="img", kind="IMAGE", url_or_path="https://img/x.png",
                 metadata={"image_type": "poster"}),
        Artifact(artifact_id="txt", kind="TEXT", url_or_path="文案内容", metadata={}),
    ]
    intent, summary, _ = _make()
    result = TaskResult(result_id="r2", task_id="t2", artifacts=arts, status=TaskStatus.DELIVERED)
    archive_accepted_task(intent, summary, result)
    with db.get_conn() as conn:
        arows = conn.execute("SELECT * FROM assets WHERE product_name=?", (UT_PRODUCT,)).fetchall()
    assert len(arows) == 1
    assert arows[0]["asset_type"] == "poster"


def test_archive_bad_image_type_falls_back_main(sqlite_db):
    from boss_aigc.asset.db_archive import archive_accepted_task
    from boss_aigc.contracts.enums import TaskStatus
    arts = [Artifact(artifact_id="img", kind="IMAGE", url_or_path="https://img/y.png",
                     metadata={"image_type": "不合法"})]
    intent, summary, _ = _make()
    result = TaskResult(result_id="r3", task_id="t3", artifacts=arts, status=TaskStatus.DELIVERED)
    archive_accepted_task(intent, summary, result)
    with db.get_conn() as conn:
        arows = conn.execute("SELECT * FROM assets WHERE product_name=?", (UT_PRODUCT,)).fetchall()
    assert arows[0]["asset_type"] == "main"


# ---------- Supabase 路径（fake client）：锁住 C1/H1/H2 ----------

class _FakeExec:
    def __init__(self, data):
        self._data = data
    def execute(self):
        return type("R", (), {"data": self._data})()


class _FakeTable:
    def __init__(self, name, log, task_data):
        self.name = name
        self.log = log
        self.task_data = task_data
    def insert(self, payload):
        self.log.append((self.name, payload))
        return _FakeExec(self.task_data if self.name == "ai_tasks" else [{}])


class _FakeSB:
    def __init__(self, task_data):
        self.log = []
        self._task_data = task_data
    def table(self, name):
        return _FakeTable(name, self.log, self._task_data)


def test_supabase_passes_objects_and_batches(monkeypatch):
    """C1：JSONB 列传 Python 对象（非 json 字符串）；H1：assets 批量单次 insert。"""
    from boss_aigc.asset import db_archive as arch
    fake = _FakeSB(task_data=[{"id": 999}])
    monkeypatch.setattr(arch, "get_supabase", lambda: fake)
    intent, summary, result = _make()  # 2 张 IMAGE
    task_id = arch.archive_accepted_task(intent, summary, result)
    assert task_id == 999
    # ai_tasks insert：params 是 dict、artifacts 是 list（不是 json 字符串）
    ai_calls = [p for (t, p) in fake.log if t == "ai_tasks"]
    assert len(ai_calls) == 1
    assert isinstance(ai_calls[0]["params"], dict)
    assert isinstance(ai_calls[0]["artifacts"], list)
    assert ai_calls[0]["status"] == "done"
    # assets insert：一次批量，payload 是长度 2 的 list
    asset_calls = [p for (t, p) in fake.log if t == "assets"]
    assert len(asset_calls) == 1
    assert isinstance(asset_calls[0], list) and len(asset_calls[0]) == 2
    assert asset_calls[0][0]["task_id"] == 999


def test_supabase_empty_data_raises(monkeypatch):
    """H2：ai_tasks insert 未返回行 id 时，抛清晰异常（不静默）。"""
    from boss_aigc.asset import db_archive as arch
    fake = _FakeSB(task_data=[])  # 空 data
    monkeypatch.setattr(arch, "get_supabase", lambda: fake)
    intent, summary, result = _make()
    with pytest.raises(RuntimeError):
        arch.archive_accepted_task(intent, summary, result)
