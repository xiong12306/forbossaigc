"""contracts.execution 执行与交付层数据契约。

包含确认后的任务、执行过程、步骤、产出物等结构。
编排层与执行层通过这些契约通信。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from boss_aigc.contracts.enums import PlatformKind, TaskStatus
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary


class ConfirmedTask(BaseModel):
    """已确认任务：确认层放行后交给编排层的载体。

    Attributes:
        task_id: 任务唯一 ID。
        intent: 原始任务意图。
        summary: 老板确认时的任务摘要（含最终参数）。
        confirmed_at: 确认时间戳。
    """

    task_id: str = Field(..., description="任务唯一 ID")
    intent: TaskIntent = Field(..., description="原始任务意图")
    summary: TaskSummary = Field(..., description="老板确认时的任务摘要")
    confirmed_at: datetime = Field(
        default_factory=datetime.now, description="确认时间"
    )


class Artifact(BaseModel):
    """产出物：执行层返回的单个结果单元（图/视频/文本）。

    Attributes:
        artifact_id: 产出物唯一 ID。
        kind: 产出类型（IMAGE / VIDEO / TEXT）。
        url_or_path: 资源 URL 或本地路径。
        thumbnail_path: 缩略图路径（用于卡片预览）。
        metadata: 附加元数据（如尺寸/时长/生成参数）。
    """

    artifact_id: str = Field(..., description="产出物唯一 ID")
    kind: str = Field(..., description="产出类型：IMAGE / VIDEO / TEXT")
    url_or_path: Optional[str] = Field(
        default=None, description="资源 URL 或本地路径"
    )
    thumbnail_path: Optional[str] = Field(
        default=None, description="缩略图路径"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="附加元数据"
    )


class TaskStep(BaseModel):
    """执行步骤：多步编排任务中的单步。

    Attributes:
        step_id: 步骤唯一 ID。
        name: 步骤名（如「出主图」「图转视频」）。
        platform: 该步骤使用的执行平台。
        input_refs: 前序步骤产出物的引用 ID 列表（DAG 边）。
        status: 步骤状态。
        result: 该步骤产出（完成后填充）。
    """

    step_id: str = Field(..., description="步骤唯一 ID")
    name: str = Field(..., description="步骤名")
    platform: PlatformKind = Field(
        default=PlatformKind.MOCK, description="该步骤使用的执行平台"
    )
    input_refs: list[str] = Field(
        default_factory=list,
        description="前序步骤产出物的引用 ID 列表（DAG 边）",
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, description="步骤状态"
    )
    result: Optional[Artifact] = Field(
        default=None, description="该步骤产出，完成后填充"
    )


class TaskExecution(BaseModel):
    """任务执行：编排层派发给执行层的执行体。

    Attributes:
        execution_id: 执行实例唯一 ID。
        task_id: 关联的任务 ID。
        platform: 主执行平台。
        steps: 步骤列表（单步任务仅一项，多步任务为 DAG）。
        status: 执行整体状态。
        started_at: 开始时间。
        progress: 进度 0~100。
    """

    execution_id: str = Field(..., description="执行实例唯一 ID")
    task_id: str = Field(..., description="关联的任务 ID")
    platform: PlatformKind = Field(
        default=PlatformKind.MOCK, description="主执行平台"
    )
    steps: list[TaskStep] = Field(
        default_factory=list, description="步骤列表（单步或多步 DAG）"
    )
    status: TaskStatus = Field(
        default=TaskStatus.EXECUTING, description="执行整体状态"
    )
    started_at: datetime = Field(
        default_factory=datetime.now, description="开始时间"
    )
    progress: int = Field(
        default=0, ge=0, le=100, description="进度 0~100"
    )


class TaskResult(BaseModel):
    """任务结果：交付层收到的最终打包结果。

    Attributes:
        result_id: 结果唯一 ID。
        task_id: 关联的任务 ID。
        artifacts: 产出物列表。
        status: 最终状态（DELIVERED / FAILED）。
        completed_at: 完成时间。
    """

    result_id: str = Field(..., description="结果唯一 ID")
    task_id: str = Field(..., description="关联的任务 ID")
    artifacts: list[Artifact] = Field(
        default_factory=list, description="产出物列表"
    )
    status: TaskStatus = Field(
        default=TaskStatus.DELIVERED, description="最终状态"
    )
    completed_at: datetime = Field(
        default_factory=datetime.now, description="完成时间"
    )
