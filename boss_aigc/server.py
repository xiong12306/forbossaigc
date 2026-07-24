"""boss_aigc.server FastAPI HTTP 层。

把已实现的七层 Pipeline 通过 HTTP 暴露给前端，按 session_id 维护 SessionContext。
生产部署：
  - gunicorn boss_aigc.server:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
  - 前端构建后由本服务 StaticFiles 托管
启动开发模式：
  uvicorn boss_aigc.server:app --reload --port 8000
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from boss_aigc._e2e_test import build_full_pipeline
from boss_aigc.asset import AssetStore, create_default_asset_store
from boss_aigc.auth import (
    auth_router,
    ensure_password_configured,
    is_auth_enabled,
    decode_token,
)
from boss_aigc.contracts.enums import TaskStatus
from boss_aigc.pipeline import Pipeline, Response, SessionContext
from boss_aigc.db import init_db
from boss_aigc.api import dashboard, products, assets, marketing, service, finance

app = FastAPI(title="BossAIGC 老板 AI 助手 API", version="0.3.0")

# 初始化数据库
init_db()

# ---------- CORS 配置（环境变量化）----------
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175"
_allowed_origins = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 全局会话存储（内存，demo 级）----------
_shared_asset_store: AssetStore = create_default_asset_store()
_sessions: dict[str, tuple[Pipeline, SessionContext]] = {}

# 简易请求计数（供 /metrics 用）
_request_counter: dict[str, int] = {}


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, Pipeline, SessionContext]:
    """按 session_id 取/创建会话。首次传入 None 时新建。"""
    if session_id and session_id in _sessions:
        return session_id, *_sessions[session_id]
    new_id = session_id or uuid.uuid4().hex[:12]
    pipeline, ctx = build_full_pipeline(asset_store=_shared_asset_store)
    ctx.session_id = new_id
    _sessions[new_id] = (pipeline, ctx)
    return new_id, pipeline, ctx


# ---------- 认证中间件 ----------
# 白名单：登录、健康检查、metrics、文档
_AUTH_WHITELIST = {"/api/auth/login", "/api/health", "/metrics", "/", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """全局认证中间件。

    - 未配置 JWT_SECRET 时完全放行（dev 模式）
    - 配置了 JWT_SECRET 时，除白名单外 /api/* 需要 Bearer token
    """
    path = request.url.path
    # 统计请求
    _request_counter[path] = _request_counter.get(path, 0) + 1

    # 静态资源、白名单、非 /api 路径直接放行
    if (
        not path.startswith("/api")
        or path in _AUTH_WHITELIST
        or not is_auth_enabled()
    ):
        return await call_next(request)

    # /api/* 需要 token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        payload = decode_token(token)
        if payload is not None:
            return await call_next(request)

    return JSONResponse(
        status_code=401,
        content={"detail": "未认证或 token 已过期，请先登录"},
    )


# ---------- 请求/响应模型 ----------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class SummaryOut(BaseModel):
    task_type: str
    product: Optional[str] = None
    params: dict[str, Any] = {}
    platform: str = "mock"
    estimated_duration_sec: int = 0
    estimated_cost: int = 0
    is_high_cost: bool = False


class ArtifactOut(BaseModel):
    artifact_id: str
    kind: str
    url_or_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: dict[str, Any] = {}


class TimelineNode(BaseModel):
    label: str
    status: str  # done / active / pending


class ChatResponse(BaseModel):
    session_id: str
    status: str
    message: str
    speak_text: Optional[str] = None
    follow_up_question: Optional[str] = None
    summary: Optional[SummaryOut] = None
    artifacts: Optional[list[ArtifactOut]] = None
    timeline: list[TimelineNode] = []


class ResetRequest(BaseModel):
    session_id: str


class ResetResponse(BaseModel):
    session_id: str


# ---------- 状态时间线构建 ----------

_TIMELINE_LABELS = ["理解指令", "确认任务", "执行生成", "交付产出", "验收归档"]


def _build_timeline(status: TaskStatus) -> list[TimelineNode]:
    """根据当前 status 构造时间线节点状态。"""
    status_to_stage = {
        TaskStatus.PENDING: 0,
        TaskStatus.UNDERSTANDING: 0,
        TaskStatus.AWAITING_CONFIRMATION: 1,
        TaskStatus.CONFIRMED: 2,
        TaskStatus.EXECUTING: 2,
        TaskStatus.DELIVERED: 3,
        TaskStatus.ACCEPTED: 4,
        TaskStatus.CANCELLED: 0,
        TaskStatus.FAILED: 2,
    }
    current = status_to_stage.get(status, 0)
    nodes: list[TimelineNode] = []
    for idx, label in enumerate(_TIMELINE_LABELS):
        if idx < current:
            nodes.append(TimelineNode(label=label, status="done"))
        elif idx == current:
            nodes.append(TimelineNode(label=label, status="active"))
        else:
            nodes.append(TimelineNode(label=label, status="pending"))
    if status in (TaskStatus.CANCELLED, TaskStatus.FAILED):
        nodes[current] = TimelineNode(label=_TIMELINE_LABELS[current], status="cancelled")
    return nodes


# ---------- 从 context 组装 ChatResponse ----------

def _summary_to_out(summary) -> Optional[SummaryOut]:
    if summary is None:
        return None
    return SummaryOut(
        task_type=summary.task_type.value if hasattr(summary.task_type, "value") else str(summary.task_type),
        product=summary.product,
        params=summary.params,
        platform=summary.platform.value if hasattr(summary.platform, "value") else str(summary.platform),
        estimated_duration_sec=summary.estimated_duration_sec,
        estimated_cost=summary.estimated_cost,
        is_high_cost=summary.is_high_cost,
    )


def _artifacts_to_out(result) -> Optional[list[ArtifactOut]]:
    if result is None or not getattr(result, "artifacts", None):
        return None
    out: list[ArtifactOut] = []
    for a in result.artifacts:
        out.append(ArtifactOut(
            artifact_id=a.artifact_id,
            kind=a.kind,
            url_or_path=a.url_or_path,
            thumbnail_path=a.thumbnail_path,
            metadata=a.metadata,
        ))
    return out


def _build_chat_response(resp: Response, ctx: SessionContext) -> ChatResponse:
    """把 Pipeline Response + context.extras 组装成前端可用的 ChatResponse。"""
    status_val = ctx.status.value if hasattr(ctx.status, "value") else str(ctx.status)
    speak_text = ctx.extras.get("speak_text")
    follow_up = ctx.extras.get("follow_up_question")

    summary_out = None
    if ctx.status in (TaskStatus.AWAITING_CONFIRMATION, TaskStatus.CONFIRMED):
        summary_out = _summary_to_out(ctx.pending_summary)

    artifacts_out = None
    if ctx.status in (TaskStatus.DELIVERED, TaskStatus.ACCEPTED):
        artifacts_out = _artifacts_to_out(ctx.result)

    return ChatResponse(
        session_id=ctx.session_id,
        status=status_val,
        message=resp.message,
        speak_text=speak_text,
        follow_up_question=follow_up,
        summary=summary_out,
        artifacts=artifacts_out,
        timeline=_build_timeline(ctx.status),
    )


# ---------- 业务路由 ----------

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """处理一轮老板输入，返回助手反馈。"""
    session_id, pipeline, ctx = _get_or_create_session(req.session_id)
    resp = pipeline.handle_user_input(req.message, ctx)
    return _build_chat_response(resp, ctx)


@app.post("/api/reset", response_model=ResetResponse)
def reset(req: ResetRequest) -> ResetResponse:
    """重置会话。"""
    _sessions.pop(req.session_id, None)
    return ResetResponse(session_id=req.session_id)


@app.get("/api/health")
def health() -> dict:
    """健康检查：服务状态 + 会话数 + 认证状态。"""
    return {
        "ok": True,
        "service": "BossAIGC",
        "version": "0.3.0",
        "sessions": len(_sessions),
        "auth_enabled": is_auth_enabled(),
    }


@app.get("/metrics")
def metrics() -> dict:
    """简易监控指标（Prometheus 文本格式可用 prometheus_client 扩展）。"""
    return {
        "sessions_active": len(_sessions),
        "request_total": sum(_request_counter.values()),
        "request_by_path": dict(_request_counter),
        "uptime_sec": int(time.time() - _START_TIME),
    }


_START_TIME = time.time()


# ---------- 平台业务 API 路由 ----------
app.include_router(auth_router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(assets.router)
app.include_router(marketing.router)
app.include_router(service.router)
app.include_router(finance.router)


# ---------- 前端静态文件托管（生产模式）----------

class SPAStaticFiles(StaticFiles):
    """SPA 静态文件托管：未匹配路径返回 index.html，支持前端路由。"""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:
            # StaticFiles 文件不存在时抛 HTTPException(404)
            # 对非 API 路径返回 index.html（SPA fallback）
            if not path.startswith("api"):
                index_file = Path(self.directory) / "index.html"
                if index_file.is_file():
                    return FileResponse(str(index_file), media_type="text/html")
            raise


_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    # 前端构建产物（npm run build）输出到 boss_aigc/static/
    app.mount("/", SPAStaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")


# ---------- 启动事件 ----------
@app.on_event("startup")
async def _on_startup():
    """启动时检查配置，打印临时密码（若自动生成）。"""
    temp_pw = ensure_password_configured()
    if temp_pw:
        print("\n" + "=" * 60)
        print("⚠️  未配置 BOSS_PASSWORD_HASH，已生成临时密码：")
        print(f"    用户名：{os.environ.get('BOSS_USERNAME', 'boss')}")
        print(f"    密码：{temp_pw}")
        print("    请尽快在 .env 中设置 BOSS_PASSWORD_HASH（环境变量）。")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
