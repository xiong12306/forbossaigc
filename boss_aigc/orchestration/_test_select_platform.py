from boss_aigc.config import configure
from boss_aigc.contracts.enums import PlatformKind, TaskType
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.orchestration.planner import select_platform

import pytest


def _summary():
    return TaskSummary(summary_id="s1", task_type=TaskType.IMAGE_GEN)


@pytest.fixture(autouse=True)
def _reset():
    yield
    configure(platform_provider="mock", modelscope_api_key="", nanobanana_api_key="")


def test_modelscope_selected():
    configure(platform_provider="modelscope", modelscope_api_key="k")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.MODELSCOPE


def test_modelscope_no_key_falls_to_mock():
    configure(platform_provider="modelscope", modelscope_api_key="")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.MOCK


def test_nanobanana_selected():
    configure(platform_provider="nanobanana", nanobanana_api_key="nb")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.NANOBANANA


def test_mock_default():
    configure(platform_provider="mock")
    assert select_platform(TaskType.IMAGE_GEN, _summary()) == PlatformKind.MOCK
