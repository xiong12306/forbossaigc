# 助手验收归档落库、打通平台资产库 — 设计方案

- 日期：2026-07-27
- 状态：已评审通过（错误处理选 B），待写实现计划
- 范围：验收（ACCEPT）时把任务与产出图持久化到 DB（`ai_tasks` + `assets`），使平台"资产/仪表盘"页可见、且重启不丢

## 1. 背景与目标

当前语音助手验收（老板点"可以了，验收"→ 发送"可以了"）走 `delivery/acceptance.py::_handle_accept`，只归档到**进程内存** `asset_store`（`TaskHistoryStore`/`ProductAssetStore`，源码注释"本阶段为内存存储"）。问题：

1. 重启后端即丢。
2. 与平台后台"资产/仪表盘"页读取的 DB（SQLite `db.py` / 可选 Supabase）**完全没打通**——助手归档的图不出现在平台素材库。

目标：验收时在保留内存归档的基础上，**新增 DB 双写**，把任务写 `ai_tasks`、把每张生成图写 `assets`，让平台页可见且持久。

## 2. 现有 DB 结构（事实依据）

访问模式（`api/*.py` 统一）：先 `get_supabase()`；返回 None 则 `get_conn()`（SQLite，`boss_aigc/db.py`，`get_conn()` 上下文管理器自动 commit，`_now()` 返回 ISO 时间串）。目前**无现成的"插入 asset / 插入 task"辅助函数**（`db.py` 里只有 `_seed_if_empty` 的种子 INSERT）。

- `ai_tasks`：`id`、`task_type`、`product`、`params`(JSON 文本)、`status`(pending/executing/done/failed)、`artifacts`(JSON 文本)、`cost`、`created_at`、`completed_at`。仪表盘 recent_tasks 读它。
- `assets`：`id`、`asset_type`(main/detail/scene/poster/carousel)、`product_name`、`url`、`thumbnail_url`、`task_id`、`created_at`。`GET /api/assets`（平台"资产"页）读它。

## 3. 架构定位

只在验收 ACCEPT 分支加一步"写 DB"。内存 `asset_store` 归档保留不动（助手侧回查可能依赖）；新增 DB 双写供平台页读取。

```
点「可以了，验收」→ /api/chat "可以了" → delivery 分支 B → _handle_accept
    ① 内存归档（现有，保留不动）
    ② archive_accepted_task(intent, summary, result)  ← 新增 DB 双写
    ③ status=ACCEPTED（②失败则不置，见 §5）
```

## 4. 新增持久化单元

新建 `boss_aigc/asset/db_archive.py`，单一职责、可独立测试：

```python
def archive_accepted_task(intent: TaskIntent, summary: TaskSummary, result: TaskResult) -> int:
    """把已验收任务写入 DB：ai_tasks 一行 + 每张 IMAGE 一行 assets。返回 ai_tasks 行 id。
    Supabase 已配则走 Supabase，否则 SQLite。DB 失败向上抛出（由调用方按 §5 处理）。
    """
```

行为：
- **ai_tasks 一行**：
  - `task_type` = `intent.task_type` 的值（如 `image_gen`）
  - `product` = `intent.product or ""`
  - `params` = `json.dumps(summary.params, ensure_ascii=False)`
  - `status` = `"done"`
  - `artifacts` = `json.dumps([{artifact_id, kind, url_or_path, thumbnail_path, metadata}...], ensure_ascii=False)`
  - `cost` = `getattr(summary, "estimated_cost", 0) or 0`
  - `created_at` / `completed_at` = `_now()`
  - 取插入行 id：SQLite 用 `cur.lastrowid`；Supabase 用 insert 返回 `data[0]["id"]`。
- **assets N 行**：遍历 `result.artifacts`，仅 `kind == "IMAGE"` 的：
  - `asset_type` = `metadata.get("image_type")`，非法/缺失回退 `"main"`
  - `product_name` = `intent.product or ""`
  - `url` = `artifact.url_or_path`
  - `thumbnail_url` = `artifact.thumbnail_path or artifact.url_or_path or ""`
  - `task_id` = 上面 ai_tasks 的 id
  - `created_at` = `_now()`
- 双路：`sb = get_supabase()`；`if sb:` 用 `sb.table(...).insert(...).execute()`；`else:` 用 `with get_conn() as conn: conn.execute("INSERT ...", (...))`。

## 5. 接线与错误处理（方案 B）

`_handle_accept`（`delivery/acceptance.py`）在原有内存归档之后、置 `ACCEPTED` 之前，调用 `archive_accepted_task`：

- 成功 → 继续原逻辑：`status=ACCEPTED`，speak_text = "已归档到资产库"。
- **失败（方案 B，遵"不擅自加兜底"）**：捕获异常 → **不置 ACCEPTED、保持 `status=DELIVERED`**，speak_text = `f"归档失败：{原因}，请重试"`，`logger.error(...)` 记全异常。老板明确知道没归档成功、可重试，错误可定位；既不吞错也不假装成功。

内存归档段现有的 try/except 保持原样，不在本次范围。

## 6. 幂等

按"每次 ACCEPT 插入"实现。ACCEPT 为终态、正常只发生一次；重复验收会多插记录，可接受，不做去重（YAGNI）。

## 7. 测试

- 新增 `boss_aigc/asset/_test_db_archive.py`：
  1. **成功写入（SQLite）**：monkeypatch `boss_aigc.db.DB_PATH` 指向 tmp 文件 + 调 `init_db()` 建表 + monkeypatch `get_supabase` 返回 None → 造 intent/summary/result（含 2 张 IMAGE artifact）→ 调 `archive_accepted_task` → 断言 `ai_tasks` 1 行（status=done、product 正确、artifacts JSON 可解析）、`assets` 2 行（asset_type/url/task_id 关联正确）。
  2. **非 IMAGE 不写 assets**：result 含 1 IMAGE + 1 非 IMAGE → assets 只 1 行。
  3. **返回 task_id** 与 assets.task_id 一致。
- `_handle_accept` 集成（在 `delivery/_test_acceptance.py`，若无则新建）：
  4. **ACCEPT 成功**：临时 DB → 走 `_handle_accept(ACCEPT)` → status=ACCEPTED 且 DB 有记录。
  5. **DB 失败走方案 B**：monkeypatch `archive_accepted_task` 抛异常 → 断言 status 保持 DELIVERED、prompt 含"归档失败"、未误置 ACCEPTED。
- 现有 e2e/各层单测保持绿（内存归档行为不变；注意既有 5 个无关失败与本次无关）。

## 8. 明确不做（YAGNI）

- 不改前端（"资产/仪表盘"页已读这两张表，归档后自动出现）。
- 不动 MODIFY/REGENERATE/OTHER 分支、不动内存 store 实现。
- 不做资产去重、不更新已存在商品资产、不回填 `products.image_url`。
- 不改 Supabase `schema.sql`（表已存在）。

## 9. 验收标准

1. 配 SQLite（默认）下，走完"下任务→确认→出图→可以了"，`ai_tasks` 新增 1 行 status=done、`assets` 新增 N 行（N=出图数），`GET /api/assets` 能查到。
2. DB 写失败时状态保持 DELIVERED 且提示"归档失败…请重试"，不误报已归档。
3. 新增单测 + 现有测试（除既有 5 个无关失败外）全绿。
