"""boss_aigc.api.canvas 无限画布专用API。

支持异步生图（submit+poll）和同步生图（generate）。
按 model 参数分发到 ModelScope / SiliconFlow / NanoBanana 平台。
任务持久化到 SQLite，支持刷新恢复。
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import uuid
import json
import time
import threading
from pathlib import Path
from typing import Any
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from boss_aigc.config import get_settings
from boss_aigc.db import get_conn
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="api")

router = APIRouter(prefix="/api/canvas", tags=["canvas"])

_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

_SIZE_MAP: dict[str, str] = {
    "1:1": "1024x1024",
    "3:4": "768x1024",
    "4:3": "1024x768",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "2k": "1536x2048",
}

_PRESET_PROMPTS: dict[str, str] = {
    "main": "商品主图，纯白色背景，商品居中放置，主体占画面70%，45度侧角拍摄，专业电商摄影",
    "detail": "详情图，浅色纯净背景，商品细节微距特写，展示材质纹理、工艺接缝，浅景深虚化背景",
    "scene": "场景图，真实生活场景，商品自然融入使用环境，自然窗光柔和照射",
    "poster": "营销海报，简约大气背景，商品居中突出，精致光影设计感，高端品牌质感",
    "white_bg": "白底图，纯白背景#FFFFFF，商品正面居中，均匀无影照明，电商上架标准图",
    "model": "模特图，真人模特手持/穿戴商品，自然姿态，棚拍柔光，肤色真实自然",
    "contrast": "对比图，左右对比布局，使用前vs使用后，突出效果差异，信息图风格",
    "lifestyle": "生活方式图，商品融入真实使用场景，生活化构图，温暖自然光",
    "detail_macro": "细节微距图，极近距离特写，展示材质纹理和做工细节，专业微距摄影",
    "multi_angle": "多角度图，商品45度/正面/侧面三视角，白色背景，全方位展示",
    "infographic": "信息图，商品功能标注图，箭头指示关键卖点，简洁扁平设计风格",
    "carousel": "轮播图，适合电商详情页，商品不同角度切换，统一色调风格",
}

# 预设分类（供前端分组展示）
_PRESET_CATEGORIES: list[dict[str, Any]] = [
    {"id": "basic", "name": "基础", "presets": ["main", "detail", "scene", "poster"]},
    {"id": "ecommerce", "name": "电商", "presets": ["white_bg", "model", "contrast", "carousel"]},
    {"id": "detail", "name": "细节", "presets": ["detail_macro", "multi_angle", "infographic"]},
    {"id": "scene", "name": "场景", "presets": ["scene", "lifestyle"]},
]

# 错误分类映射：HTTP状态码/关键词 → error_kind
def _classify_error(status_code: int, detail: str) -> str:
    """将错误归类为前端可识别的 error_kind。"""
    detail_lower = detail.lower()
    if status_code == 429 or "rate" in detail_lower or "limit" in detail_lower:
        return "rate_limit"
    if status_code == 504 or "timeout" in detail_lower or "超时" in detail:
        return "timeout"
    if status_code == 400 or "不存在" in detail or "invalid" in detail_lower:
        return "invalid_input"
    if status_code == 503 or "未配置" in detail or "key" in detail_lower:
        return "config_error"
    if status_code in (500, 502):
        return "platform_error"
    return "unknown"

# 错误建议文案
_ERROR_SUGGESTIONS: dict[str, str] = {
    "rate_limit": "平台限流，建议等待30秒后重试，或切换其他模型",
    "timeout": "生成超时（5分钟），可能排队较多，建议稍后重试",
    "invalid_input": "输入参数有误，请检查参考图是否存在、prompt是否为空",
    "config_error": "平台API Key未配置，请联系管理员",
    "platform_error": "生图平台异常，建议切换模型重试",
    "unknown": "未知错误，建议重试或切换模型",
}

_QUALITY_SUFFIX = (
    "professional product photography, 8k, high detail, "
    "sharp focus, accurate color, photorealistic"
)

_NEGATIVE_PROMPT = (
    "low quality, blurry, distorted, deformed, watermark, text, signature, "
    "logo, brand name, error, worst quality, low resolution, jpeg artifacts, "
    "bad anatomy, extra limbs, disfigured, mosaic, pixelated, "
    "dark background, colored background, shadow on product, "
    "product not centered, cropped product, tilted composition"
)


class CanvasGenerateRequest(BaseModel):
    prompt: str = ""
    reference_images: list[str] = []
    reference_texts: list[str] = []
    model: str = "modelscope"  # modelscope | siliconflow | nanobanana
    size: str = "1:1"
    preset: str = "main"


class CanvasGenerateResponse(BaseModel):
    image_url: str
    prompt_used: str
    model_used: str


# ============ 异步任务系统 ============

class CanvasSubmitRequest(BaseModel):
    prompt: str = ""
    reference_images: list[str] = []
    reference_texts: list[str] = []
    model: str = "modelscope"
    size: str = "1:1"
    preset: str = "main"


class CanvasSubmitResponse(BaseModel):
    task_id: str
    status: str = "pending"


class CanvasTaskStatus(BaseModel):
    task_id: str
    status: str  # pending | running | succeeded | failed
    stage: str = ""  # submitting | queued | generating | downloading | done
    image_url: str = ""
    error: str = ""
    error_kind: str = ""
    error_suggestion: str = ""
    prompt_used: str = ""
    model_used: str = ""
    created_at: float = 0.0


# 内存任务存储（带锁）
_canvas_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()
_TASK_TTL = 3600  # 任务记录保留1小时


def _set_task(task_id: str, **fields) -> None:
    with _tasks_lock:
        task = _canvas_tasks.get(task_id)
        if task is None:
            task = {"task_id": task_id, "created_at": time.time(), "status": "pending", "stage": ""}
        task.update(fields)
        _canvas_tasks[task_id] = task
        # 同时持久化到DB
        _persist_task(task)


def _get_task(task_id: str) -> dict | None:
    with _tasks_lock:
        task = _canvas_tasks.get(task_id)
        if task:
            return dict(task)
    # 尝试从DB加载
    return _load_task_from_db(task_id)


def _cleanup_old_tasks() -> None:
    """清理超过TTL的已完成任务。"""
    now = time.time()
    with _tasks_lock:
        expired = [tid for tid, t in _canvas_tasks.items()
                   if now - t.get("created_at", 0) > _TASK_TTL and t.get("status") in ("succeeded", "failed")]
        for tid in expired:
            del _canvas_tasks[tid]


def _persist_task(task: dict) -> None:
    """持久化任务到SQLite。"""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO canvas_tasks "
                "(task_id, status, stage, image_url, error, error_kind, prompt_used, model_used, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    task["task_id"],
                    task.get("status", "pending"),
                    task.get("stage", ""),
                    task.get("image_url", ""),
                    task.get("error", ""),
                    task.get("error_kind", ""),
                    task.get("prompt_used", ""),
                    task.get("model_used", ""),
                    datetime.fromtimestamp(task.get("created_at", time.time())).isoformat(),
                    datetime.now().isoformat(),
                )
            )
    except Exception as e:
        logger.warning("持久化任务失败: %s", e)


def _load_task_from_db(task_id: str) -> dict | None:
    """从SQLite加载任务。"""
    try:
        with get_conn() as conn:
            r = conn.execute(
                "SELECT * FROM canvas_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        if not r:
            return None
        created_at = time.time()
        try:
            created_at = datetime.fromisoformat(r["created_at"]).timestamp()
        except Exception:
            pass
        return {
            "task_id": r["task_id"],
            "status": r["status"],
            "stage": r["stage"] or "",
            "image_url": r["image_url"] or "",
            "error": r["error"] or "",
            "error_kind": r["error_kind"] or "",
            "prompt_used": r["prompt_used"] or "",
            "model_used": r["model_used"] or "",
            "created_at": created_at,
        }
    except Exception as e:
        logger.warning("加载任务失败: %s", e)
        return None


async def _run_generation_task(task_id: str, req: CanvasSubmitRequest) -> None:
    """后台执行生图任务，更新任务状态。"""
    _set_task(task_id, status="running", stage="submitting")
    try:
        final_prompt = _build_final_prompt(req)
        ref_data_uris = _resolve_ref_images(req)

        model = (req.model or "").lower()
        settings = get_settings()
        if not model:
            if settings.platform_provider == "siliconflow" and settings.siliconflow_api_key:
                model = "siliconflow"
            elif settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
                model = "nanobanana"
            else:
                model = "modelscope"

        _set_task(task_id, stage="queued", prompt_used=final_prompt)

        result: CanvasGenerateResponse | None = None

        if model == "nanobanana":
            _set_task(task_id, stage="generating")
            result = await _generate_via_nanobanana(req, final_prompt, ref_data_uris)
        elif model == "siliconflow":
            _set_task(task_id, stage="generating")
            result = await _generate_via_siliconflow(req, final_prompt, ref_data_uris)
        else:
            _set_task(task_id, stage="generating")
            try:
                result = await _generate_via_modelscope(req, final_prompt, ref_data_uris)
            except HTTPException as e:
                if e.status_code in (429, 502, 503, 504):
                    if settings.siliconflow_api_key:
                        logger.warning("ModelScope 不可用（%d），降级到 SiliconFlow", e.status_code)
                        _set_task(task_id, stage="generating")
                        try:
                            result = await _generate_via_siliconflow(req, final_prompt, ref_data_uris)
                        except HTTPException:
                            pass
                    if result is None and settings.nanobanana_api_key:
                        logger.warning("降级到 NanoBanana")
                        _set_task(task_id, stage="generating")
                        result = await _generate_via_nanobanana(req, final_prompt, ref_data_uris)
                if result is None:
                    raise

        if result and result.image_url:
            _set_task(
                task_id,
                status="succeeded",
                stage="done",
                image_url=result.image_url,
                model_used=result.model_used,
            )
        else:
            _set_task(
                task_id,
                status="failed",
                stage="",
                error="未返回图片",
                error_kind="platform_error",
                error_suggestion=_ERROR_SUGGESTIONS["platform_error"],
            )
    except HTTPException as e:
        err_kind = _classify_error(e.status_code, str(e.detail))
        _set_task(
            task_id,
            status="failed",
            stage="",
            error=str(e.detail),
            error_kind=err_kind,
            error_suggestion=_ERROR_SUGGESTIONS.get(err_kind, _ERROR_SUGGESTIONS["unknown"]),
        )
    except Exception as e:
        err_kind = _classify_error(500, str(e))
        _set_task(
            task_id,
            status="failed",
            stage="",
            error=str(e)[:200],
            error_kind=err_kind,
            error_suggestion=_ERROR_SUGGESTIONS.get(err_kind, _ERROR_SUGGESTIONS["unknown"]),
        )
    finally:
        _cleanup_old_tasks()


@router.post("/submit", response_model=CanvasSubmitResponse)
async def canvas_submit(req: CanvasSubmitRequest) -> CanvasSubmitResponse:
    """异步提交生图任务，立即返回 task_id。"""
    _cleanup_old_tasks()
    task_id = f"task-{uuid.uuid4().hex[:16]}"
    _set_task(task_id, status="pending", stage="submitting", prompt_used=req.prompt)
    # 启动后台任务
    asyncio.create_task(_run_generation_task(task_id, req))
    return CanvasSubmitResponse(task_id=task_id, status="pending")


@router.get("/status/{task_id}", response_model=CanvasTaskStatus)
async def canvas_status(task_id: str) -> CanvasTaskStatus:
    """查询任务状态。"""
    task = _get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return CanvasTaskStatus(
        task_id=task["task_id"],
        status=task.get("status", "pending"),
        stage=task.get("stage", ""),
        image_url=task.get("image_url", ""),
        error=task.get("error", ""),
        error_kind=task.get("error_kind", ""),
        error_suggestion=task.get("error_suggestion", ""),
        prompt_used=task.get("prompt_used", ""),
        model_used=task.get("model_used", ""),
        created_at=task.get("created_at", 0.0),
    )


@router.get("/presets")
async def get_presets() -> dict:
    """获取预设列表和分类。"""
    return {
        "presets": {k: v for k, v in _PRESET_PROMPTS.items()},
        "categories": _PRESET_CATEGORIES,
    }


def _resolve_local_image(url_path: str) -> str:
    """将 /uploads/xxx.png 路径转为 base64 data URI。"""
    if url_path.startswith(("http://", "https://", "data:")):
        return url_path
    filename = Path(url_path).name
    filepath = _UPLOAD_DIR / filename
    if not filepath.is_file():
        raise HTTPException(status_code=400, detail=f"参考图片不存在: {filename}")
    mime, _ = mimetypes.guess_type(str(filepath))
    mime = mime or "image/png"
    data = base64.b64encode(filepath.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


async def _download_image(client: httpx.AsyncClient, url: str) -> str:
    """下载远程图片到本地 uploads/ 目录，返回 /uploads/xxx.png 路径。"""
    _UPLOAD_DIR.mkdir(exist_ok=True)
    ext = ".png"
    path_str = url.split("?")[0].lower()
    for candidate in (".png", ".jpg", ".jpeg", ".webp"):
        if candidate in path_str[-8:]:
            ext = candidate
            break
    filename = f"gen-{uuid.uuid4().hex[:12]}{ext}"
    filepath = _UPLOAD_DIR / filename
    async with client.stream("GET", url, follow_redirects=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            async for chunk in r.aiter_bytes(chunk_size=65536):
                f.write(chunk)
    local_url = f"/uploads/{filename}"
    logger.info("图片已下载: %s", local_url)
    return local_url


def _build_final_prompt(req: CanvasGenerateRequest) -> str:
    """构建最终 prompt：预设 + 参考文本 + 用户prompt + 质量后缀。"""
    prompt_parts: list[str] = []
    preset_desc = _PRESET_PROMPTS.get(req.preset)
    if preset_desc:
        prompt_parts.append(preset_desc)
    for text in req.reference_texts:
        text = text.strip()
        if text:
            prompt_parts.append(text)
    user_prompt = req.prompt.strip()
    if user_prompt:
        prompt_parts.append(user_prompt)
    prompt_parts.append(_QUALITY_SUFFIX)
    return "，".join(prompt_parts)


def _resolve_ref_images(req: CanvasGenerateRequest) -> list[str]:
    """解析参考图为 data URI 列表。"""
    ref_data_uris: list[str] = []
    for img_url in req.reference_images:
        try:
            ref_data_uris.append(_resolve_local_image(img_url))
        except HTTPException:
            logger.warning("参考图解析失败，跳过: %s", img_url)
    return ref_data_uris


# ============ NanoBanana 平台调用 ============

def _nanobanana_generate_sync(
    api_key: str,
    api_base: str,
    prompt: str,
    ref_data_uris: list[str],
    timeout: float,
) -> str:
    """同步调用 NanoBanana API，返回远程图片 URL。

    NanoBanana 通过 Ace Data Cloud 接入，POST /nano-banana/images 同步返回结果。
    支持参考图（image_url 字段传 data URI）。使用 httpx.Client 替代 requests。
    """
    url = f"{api_base.rstrip('/')}/images"
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "application/json",
        "content-type": "application/json",
    }
    payload: dict[str, Any] = {
        "action": "generate",
        "prompt": prompt,
        "model": "nano-banana-pro",  # Ace Data Cloud 要求显式指定模型
    }
    if ref_data_uris:
        payload["image_url"] = ref_data_uris[0]  # NanoBanana 单参考图

    with httpx.Client(trust_env=False, timeout=timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        result = resp.json()

    # 兼容多种响应格式提取图片 URL
    for key in ["url", "image_url", "image", "data", "images", "result", "output"]:
        value = result.get(key) if isinstance(result, dict) else None
        if value is None:
            continue
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
        if isinstance(value, list) and len(value) > 0:
            first = value[0]
            if isinstance(first, str) and first.startswith(("http://", "https://")):
                return first
            if isinstance(first, dict):
                for nested_key in ["url", "image_url", "image"]:
                    nested_val = first.get(nested_key)
                    if isinstance(nested_val, str) and nested_val.startswith(("http://", "https://")):
                        return nested_val
        if isinstance(value, dict):
            for nested_key in ["url", "image_url", "image"]:
                nested_val = value.get(nested_key)
                if isinstance(nested_val, str) and nested_val.startswith(("http://", "https://")):
                    return nested_val

    raise HTTPException(status_code=502, detail=f"NanoBanana 返回未含图片URL: {str(result)[:200]}")


async def _generate_via_nanobanana(req: CanvasGenerateRequest, final_prompt: str, ref_data_uris: list[str]) -> CanvasGenerateResponse:
    """通过 NanoBanana 生成图片（同步API，用线程池避免阻塞事件循环）。"""
    settings = get_settings()
    if not settings.nanobanana_api_key:
        raise HTTPException(status_code=503, detail="NanoBanana API key 未配置")

    api_base = settings.nanobanana_api_base
    api_key = settings.nanobanana_api_key
    timeout = min(settings.request_timeout_sec, 180.0)

    logger.info("NanoBanana 画布生成: refs=%d prompt=%s", len(ref_data_uris), final_prompt[:100])

    # 重试 3 次
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            remote_url = await asyncio.to_thread(
                _nanobanana_generate_sync,
                api_key, api_base, final_prompt, ref_data_uris, timeout,
            )
            # 下载到本地
            async with httpx.AsyncClient(trust_env=False, http2=False) as client:
                try:
                    local_url = await _download_image(client, remote_url)
                except Exception as e:
                    logger.warning("NanoBanana 下载失败，使用原始URL: %s", e)
                    local_url = remote_url

            return CanvasGenerateResponse(
                image_url=local_url,
                prompt_used=final_prompt,
                model_used="nanobanana",
            )
        except HTTPException:
            raise
        except httpx.TimeoutException as e:
            last_err = e
            logger.warning("NanoBanana 超时（重试%d/3）", attempt + 1)
        except httpx.RequestError as e:
            last_err = e
            logger.warning("NanoBanana 请求失败（重试%d/3）: %s", attempt + 1, str(e)[:100])
        except Exception as e:
            last_err = e
            logger.warning("NanoBanana 未知错误（重试%d/3）: %s", attempt + 1, str(e)[:100])

        if attempt < 2:
            await asyncio.sleep(2)

    raise HTTPException(status_code=502, detail=f"NanoBanana 生成失败（重试3次）: {last_err}")


# ============ ModelScope 平台调用 ============

async def _generate_via_modelscope(req: CanvasGenerateRequest, final_prompt: str, ref_data_uris: list[str]) -> CanvasGenerateResponse:
    """通过 ModelScope 异步生成图片（提交+轮询）。"""
    settings = get_settings()
    if not settings.modelscope_api_key:
        raise HTTPException(status_code=503, detail="ModelScope API key 未配置")

    ms_size = _SIZE_MAP.get(req.size, "1024x1024")
    is_edit = len(ref_data_uris) > 0
    model_name = "Qwen/Qwen-Image-Edit-2509" if is_edit else settings.modelscope_model

    logger.info("ModelScope 画布生成: is_edit=%s refs=%d model=%s prompt=%s",
                is_edit, len(ref_data_uris), model_name, final_prompt[:120])

    api_base = settings.modelscope_api_base.rstrip("/")
    api_key = settings.modelscope_api_key

    body: dict[str, Any] = {
        "prompt": final_prompt,
        "size": ms_size,
        "model": model_name,
    }
    # Qwen-Image-Edit 参考图参数：input.image 传单个图片URL或data URI
    if is_edit:
        body["input"] = {"image": ref_data_uris[0]}
        body["negative_prompt"] = _NEGATIVE_PROMPT
    else:
        body["negative_prompt"] = _NEGATIVE_PROMPT

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true",
    }

    submit_timeout = httpx.Timeout(connect=15.0, read=180.0, write=180.0, pool=15.0)
    poll_timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

    async with httpx.AsyncClient(trust_env=False, http2=False) as client:
        # 1. 提交任务（带重试，包括429限流等待）
        resp = None
        for attempt in range(5):
            try:
                resp = await client.post(
                    f"{api_base}/images/generations",
                    json=body,
                    headers=headers,
                    timeout=submit_timeout,
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    wait_sec = min(retry_after, 15)
                    logger.warning("ModelScope 限流429，等待%ds后重试（%d/5）", wait_sec, attempt + 1)
                    await asyncio.sleep(wait_sec)
                    continue
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 4:
                    retry_after = int(e.response.headers.get("Retry-After", "5"))
                    wait_sec = min(retry_after, 15)
                    logger.warning("ModelScope 限流429，等待%ds后重试（%d/5）", wait_sec, attempt + 1)
                    await asyncio.sleep(wait_sec)
                    continue
                raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning("提交失败（重试%d/5）: %s", attempt + 1, type(e).__name__)
                if attempt == 4:
                    raise HTTPException(status_code=502, detail=f"ModelScope 提交失败: {e}")
                await asyncio.sleep(2)

        if resp is None:
            raise HTTPException(status_code=502, detail="ModelScope 提交失败：无响应")

        submit_data = resp.json()
        ms_task_id = submit_data.get("task_id")
        if not ms_task_id:
            # 同步返回（部分模型可能同步返回结果）
            images = submit_data.get("images") or submit_data.get("output_images") or []
            if images:
                remote_url = images[0] if isinstance(images[0], str) else images[0].get("url", "")
                if remote_url:
                    try:
                        local_url = await _download_image(client, remote_url)
                    except Exception as e:
                        logger.warning("下载失败，使用原始 URL: %s", e)
                        local_url = remote_url
                    return CanvasGenerateResponse(
                        image_url=local_url, prompt_used=final_prompt, model_used="modelscope"
                    )
            raise HTTPException(status_code=502, detail=f"未返回 task_id: {str(submit_data)[:200]}")

        logger.info("任务已提交: ms_task_id=%s", ms_task_id)

        # 2. 异步轮询
        poll_url = f"{api_base}/tasks/{ms_task_id}"
        poll_headers = {
            "Authorization": f"Bearer {api_key}",
            "X-ModelScope-Task-Type": "image_generation",
        }

        deadline = asyncio.get_event_loop().time() + 300  # 5分钟超时
        poll_count = 0
        consecutive_failures = 0

        while True:
            try:
                r = await client.get(poll_url, headers=poll_headers, timeout=poll_timeout)
                if r.status_code == 429:
                    await asyncio.sleep(5)
                    continue
                r.raise_for_status()
                data = r.json()
                consecutive_failures = 0
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                consecutive_failures += 1
                logger.warning("轮询失败（连续%d次）: %s", consecutive_failures, type(e).__name__)
                if consecutive_failures >= 10:
                    raise HTTPException(status_code=502, detail=f"连续轮询失败: {e}")
                await asyncio.sleep(3)
                continue

            status = data.get("task_status")
            logger.info("轮询 #%d: status=%s", poll_count + 1, status)

            if status == "SUCCEED":
                images = data.get("output_images") or data.get("images") or []
                if not images and "outputs" in data:
                    for out in (data.get("outputs") or []):
                        if isinstance(out, dict):
                            url = out.get("url") or out.get("image_url") or out.get("image")
                            if url:
                                images.append(url)
                        elif isinstance(out, str):
                            images.append(out)
                if not images:
                    raise HTTPException(status_code=500, detail=f"SUCCEED 但未找到图片: {str(data)[:200]}")

                remote_url = images[0] if isinstance(images[0], str) else (images[0].get("url") or images[0].get("image_url", ""))
                try:
                    local_url = await _download_image(client, remote_url)
                except Exception as e:
                    logger.warning("下载失败，使用原始 URL: %s", e)
                    local_url = remote_url

                return CanvasGenerateResponse(
                    image_url=local_url,
                    prompt_used=final_prompt,
                    model_used="modelscope",
                )

            if status == "FAILED":
                raise HTTPException(status_code=500, detail=f"生成失败: {str(data)[:200]}")

            if status not in ("PROCESSING", "PENDING", "RUNNING"):
                raise HTTPException(status_code=500, detail=f"未知状态: {status}")

            if asyncio.get_event_loop().time() > deadline:
                raise HTTPException(status_code=504, detail="生成超时（5分钟）")

            poll_count += 1
            if poll_count <= 3:
                wait = 1.5
            elif poll_count <= 10:
                wait = 3.0
            else:
                wait = 5.0
            await asyncio.sleep(wait)


# ============ SiliconFlow 平台调用 ============

def _siliconflow_generate_sync(
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    image_size: str,
    ref_data_uris: list[str],
    timeout: float,
) -> str:
    """同步调用 SiliconFlow API，返回远程图片 URL。

    SiliconFlow 是同步 API：POST /images/generations 返回 images[0].url。
    文生图不传 image；图生图传 image 字段为 base64 data URI。
    多参考图时传数组（部分模型支持），单图传字符串保持兼容。
    生成的 URL 有效期仅 1 小时，必须立即下载转存。
    """
    url = f"{api_base.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "image_size": image_size,
    }
    if len(ref_data_uris) == 1:
        body["image"] = ref_data_uris[0]
    elif len(ref_data_uris) > 1:
        # 多参考图：传数组（Qwen-Image-Edit 等模型支持多图输入）
        body["image"] = ref_data_uris

    with httpx.Client(trust_env=False, http2=False) as client:
        resp = client.post(url, json=body, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

    images = data.get("images") or []
    if not images and data.get("data"):
        images = data["data"]
    if not images or not images[0].get("url"):
        raise HTTPException(status_code=502, detail=f"SiliconFlow 返回未含图片URL: {str(data)[:200]}")
    return images[0]["url"]


async def _generate_via_siliconflow(req: CanvasGenerateRequest, final_prompt: str, ref_data_uris: list[str]) -> CanvasGenerateResponse:
    """通过 SiliconFlow 生成图片（同步API，用线程池避免阻塞事件循环）。"""
    settings = get_settings()
    if not settings.siliconflow_api_key:
        raise HTTPException(status_code=503, detail="SiliconFlow API key 未配置")

    sf_size = _SIZE_MAP.get(req.size, "1024x1024")
    is_edit = len(ref_data_uris) > 0
    model_name = settings.siliconflow_edit_model if is_edit else settings.siliconflow_model

    logger.info("SiliconFlow 画布生成: is_edit=%s refs=%d model=%s prompt=%s",
                is_edit, len(ref_data_uris), model_name, final_prompt[:120])

    api_base = settings.siliconflow_api_base
    api_key = settings.siliconflow_api_key
    timeout = httpx.Timeout(connect=15.0, read=120.0, write=60.0, pool=15.0)

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            remote_url = await asyncio.to_thread(
                _siliconflow_generate_sync,
                api_key, api_base, model_name, final_prompt, sf_size, ref_data_uris, timeout,
            )
            async with httpx.AsyncClient(trust_env=False, http2=False) as client:
                try:
                    local_url = await _download_image(client, remote_url)
                except Exception as e:
                    logger.warning("SiliconFlow 下载失败，使用原始URL: %s", e)
                    local_url = remote_url

            return CanvasGenerateResponse(
                image_url=local_url,
                prompt_used=final_prompt,
                model_used="siliconflow",
            )
        except HTTPException:
            raise
        except httpx.TimeoutException as e:
            last_err = e
            logger.warning("SiliconFlow 超时（重试%d/3）", attempt + 1)
        except httpx.RequestError as e:
            last_err = e
            logger.warning("SiliconFlow 请求失败（重试%d/3）: %s", attempt + 1, str(e)[:100])
        except Exception as e:
            last_err = e
            logger.warning("SiliconFlow 未知错误（重试%d/3）: %s", attempt + 1, str(e)[:100])

        if attempt < 2:
            await asyncio.sleep(2)

    raise HTTPException(status_code=502, detail=f"SiliconFlow 生成失败（重试3次）: {last_err}")


# ============ 主入口：按 model 分发 ============

@router.post("/generate", response_model=CanvasGenerateResponse)
async def canvas_generate(req: CanvasGenerateRequest) -> CanvasGenerateResponse:
    """画布异步生成图片，按 model 参数分发到对应平台。

    用户指定模型优先（modelscope|siliconflow|nanobanana）。
    未显式指定时按 PLATFORM_PROVIDER 选默认平台。
    当前用户指定的平台失败时，可降级到其他可用平台。
    """
    final_prompt = _build_final_prompt(req)
    ref_data_uris = _resolve_ref_images(req)

    model = (req.model or "").lower()
    settings = get_settings()

    # 未指定时按 PLATFORM_PROVIDER 选默认
    if not model:
        if settings.platform_provider == "siliconflow" and settings.siliconflow_api_key:
            model = "siliconflow"
        elif settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
            model = "nanobanana"
        else:
            model = "modelscope"

    # 用户指定模型优先
    if model == "nanobanana":
        return await _generate_via_nanobanana(req, final_prompt, ref_data_uris)
    if model == "siliconflow":
        return await _generate_via_siliconflow(req, final_prompt, ref_data_uris)

    # 默认走 ModelScope，失败时尝试降级
    try:
        return await _generate_via_modelscope(req, final_prompt, ref_data_uris)
    except HTTPException as e:
        # 429/502/503/504 时按顺序尝试 SiliconFlow → NanoBanana
        if e.status_code in (429, 502, 503, 504):
            if settings.siliconflow_api_key:
                logger.warning("ModelScope 不可用（%d），降级到 SiliconFlow", e.status_code)
                try:
                    return await _generate_via_siliconflow(req, final_prompt, ref_data_uris)
                except HTTPException:
                    pass
            if settings.nanobanana_api_key:
                logger.warning("降级到 NanoBanana", e.status_code)
                return await _generate_via_nanobanana(req, final_prompt, ref_data_uris)
        raise


# ============ 画布持久化 API ============

def _now() -> str:
    return datetime.now().isoformat()


class CanvasSaveRequest(BaseModel):
    canvas_id: str | None = None
    name: str = "未命名画布"
    nodes: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []


class CanvasInfo(BaseModel):
    canvas_id: str
    name: str
    owner: str
    thumbnail_url: str
    created_at: str
    updated_at: str
    node_count: int
    connection_count: int


class CanvasDetail(CanvasInfo):
    nodes: list[dict[str, Any]]
    connections: list[dict[str, Any]]


@router.get("/list", response_model=list[CanvasInfo])
async def list_canvases(owner: str = Query("boss")):
    """获取用户的所有画布列表（按更新时间倒序）。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT canvas_id, name, owner, thumbnail_url, created_at, updated_at, "
            "nodes_json, connections_json FROM canvases WHERE owner = ? ORDER BY updated_at DESC LIMIT 50",
            (owner,)
        ).fetchall()
    result = []
    for r in rows:
        try:
            nodes = json.loads(r["nodes_json"])
            conns = json.loads(r["connections_json"])
        except (json.JSONDecodeError, TypeError):
            nodes, conns = [], []
        result.append(CanvasInfo(
            canvas_id=r["canvas_id"], name=r["name"], owner=r["owner"],
            thumbnail_url=r["thumbnail_url"] or "",
            created_at=r["created_at"], updated_at=r["updated_at"],
            node_count=len(nodes), connection_count=len(conns),
        ))
    return result


