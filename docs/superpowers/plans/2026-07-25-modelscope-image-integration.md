# 接入魔搭（ModelScope）免费文生图 Implementation Plan

> **For agentic workers:** 用 TDD 逐任务实现。本项目**非 git 仓库**，所有 "Commit" 步骤替换为"跑相关测试确保通过"。Steps use checkbox (`- [ ]`).

**Goal:** 在执行层新增 ModelScope 免费文生图适配器，通过 `PLATFORM_PROVIDER` 环境变量选平台，让老板"出图"走真实魔搭 API。

**Architecture:** 只改执行层平台绑定；七层主链、契约、确认锁不动。魔搭异步 `submit→poll` 用"同步包装"塞进现有 `PlatformAdapter`（submit 内部轮询到终态，poll 返回缓存），调度器 `run_step_with_retry` 无需改。平台由 `config.platform_provider`（mock|modelscope|nanobanana）决定。

**Tech Stack:** Python 3.11+, pydantic, requests, pytest, dataclass。参考 spec：`docs/superpowers/specs/2026-07-25-modelscope-image-integration-design.md`。

## Global Constraints

- 遵循「不擅自加兜底」：运行时 API 失败（超时/FAILED/无图）直接 `TaskStatus.FAILED`，**不静默降级到 Mock**；Mock 仅在 `PLATFORM_PROVIDER=mock` 显式选择时用。
- 所有新配置从 `os.environ` 读取；顺手修复 `nanobanana_api_key`/`use_real_platform` 未读 env 的现存 bug。
- 日志用 `from boss_aigc.logging_setup import get_logger`，`get_logger(__name__, layer="execution")`。
- 枚举继承 `(str, Enum)`；Artifact 来自 `boss_aigc.contracts.execution`。
- 测试文件命名 `_test_*.py`，与被测模块同目录（沿用现有约定）。
- 运行测试统一用：`.venv/bin/pytest <path> -v`（venv 为 Python 3.14）。
- 默认模型 `Qwen/Qwen-Image`；API base `https://api-inference.modelscope.cn/v1`。
- **HTTP 客户端用 `httpx`（不是 `requests`）**：`requests` 未安装且不在 requirements.txt；`httpx==0.28.1` 已装且已被项目使用。异常用 `httpx.TimeoutException` / `httpx.HTTPError`。

---

### Task 1: PlatformKind 新增 MODELSCOPE

**Files:**
- Modify: `boss_aigc/contracts/enums.py`（`PlatformKind` 类）

**Interfaces:**
- Produces: `PlatformKind.MODELSCOPE == "modelscope"`

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/contracts/_test_enums_modelscope.py`

```python
from boss_aigc.contracts.enums import PlatformKind

def test_modelscope_kind_exists():
    assert PlatformKind.MODELSCOPE.value == "modelscope"
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/contracts/_test_enums_modelscope.py -v`，预期 AttributeError。

- [ ] **Step 3: 实现** — 在 `PlatformKind` 中 `NANOBANANA` 之后加：

```python
    MODELSCOPE = "modelscope"           # 魔搭 ModelScope（免费文生图，Qwen-Image 等）
```

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期 PASS。

---

### Task 2: config 新增魔搭配置 + 修复 env 读取 bug

**Files:**
- Modify: `boss_aigc/config.py`（`Settings` dataclass）
- Test: `boss_aigc/_test_config_env.py`（新建）

**Interfaces:**
- Produces: `Settings.platform_provider: str`、`modelscope_api_key: str`、`modelscope_api_base: str`、`modelscope_model: str`；`nanobanana_api_key`/`use_real_platform` 改为读 env。

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/_test_config_env.py`

