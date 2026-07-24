"""boss_aigc.access.tts TTS（语音合成）抽象接口与 Mock 实现。

真实接入时实现火山/阿里云等 TTSProvider 子类即可，
本阶段用 MockTTSProvider 跑通链路（无需 API key）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="access")


@dataclass
class TTSResult:
    """TTS 合成结果。

    Attributes:
        audio_bytes: 合成音频字节流。
        format: 音频格式（如 "mp3" / "mock"）。
    """

    audio_bytes: bytes
    format: str = "mp3"


class TTSProvider(ABC):
    """TTS 抽象基类：把文本合成为音频字节流。

    所有真实 TTS 服务 SHALL 实现该接口，
    接入层及其他层通过 speak 辅助函数调用，对具体平台无感知。
    """

    @abstractmethod
    def synthesize(self, text: str) -> TTSResult:
        """合成语音。

        Args:
            text: 待播报文本。

        Returns:
            TTSResult 合成结果。
        """
        raise NotImplementedError


class MockTTSProvider(TTSProvider):
    """Mock TTS 实现。

    把文本按 utf-8 编码回字节流作为「音频」，format="mock"，
    同时打印一行播报日志模拟语音播报。
    """

    def __init__(self, format: str = "mock") -> None:
        self.format = format

    def synthesize(self, text: str) -> TTSResult:
        # 打印播报日志模拟语音输出
        logger.info("[TTS 播报] %s", text)
        audio_bytes = text.encode("utf-8")
        return TTSResult(audio_bytes=audio_bytes, format=self.format)
