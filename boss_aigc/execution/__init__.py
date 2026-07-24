"""boss_aigc.execution 执行层包。

职责：统一适配器接口 + Mock 实现 + 注册机制。
编排层通过 registry 取用适配器，无需感知具体平台。
"""

from boss_aigc.execution.adapter import PlatformAdapter
from boss_aigc.execution.registry import (
    AdapterRegistry,
    get_registry,
    register_default_adapters,
)
from boss_aigc.execution.mock_adapter import MockAdapter

__all__ = [
    "PlatformAdapter",
    "AdapterRegistry",
    "get_registry",
    "register_default_adapters",
    "MockAdapter",
]
