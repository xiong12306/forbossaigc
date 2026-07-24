"""boss_aigc.supabase_client Supabase 客户端。

从环境变量读取配置，初始化 Supabase 客户端。
未配置时返回 None，API 层自动 fallback 到 SQLite。
"""

from __future__ import annotations

import os
from typing import Optional

# 先加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
    import httpx
    _HAS_SUPABASE = True
except ImportError:
    _HAS_SUPABASE = False
    Client = None  # type: ignore
    httpx = None  # type: ignore


def _get_env(key: str) -> str:
    return os.environ.get(key, "")


# 配置优先级：环境变量 > 空值
SUPABASE_URL = _get_env("SUPABASE_URL") or _get_env("VITE_SUPABASE_URL")
SUPABASE_KEY = _get_env("SUPABASE_ANON_KEY") or _get_env("VITE_SUPABASE_ANON_KEY")


def is_configured() -> bool:
    """检查 Supabase 是否已配置（有 URL 和 key 且已安装库）。"""
    return _HAS_SUPABASE and bool(SUPABASE_URL) and bool(SUPABASE_KEY)


def get_client() -> Optional[Client]:
    """获取 Supabase 客户端实例。

    返回 None 表示未配置，调用方应 fallback 到 SQLite。
    """
    if not is_configured():
        return None
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # 覆盖 httpx 默认超时（默认 5s 太短）
        client.rest._client._client.timeout = httpx.Timeout(30.0)
        return client
    except Exception:
        return None


# 模块级单例 + 连通性缓存
_supabase: Optional[Client] = None
_last_check_time: float = 0.0
_last_check_result: bool = False


def get_supabase() -> Optional[Client]:
    """获取全局 Supabase 客户端单例。

    返回前会做一次轻量连通性检查（ping products 表），结果缓存 60 秒。
    不可用（未配置 / 网络不通）时返回 None，调用方应 fallback 到 SQLite。
    """
    import time
    global _supabase, _last_check_time, _last_check_result
    now = time.time()
    # 60 秒内复用上次检查结果
    if now - _last_check_time < 60:
        return _supabase if _last_check_result else None
    # 缓存过期，重新检查
    if not is_configured():
        _last_check_time = now
        _last_check_result = False
        return None
    if _supabase is None:
        _supabase = get_client()
    if _supabase is None:
        _last_check_time = now
        _last_check_result = False
        return None
    try:
        _supabase.table("products").select("id").limit(1).execute()
        _last_check_time = now
        _last_check_result = True
        return _supabase
    except Exception:
        _last_check_time = now
        _last_check_result = False
        return None


def is_available() -> bool:
    """检查 Supabase 是否可用（已配置且能连通）。

    做一次轻量 ping，失败则返回 False，调用方 fallback 到 SQLite。
    结果缓存 60 秒避免每次请求都 ping。
    """
    return get_supabase() is not None
