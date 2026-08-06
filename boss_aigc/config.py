"""boss_aigc.config 配置管理。

集中管理各服务 provider、API key 占位、阈值等配置。
支持从 .env 文件和环境变量加载配置。
"""

import os
from dataclasses import dataclass, field

# 自动加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Settings:
    """全局配置项。

    Attributes:
        asr_provider: ASR 服务提供方（mock / volcano / aliyun），本阶段用 mock。
        asr_confidence_threshold: ASR 低置信度阈值，低于此值标记降级提示。
        tts_provider: TTS 服务提供方（mock / volcano），本阶段用 mock。
        wake_word: 语音唤醒词（参考小爱同学范式），默认「小帮小帮」。
        llm_provider: 意图理解 LLM 提供方，默认 "rule"（规则引擎，无需 API key），
            后续可换 "qwen"/"glm" 等真实 LLM provider。
        nanobanana_api_key: NanoBanana API key（通过Ace Data Cloud接入）。
        nanobanana_api_base: NanoBanana API base URL。
        jimeng_api_key: 即梦 API key 占位（后续阶段接入）。
        tongyi_api_key: 通义万相 API key 占位（后续阶段接入）。
        llm_api_key: 文案 LLM API key 占位。
        high_cost_image_threshold: 高成本图片数量阈值，超此需二次确认。
        high_cost_credits_threshold: 高成本积分阈值。
        high_cost_threshold: 确认层判定高成本任务的积分阈值（estimated_cost > 此值则需二次确认）。
        retry_max: 适配器失败重试次数上限。
        poll_interval_sec: 轮询平台状态间隔（秒）。
        request_timeout_sec: 单次请求超时（秒）。
        default_delivery_channel: 默认交付通道名（dialog / wechat / wecom），
            交付层 DeliveryPusher 未显式指定通道时使用。
        use_real_platform: 是否使用真实平台（True=NanoBanana，False=Mock）。
        platform_provider: 出图平台选择（mock/modelscope/nanobanana），由 PLATFORM_PROVIDER 环境变量决定。
        modelscope_api_key: 魔搭 ModelScope API key（SDK Token）。
        modelscope_api_base: 魔搭 ModelScope API base URL。
        modelscope_model: 魔搭文生图默认模型。
    """

    asr_provider: str = "mock"                # ASR 提供方（本阶段 mock，真实 volcano 留后续）
    asr_confidence_threshold: float = 0.6     # ASR 低置信度阈值
    tts_provider: str = "mock"                # TTS 提供方（本阶段 mock）
    wake_word: str = "小帮小帮"                # 语音唤醒词
    llm_provider: str = "rule"                # 意图理解 provider：rule=规则引擎（默认，无需 key），可换 "qwen"/"glm"

    nanobanana_api_key: str = os.environ.get("NANOBANANA_API_KEY", "")  # NanoBanana API key（通过Ace Data Cloud接入）
    nanobanana_api_base: str = "https://api.acedata.cloud/nano-banana"  # NanoBanana API base URL
    jimeng_api_key: str = ""                  # 即梦 API key 占位
    tongyi_api_key: str = ""                  # 通义万相 API key 占位
    llm_api_key: str = ""                     # 文案 LLM API key 占位

    platform_provider: str = os.environ.get("PLATFORM_PROVIDER", "mock")  # mock|modelscope|siliconflow|nanobanana
    modelscope_api_key: str = os.environ.get("MODELSCOPE_API_KEY", "")
    modelscope_api_base: str = os.environ.get("MODELSCOPE_API_BASE", "https://api-inference.modelscope.cn/v1")
    modelscope_model: str = os.environ.get("MODELSCOPE_MODEL", "Qwen/Qwen-Image")

    # 硅基流动 SiliconFlow（新用户送 2000 万 token 永久免费）
    # 默认 Qwen/Qwen-Image（免实名即可用）；FLUX 系列需实名后才能调用
    siliconflow_api_key: str = os.environ.get("SILICONFLOW_API_KEY", "")
    siliconflow_api_base: str = os.environ.get("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")
    siliconflow_model: str = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen-Image")
    siliconflow_edit_model: str = os.environ.get("SILICONFLOW_EDIT_MODEL", "Qwen/Qwen-Image-Edit")
    # 文案 LLM：默认复用 SiliconFlow key 调用 Qwen2.5-14B-Instruct（免实名、中文好、稳定性强）
    # 7B 在小红书口语化场景偶发重复内容，14B 质量明显提升
    # 也可换成 deepseek-ai/DeepSeek-V3 或 Qwen/Qwen2.5-72B-Instruct（需实名）
    llm_chat_model: str = os.environ.get("LLM_CHAT_MODEL", "Qwen/Qwen2.5-14B-Instruct")
    llm_chat_api_base: str = os.environ.get("LLM_CHAT_API_BASE", "")  # 空则复用 siliconflow_api_base
    llm_chat_api_key: str = os.environ.get("LLM_CHAT_API_KEY", "")  # 空则复用 siliconflow_api_key

    high_cost_image_threshold: int = 20       # 高成本图片数量阈值
    high_cost_credits_threshold: int = 200    # 高成本积分阈值
    high_cost_threshold: int = 20             # 确认层高成本任务积分阈值（estimated_cost > 此值需二次确认）
    retry_max: int = 3                        # 适配器失败重试上限
    poll_interval_sec: float = float(os.environ.get("POLL_INTERVAL_SEC", "2.0"))  # 轮询间隔
    request_timeout_sec: float = float(os.environ.get("REQUEST_TIMEOUT_SEC", "180"))  # 单次请求超时（文生图通常需60-180s）

    default_delivery_channel: str = "dialog"  # 默认交付通道（dialog/wechat/wecom）
    use_real_platform: bool = os.environ.get("USE_REAL_PLATFORM", "").strip().lower() in ("true", "1", "yes")  # 是否使用真实平台（True=NanoBanana，False=Mock）

    # Supabase 配置（从环境变量加载）
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")
    use_supabase: bool = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY"))


# 模块级单例：进程内共享一份配置
_settings = Settings()


def get_settings() -> Settings:
    """获取全局配置（单例）。

    后续可扩展为从环境变量 / 配置文件加载，本阶段返回默认值。
    """
    return _settings


def configure(**overrides: object) -> Settings:
    """运行时覆写配置项并返回更新后的 Settings。

    用法：configure(retry_max=5, llm_provider="glm")
    """
    global _settings
    for key, value in overrides.items():
        if hasattr(_settings, key):
            setattr(_settings, key, value)
        else:
            raise AttributeError(f"未知配置项: {key}")
    return _settings
