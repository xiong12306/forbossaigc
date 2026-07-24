"""boss_aigc.logging_setup 结构化日志与埋点。

提供 get_logger(name) 统一入口，输出包含
时间/级别/模块/层名/任务ID 的结构化记录。
Pipeline 的 before_layer / after_layer 钩子使用此模块埋点。
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

_CONFIGURED = False


class _StructuredFormatter(logging.Formatter):
    """结构化日志格式器：每行一条 JSON。

    字段：ts / level / layer / module / task_id / message。
    额外的 extra 字段会被合并进 JSON。
    """

    # 标准库 logging 已有的属性名，避免重复输出。
    # 注意：Python 3.12+ 的 LogRecord 自带 taskName（asyncio 任务名），需排除避免泄露 null。
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        # 层名：约定通过 extra 注入 layer 字段
        if hasattr(record, "layer"):
            payload["layer"] = record.layer
        # 任务 ID：约定通过 extra 注入 task_id 字段
        if hasattr(record, "task_id"):
            payload["task_id"] = record.task_id
        # 合并其余 extra 字段
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO, *, force: bool = False) -> None:
    """配置根 logger，输出结构化 JSON 到 stdout。

    幂等：重复调用默认不重复添加 handler，除非 force=True。
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    root = logging.getLogger()
    root.setLevel(level)
    # 清理旧 handler，避免重复输出
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_StructuredFormatter())
    root.addHandler(handler)

    _CONFIGURED = True


class _LayerLoggerAdapter(logging.LoggerAdapter):
    """带层上下文的 logger 适配器。

    重写 process：把适配器默认 extra 与每次调用传入的 extra 合并，
    调用级 extra 优先（per-call wins）。
    默认 LoggerAdapter 在 merge_extra=False 时会用 self.extra 直接覆盖
    per-call extra，导致 task_id 等动态字段丢失，故此处显式合并。
    """

    def process(self, msg: str, kwargs: dict) -> tuple:  # type: ignore[override]
        merged = dict(self.extra or {})
        merged.update(kwargs.get("extra") or {})
        kwargs["extra"] = merged
        return msg, kwargs


def get_logger(name: str, layer: Optional[str] = None) -> logging.LoggerAdapter:
    """获取一个带 layer 上下文的 logger。

    Args:
        name: 通常传 __name__。
        layer: 默认层名（access/understanding/confirmation/orchestration/
               execution/delivery/asset），用于在日志中标注来源层。
               调用时可通过 extra={"layer": ...} 覆盖。
    """
    if not _CONFIGURED:
        configure_logging()
    logger = logging.getLogger(name)
    return _LayerLoggerAdapter(logger, extra={"layer": layer or name})
