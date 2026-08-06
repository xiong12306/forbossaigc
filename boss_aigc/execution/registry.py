"""execution.registry 适配器注册机制。

提供按 PlatformKind 注册 / 取用适配器的能力。
编排层通过 registry 取适配器，从而实现「Mock ↔ 真实平台」热替换。
"""

from typing import Optional

from boss_aigc.contracts.enums import PlatformKind
from boss_aigc.execution.adapter import PlatformAdapter


class AdapterRegistry:
    """适配器注册表：按平台类型登记适配器实例。

    用法：
        registry = get_registry()
        registry.register(PlatformKind.MOCK, MockAdapter())
        adapter = registry.get(PlatformKind.MOCK)
    """

    def __init__(self) -> None:
        self._adapters: dict[PlatformKind, PlatformAdapter] = {}

    def register(self, kind: PlatformKind, adapter: PlatformAdapter) -> None:
        """登记一个适配器（同类型会被覆盖）。"""
        self._adapters[kind] = adapter

    def unregister(self, kind: PlatformKind) -> None:
        """移除一个适配器。"""
        self._adapters.pop(kind, None)

    def get(self, kind: PlatformKind) -> Optional[PlatformAdapter]:
        """按平台类型取用适配器；未注册返回 None。"""
        return self._adapters.get(kind)

    def list_kinds(self) -> list[PlatformKind]:
        """列出已注册的平台类型。"""
        return list(self._adapters.keys())


# 模块级单例：整个进程共享一个注册表
_registry = AdapterRegistry()


def get_registry() -> AdapterRegistry:
    """获取全局适配器注册表（单例）。"""
    return _registry


def register_default_adapters() -> AdapterRegistry:
    """注册本阶段内置的默认适配器。

    根据config.platform_provider决定注册哪个真实平台：
    - platform_provider == "modelscope" 且已配 key: 注册 ModelScopeAdapter
    - platform_provider == "siliconflow" 且已配 key: 注册 SiliconFlowAdapter
    - platform_provider == "nanobanana" 且已配 key: 注册 NanoBananaAdapter
    - 其余情况: 仅注册 Mock 适配器
    始终注册 Mock 适配器（供 PLATFORM_PROVIDER=mock 显式使用）。

    幂等：重复调用会以新实例覆盖同类型的旧适配器。

    Returns:
        注册完成后的全局注册表（便于链式调用）。
    """
    from boss_aigc.config import get_settings
    from boss_aigc.execution.mock_adapter import MockAdapter

    settings = get_settings()
    registry = get_registry()

    # 总是注册Mock作为fallback
    registry.register(PlatformKind.MOCK, MockAdapter())

    if settings.platform_provider == "modelscope" and settings.modelscope_api_key:
        from boss_aigc.execution.modelscope_adapter import ModelScopeAdapter
        registry.register(PlatformKind.MODELSCOPE, ModelScopeAdapter())
    elif settings.platform_provider == "siliconflow" and settings.siliconflow_api_key:
        from boss_aigc.execution.siliconflow_adapter import SiliconFlowAdapter
        registry.register(PlatformKind.SILICONFLOW, SiliconFlowAdapter())
    elif settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
        from boss_aigc.execution.nanobanana_adapter import NanoBananaAdapter
        registry.register(PlatformKind.NANOBANANA, NanoBananaAdapter())

    return registry