@router.post("/save", response_model=CanvasDetail)
async def save_canvas(req: CanvasSaveRequest, owner: str = Query("boss")):
    """保存画布节点和连线到数据库。canvas_id 为空则新建。"""
    now = _now()
    canvas_id = req.canvas_id or f"canvas-{uuid.uuid4().hex[:12]}"
    nodes_json = json.dumps(req.nodes, ensure_ascii=False, default=str)
    connections_json = json.dumps(req.connections, ensure_ascii=False, default=str)

    # 尝试找第一个图片节点作为缩略图
    thumbnail = ""
    for n in req.nodes:
        if n.get("imageUrl"):
            thumbnail = n["imageUrl"]
            break

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM canvases WHERE canvas_id = ? AND owner = ?",
            (canvas_id, owner)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE canvases SET name=?, nodes_json=?, connections_json=?, thumbnail_url=?, updated_at=? "
                "WHERE canvas_id=? AND owner=?",
                (req.name, nodes_json, connections_json, thumbnail, now, canvas_id, owner)
            )
        else:
            conn.execute(
                "INSERT INTO canvases (canvas_id, name, owner, nodes_json, connections_json, thumbnail_url, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (canvas_id, req.name, owner, nodes_json, connections_json, thumbnail, now, now)
            )

    return CanvasDetail(
        canvas_id=canvas_id, name=req.name, owner=owner,
        thumbnail_url=thumbnail, created_at=now, updated_at=now,
        node_count=len(req.nodes), connection_count=len(req.connections),
        nodes=req.nodes, connections=req.connections,
    )