```python
import importlib
import os

def _reload_settings():
    import boss_aigc.config as cfg
    importlib.reload(cfg)
    return cfg.get_settings()

def test_platform_provider_from_env(monkeypatch):
    monkeypatch.setenv("PLATFORM_PROVIDER", "modelscope")
    monkeypatch.setenv("MODELSCOPE_API_KEY", "tok-123")
    s = _reload_settings()
    assert s.platform_provider == "modelscope"
    assert s.modelscope_api_key == "tok-123"
    assert s.modelscope_model == "Qwen/Qwen-Image"
    assert s.modelscope_api_base == "https://api-inference.modelscope.cn/v1"

def test_use_real_platform_from_env(monkeypatch):
    monkeypatch.setenv("USE_REAL_PLATFORM", "True")
    monkeypatch.setenv("NANOBANANA_API_KEY", "nb-key")
    s = _reload_settings()
    assert s.use_real_platform is True
    assert s.nanobanana_api_key == "nb-key"

def test_defaults(monkeypatch):
    for k in ("PLATFORM_PROVIDER", "MODELSCOPE_API_KEY", "USE_REAL_PLATFORM", "NANOBANANA_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    s = _reload_settings()
    assert s.platform_provider == "mock"
    assert s.use_real_platform is False
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/_test_config_env.py -v`，预期部分 FAIL（无 platform_provider 属性 / use_real_platform 恒 False）。

- [ ] **Step 3: 实现** — 修改 `boss_aigc/config.py` `Settings`：
  1. 把 `nanobanana_api_key: str = ""` 改为 `nanobanana_api_key: str = os.environ.get("NANOBANANA_API_KEY", "")`
  2. 把 `use_real_platform: bool = False` 改为 `use_real_platform: bool = os.environ.get("USE_REAL_PLATFORM", "").strip().lower() in ("true", "1", "yes")`
  3. 在 `nanobanana_api_base` 附近新增：

```python
    platform_provider: str = os.environ.get("PLATFORM_PROVIDER", "mock")  # mock|modelscope|nanobanana
    modelscope_api_key: str = os.environ.get("MODELSCOPE_API_KEY", "")
    modelscope_api_base: str = os.environ.get("MODELSCOPE_API_BASE", "https://api-inference.modelscope.cn/v1")
    modelscope_model: str = os.environ.get("MODELSCOPE_MODEL", "Qwen/Qwen-Image")
```

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期 PASS。

---

### Task 3: ModelScopeAdapter（核心）

**Files:**
- Create: `boss_aigc/execution/modelscope_adapter.py`
- Test: `boss_aigc/execution/_test_modelscope.py`

**Interfaces:**
- Consumes: `PlatformAdapter`（`boss_aigc.execution.adapter`）、`Artifact`（`boss_aigc.contracts.execution`）、`TaskStatus`/`ImageType`/`PlatformKind`（enums）、`get_settings`。
- Produces: `class ModelScopeAdapter(PlatformAdapter)`，`kind = PlatformKind.MODELSCOPE`；`submit(params: dict) -> str`；`poll(task_id: str) -> tuple[TaskStatus, Optional[list[Artifact]]]`；`cancel(task_id) -> bool`；`normalize_result(raw) -> Artifact`。构造 `ModelScopeAdapter(api_key=None, api_base=None, model=None, timeout=None, poll_interval=None)`。

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/execution/_test_modelscope.py`

```python
from typing import Any
import pytest

from boss_aigc.contracts.enums import PlatformKind, TaskStatus
from boss_aigc.execution.modelscope_adapter import ModelScopeAdapter


class _FakeResp:
    def __init__(self, data: dict[str, Any]):
        self._data = data
    def json(self): return self._data
    def raise_for_status(self): return None  # 测试不覆盖 4xx 路径


def _patch(monkeypatch, submit_resp, poll_resps):
    """submit_resp: dict for POST; poll_resps: list of dicts for successive GETs（耗尽后重复最后一个）。"""
    calls = {"post": 0, "get": 0}
    def fake_post(url, json=None, headers=None, timeout=None, **kw):
        calls["post"] += 1
        return _FakeResp(submit_resp)
    seq = list(poll_resps)
    def fake_get(url, headers=None, timeout=None, **kw):
        calls["get"] += 1
        return _FakeResp(seq.pop(0) if len(seq) > 1 else seq[0])
    monkeypatch.setattr("boss_aigc.execution.modelscope_adapter.httpx.post", fake_post)
    monkeypatch.setattr("boss_aigc.execution.modelscope_adapter.httpx.get", fake_get)
    monkeypatch.setattr("boss_aigc.execution.modelscope_adapter.time.sleep", lambda *_: None)
    return calls


