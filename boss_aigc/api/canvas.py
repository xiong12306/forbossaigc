"""boss_aigc.api.canvas 无限画布专用API。

直接异步调用 ModelScope / NanoBanana API，不经过七层pipeline，
避免阻塞 FastAPI 事件循环。按 model 参数分发到对应平台。
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import uuid
import json
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
    ref_data_uri: str | None,
    timeout: float,
) -> str:
    """同步调用 SiliconFlow API，返回远程图片 URL。

    SiliconFlow 是同步 API：POST /images/generations 返回 images[0].url。
    文生图不传 image；图生图传 image 字段为 base64 data URI（FLUX.1-Kontext-dev/Qwen-Image-Edit）。
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
    if ref_data_uri:
        body["image"] = ref_data_uri

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
    ref_uri = ref_data_uris[0] if ref_data_uris else None

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            remote_url = await asyncio.to_thread(
                _siliconflow_generate_sync,
                api_key, api_base, model_name, final_prompt, sf_size, ref_uri, timeout,
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
