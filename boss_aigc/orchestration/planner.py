"""boss_aigc.orchestration.planner 编排层规划器。

职责：
- plan_execution: 把 ConfirmedTask → ExecutionPlan（含步骤列表 + 每步参数）
- select_platform: 选择执行平台（本阶段固定 MOCK，后续按 task_type 选即梦/通义万相/LLM）

设计要点：
- ExecutionPlan 继承 TaskExecution，额外携带 step_params（每步 adapter 调用参数）与 metadata（降级记录）。
  这样既兼容 LayerHandler 协议（context.execution 仍是 TaskExecution），又能在 scheduler 里取到参数。
- 多步触发条件：VIDEO_GEN 且 intent.slots 无 source_image → 拆为 IMAGE_GEN + VIDEO_GEN 两步。
  其余任务类型一律单步。
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from boss_aigc.contracts.enums import PlatformKind, TaskType
from boss_aigc.contracts.execution import ConfirmedTask, TaskExecution, TaskStep
from boss_aigc.contracts.summary import TaskSummary


# 各 task_type 对应的单步中文名（用于 step.name 展示）
_STEP_NAMES: dict[TaskType, str] = {
    TaskType.IMAGE_GEN: "出主图",
    TaskType.IMAGE_EDIT: "改图",
    TaskType.VIDEO_GEN: "生成视频",
    TaskType.COPYWRITING: "写文案",
    TaskType.DATA_QUERY: "查数据",
}


class ExecutionPlan(TaskExecution):
    """执行计划：TaskExecution + 各步骤参数 + 元数据。

    继承 TaskExecution 以兼容 LayerHandler 协议（context.execution 仍是 TaskExecution 类型）。
    额外字段：
        step_params: step_id → adapter 调用参数 dict（含 task_type/quantity/style 等）。
        metadata: 附加元数据（如「已切换到备用平台」记录）。
    """

    step_params: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="step_id → adapter 调用参数"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="附加元数据（降级记录等）"
    )


def select_platform(task_type: TaskType, summary: TaskSummary) -> PlatformKind:
    """选择执行平台。

    根据config.platform_provider和task_type选择平台：
    - IMAGE_GEN → 按 platform_provider（modelscope/siliconflow/nanobanana）选择对应真实平台，
      未配置对应 key 时降级为 MOCK
    - 其他类型 → MOCK
    后续可扩展：
    - VIDEO_GEN → 即梦（Seedance 图转视频）
    - COPYWRITING → LLM（写商品文案/标题）
    - DATA_QUERY → 内部数据库 / LLM 汇总
    """
    from boss_aigc.config import get_settings
    settings = get_settings()

    if task_type == TaskType.IMAGE_GEN:
        if settings.platform_provider == "modelscope" and settings.modelscope_api_key:
            return PlatformKind.MODELSCOPE
        if settings.platform_provider == "siliconflow" and settings.siliconflow_api_key:
            return PlatformKind.SILICONFLOW
        if settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
            return PlatformKind.NANOBANANA
    return PlatformKind.MOCK


def _merge_params(confirmed_task: ConfirmedTask) -> dict[str, Any]:
    """合并 summary.params + intent.slots → adapter 调用参数 dict。

    优先级：summary.params > intent.slots（确认层最终参数覆盖理解层解析值）。
    输出含 task_type / product / quantity / style / size / prompt 等字段。
    prompt 取 intent.raw_text，让用户自定义描述流入 adapter 构建 prompt。
    """
    params: dict[str, Any] = {}
    # 先放 slots（拍平 SlotValue.value 到顶层 key）
    for slot_name, slot_value in confirmed_task.intent.slots.items():
        params[slot_name] = slot_value.value
    # 再用 summary.params 覆盖（确认层最终参数优先）
    params.update(confirmed_task.summary.params)
    # 兜底加 task_type / product
    params.setdefault("task_type", confirmed_task.intent.task_type)
    params.setdefault("product", confirmed_task.intent.product)
    # 把用户原始描述传给 adapter 作为 prompt 补充
    raw = confirmed_task.intent.raw_text.strip()
    if raw:
        params.setdefault("prompt", raw)
    return params


def plan_execution(confirmed_task: ConfirmedTask) -> ExecutionPlan:
    """规划执行：把 ConfirmedTask → ExecutionPlan。

    规则：
    - 多步触发条件：task_type=VIDEO_GEN 且 intent.slots 无 source_image → 拆为两步：
        * Step 1: IMAGE_GEN（先生成一张图），name="生成主图"
        * Step 2: VIDEO_GEN（用 step1 产出转视频），name="图转视频"，
          input_refs=[step1.step_id]；step2 的 params.source_image 占位 None，
          scheduler 执行时用 step1 产出填入。
    - 其余任务（IMAGE_GEN / IMAGE_EDIT / COPYWRITING / DATA_QUERY / 已带 source_image 的 VIDEO_GEN）→ 单步。

    Args:
        confirmed_task: 已确认任务。

    Returns:
        ExecutionPlan（含 steps + step_params + 元数据）。
    """
    task_type = confirmed_task.intent.task_type
    summary = confirmed_task.summary
    platform = select_platform(task_type, summary)

    # 判断多步触发条件
    needs_image_first = (
        task_type == TaskType.VIDEO_GEN
        and "source_image" not in confirmed_task.intent.slots
    )

    base_params = _merge_params(confirmed_task)
    step_params: dict[str, dict[str, Any]] = {}

    if needs_image_first:
        # 多步：先生成主图，再转视频
        step1_id = f"step-{uuid.uuid4().hex[:8]}"
        step2_id = f"step-{uuid.uuid4().hex[:8]}"

        # step1: IMAGE_GEN（强制 task_type=IMAGE_GEN）
        s1_params = dict(base_params)
        s1_params["task_type"] = TaskType.IMAGE_GEN
        step_params[step1_id] = s1_params

        # step2: VIDEO_GEN，source_image 占位（scheduler 执行时填入 step1 产出）
        s2_params = dict(base_params)
        s2_params["task_type"] = TaskType.VIDEO_GEN
        s2_params["source_image"] = None  # 占位
        step_params[step2_id] = s2_params

        steps = [
            TaskStep(step_id=step1_id, name="生成主图", platform=platform),
            TaskStep(
                step_id=step2_id,
                name="图转视频",
                platform=platform,
                input_refs=[step1_id],
            ),
        ]
    else:
        # 单步
        step_id = f"step-{uuid.uuid4().hex[:8]}"
        step_params[step_id] = base_params
        step_name = _STEP_NAMES.get(task_type, "执行任务")
        steps = [TaskStep(step_id=step_id, name=step_name, platform=platform)]

    plan = ExecutionPlan(
        execution_id=f"exec-{uuid.uuid4().hex[:12]}",
        task_id=confirmed_task.task_id,
        platform=platform,
        steps=steps,
        step_params=step_params,
    )
    return plan
