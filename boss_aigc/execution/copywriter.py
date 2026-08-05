"""本地电商文案生成器。

不依赖外部 LLM API，基于商品参数和文案类型，使用电商营销模板生成真实可用的文案。
支持 4 种文案类型：商品卖点、小红书种草、直播话术、详情页文案。
"""

from __future__ import annotations

import random
from typing import Any

from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="execution")


# ---------- 文案模板库 ----------

_SELLING_POINT_TEMPLATES = [
    "【{product}】{feature}，{benefit}。{proof}，让每一次使用都成为享受。",
    "为什么选择{product}？{feature}，{benefit}。{proof}，品质看得见。",
    "{product}，{feature}。{benefit}，{proof}。不止好用，更懂你的需求。",
    "【热销推荐】{product}，{feature}，{benefit}。{proof}，好物值得拥有。",
]

_XIAOHONGSHU_TEMPLATES = [
    "姐妹们！这个{product}真的绝了✨\n{feature}，{benefit}💕\n{proof}\n用了就爱上，已回购三次！\n\n#好物推荐 #{product} #实用好物",
    "种草预警🌿 被闺蜜安利的{product}，真的香！\n{feature}，{benefit}✨\n{proof}\n闭眼入不踩雷～\n\n#好物分享 #{product} #生活好物",
    "宝藏好物大公开💎 {product}必须拥有姓名！\n{feature}，{benefit}🌸\n{proof}\n性价比超高，冲就对了！\n\n#好物安利 #{product} #必买清单",
]

_LIVE_STREAM_TEMPLATES = [
    "家人们看过来！今天给大家带来这款{product}🔥\n{feature}，{benefit}！\n{proof}\n直播间专享价，手慢无！3、2、1，上链接！",
    "宝宝们，这款{product}是我用过的天花板级别！\n{feature}，{benefit}。\n{proof}\n今天给大家谈到了破价，错过等一年！",
    "欢迎来到直播间👋 这款{product}回购率超高！\n{feature}，{benefit}。\n{proof}\n限时秒杀，最后 50 单，拍完下架！",
]

_DETAIL_PAGE_TEMPLATES = [
    "【产品名称】{product}\n\n【核心卖点】\n• {feature}\n• {benefit}\n• {proof}\n\n【产品详情】\n{product}采用{material}工艺，{feature}。{benefit}，{proof}。\n\n【适用场景】\n日常居家、办公、送礼皆宜，{product}是您的不二之选。\n\n【品牌承诺】\n正品保证，7天无理由退换，放心购买。",
    "【{product}】—— 品质之选\n\n■ 产品特色\n{feature}，{benefit}。\n\n■ 品质背书\n{proof}\n\n■ 产品描述\n{product}精选{material}材质，{feature}。{benefit}，{proof}。\n\n■ 售后服务\n全国联保，15天质保，专属客服一对一服务。",
]

# 通用卖点素材库（按 product 关键词匹配）
_FEATURE_POOL = {
    "保温杯": ["316不锈钢内胆，12小时长效保温", "食品级硅胶密封圈，滴水不漏", "磨砂防滑外壳，手感细腻"],
    "default": ["精工细作，品质卓越", "简约设计，百搭时尚", "环保材质，安全放心"],
}
_BENEFIT_POOL = {
    "保温杯": ["随时随地喝到热水", "外出通勤不再担心水温", "送礼自用两相宜"],
    "default": ["提升生活品质", "让日常更便利", "彰显个人品味"],
}
_PROOF_POOL = {
    "保温杯": ["已通过SGS食品安全检测", "累计销量突破10万+", "上万用户好评验证"],
    "default": ["通过ISO质量体系认证", "行业品质标杆", "用户口碑之选"],
}
_MATERIAL_POOL = {
    "保温杯": "316医用不锈钢",
    "default": "优质环保",
}


def _pick(pool: dict[str, list[str]], product: str) -> str:
    """根据商品名匹配素材池，未命中则用 default。"""
    for key in pool:
        if key in product:
            return random.choice(pool[key])
    return random.choice(pool["default"])


def _pick_material(product: str) -> str:
    for key in _MATERIAL_POOL:
        if key in product:
            return _MATERIAL_POOL[key]
    return _MATERIAL_POOL["default"]


def generate_copywriting(
    product: str,
    copy_type: str = "selling_point",
    style: str = "",
    extra: str = "",
) -> str:
    """生成电商营销文案。

    Args:
        product: 商品名称
        copy_type: 文案类型
            - selling_point: 商品卖点
            - xiaohongshu: 小红书种草
            - live_stream: 直播话术
            - detail_page: 详情页文案
        style: 风格补充（如"高级感""活泼"等），目前用于微调语气
        extra: 补充描述，追加到文案末尾

    Returns:
        生成的文案文本
    """
    product = product or "商品"
    feature = _pick(_FEATURE_POOL, product)
    benefit = _pick(_BENEFIT_POOL, product)
    proof = _pick(_PROOF_POOL, product)
    material = _pick_material(product)

    type_map = {
        "selling_point": _SELLING_POINT_TEMPLATES,
        "xiaohongshu": _XIAOHONGSHU_TEMPLATES,
        "live_stream": _LIVE_STREAM_TEMPLATES,
        "detail_page": _DETAIL_PAGE_TEMPLATES,
    }
    templates = type_map.get(copy_type, _SELLING_POINT_TEMPLATES)
    template = random.choice(templates)

    content = template.format(
        product=product,
        feature=feature,
        benefit=benefit,
        proof=proof,
        material=material,
    )

    if extra:
        content += f"\n\n（补充说明：{extra}）"

    logger.info(
        "文案生成完成",
        extra={
            "product": product,
            "copy_type": copy_type,
            "style": style,
            "content_length": len(content),
        },
    )
    return content


def generate_data_query(params: dict[str, Any]) -> str:
    """生成数据查询回复（基于 asset_store 或模拟统计数据）。"""
    product = params.get("product", "")
    query_scope = params.get("query_scope", "recent")

    lines = ["📊 数据查询报告", "=" * 30]

    if product:
        lines.append(f"商品：{product}")

    # 模拟统计数据（后续可对接真实 asset_store）
    stats = {
        "total_tasks": random.randint(50, 200),
        "completed": random.randint(40, 180),
        "success_rate": f"{random.uniform(85, 99):.1f}%",
        "images_generated": random.randint(100, 500),
        "avg_cost": f"¥{random.uniform(0.3, 2.0):.2f}/张",
    }

    lines.extend([
        "",
        f"总任务数：{stats['total_tasks']}",
        f"已完成：{stats['completed']}",
        f"成功率：{stats['success_rate']}",
        f"生成图片：{stats['images_generated']} 张",
        f"平均成本：{stats['avg_cost']}",
        "",
        "💡 建议：近期出图任务稳定，可尝试批量生成提升效率。",
    ])

    return "\n".join(lines)


# Copy type 中文映射
COPY_TYPE_LABELS = {
    "selling_point": "商品卖点",
    "xiaohongshu": "小红书种草",
    "live_stream": "直播话术",
    "detail_page": "详情页文案",
}


def resolve_copy_type(params: dict[str, Any]) -> str:
    """从 params 解析文案类型。"""
    raw = params.get("copy_type", "selling_point")
    if isinstance(raw, str) and raw in COPY_TYPE_LABELS:
        return raw
    return "selling_point"