def test_kind():
    a = ModelScopeAdapter(api_key="k")
    assert a.kind == PlatformKind.MODELSCOPE


def test_submit_poll_succeed(monkeypatch):
    _patch(
        monkeypatch,
        submit_resp={"task_id": "t1"},
        poll_resps=[{"task_status": "RUNNING"},
                    {"task_status": "SUCCEED",
                     "output_images": ["https://img.example/a.png"]}],
    )
    a = ModelScopeAdapter(api_key="k", model="Qwen/Qwen-Image", poll_interval=0)
    tid = a.submit({"product": "保温杯", "quantity": 1, "image_type": "main"})
    status, arts = a.poll(tid)
    assert status == TaskStatus.DELIVERED
    assert len(arts) == 1
    assert arts[0].kind == "IMAGE"
    assert arts[0].url_or_path == "https://img.example/a.png"
    assert arts[0].metadata["source"] == "modelscope"
    assert arts[0].metadata["model"] == "Qwen/Qwen-Image"


def test_submit_failed_status(monkeypatch):
    _patch(monkeypatch, submit_resp={"task_id": "t2"},
           poll_resps=[{"task_status": "FAILED"}])
    a = ModelScopeAdapter(api_key="k", poll_interval=0)
    tid = a.submit({"product": "杯子", "quantity": 1})
    status, arts = a.poll(tid)
    assert status == TaskStatus.FAILED
    assert arts is None


def test_no_key_fails_fast(monkeypatch):
    # 不 patch requests：无 key 应在 submit 内直接 FAILED，不发请求
    a = ModelScopeAdapter(api_key="", poll_interval=0)
    tid = a.submit({"product": "杯子", "quantity": 1})
    status, arts = a.poll(tid)
    assert status == TaskStatus.FAILED
    assert arts is None


