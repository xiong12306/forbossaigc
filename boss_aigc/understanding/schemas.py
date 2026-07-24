"""boss_aigc.understanding.schemas 任务类型与槽位 schema。

定义各 TaskType 的槽位规格（必填/可选/默认值），
供意图识别器、多轮追问、确认层等查询使用。

每个槽位规格为 (是否必填, 默认值) 二元组：
- 必填槽位缺失时进入 missing_slots 触发追问
- 可选槽位缺失时使用默认值（None 表示无默认，由下游决定）
"""

from __future__ import annotations

from typing import Any

from boss_aigc.contracts.enums import TaskType

from boss_aigc.contracts.enums import ImageType

# 各 TaskType 的槽位 schema：槽位名 -> (是否必填, 默认值)
SLOT_SCHEMAS: dict[TaskType, dict[str, tuple[bool, Any]]] = {
    TaskType.IMAGE_GEN: {
        "product": (True, None),
        "quantity": (False, 1),
        "image_type": (False, ImageType.MAIN.value),
        "style": (False, None),
        "size": (False, "1024x1024"),
        "reference_image": (False, None),
    },
    TaskType.IMAGE_EDIT: {
        "product": (True, None),
        "edit_instruction": (True, None),
        "target_image": (False, None),
    },
    TaskType.VIDEO_GEN: {
        "product": (True, None),
        "duration_sec": (False, 15),
        "source_image": (False, None),
        "style": (False, None),
    },
    TaskType.COPYWRITING: {
        "product": (True, None),
        "copy_type": (True, None),  # title / detail / xiaohongshu
        "word_count": (False, None),
    },
    TaskType.DATA_QUERY: {
        "query_target": (True, None),  # history / asset
    },
}

# 枚举型槽位的合法取值（用于校验/澄清）
SLOT_ENUMS: dict[str, list[str]] = {
    "copy_type": ["title", "detail", "xiaohongshu"],
    "query_target": ["history", "asset"],
    "image_type": [t.value for t in ImageType],
}

# 图片类型中文名映射
IMAGE_TYPE_NAMES: dict[str, str] = {
    ImageType.MAIN.value: "商品主图",
    ImageType.DETAIL.value: "产品详情图",
    ImageType.SCENE.value: "场景图",
    ImageType.POSTER.value: "营销海报",
    ImageType.CAROUSEL.value: "轮播图",
}


def get_required_slots(task_type: TaskType) -> list[str]:
    """返回某任务类型的必填槽位名列表。"""
    schema = SLOT_SCHEMAS.get(task_type, {})
    return [name for name, (required, _) in schema.items() if required]


def get_optional_slots(task_type: TaskType) -> list[str]:
    """返回某任务类型的可选槽位名列表。"""
    schema = SLOT_SCHEMAS.get(task_type, {})
    return [name for name, (required, _) in schema.items() if not required]


def get_default(slot_name: str, task_type: TaskType) -> Any:
    """返回某槽位在该任务类型下的默认值（无默认返回 None）。"""
    schema = SLOT_SCHEMAS.get(task_type, {})
    if slot_name not in schema:
        return None
    _, default = schema[slot_name]
    return default
