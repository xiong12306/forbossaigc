import importlib
import os

def _reload_settings():
    import boss_aigc.config as cfg
    importlib.reload(cfg)
    return cfg.get_settings()

def test_platform_provider_from_env(monkeypatch):
    monkeypatch.setenv("PLATFORM_PROVIDER", "modelscope")
    monkeypatch.setenv("MODELSCOPE_API_KEY", "tok-123")
    s = _reload_settings()
    assert s.platform_provider == "modelscope"
    assert s.modelscope_api_key == "tok-123"
    assert s.modelscope_model == "Qwen/Qwen-Image"
    assert s.modelscope_api_base == "https://api-inference.modelscope.cn/v1"

def test_use_real_platform_from_env(monkeypatch):
    monkeypatch.setenv("USE_REAL_PLATFORM", "True")
    monkeypatch.setenv("NANOBANANA_API_KEY", "nb-key")
    s = _reload_settings()
    assert s.use_real_platform is True
    assert s.nanobanana_api_key == "nb-key"

def test_defaults(monkeypatch):
    for k in ("PLATFORM_PROVIDER", "MODELSCOPE_API_KEY", "USE_REAL_PLATFORM", "NANOBANANA_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    s = _reload_settings()
    assert s.platform_provider == "mock"
    assert s.use_real_platform is False
