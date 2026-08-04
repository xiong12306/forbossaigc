# 助手验收归档落库 Implementation Plan

> **For agentic workers:** 用 TDD 逐任务实现。本项目**非 git 仓库**，所有 "Commit" 步骤替换为"跑相关测试确保通过"。Steps use checkbox (`- [ ]`).

**Goal:** 验收（ACCEPT）时把任务写 `ai_tasks`、把每张生成图写 `assets`，让平台"资产/仪表盘"页可见且重启不丢；内存归档保留不动。

**Architecture:** 新建隔离持久化单元 `asset/db_archive.py::archive_accepted_task`，在 `delivery/acceptance.py::_handle_accept` 里内存归档之后、置 ACCEPTED 之前调用。DB 走 `get_supabase() → get_conn()` 双路。DB 失败按方案 B：保持 DELIVERED + 明确失败提示，不静默、不假装成功。

**Tech Stack:** Python 3.11+（venv 为 3.14）, pydantic, sqlite3, pytest。参考 spec：`docs/superpowers/specs/2026-07-27-archive-to-db-design.md`。

## Global Constraints

- 遵「不擅自加兜底」：DB 写失败**不吞错、不假装成功**。按方案 B——`_handle_accept` 捕获后保持 `status=DELIVERED`、speak_text 含"归档失败"、`logger.error` 记全。`archive_accepted_task` 内部**不吞异常**，向上抛。
- 双路访问：`from boss_aigc.supabase_client import get_supabase`；`sb=get_supabase()`；`if sb:` 用 Supabase，`else:` 用 `from boss_aigc.db import get_conn, _now`。
- 仅 `kind == "IMAGE"` 的 artifact 写 `assets`。
- `asset_type` 取 `artifact.metadata.get("image_type")`，不在 {main,detail,scene,poster,carousel} 内则回退 `"main"`。
- 枚举取值统一 `x.value if hasattr(x,"value") else x`。
- 日志：`from boss_aigc.logging_setup import get_logger`；`get_logger(__name__, layer="asset")`（db_archive）。
- 运行测试：`.venv/bin/pytest <path> -v`。
- 只改本计划列出的文件，不做计划外重构；不改前端、不改 schema.sql、不动内存 store 实现。

---

### Task 1: archive_accepted_task 持久化单元（核心）

**Files:**
- Create: `boss_aigc/asset/db_archive.py`
- Test: `boss_aigc/asset/_test_db_archive.py`

**Interfaces:**
- Consumes: `get_supabase`（supabase_client）、`get_conn`/`_now`（db）、`TaskIntent`/`TaskSummary`/`TaskResult`/`Artifact`（contracts）。
- Produces: `archive_accepted_task(intent: TaskIntent, summary: TaskSummary, result: TaskResult) -> int`（返回 ai_tasks 行 id）。

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/asset/_test_db_archive.py`

```python
import json
import pytest

