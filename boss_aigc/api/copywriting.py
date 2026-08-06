"""boss_aigc.api.copywriting 电商文案生成 API。

调用 SiliconFlow / 其他 OpenAI 兼容 LLM API 的 chat completions，
根据文案类型（商品标题/卖点/小红书种草/短视频脚本）生成高质量电商文案。
默认复用 SILICONFLOW_API_KEY（新用户送 2000 万 token 永久免费）。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from boss_aigc.config import get_settings
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="api")

router = APIRouter(prefix="/api/copywriting", tags=["copywriting"])


# ---------- 请求/响应模型 ----------

class CopywritingGenerateRequest(BaseModel):
    product: str
    copy_type: str = "title"   # title | selling | xhs | script
    style: str = "专业带货"
    extra: str = ""            # 用户附加要求
    temperature: float = 0.7


class CopywritingGenerateResponse(BaseModel):
    content: str
    model_used: str
    copy_type: str
    style: str


# ---------- 文案类型 → System Prompt & User Prompt 模板 ----------

_SYSTEM_PROMPT = (
    "你是一位资深电商文案策划专家，拥有10年以上淘宝/抖音/小红书内容营销经验。"
    "你的文案风格精准抓眼球、卖点突出、转化率高，符合平台调性。"
    "请严格按用户要求的文案类型和风格撰写，**只输出文案内容本身，不要任何开场白、解释或结尾语**。"
)

_COPY_TYPE_PROMPTS: dict[str, dict[str, Any]] = {
    "title": {
        "label": "商品标题",
        "instruction": (
            "请为商品【{product}】撰写一个优质电商商品标题（用于淘宝/天猫/京东/抖音商品展示）。"
            "要求：\n"
            "1. 长度 15-30 字，必须包含商品名 + 1-2 个核心卖点关键词（如材质/功能/场景/人群）\n"
            "2. 利于搜索，避免空洞词（如「好用」「超值」单独出现）\n"
            "3. 风格：{style}\n"
            "4. 参考淘宝爆款标题格式，用空格分隔关键词\n"
            "5. 只输出标题本身，不要加引号、序号、前缀或解释\n"
            "{extra_instruction}"
        ),
        "max_tokens": 120,
    },
    "selling": {
        "label": "卖点文案",
        "instruction": (
            "请为商品【{product}】撰写 3-5 条核心卖点文案。"
            "要求：\n"
            "1. 每条以「•」开头，一行一条\n"
            "2. 格式：卖点关键词 + 具体利益点（解决什么痛点/带来什么好处）\n"
            "3. 语言精炼有力，直击用户需求\n"
            "4. 风格：{style}\n"
            "{extra_instruction}"
        ),
        "max_tokens": 400,
    },
    "xhs": {
        "label": "小红书种草",
        "instruction": (
            "请为商品【{product}】写一篇小红书种草笔记。"
            "要求：\n"
            "1. 标题要有 emoji 吸引眼球\n"
            "2. 正文口语化，像闺蜜分享，加入真实使用感受\n"
            "3. 分段清晰，适当使用 emoji\n"
            "4. 结尾加 5-8 个相关话题标签 #\n"
            "5. 总字数 200-400 字\n"
            "6. 风格：{style}\n"
            "{extra_instruction}"
        ),
        "max_tokens": 600,
    },
    "script": {
        "label": "短视频脚本",
        "instruction": (
            "请为商品【{product}】写一个 15-30 秒短视频带货脚本。"
            "要求：\n"
            "1. 分镜格式：【镜头N】画面描述 + 口播文案\n"
            "2. 开头 3 秒黄金钩子（制造悬念/痛点/反差）\n"
            "3. 中间展示产品使用场景和核心卖点\n"
            "4. 结尾行动召唤（点击小黄车/限时优惠等）\n"
            "5. 总共 4-6 个镜头\n"
            "6. 风格：{style}\n"
            "{extra_instruction}"
        ),
        "max_tokens": 600,
    },
}


def _build_prompt(product: str, copy_type: str, style: str, extra: str) -> tuple[str, int]:
    """构建用户 prompt，返回 (prompt_text, max_tokens)。"""
    cfg = _COPY_TYPE_PROMPTS.get(copy_type, _COPY_TYPE_PROMPTS["title"])
    extra_instruction = f"7. 附加要求：{extra}\n" if extra.strip() else ""
    prompt = cfg["instruction"].format(
        product=product,
        style=style,
        extra_instruction=extra_instruction,
    )
    return prompt, cfg["max_tokens"]


async def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> tuple[str, str]:
    """调用 LLM chat completions（OpenAI 兼容格式），返回 (content, model_used)。

    默认使用 SiliconFlow 的 Qwen2.5-7B-Instruct（免实名、中文好、速度快）。
    可通过 LLM_CHAT_API_BASE / LLM_CHAT_API_KEY / LLM_CHAT_MODEL 环境变量覆盖。
    """
    settings = get_settings()
    api_base = (settings.llm_chat_api_base or settings.siliconflow_api_base).rstrip("/")
    api_key = settings.llm_chat_api_key or settings.siliconflow_api_key
    model = settings.llm_chat_model

    if not api_key:
        raise HTTPException(status_code=503, detail="LLM API key 未配置，请设置 SILICONFLOW_API_KEY 或 LLM_CHAT_API_KEY")

    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.9,
        "frequency_penalty": 0.5,   # 抑制重复（7B/14B 模型口语化场景防复读）
        "presence_penalty": 0.3,     # 鼓励话题多样性
    }

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)

    async def _do_request() -> dict[str, Any]:
        async with httpx.AsyncClient(trust_env=False, http2=False) as client:
            r = await client.post(url, json=body, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()

    # 重试 2 次
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            data = await _do_request()
            choices = data.get("choices") or []
            if not choices:
                raise HTTPException(status_code=502, detail=f"LLM 返回为空: {str(data)[:200]}")
            msg = choices[0].get("message") or {}
            content = (msg.get("content") or "").strip()
            if not content:
                raise HTTPException(status_code=502, detail="LLM 返回内容为空")
            return content, model
        except HTTPException:
            raise
        except httpx.HTTPStatusError as e:
            last_err = e
            err_text = e.response.text[:200] if e.response else ""
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", "3"))
                logger.warning("LLM 限流429，等待%ds（重试%d/3）", retry_after, attempt + 1)
                await asyncio.sleep(retry_after)
                continue
            logger.warning("LLM HTTP %d（重试%d/3）: %s", e.response.status_code, attempt + 1, err_text)
            if attempt == 2:
                raise HTTPException(status_code=502, detail=f"LLM 请求失败(HTTP {e.response.status_code}): {err_text}")
            await asyncio.sleep(1)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            last_err = e
            logger.warning("LLM 网络错误（重试%d/3）: %s", attempt + 1, type(e).__name__)
            if attempt == 2:
                raise HTTPException(status_code=502, detail=f"LLM 网络错误: {e}")
            await asyncio.sleep(2)

    raise HTTPException(status_code=502, detail=f"LLM 请求失败: {last_err}")


# ---------- API 端点 ----------

@router.post("/generate", response_model=CopywritingGenerateResponse)
async def generate_copywriting(req: CopywritingGenerateRequest) -> CopywritingGenerateResponse:
    """电商文案生成 API。

    根据商品名 + 文案类型 + 风格，调用 LLM 生成对应文案。
    支持四种类型：title（商品标题）、selling（卖点文案）、xhs（小红书种草）、script（短视频脚本）。
    """
    product = req.product.strip()
    if not product:
        raise HTTPException(status_code=400, detail="商品名称不能为空")

    copy_type = req.copy_type.strip().lower()
    if copy_type not in _COPY_TYPE_PROMPTS:
        raise HTTPException(status_code=400, detail=f"不支持的文案类型: {copy_type}，支持：{list(_COPY_TYPE_PROMPTS.keys())}")

    style = req.style.strip() or "专业带货"

    user_prompt, max_tokens = _build_prompt(product, copy_type, style, req.extra)
    logger.info("文案生成请求: type=%s product=%s style=%s", copy_type, product, style)

    content, model_used = await _call_llm(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=req.temperature,
    )

    logger.info("文案生成完成: model=%s length=%d", model_used, len(content))
    return CopywritingGenerateResponse(
        content=content,
        model_used=model_used,
        copy_type=copy_type,
        style=style,
    )