@router.get("/load/{canvas_id}", response_model=CanvasDetail)
async def load_canvas(canvas_id: str, owner: str = Query("boss")):
    """加载单个画布的完整数据（节点+连线）。"""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM canvases WHERE canvas_id = ? AND owner = ?",
            (canvas_id, owner)
        ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"画布不存在: {canvas_id}")
    try:
        nodes = json.loads(r["nodes_json"])
        conns = json.loads(r["connections_json"])
    except (json.JSONDecodeError, TypeError):
        nodes, conns = [], []
    return CanvasDetail(
        canvas_id=r["canvas_id"], name=r["name"], owner=r["owner"],
        thumbnail_url=r["thumbnail_url"] or "",
        created_at=r["created_at"], updated_at=r["updated_at"],
        node_count=len(nodes), connection_count=len(conns),
        nodes=nodes, connections=conns,
    )


@router.delete("/{canvas_id}")
async def delete_canvas(canvas_id: str, owner: str = Query("boss")):
    """删除画布。"""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM canvases WHERE canvas_id = ? AND owner = ?",
            (canvas_id, owner)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"画布不存在: {canvas_id}")
    return {"ok": True, "deleted": canvas_id}


@router.post("/new")
async def create_new_canvas(owner: str = Query("boss")):
    """创建一个空的新画布，返回canvas_id。"""
    canvas_id = f"canvas-{uuid.uuid4().hex[:12]}"
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO canvases (canvas_id, name, owner, nodes_json, connections_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (canvas_id, "未命名画布", owner, "[]", "[]", now, now)
        )
    return {"canvas_id": canvas_id, "name": "未命名画布"}
