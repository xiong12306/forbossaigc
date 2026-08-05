"""execution._test_mock Mock 适配器单元测试。

验证内容：
1. 注册 MockAdapter → submit 出图任务（quantity=3）→ poll 直到完成 → 断言 3 个 IMAGE artifact
2. fail_mode="fail"：poll 立刻返回 FAILED
3. fail_mode="fail_then_succeed"：前 N 次失败后最终成功
4. 顺带覆盖 cancel / normalize_result / 其他任务类型 产出

运行：.venv/bin/python -m boss_aigc.execution._test_mock
"""

from __future__ import annotations

from boss_aigc.contracts.enums import PlatformKind, TaskStatus, TaskType
from boss_aigc.execution import (
    MockAdapter,
    get_registry,
    register_default_adapters,
)


def _poll_until_terminal(
    adapter: MockAdapter,
    task_id: str,
    max_polls: int = 20,
) -> tuple[TaskStatus, list]:
    """轮询直到状态进入终态（DELIVERED/FAILED/CANCELLED）或达到 max_polls。"""
    status = TaskStatus.EXECUTING
    artifacts: list = []
    for _ in range(max_polls):
        status, arts = adapter.poll(task_id)
        if status in (TaskStatus.DELIVERED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            artifacts = arts or []
            break
    return status, artifacts


def test_register_and_complete_image_gen_quantity_3() -> None:
    """验收点 1：注册 Mock → submit quantity=3 → poll 完成 → 3 个 IMAGE artifact。"""
    # 通过 register_default_adapters 注册默认适配器，再覆盖为本测试用实例
    register_default_adapters()
    registry = get_registry()
    adapter = MockAdapter()  # 默认 fail_mode="none", polls_to_complete=2
    registry.register(PlatformKind.MOCK, adapter)
    assert registry.get(PlatformKind.MOCK) is adapter

    # 提交出图任务（quantity=3）
    task_id = adapter.submit({
        "task_type": TaskType.IMAGE_GEN,
        "quantity": 3,
        "product": "保温杯",
        "style": "轻奢暖色调",
    })
    assert task_id.startswith("mock-task-"), f"task_id 应以 mock-task- 开头，实际 {task_id}"

    # 首次 poll 应为 EXECUTING（polls_to_complete=2，未达到完成次数）
    status, arts = adapter.poll(task_id)
    assert status == TaskStatus.EXECUTING, f"首次 poll 应为 EXECUTING，实际 {status}"
    assert arts is None, f"EXECUTING 阶段不应有产出，实际 {arts}"
    # 进度应在 0~99 之间
    progress = adapter.get_progress(task_id)
    assert 0 <= progress < 100, f"进行中进度应在 [0,100)，实际 {progress}"

    # 第 2 次 poll：达到 polls_to_complete=2，应返回 DELIVERED + 3 个 IMAGE artifact
    status, arts = adapter.poll(task_id)
    assert status == TaskStatus.DELIVERED, f"应完成 DELIVERED，实际 {status}"
    assert arts is not None, "DELIVERED 后产出物不应为 None"
    assert len(arts) == 3, f"quantity=3 应返回 3 个 artifact，实际 {len(arts)}"
    assert all(a.kind == "IMAGE" for a in arts), f"应为 IMAGE 类型，实际 {[a.kind for a in arts]}"
    # 每张图应带 placeholder 标记 + mock URL
    for idx, art in enumerate(arts, start=1):
        assert art.metadata.get("placeholder") is True
        assert art.metadata.get("source") == "mock"
        assert art.url_or_path and art.url_or_path.startswith("mock://image/"), art.url_or_path
        assert art.thumbnail_path and art.thumbnail_path.startswith("mock://thumb/"), art.thumbnail_path
    # 完成后进度应为 100
    assert adapter.get_progress(task_id) == 100

    # 再次 poll 已完成任务：应幂等返回 DELIVERED + 同样的产出
    status2, arts2 = adapter.poll(task_id)
    assert status2 == TaskStatus.DELIVERED
    assert len(arts2) == 3

    print("[1/4] quantity=3 出图任务 OK，产出 3 张 IMAGE")


def test_fail_mode_fail() -> None:
    """验收点 2：fail_mode='fail' → poll 立刻返回 FAILED。"""
    adapter = MockAdapter(fail_mode="fail")
    task_id = adapter.submit({"task_type": TaskType.IMAGE_GEN, "quantity": 1})

    # 第 1 次 poll 即失败
    status, arts = adapter.poll(task_id)
    assert status == TaskStatus.FAILED, f"fail 模式应返回 FAILED，实际 {status}"
    assert arts is None, f"失败时产出物应为 None，实际 {arts}"

    # 再次 poll 仍应失败（fail 模式不会自愈）
    status2, _ = adapter.poll(task_id)
    assert status2 == TaskStatus.FAILED, f"fail 模式应持续失败，实际 {status2}"

    print("[2/4] fail_mode='fail' 始终返回 FAILED OK")


def test_fail_mode_fail_then_succeed() -> None:
    """验收点 3：fail_mode='fail_then_succeed' → 前 N 次失败后最终成功。"""
    n = 2
    adapter = MockAdapter(
        fail_mode="fail_then_succeed",
        fail_then_succeed_n=n,
        polls_to_complete=1,  # 进入正常流程后 1 次 poll 即完成
    )
    task_id = adapter.submit({"task_type": TaskType.IMAGE_GEN, "quantity": 1})

    # 前 N 次 poll 应失败
    for i in range(n):
        status, arts = adapter.poll(task_id)
        assert status == TaskStatus.FAILED, f"第 {i + 1} 次 poll 应 FAILED，实际 {status}"
        assert arts is None

    # 第 N+1 次 poll：失败阶段结束，进入正常流程；polls_to_complete=1，本次即应完成
    status, arts = adapter.poll(task_id)
    assert status == TaskStatus.DELIVERED, f"第 {n + 1} 次 poll 应 DELIVERED，实际 {status}"
    assert arts is not None and len(arts) == 1, f"应返回 1 个 artifact，实际 {arts}"
    assert arts[0].kind == "IMAGE"

    print(f"[3/4] fail_mode='fail_then_succeed' 前 {n} 次失败后第 {n + 1} 次成功 OK")


def test_misc_cancel_and_other_task_types() -> None:
    """补充覆盖：cancel / timeout / 其他任务类型产出 / normalize_result。"""
    # ---- cancel ----
    adapter = MockAdapter()
    task_id = adapter.submit({"task_type": TaskType.IMAGE_GEN, "quantity": 2})
    ok = adapter.cancel(task_id)
    assert ok is True
    status, arts = adapter.poll(task_id)
    assert status == TaskStatus.CANCELLED, f"取消后 poll 应 CANCELLED，实际 {status}"
    assert arts is None

    # ---- timeout：长时间 EXECUTING ----
    timeout_adapter = MockAdapter(fail_mode="timeout")
    timeout_id = timeout_adapter.submit({"task_type": TaskType.IMAGE_GEN})
    for i in range(5):
        s, _ = timeout_adapter.poll(timeout_id)
        assert s == TaskStatus.EXECUTING, f"timeout 模式第 {i + 1} 次应 EXECUTING，实际 {s}"

    # ---- VIDEO_GEN → 1 个 VIDEO ----
    video_adapter = MockAdapter(polls_to_complete=1)
    vid_id = video_adapter.submit({"task_type": TaskType.VIDEO_GEN})
    s, arts = video_adapter.poll(vid_id)
    assert s == TaskStatus.DELIVERED
    assert len(arts) == 1 and arts[0].kind == "VIDEO"
    assert arts[0].metadata.get("duration_sec") == 5

    # ---- COPYWRITING → 1 个 TEXT ----
    copy_id = video_adapter.submit({"task_type": TaskType.COPYWRITING, "product": "保温杯"})
    s, arts = video_adapter.poll(copy_id)
    assert s == TaskStatus.DELIVERED
    assert len(arts) == 1 and arts[0].kind == "TEXT"
    assert "保温杯" in arts[0].metadata.get("content", "")

    # ---- DATA_QUERY → 1 个 TEXT ----
    data_id = video_adapter.submit({"task_type": TaskType.DATA_QUERY})
    s, arts = video_adapter.poll(data_id)
    assert s == TaskStatus.DELIVERED
    assert len(arts) == 1 and arts[0].kind == "TEXT"
    assert "数据查询" in arts[0].metadata.get("content", "")

    # ---- IMAGE_EDIT → 1 张 IMAGE（忽略 quantity）----
    edit_id = video_adapter.submit({"task_type": TaskType.IMAGE_EDIT, "quantity": 5})
    s, arts = video_adapter.poll(edit_id)
    assert s == TaskStatus.DELIVERED
    assert len(arts) == 1 and arts[0].kind == "IMAGE", f"IMAGE_EDIT 应只产 1 张，实际 {len(arts)}"

    # ---- task_type 用字符串也能解析 ----
    str_id = video_adapter.submit({"task_type": "image_gen", "quantity": 2})
    s, arts = video_adapter.poll(str_id)
    assert s == TaskStatus.DELIVERED
    assert len(arts) == 2

    # ---- normalize_result：dict 输入 ----
    norm = video_adapter.normalize_result({
        "artifact_id": "x1",
        "kind": "IMAGE",
        "url_or_path": "mock://image/x1",
        "metadata": {"foo": "bar"},
    })
    assert norm.artifact_id == "x1"
    assert norm.kind == "IMAGE"
    assert norm.url_or_path == "mock://image/x1"
    assert norm.metadata == {"foo": "bar"}

    # ---- normalize_result：str 输入 ----
    norm2 = video_adapter.normalize_result("mock://image/yy")
    assert norm2.kind == "IMAGE"
    assert norm2.url_or_path == "mock://image/yy"

    # ---- 非法 fail_mode 抛 ValueError ----
    try:
        MockAdapter(fail_mode="bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("非法 fail_mode 应抛 ValueError")

    # ---- 未知 task_id 的 poll 返回 FAILED ----
    s, _ = adapter.poll("not-exist-task-id")
    assert s == TaskStatus.FAILED

    print("[4/4] cancel / timeout / VIDEO/TEXT 产出 / normalize_result / 非法参数 OK")


def main() -> None:
    test_register_and_complete_image_gen_quantity_3()
    test_fail_mode_fail()
    test_fail_mode_fail_then_succeed()
    test_misc_cancel_and_other_task_types()
    print("\n全部 Mock 适配器测试通过 ✅")


if __name__ == "__main__":
    main()
