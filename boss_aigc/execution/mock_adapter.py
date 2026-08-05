"""execution.mock_adapter Mock 适配器实现。

在不需要真实出图平台的情况下，提供「提交→轮询→完成」的内存模拟，
供编排层、确认锁、降级路径等端到端验证使用。

核心特性：
- 根据 params.task_type / params.quantity 决定产出物类型与数量
- 通过「提交后 N 次 poll 内完成」模拟异步耗时
- 支持 fail_mode 故障注入：none / fail / timeout / fail_then_succeed

用法示例：
    # 正常出图
    adapter = MockAdapter()
    task_id = adapter.submit({"task_type": TaskType.IMAGE_GEN, "quantity": 3})
    status, artifacts = adapter.poll(task_id)

    # 故障注入：模拟总是失败
    fail_adapter = MockAdapter(fail_mode="fail")
    fail_task_id = fail_adapter.submit({"task_type": TaskType.IMAGE_GEN})
    status, _ = fail_adapter.poll(fail_task_id)  # status == TaskStatus.FAILED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from boss_aigc.contracts.enums import PlatformKind, TaskStatus, TaskType
from boss_aigc.contracts.execution import Artifact
from boss_aigc.execution.adapter import PlatformAdapter


# 合法的故障模式
_VALID_FAIL_MODES = {"none", "fail", "timeout", "fail_then_succeed"}


@dataclass
class _MockTaskState:
    """Mock 任务内存状态：跟踪单次 submit 后的轮询进度与最终产出。"""

    task_id: str
    params: dict[str, Any]
    submitted_at: datetime
    poll_count: int = 0           # 累计 poll 次数
    fail_phase_done: bool = False  # fail_then_succeed 模式下，失败阶段是否已结束
    status: TaskStatus = TaskStatus.EXECUTING
    artifacts: list[Artifact] = field(default_factory=list)


class MockAdapter(PlatformAdapter):
    """Mock 适配器：内存模拟出图/改图/生视频/写文案/查数据全流程。

    通过「提交后 N 次 poll 内完成」模拟异步耗时，配合 fail_mode 注入故障用于验证降级路径。

    Args:
        fail_mode: 故障模式，可选：
            - "none"（默认）：正常完成
            - "fail"：poll 总是返回 FAILED
            - "timeout"：poll 长时间返回 EXECUTING（模拟超时，永不完成）
            - "fail_then_succeed"：前 fail_then_succeed_n 次 poll 返回 FAILED，之后转为正常流程
        polls_to_complete: 正常流程下需要 poll 多少次才返回 DELIVERED（默认 2）。
        fail_then_succeed_n: fail_then_succeed 模式下前 N 次 poll 返回 FAILED（默认 2）。
    """

    kind: PlatformKind = PlatformKind.MOCK

    def __init__(
        self,
        fail_mode: str = "none",
        polls_to_complete: int = 2,
        fail_then_succeed_n: int = 2,
    ) -> None:
        if fail_mode not in _VALID_FAIL_MODES:
            raise ValueError(
                f"非法 fail_mode={fail_mode!r}，合法值: {_VALID_FAIL_MODES}"
            )
        if polls_to_complete < 1:
            raise ValueError("polls_to_complete 必须 >= 1")
        if fail_then_succeed_n < 1:
            raise ValueError("fail_then_succeed_n 必须 >= 1")

        self.fail_mode = fail_mode
        self.polls_to_complete = polls_to_complete
        self.fail_then_succeed_n = fail_then_succeed_n
        self._tasks: dict[str, _MockTaskState] = {}
        self._counter = 0  # 自增计数器，用于生成稳定的 task_id

    # ---------- PlatformAdapter 实现 ----------

    def submit(self, params: dict[str, Any]) -> str:
        """提交 Mock 任务，生成 task_id 并在内存登记初始状态（EXECUTING）。"""
        self._counter += 1
        task_id = f"mock-task-{self._counter}"
        self._tasks[task_id] = _MockTaskState(
            task_id=task_id,
            params=dict(params),
            submitted_at=datetime.now(),
        )
        return task_id

    def poll(self, platform_task_id: str) -> tuple[TaskStatus, Optional[list[Artifact]]]:
        """轮询 Mock 任务状态。

        模拟异步：
        - 首次若干次 poll 返回 EXECUTING（无产出）；
        - 达到 polls_to_complete 次后返回 DELIVERED + Artifact 列表；
        - 故障模式下按 fail_mode 返回 FAILED / 长时间 EXECUTING。
        """
        state = self._tasks.get(platform_task_id)
        if state is None:
            # 未知任务：直接判定失败
            return TaskStatus.FAILED, None

        # 已取消：恒返回 CANCELLED
        if state.status == TaskStatus.CANCELLED:
            return TaskStatus.CANCELLED, None

        # 已交付：恒返回 DELIVERED + 缓存的产出物
        if state.status == TaskStatus.DELIVERED:
            return TaskStatus.DELIVERED, list(state.artifacts)

        state.poll_count += 1

        # 1) fail 模式：始终失败
        if self.fail_mode == "fail":
            state.status = TaskStatus.FAILED
            return TaskStatus.FAILED, None

        # 2) timeout 模式：永远执行中，模拟超时
        if self.fail_mode == "timeout":
            state.status = TaskStatus.EXECUTING
            return TaskStatus.EXECUTING, None

        # 3) fail_then_succeed 模式：前 N 次失败，之后转正常流程
        if self.fail_mode == "fail_then_succeed" and not state.fail_phase_done:
            if state.poll_count <= self.fail_then_succeed_n:
                state.status = TaskStatus.FAILED
                return TaskStatus.FAILED, None
            # 失败阶段结束：重置计数，本次 poll 计入正常流程第 1 次
            state.fail_phase_done = True
            state.poll_count = 1

        # 4) 正常流程：达到完成次数后返回 DELIVERED + Artifact 列表
        if state.poll_count >= self.polls_to_complete:
            state.artifacts = self._build_artifacts(state)
            state.status = TaskStatus.DELIVERED
            return TaskStatus.DELIVERED, list(state.artifacts)

        # 5) 未达到完成次数：返回 EXECUTING（进度可通过 get_progress 查询）
        state.status = TaskStatus.EXECUTING
        return TaskStatus.EXECUTING, None

    def cancel(self, platform_task_id: str) -> bool:
        """取消 Mock 任务。Mock 总是允许取消（即使任务 ID 不存在也返回 True），
        以保持与「Mock 即占位」的语义一致。
        """
        state = self._tasks.get(platform_task_id)
        if state is not None:
            state.status = TaskStatus.CANCELLED
        return True

    def normalize_result(self, raw: Any) -> Artifact:
        """把 Mock 原始产出标准化为 Artifact。

        支持两种输入：
        - dict：可包含 artifact_id / kind / url_or_path / thumbnail_path / metadata
        - str：当作 URL，包装为 IMAGE Artifact
        """
        if isinstance(raw, dict):
            return Artifact(
                artifact_id=raw.get("artifact_id") or f"mock-art-{uuid.uuid4().hex[:8]}",
                kind=raw.get("kind", "IMAGE"),
                url_or_path=raw.get("url_or_path"),
                thumbnail_path=raw.get("thumbnail_path"),
                metadata=dict(raw.get("metadata", {})) or {"placeholder": True},
            )
        return Artifact(
            artifact_id=f"mock-art-{uuid.uuid4().hex[:8]}",
            kind="IMAGE",
            url_or_path=str(raw) if raw is not None else None,
            metadata={"placeholder": True, "source": "mock"},
        )

    # ---------- Mock 专属辅助方法 ----------

    def get_progress(self, platform_task_id: str) -> int:
        """获取任务进度（0~100），仅 Mock 用途，便于编排层测试进度汇总。"""
        state = self._tasks.get(platform_task_id)
        if state is None:
            return 0
        if state.status == TaskStatus.DELIVERED:
            return 100
        if state.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            return 0
        # 按 poll_count / polls_to_complete 估算进度，封顶 99 防止假完成
        return min(99, int(state.poll_count / self.polls_to_complete * 100))

    # ---------- 内部：根据 task_type 构造产出物 ----------

    def _build_artifacts(self, state: _MockTaskState) -> list[Artifact]:
        """根据任务类型与数量生成对应的 Mock Artifact 列表。"""
        task_type = self._resolve_task_type(state.params)
        quantity = self._resolve_quantity(state.params)

        artifacts: list[Artifact] = []

        if task_type == TaskType.IMAGE_GEN:
            # 出图：返回 N 张 IMAGE（N=quantity）
            for i in range(quantity):
                artifacts.append(self._make_media_artifact("IMAGE", state.task_id, i))
        elif task_type == TaskType.IMAGE_EDIT:
            # 改图：返回 1 张 IMAGE
            artifacts.append(self._make_media_artifact("IMAGE", state.task_id, 0))
        elif task_type == TaskType.VIDEO_GEN:
            # 生视频：返回 1 个 VIDEO
            artifacts.append(self._make_media_artifact("VIDEO", state.task_id, 0))
        elif task_type == TaskType.COPYWRITING:
            # 写文案：使用本地文案生成器生成真实可用文案
            from boss_aigc.execution.copywriter import generate_copywriting, resolve_copy_type
            product = state.params.get("product", "商品")
            copy_type = resolve_copy_type(state.params)
            style = state.params.get("style", "")
            extra = state.params.get("extra", "") or state.params.get("description", "")
            content = generate_copywriting(
                product=product, copy_type=copy_type, style=style, extra=extra
            )
            artifacts.append(self._make_text_artifact(state.task_id, content=content))
        elif task_type == TaskType.DATA_QUERY:
            # 查数据：使用本地数据查询生成器
            from boss_aigc.execution.copywriter import generate_data_query
            content = generate_data_query(state.params)
            artifacts.append(self._make_text_artifact(state.task_id, content=content))
        else:
            # 兜底：未知类型返回 1 张 IMAGE
            artifacts.append(self._make_media_artifact("IMAGE", state.task_id, 0))

        return artifacts

    @staticmethod
    def _resolve_task_type(params: dict[str, Any]) -> TaskType:
        """从 params 解析 task_type，兼容 TaskType 枚举与字符串。"""
        raw = params.get("task_type", TaskType.IMAGE_GEN)
        if isinstance(raw, TaskType):
            return raw
        if isinstance(raw, str):
            try:
                return TaskType(raw)
            except ValueError:
                return TaskType.IMAGE_GEN
        return TaskType.IMAGE_GEN

    @staticmethod
    def _resolve_quantity(params: dict[str, Any]) -> int:
        """从 params 解析 quantity，非法值降级为 1。"""
        raw = params.get("quantity", 1)
        try:
            q = int(raw)
            return q if q >= 1 else 1
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _make_media_artifact(kind: str, task_id: str, idx: int) -> Artifact:
        """生成图/视频类 Mock Artifact。"""
        artifact_id = f"{task_id}-art-{idx + 1}"
        if kind == "IMAGE":
            url = f"mock://image/{task_id}/{idx + 1}"
            thumb = f"mock://thumb/{task_id}/{idx + 1}"
            metadata: dict[str, Any] = {
                "placeholder": True,
                "source": "mock",
                "width": 1024,
                "height": 1024,
            }
        else:  # VIDEO
            url = f"mock://video/{task_id}/{idx + 1}"
            thumb = f"mock://thumb/{task_id}/{idx + 1}"
            metadata = {
                "placeholder": True,
                "source": "mock",
                "duration_sec": 5,
                "resolution": "1080p",
            }
        return Artifact(
            artifact_id=artifact_id,
            kind=kind,
            url_or_path=url,
            thumbnail_path=thumb,
            metadata=metadata,
        )

    @staticmethod
    def _make_text_artifact(task_id: str, content: str) -> Artifact:
        """生成文本类 Mock Artifact（文案/数据查询）。"""
        return Artifact(
            artifact_id=f"{task_id}-art-1",
            kind="TEXT",
            url_or_path=None,
            metadata={
                "placeholder": True,
                "source": "mock",
                "content": content,
            },
        )
