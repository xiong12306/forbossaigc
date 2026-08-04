"""pytest 全局夹具：测试隔离本地 .env 的平台配置。

本地 .env 可能配了真实 PLATFORM_PROVIDER=modelscope + MODELSCOPE_API_KEY（用于线上/联调），
若不隔离，会泄漏进测试导致：
  1. 平台选择变成 modelscope，破坏假设默认 mock 的用例（如 confirmation.build_summary）；
  2. e2e 用例真打魔搭 API（慢 + 烧真实额度）。

故每个测试前把全局配置强制回落到 mock 平台。需要测真实平台选择/注册的用例，
在用例内用 configure(...) 自行覆写（在本夹具之后生效）。
"""

import pytest

from boss_aigc.config import configure


@pytest.fixture(autouse=True)
def _force_mock_platform():
    configure(
        platform_provider="mock",
        modelscope_api_key="",
        nanobanana_api_key="",
        use_real_platform=False,
    )
    yield
