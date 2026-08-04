"""boss_aigc.api.canvas 无限画布专用API。

直接异步调用 ModelScope API，不经过七层pipeline，不使用同步适配器，
避免阻塞 FastAPI 事件循环。
"""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from boss_aigc.config import get_settings
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
    model: str = "modelscope"
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


@router.post("/generate", response_model=CanvasGenerateResponse)
async def canvas_generate(req: CanvasGenerateRequest) -> CanvasGenerateResponse:
    """画布异步生成图片，直接调用 ModelScope API。"""
    settings = get_settings()
    if not settings.modelscope_api_key:
        raise HTTPException(status_code=503, detail="ModelScope API key 未配置")

    ms_size = _SIZE_MAP.get(req.size, "1024x1024")

    # 构建 prompt
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
    final_prompt = "，".join(prompt_parts)

    # 解析参考图
    ref_data_uris: list[str] = []
    for img_url in req.reference_images:
        try:
            ref_data_uris.append(_resolve_local_image(img_url))
        except HTTPException:
            logger.warning("参考图解析失败，跳过: %s", img_url)

    is_edit = len(ref_data_uris) > 0
    model_name = "Qwen/Qwen-Image-Edit-2509" if is_edit else settings.modelscope_model

    logger.info(
        "画布生成: is_edit=%s refs=%d prompt=%s",
        is_edit, len(ref_data_uris), final_prompt[:100],
    )

    api_base = settings.modelscope_api_base.rstrip("/")
    api_key = settings.modelscope_api_key

    # 构建 API 请求体
    body: dict[str, Any] = {
        "prompt": final_prompt,
        "size": ms_size,
        "negative_prompt": _NEGATIVE_PROMPT,
        "model": model_name,
    }
    if is_edit:
        body["image_url"] = ref_data_uris

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true",
    }

    submit_timeout = httpx.Timeout(connect=15.0, read=180.0, write=180.0, pool=15.0)
    poll_timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)

    async with httpx.AsyncClient(trust_env=False, http2=False) as client:
        # 1. 提交任务（带重试）
        resp = None
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{api_base}/images/generations",
                    json=body,
                    headers=headers,
                    timeout=submit_timeout,
                )
                resp.raise_for_status()
                break
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning("提交失败（重试%d/3）: %s", attempt + 1, type(e).__name__)
                if attempt == 2:
                    raise HTTPException(status_code=502, detail=f"ModelScope 提交失败: {e}")
                await asyncio.sleep(2)

        submit_data = resp.json()
        ms_task_id = submit_data.get("task_id")
        if not ms_task_id:
            raise HTTPException(status_code=502, detail=f"未返回 task_id: {str(submit_data)[:200]}")

        logger.info("任务已提交: ms_task_id=%s", ms_task_id)

        # 2. 异步轮询（不阻塞事件循环）
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

                remote_url = images[0]
                try:
                    local_url = await _download_image(client, remote_url)
                except Exception as e:
                    logger.warning("下载失败，使用原始 URL: %s", e)
                    local_url = remote_url

                return CanvasGenerateResponse(
                    image_url=local_url,
                    prompt_used=final_prompt,
                    model_used=req.model,
                )

            if status == "FAILED":
                raise HTTPException(status_code=500, detail=f"生成失败: {str(data)[:200]}")

            if status not in ("PROCESSING", "PENDING", "RUNNING"):
                raise HTTPException(status_code=500, detail=f"未知状态: {status}")

            if asyncio.get_event_loop().time() > deadline:
                raise HTTPException(status_code=504, detail="生成超时（5分钟）")

            poll_count += 1
            # 自适应间隔：前3次1.5秒快速检测，4-10次3秒，之后5秒
            if poll_count <= 3:
                wait = 1.5
            elif poll_count <= 10:
                wait = 3.0
            else:
                wait = 5.0
            await asyncio.sleep(wait)
