"""boss_aigc.access 接入层包。

职责：语音唤醒 / ASR 转写 / TTS 播报 / 文字输入降级 / 卡片渲染。
本阶段提供抽象接口 + Mock 实现，真实 ASR/TTS 留待后续阶段接入。

参考小爱同学的交互范式：
    老板说唤醒词 → ASR 转写指令 → 后续层理解/确认/执行 → TTS 播报反馈
"""

from boss_aigc.access.asr import ASRProvider, ASRResult, MockASRProvider
from boss_aigc.access.tts import MockTTSProvider, TTSProvider, TTSResult
from boss_aigc.access.wake_word import WakeWordDetector
from boss_aigc.access.handler import (
    build_access_handler,
    create_default_access,
    speak,
)

__all__ = [
    "ASRProvider",
    "ASRResult",
    "MockASRProvider",
    "TTSProvider",
    "TTSResult",
    "MockTTSProvider",
    "WakeWordDetector",
    "build_access_handler",
    "create_default_access",
    "speak",
]
