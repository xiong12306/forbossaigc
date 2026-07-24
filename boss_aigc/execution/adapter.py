"""execution.adapter 统一适配器接口。

所有执行平台（Mock / 即梦 / 通义万相 / 文案 LLM）SHALL 实现该接口。
编排层仅依赖此抽象接口，对具体平台无感知，从而实现「适配器可替换」。

接口能力：
- submit(params) -> platform_task_id
- poll(platform_task_id) -> (TaskStatus, Optional[list[Artifact]])
- cancel(platform_task_id) -> bool
- normalize_result(raw) -> Artifact
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from boss_aigc.contracts.enums import PlatformKind, TaskStatus
from boss_aigc.contracts.execution import Artifact


class PlatformAdapter(ABC):
    """统一适配器抽象接口。

    每个适配器实例对应一个执行平台，提供提交、轮询、取消、结果标准化四个能力。
    子类 SHALL 覆写 submit / poll / cancel；normalize_result 提供默认实现可按需覆写。
    """

    kind: PlatformKind = PlatformKind.MOCK  # 子类覆写

    @abstractmethod
    def submit(self, params: dict[str, Any]) -> str:
        """提交任务到平台，返回平台侧任务 ID（用于后续轮询）。

        Args:
            params: 任务参数（槽位 + 上下文），由编排层组装。
                常见字段：task_type、quantity、style、product 等。

        Returns:
            平台侧任务 ID。
        """
        raise NotImplementedError

    @abstractmethod
    def poll(self, platform_task_id: str) -> tuple[TaskStatus, Optional[list[Artifact]]]:
        """轮询任务状态。

        Args:
            platform_task_id: submit 返回的平台任务 ID。

        Returns:
            (状态, 产出物列表) 二元组。
            - 未完成时产出物为 None；
            - 已完成（DELIVERED）时产出物为 Artifact 列表（可能含多项，如多张图）；
            - 失败/取消时产出物为 None。
        """
        raise NotImplementedError

    @abstractmethod
    def cancel(self, platform_task_id: str) -> bool:
        """取消任务，返回是否取消成功。"""
        raise NotImplementedError

    def normalize_result(self, raw: Any) -> Artifact:
        """将平台原生返回的单个结果标准化为 Artifact。

        默认实现仅做透传：把 raw 当作 URL 字符串包装为 IMAGE Artifact。
        子类可覆写以做字段映射（如把 dict 映射为 Artifact）。
        """
        return Artifact(
            artifact_id=str(id(raw)),
            kind="IMAGE",
            url_or_path=str(raw) if raw is not None else None,
        )
