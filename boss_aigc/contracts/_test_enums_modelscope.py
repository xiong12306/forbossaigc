from boss_aigc.contracts.enums import PlatformKind

def test_modelscope_kind_exists():
    assert PlatformKind.MODELSCOPE.value == "modelscope"
