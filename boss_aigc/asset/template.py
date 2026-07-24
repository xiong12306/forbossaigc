"""asset.template 常用模板沉淀接口（预留）。

把高频/满意的历史任务沉淀为模板，供老板一键复用。

Note:
    模板一键复用的完整逻辑在后续阶段实现（需对接理解层模板解析、
    把模板字段映射回 TaskIntent 槽位）。本阶段只做存储与基本检索。
"""

from typing import Any, Optional


class TaskTemplateStore:
    """任务模板存储：内存存储（dict 实现，按模板名去重）。"""

    def __init__(self) -> None:
        self._templates: dict[str, dict[str, Any]] = {}

    def promote_to_template(
        self,
        history_record: dict[str, Any],
        template_name: str,
    ) -> None:
        """把一条历史任务沉淀为模板。

        Args:
            history_record: TaskHistoryStore 产出的任务记录 dict。
            template_name: 模板名（同名将覆盖）。
        """
        self._templates[template_name] = {
            "name": template_name,
            "task_type": history_record.get("task_type"),
            "product": history_record.get("product"),
            "raw_text": history_record.get("raw_text"),
            "summary": dict(history_record.get("summary") or {}),
            "created_from_task_id": history_record.get("task_id"),
        }

    def get_template(self, name: str) -> Optional[dict[str, Any]]:
        """按名取模板；未找到返回 None。"""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """列出所有模板名。"""
        return list(self._templates.keys())

    def suggest_template(
        self,
        task_type: str,
        product: str,
    ) -> Optional[str]:
        """根据任务类型与商品建议模板。

        本阶段简单策略：返回首个任务类型匹配的模板名；找不到返回 None。
        完整推荐策略（结合使用频次 / 商品关联 / 老板偏好）留待后续阶段。
        """
        for name, tpl in self._templates.items():
            if tpl.get("task_type") == task_type:
                return name
        return None
