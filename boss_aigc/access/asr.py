"""boss_aigc.access.asr ASR（语音转写）抽象接口与 Mock 实现。

真实接入时实现火山/阿里云等 ASRProvider 子类即可，
本阶段用 MockASRProvider 跑通链路（无需 API key）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from boss_aigc.config import get_settings
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="access")


@dataclass
class ASRResult:
    """ASR 转写结果。

    Attributes:
        text: 转写出的文本。
        confidence: 置信度（0~1）。
        is_low_confidence: 是否低置信度（confidence < 阈值时为 True）。
    """

    text: str
    confidence: float
    is_low_confidence: bool = False


class ASRProvider(ABC):
    """ASR 抽象基类：把音频字节流转写为文本。

    所有真实 ASR 服务（火山/阿里云）SHALL 实现该接口，
    接入层处理器仅依赖此抽象接口，对具体平台无感知。
    """

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> ASRResult:
        """转写音频。

        Args:
            audio_bytes: 音频原始字节流。

        Returns:
            ASRResult 转写结果。
        """
        raise NotImplementedError


class MockASRProvider(ASRProvider):
    """Mock ASR 实现。

    简化约定：不真的识别音频，而是把传入的字节流按 utf-8 解码为文本，
    直接当作转写结果。confidence 固定为可配置值（默认 0.95）。
    这样 demo 时调用方可以直接传文本字节，无需真实录音。
    """

    def __init__(
        self,
        confidence: float = 0.95,
        confidence_threshold: float | None = None,
    ) -> None:
        self.confidence = confidence
        # 阈值未显式传入时从全局配置读取
        if confidence_threshold is None:
            confidence_threshold = get_settings().asr_confidence_threshold
        self.confidence_threshold = confidence_threshold

    def transcribe(self, audio_bytes: bytes) -> ASRResult:
        # 把字节流解码为文本作为转写结果（demo 约定：文本即音频）
        text = audio_bytes.decode("utf-8", errors="replace")
        is_low = self.confidence < self.confidence_threshold
        logger.info(
            "MockASR 转写完成: text=%r confidence=%.2f low_confidence=%s",
            text, self.confidence, is_low,
        )
        return ASRResult(text=text, confidence=self.confidence, is_low_confidence=is_low)
