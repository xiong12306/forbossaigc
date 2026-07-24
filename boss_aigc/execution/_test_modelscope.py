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


def test_unknown_status_fails_fast(monkeypatch):
    # H1：未知 task_status 应立即 FAILED，而非空转到超时掩盖真因
    _patch(monkeypatch, submit_resp={"task_id": "tU"},
           poll_resps=[{"task_status": "QUOTA_EXCEEDED"}])
    a = ModelScopeAdapter(api_key="k", poll_interval=0)
    tid = a.submit({"product": "杯子", "quantity": 1})
    status, arts = a.poll(tid)
    assert status == TaskStatus.FAILED
    assert arts is None


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
