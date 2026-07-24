import pytest
from boss_aigc.config import configure
from boss_aigc.contracts.enums import PlatformKind
from boss_aigc.execution.registry import get_registry, register_default_adapters


@pytest.fixture(autouse=True)
def _reset():
    yield
    configure(platform_provider="mock", modelscope_api_key="", nanobanana_api_key="")
    # registry 是模块级单例，跨测试用例不会自动清空；显式反注册避免状态泄漏
    get_registry().unregister(PlatformKind.MODELSCOPE)
    get_registry().unregister(PlatformKind.NANOBANANA)


def test_modelscope_registered():
    configure(platform_provider="modelscope", modelscope_api_key="k")
    reg = register_default_adapters()
    assert reg.get(PlatformKind.MOCK) is not None
    assert reg.get(PlatformKind.MODELSCOPE) is not None


def test_mock_only_when_provider_mock():
    configure(platform_provider="mock", modelscope_api_key="")
    reg = register_default_adapters()
    assert reg.get(PlatformKind.MOCK) is not None
    assert reg.get(PlatformKind.MODELSCOPE) is None