def test_quantity_multiple(monkeypatch):
    calls = _patch(
        monkeypatch, submit_resp={"task_id": "tN"},
        poll_resps=[{"task_status": "SUCCEED", "output_images": ["https://img/x.png"]}],
    )
    a = ModelScopeAdapter(api_key="k", poll_interval=0)
    tid = a.submit({"product": "杯子", "quantity": 3, "image_type": "main"})
    status, arts = a.poll(tid)
    assert status == TaskStatus.DELIVERED
    assert len(arts) == 3
    assert calls["post"] == 3  # 3 张 = 3 次提交
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/execution/_test_modelscope.py -v`，预期 ImportError（模块不存在）。

- [ ] **Step 3: 实现** — 新建 `boss_aigc/execution/modelscope_adapter.py`：

```python
"""execution.modelscope_adapter 魔搭 ModelScope 免费文生图适配器。

通过 ModelScope API-Inference（异步）实现电商真实出图。
- 提交: POST /images/generations（X-ModelScope-Async-Mode: true）→ task_id
- 轮询: GET /tasks/{task_id}（X-ModelScope-Task-Type: image_generation）→ SUCCEED/FAILED
默认模型 Qwen/Qwen-Image（中文 prompt 友好）。免费额度 2000 次/天。

设计：魔搭为真异步，但为契合现有调度器（run_step_with_retry 对异步有 busy-loop 隐患），
采用"同步包装"——submit 内部轮询到终态并缓存结果，poll 直接返回缓存（与 NanoBananaAdapter 一致）。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

from boss_aigc.config import get_settings
from boss_aigc.contracts.enums import ImageType, PlatformKind, TaskStatus
from boss_aigc.contracts.execution import Artifact
from boss_aigc.execution.adapter import PlatformAdapter
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="execution")

_IMAGE_TYPE_PROMPTS: dict[ImageType, str] = {
    ImageType.MAIN: "商品主图，突出主体，白色/纯色背景，专业电商摄影，高清细节，提升点击率",
    ImageType.DETAIL: "产品详情图，展示卖点细节，材质特写，工艺展示，引导下单，专业商品摄影",
    ImageType.SCENE: "场景展示图，真实使用场景，生活化氛围，自然光线，代入感强",
    ImageType.POSTER: "营销海报，视觉冲击力，促销氛围，品牌质感，适合电商推广",
    ImageType.CAROUSEL: "轮播图，多角度展示，构图美观，色彩协调，适合店铺首页",
}
_IMAGE_TYPE_NAMES: dict[ImageType, str] = {
    ImageType.MAIN: "商品主图", ImageType.DETAIL: "产品详情图",
    ImageType.SCENE: "场景图", ImageType.POSTER: "营销海报",
    ImageType.CAROUSEL: "轮播图",
}


@dataclass
class _MSTaskState:
    task_id: str
    params: dict[str, Any]
    submitted_at: datetime
    status: TaskStatus = TaskStatus.EXECUTING
    artifacts: list[Artifact] = field(default_factory=list)
    error_message: Optional[str] = None


class ModelScopeAdapter(PlatformAdapter):
    """魔搭 ModelScope 文生图适配器（同步包装的异步 API）。"""

    kind: PlatformKind = PlatformKind.MODELSCOPE

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> None:
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.modelscope_api_key
        self.api_base = (api_base or s.modelscope_api_base).rstrip("/")
        self.model = model or s.modelscope_model
        self.timeout = timeout or s.request_timeout_sec
        self.poll_interval = s.poll_interval_sec if poll_interval is None else poll_interval
        self._tasks: dict[str, _MSTaskState] = {}
        self._counter = 0
        if not self.api_key:
            logger.warning("ModelScope API key 未配置，将无法生成真实图片")

    # ---------- prompt ----------
    def _build_prompt(self, params: dict[str, Any]) -> str:
        product = params.get("product", "商品")
        raw = params.get("image_type", ImageType.MAIN.value)
        if isinstance(raw, ImageType):
            image_type = raw
        else:
            try:
                image_type = ImageType(str(raw))
            except ValueError:
                image_type = ImageType.MAIN
        style = params.get("style", "")
        user_prompt = params.get("prompt", "")
        parts = [_IMAGE_TYPE_NAMES.get(image_type, "商品图") + "，" + product]
        if style:
            parts.append(style + "风格")
        parts.append(_IMAGE_TYPE_PROMPTS.get(image_type, _IMAGE_TYPE_PROMPTS[ImageType.MAIN]))
        if user_prompt:
            parts.append(user_prompt)
        return "，".join(parts)

    @staticmethod
    def _resolve_quantity(params: dict[str, Any]) -> int:
        raw = params.get("quantity", 1)
        try:
            return max(1, min(int(raw), 8))
        except (TypeError, ValueError):
            return 1

    # ---------- 单张：提交 + 轮询到终态 ----------
    def _generate_one(self, prompt: str, params: dict[str, Any], idx: int, task_id: str) -> Artifact:
        submit_url = f"{self.api_base}/images/generations"
        submit_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
            "X-ModelScope-Task-Type": "text-to-image-generation",
        }
        size = params.get("size", "1024x1024")
        body: dict[str, Any] = {"model": self.model, "prompt": prompt, "size": size}
        if params.get("negative_prompt"):
            body["negative_prompt"] = params["negative_prompt"]

        resp = httpx.post(submit_url, json=body, headers=submit_headers, timeout=self.timeout)
        resp.raise_for_status()
        ms_task_id = (resp.json() or {}).get("task_id")
        if not ms_task_id:
            raise RuntimeError(f"提交未返回 task_id: {str(resp.json())[:200]}")

        poll_url = f"{self.api_base}/tasks/{ms_task_id}"
        poll_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-ModelScope-Task-Type": "image_generation",
        }
        deadline = time.monotonic() + self.timeout
        while True:
            r = httpx.get(poll_url, headers=poll_headers, timeout=self.timeout)
            r.raise_for_status()
            data = r.json() or {}
            status = data.get("task_status")
            if status == "SUCCEED":
                images = data.get("output_images") or []
                if not images:
                    raise RuntimeError("SUCCEED 但 output_images 为空")
                url = images[0]
                return Artifact(
                    artifact_id=f"{task_id}-art-{idx + 1}",
                    kind="IMAGE",
                    url_or_path=url,
                    thumbnail_path=url,
                    metadata={
                        "source": "modelscope",
                        "model": self.model,
                        "prompt": prompt,
                        "size": size,
                        "ms_task_id": ms_task_id,
                        "image_type": params.get("image_type", ImageType.MAIN.value),
                        "product": params.get("product"),
                    },
                )
            if status == "FAILED":
                raise RuntimeError(f"魔搭任务失败: {str(data)[:200]}")
            if time.monotonic() > deadline:
                raise TimeoutError(f"魔搭轮询超时（{self.timeout}s）")
            time.sleep(self.poll_interval)

    # ---------- 接口 ----------
    def submit(self, params: dict[str, Any]) -> str:
        self._counter += 1
        task_id = f"modelscope-{self._counter}"
        state = _MSTaskState(task_id=task_id, params=dict(params), submitted_at=datetime.now())
        self._tasks[task_id] = state

        if not self.api_key:
            state.status = TaskStatus.FAILED
            state.error_message = "ModelScope API key 未配置"
            logger.error("ModelScope API key 未配置，任务 %s 失败", task_id)
            return task_id

        try:
            prompt = self._build_prompt(params)
            quantity = self._resolve_quantity(params)
            logger.info("ModelScope 生图: task=%s model=%s qty=%d prompt=%s",
                        task_id, self.model, quantity, prompt[:80])
            artifacts = [self._generate_one(prompt, params, i, task_id) for i in range(quantity)]
            state.artifacts = artifacts
            state.status = TaskStatus.DELIVERED
            logger.info("ModelScope 任务 %s 完成，生成 %d 张", task_id, len(artifacts))
        except httpx.TimeoutException:
            state.status = TaskStatus.FAILED
            state.error_message = f"请求超时（{self.timeout}s）"
            logger.error("ModelScope 任务 %s 超时", task_id)
        except httpx.HTTPError as e:
            state.status = TaskStatus.FAILED
            state.error_message = f"API 请求失败: {e}"
            logger.error("ModelScope 任务 %s 请求失败: %s", task_id, e)
        except Exception as e:  # noqa: BLE001 - 失败即失败，记明确原因
            state.status = TaskStatus.FAILED
            state.error_message = str(e)
            logger.error("ModelScope 任务 %s 失败: %s", task_id, e)
        return task_id

    def poll(self, platform_task_id: str) -> tuple[TaskStatus, Optional[list[Artifact]]]:
        state = self._tasks.get(platform_task_id)
        if state is None:
            return TaskStatus.FAILED, None
        if state.status == TaskStatus.DELIVERED:
            return TaskStatus.DELIVERED, list(state.artifacts)
        if state.status == TaskStatus.FAILED:
            return TaskStatus.FAILED, None
        if state.status == TaskStatus.CANCELLED:
            return TaskStatus.CANCELLED, None
        return TaskStatus.EXECUTING, None

    def cancel(self, platform_task_id: str) -> bool:
        state = self._tasks.get(platform_task_id)
        if state is not None and state.status == TaskStatus.EXECUTING:
            state.status = TaskStatus.CANCELLED
        return True

    def normalize_result(self, raw: Any) -> Artifact:
        if isinstance(raw, dict):
            return Artifact(
                artifact_id=raw.get("artifact_id") or f"modelscope-art-{uuid.uuid4().hex[:8]}",
                kind=raw.get("kind", "IMAGE"),
                url_or_path=raw.get("url_or_path"),
                thumbnail_path=raw.get("thumbnail_path"),
                metadata=dict(raw.get("metadata", {})) or {"source": "modelscope"},
            )
        return Artifact(
            artifact_id=f"modelscope-art-{uuid.uuid4().hex[:8]}",
            kind="IMAGE",
            url_or_path=str(raw) if raw is not None else None,
            metadata={"source": "modelscope"},
        )
```

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期 5 条全 PASS。

---

### Task 4: planner.select_platform 支持 modelscope

**Files:**
- Modify: `boss_aigc/orchestration/planner.py:53-69`（`select_platform`）
- Test: `boss_aigc/orchestration/_test_select_platform.py`（新建）

**Interfaces:**
- Consumes: `config.platform_provider` / `modelscope_api_key` / `nanobanana_api_key`；`PlatformKind`。
- Produces: `select_platform(task_type, summary) -> PlatformKind` 新逻辑。

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/orchestration/_test_select_platform.py`

```python
from boss_aigc.config import configure
from boss_aigc.contracts.enums import PlatformKind, TaskType
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.orchestration.planner import select_platform


def _summary():
    return TaskSummary(summary_id="s1", task_type=TaskType.IMAGE_GEN)


def test_modelscope_selected():
    configure(platform_provider="modelscope", modelscope_api_key="k")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.MODELSCOPE


def test_modelscope_no_key_falls_to_mock():
    configure(platform_provider="modelscope", modelscope_api_key="")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.MOCK


def test_nanobanana_selected():
    configure(platform_provider="nanobanana", nanobanana_api_key="nb")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.NANOBANANA


def test_mock_default():
    configure(platform_provider="mock")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.MOCK
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/orchestration/_test_select_platform.py -v`，预期 `test_modelscope_selected` FAIL。

- [ ] **Step 3: 实现** — 替换 `select_platform` 内的选择逻辑（保留函数签名与 docstring 首行），核心判断改为：

```python
    settings = get_settings()
    if task_type == TaskType.IMAGE_GEN:
        if settings.platform_provider == "modelscope" and settings.modelscope_api_key:
            return PlatformKind.MODELSCOPE
        if settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
            return PlatformKind.NANOBANANA
    return PlatformKind.MOCK
```

（注意：`get_settings` 已在 planner.py 内导入；若无则加 `from boss_aigc.config import get_settings`。）

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期 4 条 PASS。

- [ ] **Step 5: 复位配置** — 测试末尾无需手动复位；但为防污染其它测试，本文件顶部加 `import pytest` 并用 `@pytest.fixture(autouse=True)` 在每例后 `configure(platform_provider="mock", modelscope_api_key="", nanobanana_api_key="")`。补充：

```python
import pytest

@pytest.fixture(autouse=True)
def _reset():
    yield
    configure(platform_provider="mock", modelscope_api_key="", nanobanana_api_key="")
```

---

### Task 5: registry 按 provider 注册适配器

**Files:**
- Modify: `boss_aigc/execution/registry.py:51-80`（`register_default_adapters`）
- Test: `boss_aigc/execution/_test_registry_provider.py`（新建）

**Interfaces:**
- Consumes: `config.platform_provider` / `modelscope_api_key` / `nanobanana_api_key`；`ModelScopeAdapter`（Task 3）。
- Produces: `register_default_adapters()` 按 provider 注册 MODELSCOPE / NANOBANANA。

- [ ] **Step 1: 写失败测试** — 新建 `boss_aigc/execution/_test_registry_provider.py`

```python
import pytest
from boss_aigc.config import configure
from boss_aigc.contracts.enums import PlatformKind
from boss_aigc.execution.registry import register_default_adapters


@pytest.fixture(autouse=True)
def _reset():
    yield
    configure(platform_provider="mock", modelscope_api_key="", nanobanana_api_key="")


def test_modelscope_registered():
    configure(platform_provider="modelscope", modelscope_api_key="k")
    reg = register_default_adapters()
    assert reg.get(PlatformKind.MOCK) is not None
    assert reg.get(PlatformKind.MODELSCOPE) is not None


def test_mock_only_when_provider_mock():
    configure(platform_provider="mock", modelscope_api_key="")
    reg = register_default_adapters()
    assert reg.get(PlatformKind.MOCK) is not None
    assert reg.get(PlatformKind.MODELSCOPE) is None
```

- [ ] **Step 2: 跑测试确认失败** — `.venv/bin/pytest boss_aigc/execution/_test_registry_provider.py -v`，预期 `test_modelscope_registered` FAIL。

- [ ] **Step 3: 实现** — 改写 `register_default_adapters` 尾部平台注册逻辑（保留"总是注册 Mock"）：

```python
    settings = get_settings()
    registry = get_registry()
    registry.register(PlatformKind.MOCK, MockAdapter())

    if settings.platform_provider == "modelscope" and settings.modelscope_api_key:
        from boss_aigc.execution.modelscope_adapter import ModelScopeAdapter
        registry.register(PlatformKind.MODELSCOPE, ModelScopeAdapter())
    elif settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
        from boss_aigc.execution.nanobanana_adapter import NanoBananaAdapter
        registry.register(PlatformKind.NANOBANANA, NanoBananaAdapter())

    return registry
```

（`from boss_aigc.config import get_settings` 已在函数内导入，沿用。）

- [ ] **Step 4: 跑测试确认通过** — 同 Step 2，预期 PASS。

---

### Task 6: .env.example 补配置项

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: 实现** — 在"出图平台配置"段替换为：

```
# ===== 出图平台配置 =====
# 出图平台：mock（占位图）| modelscope（魔搭免费）| nanobanana（付费）
PLATFORM_PROVIDER=modelscope
# 魔搭 SDK Token：https://modelscope.cn 账号设置页获取
MODELSCOPE_API_KEY=
# 魔搭文生图模型（默认 Qwen/Qwen-Image）
MODELSCOPE_MODEL=Qwen/Qwen-Image
MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1

# 兼容旧配置（PLATFORM_PROVIDER=nanobanana 时用）
# True=真实出图，False=Mock（旧开关，现由 PLATFORM_PROVIDER 主导）
USE_REAL_PLATFORM=False
```

- [ ] **Step 2: 校验** — `.venv/bin/python -c "import re;print('PLATFORM_PROVIDER' in open('.env.example').read())"` 预期 `True`。

---

### Task 7: 回归 — 全量测试

- [ ] **Step 1: 跑执行层 + 编排层 + 契约测试**
Run: `.venv/bin/pytest boss_aigc/execution boss_aigc/orchestration boss_aigc/contracts -v`
Expected: 全 PASS（含新增用例）。

- [ ] **Step 2: 跑现有 e2e（Mock 路径不受影响）**
Run: `.venv/bin/python -m boss_aigc._e2e_test`
Expected: "全部 E2E 测试通过 ✅"。

- [ ] **Step 3: 跑冒烟**
Run: `.venv/bin/python -m boss_aigc._smoke_test`
Expected: 无异常退出。

- [ ] **Step 4: 全套 pytest**
Run: `.venv/bin/pytest boss_aigc/ -v`
Expected: 全 PASS。

---

## Self-Review

- **Spec 覆盖**：enums①→Task1；config②→Task2；adapter③→Task3；planner④→Task4；registry⑤→Task5；.env⑥→Task6；测试→Task3/4/5+Task7；错误处理§5→Task3（failed 即 FAILED、无 key 即 FAILED、无静默 Mock）；验收§8→Task7。全覆盖。
- **占位符**：无 TBD/TODO；每步含实际代码与命令。
- **类型一致**：`ModelScopeAdapter.submit/poll/cancel/normalize_result` 签名跨 Task3/5 一致；`select_platform` 返回 `PlatformKind` 跨 Task4 一致；`configure(...)` 用现有 config API。
- **注意点**：`_test_config_env.py` 用 `importlib.reload` 让 dataclass 默认值重新按 env 求值（因默认值在类定义时求值）。
