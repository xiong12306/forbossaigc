"""contracts.enums 全局枚举定义。

集中放各层共用的枚举，避免散落多处导致值不一致。
所有枚举均继承 (str, Enum)，方便序列化为 JSON 字符串。
"""

from enum import Enum


class TaskType(str, Enum):
    """任务类型：助手当前支持的业务意图大类。"""

    IMAGE_GEN = "image_gen"       # 出图（生成主图/详情页/封面等）
    IMAGE_EDIT = "image_edit"     # 改图（局部修改/换背景等）
    VIDEO_GEN = "video_gen"       # 生视频（图转视频/文生视频）
    COPYWRITING = "copywriting"   # 写文案（商品标题/卖点/小红书文案）
    DATA_QUERY = "data_query"     # 查数据（任务历史/资产查询等）


class TaskStatus(str, Enum):
    """任务状态：贯穿理解→确认→执行→交付全生命周期。"""

    PENDING = "pending"                       # 已创建，尚未进入理解
    UNDERSTANDING = "understanding"            # 理解层处理中
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # 等待老板确认
    CONFIRMED = "confirmed"                    # 已确认，待编排执行
    EXECUTING = "executing"                    # 执行层处理中
    DELIVERED = "delivered"                     # 已交付，等待验收
    ACCEPTED = "accepted"                      # 老板验收通过
    CANCELLED = "cancelled"                    # 老板取消
    FAILED = "failed"                          # 执行失败


class ConfirmationAction(str, Enum):
    """确认动作：老板对任务摘要的反馈。"""

    CONFIRM = "confirm"   # 确认开始执行
    MODIFY = "modify"     # 要求修改参数（需附带修改项）
    CANCEL = "cancel"      # 取消任务


class PlatformKind(str, Enum):
    """执行平台类型：适配器实现对应的平台标识。"""

    MOCK = "mock"                       # Mock 适配器（占位结果）
    NANOBANANA = "nanobanana"           # NanoBanana（电商生图，通过Ace Data Cloud接入）
    MODELSCOPE = "modelscope"           # 魔搭 ModelScope（免费文生图，Qwen-Image 等）
    JIMENG = "jimeng"                   # 即梦（Seedream 出图 / Seedance 图转视频）
    TONGYI_WANXIANG = "tongyi_wanxiang"  # 通义万相（备用生图平台）
    LLM = "llm"                          # 文案 LLM（写商品文案/标题）


class ImageType(str, Enum):
    """电商图片类型枚举（参考无量AI流程）。"""

    MAIN = "main"                       # 商品主图（突出主体，提升点击率）
    DETAIL = "detail"                   # 产品详情图（展示卖点细节，引导下单）
    SCENE = "scene"                     # 场景图（使用场景展示）
    POSTER = "poster"                   # 营销海报
    CAROUSEL = "carousel"               # 轮播图


class DeliveryChannel(str, Enum):
    """交付通道：结果推送给老板的渠道。"""

    DIALOG = "dialog"      # 当前对话通道（默认，语音 + 卡片）
    WECHAT = "wechat"       # 微信
    WECOM = "wecom"         # 企业微信