import boss_aigc.db as db
from boss_aigc.contracts.enums import TaskType
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
    result = TaskResult(result_id="r1", task_id="t1", artifacts=artifacts, status=TaskType.IMAGE_GEN and __import__("boss_aigc.contracts.enums", fromlist=["TaskStatus"]).TaskStatus.DELIVERED)
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
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/asset/_test_db_archive.py -v`，预期 ImportError（模块不存在）。

- [ ] **Step 3: 实现** — 新建 `boss_aigc/asset/db_archive.py`

```python
"""asset.db_archive 已验收任务的 DB 持久化（打通平台资产库/任务记录）。

验收 ACCEPT 时把任务写入 ai_tasks、把每张生成图写入 assets，
使平台后台"资产/仪表盘"页可见且重启不丢。Supabase 优先，否则 SQLite。

遵「不擅自加兜底」：DB 失败不在此吞错，直接向上抛，由调用方（_handle_accept）按方案 B 处理。
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
    raw = meta.get("image_type")
    raw = _enum_value(raw)
    return raw if raw in _VALID_ASSET_TYPES else "main"


def _image_artifacts(result: TaskResult) -> list[Any]:
    return [a for a in (result.artifacts or []) if getattr(a, "kind", "") == "IMAGE"]


def archive_accepted_task(intent: TaskIntent, summary: TaskSummary, result: TaskResult) -> int:
    """把已验收任务写入 DB：ai_tasks 一行 + 每张 IMAGE 一行 assets。返回 ai_tasks 行 id。

    Supabase 已配走 Supabase，否则 SQLite。DB 失败向上抛（不吞错）。
    """
    task_type = _enum_value(intent.task_type)
    product = intent.product or ""
    params_json = json.dumps(dict(summary.params), ensure_ascii=False)
    cost = int(getattr(summary, "estimated_cost", 0) or 0)
    imgs = _image_artifacts(result)
    artifacts_json = json.dumps(
        [
            {
                "artifact_id": getattr(a, "artifact_id", ""),
                "kind": getattr(a, "kind", ""),
                "url_or_path": getattr(a, "url_or_path", None),
                "thumbnail_path": getattr(a, "thumbnail_path", None),
                "metadata": getattr(a, "metadata", {}) or {},
            }
            for a in (result.artifacts or [])
        ],
        ensure_ascii=False,
    )
    now = _now()

    sb = get_supabase()
    if sb:
        task_row = (
            sb.table("ai_tasks")
            .insert({
                "task_type": task_type, "product": product, "params": params_json,
                "status": "done", "artifacts": artifacts_json, "cost": cost,
                "created_at": now, "completed_at": now,
            })
            .execute()
        )
        task_id = int(task_row.data[0]["id"])
        for a in imgs:
            sb.table("assets").insert({
                "asset_type": _asset_type_of(a),
                "product_name": product,
                "url": getattr(a, "url_or_path", "") or "",
                "thumbnail_url": getattr(a, "thumbnail_path", None) or getattr(a, "url_or_path", "") or "",
                "task_id": task_id,
                "created_at": now,
            }).execute()
    else:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO ai_tasks (task_type, product, params, status, artifacts, cost, created_at, completed_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (task_type, product, params_json, "done", artifacts_json, cost, now, now),
            )
            task_id = int(cur.lastrowid)
            for a in imgs:
                conn.execute(
                    "INSERT INTO assets (asset_type, product_name, url, thumbnail_url, task_id, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        _asset_type_of(a), product,
                        getattr(a, "url_or_path", "") or "",
                        getattr(a, "thumbnail_path", None) or getattr(a, "url_or_path", "") or "",
                        task_id, now,
                    ),
                )
    logger.info("验收归档落库: task_id=%s, product=%s, 图片 %d 张", task_id, product, len(imgs))
    return task_id
```

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期 3 条 PASS。

---

### Task 2: 接线 _handle_accept + 方案 B 错误处理

**Files:**
- Modify: `boss_aigc/delivery/acceptance.py`（`_handle_accept`，约 143-199 行；顶部 import）
- Test: `boss_aigc/delivery/_test_accept_db.py`（新建）

**Interfaces:**
- Consumes: `archive_accepted_task`（Task 1）。
- Produces: `_handle_accept` 成功时额外落库并 `ACCEPTED`；DB 失败时保持 `DELIVERED` + 失败提示。

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/delivery/_test_accept_db.py`

```python
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
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/delivery/_test_accept_db.py -v`，预期两条都 FAIL（未落库 / DB 失败仍置 ACCEPTED）。

- [ ] **Step 3: 实现** — 修改 `boss_aigc/delivery/acceptance.py`：

3a. 顶部 import 区加：
```python
from boss_aigc.asset.db_archive import archive_accepted_task
```

3b. 在 `_handle_accept` 中，把结尾"置 ACCEPTED"那段（当前从 `context.status = TaskStatus.ACCEPTED` 到 `return TaskStatus.ACCEPTED, prompt`）替换为：先落库（方案 B 错误处理），成功才置 ACCEPTED：

```python
    # DB 双写：写 ai_tasks + assets，打通平台资产库（方案 B：失败不静默、不假装成功）
    if intent is not None and summary is not None and result is not None:
        try:
            archive_accepted_task(intent, summary, result)
        except Exception as e:
            logger.error("验收归档落库失败: %s", e, exc_info=True)
            context.status = TaskStatus.DELIVERED
            prompt = f"归档失败：{e}，请重试"
            context.extras[EXTRA_SPEAK_TEXT] = prompt
            return TaskStatus.DELIVERED, prompt

    context.status = TaskStatus.ACCEPTED
    # 清掉交付阶段标记，避免残留影响下一轮
    context.extras.pop(EXTRA_AWAITING_SECONDARY, None)
    prompt = "已归档到资产库"
    context.extras[EXTRA_SPEAK_TEXT] = prompt
    return TaskStatus.ACCEPTED, prompt
```

（`intent`/`summary`/`result` 变量在 `_handle_accept` 开头已计算，沿用。内存归档段保持原样不动。）

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期两条 PASS。

---

### Task 3: 回归 — 全量测试

- [ ] **Step 1: 新增测试**
Run: `.venv/bin/pytest boss_aigc/asset/_test_db_archive.py boss_aigc/delivery/_test_accept_db.py -v`
Expected: 5 条全 PASS。

- [ ] **Step 2: 交付层现有测试不回归**
Run: `.venv/bin/pytest boss_aigc/delivery -v`
Expected: 现有 `_test_delivery.py` 全 PASS（内存归档行为不变）。

- [ ] **Step 3: e2e（内存归档路径不变，仍应保持原状）**
Run: `.venv/bin/python -m boss_aigc._e2e_test`
Expected: 与改动前一致（既有 test_fuzzy_follow_up 失败是无关既存问题，不由本次引入）。

- [ ] **Step 4: 全套**
Run: `.venv/bin/pytest boss_aigc/ -v`
Expected: 除既有 5 个无关失败外全 PASS；新增 5 条 PASS。

---

## Self-Review

- **Spec 覆盖**：§4 archive_accepted_task→Task1；§5 接线+方案B→Task2；§7 测试→Task1/2/3；§6 幂等（插入即写，不去重）已在实现体现；§8 YAGNI（不改前端/schema/内存store）遵守。
- **占位符**：无 TBD/TODO；每步含完整代码与命令。
- **类型一致**：`archive_accepted_task(intent, summary, result) -> int` 跨 Task1 定义、Task2 调用一致；`handle_acceptance`/`AcceptanceAction`/`TaskStatus` 用现有签名。
- **注意点**：(1) `init_db()` 含种子数据，测试一律按唯一 `UT_PRODUCT` 过滤，不受种子干扰；(2) `get_conn()` 单事务内先插 ai_tasks 取 `lastrowid` 再插 assets，保证 task_id 关联；(3) 方案 B 在落库异常时保持 DELIVERED、返回"归档失败"提示，不吞错、不假装成功。
