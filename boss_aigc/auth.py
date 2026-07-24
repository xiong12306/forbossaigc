"""boss_aigc.auth JWT 认证模块。

单用户老板场景的轻量认证：
- 启动时从环境变量读取 BOSS_USERNAME / BOSS_PASSWORD_HASH
- POST /api/auth/login 校验账号密码，签发 JWT
- /api/auth/me 验证 token 并返回用户信息
- protect() 依赖项用于保护需要登录的路由

密码哈希使用 cryptography.fernet 或简单 bcrypt 风格；
本场景用 passlib[bcrypt] 过重，改用 hashlib + salt 做轻量实现。
"""

from __future__ import annotations

import os
import hashlib
import secrets
import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# 从环境变量读配置
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))

# 老板账号（单用户）
BOSS_USERNAME = os.environ.get("BOSS_USERNAME", "boss")
# 密码哈希：sha256(salt + password)，格式 "salt$hash"
# 首次启动若无配置，自动生成临时密码并打印
BOSS_PASSWORD_HASH = os.environ.get("BOSS_PASSWORD_HASH", "")


def _hash_password(password: str, salt: str = "") -> str:
    """sha256(salt + password)，返回 'salt$hash' 格式。"""
    if not salt:
        salt = secrets.token_hex(8)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${h}"


def _verify_password(password: str, stored: str) -> bool:
    """校验密码。stored 格式 'salt$hash'。"""
    try:
        salt, expected_hash = stored.split("$", 1)
        h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(h, expected_hash)
    except (ValueError, AttributeError):
        return False


def ensure_password_configured() -> str:
    """若未配置密码哈希，生成临时密码并返回（启动时调用）。

    返回值：已配置则返回空字符串；未配置则返回临时密码。
    """
    global BOSS_PASSWORD_HASH
    if BOSS_PASSWORD_HASH:
        return ""
    if not JWT_SECRET:
        return ""
    # 生成临时密码
    temp_password = secrets.token_urlsafe(8)
    BOSS_PASSWORD_HASH = _hash_password(temp_password)
    return temp_password


def create_access_token(username: str) -> str:
    """签发 JWT。"""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET 未配置，无法签发 token")
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT，失败返回 None。"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# ---------- FastAPI 路由 ----------

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    expires_in: int = JWT_EXPIRE_HOURS * 3600


class UserInfo(BaseModel):
    username: str


@auth_router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    """账号密码登录，返回 JWT。"""
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务未配置 JWT_SECRET，无法登录",
        )
    if body.username != BOSS_USERNAME or not _verify_password(body.password, BOSS_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token(body.username)
    return LoginResponse(access_token=token, username=body.username)


@auth_router.get("/me", response_model=UserInfo)
def me(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserInfo:
    """返回当前登录用户。"""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    payload = decode_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return UserInfo(username=payload.get("sub", ""))


def protect(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """路由保护依赖项。校验失败抛 401。

    用法：
        @auth_router.get("/secret", dependencies=[Depends(protect)])
        def secret(): ...
    """
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    payload = decode_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return payload


def is_auth_enabled() -> bool:
    """是否启用认证（配置了 JWT_SECRET 即视为启用）。"""
    return bool(JWT_SECRET)
