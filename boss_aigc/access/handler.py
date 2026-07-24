"""boss_aigc.access.handler 接入层处理器。

把 ASR / TTS / 唤醒词检测组装为符合 pipeline LayerHandler 协议的处理器。
职责：
    - 音频字节流（bytes）走 ASR 转写；低置信度时标记降级提示
    - 文本（str）走文字输入降级通道，与语音共用同一套后续流程
    - 唤醒词检测与剥离，得到纯指令文本
    - 把纯指令写入 context.extras['asr_text']，返回给下一层 understanding
"""

from __future__ import annotations

from typing import Any

from boss_aigc.access.asr import ASRProvider, MockASRProvider
from boss_aigc.access.tts import TTSProvider, MockTTSProvider
from boss_aigc.access.wake_word import WakeWordDetector
from boss_aigc.config import get_settings
from boss_aigc.logging_setup import get_logger
from boss_aigc.pipeline import LayerHandler, SessionContext

logger = get_logger(__name__, layer="access")


def build_access_handler(
    asr: ASRProvider,
    tts: TTSProvider,
    wake_word: WakeWordDetector,
) -> LayerHandler:
    """组装接入层处理器。

    Args:
        asr: ASR 提供方实例。
        tts: TTS 提供方实例（供低置信度降级提示及 speak 辅助函数使用）。
        wake_word: 唤醒词检测器。

    Returns:
        符合 LayerHandler 协议的可调用对象，
        输入 (upstream, context) 返回纯指令文本（str）。
    """

    def handler(upstream: Any, context: SessionContext) -> str:
        # 1. 获取原始文本：bytes 走 ASR，str 走文字降级通道
        if isinstance(upstream, (bytes, bytearray)):
            asr_result = asr.transcribe(bytes(upstream))
            text = asr_result.text
            context.extras["asr_confidence"] = asr_result.confidence
            if asr_result.is_low_confidence:
                # 低置信度：标记并提示降级
                context.extras["asr_low_confidence"] = True
                logger.warning(
                    "ASR 低置信度(%.2f)，建议走文字输入降级: %r",
                    asr_result.confidence, text,
                )
                # 通过 TTS 提示老板改用文字输入
                speak(tts, "我没有听清，请用文字再说一次。")
            else:
                context.extras["asr_low_confidence"] = False
        elif isinstance(upstream, str):
            # 文字输入降级通道：与语音走同一套后续流程
            text = upstream
            context.extras["asr_low_confidence"] = False
            logger.info("文字输入降级通道: %r", text)
        else:
            # 其他类型统一转为字符串
            text = str(upstream)
            context.extras["asr_low_confidence"] = False

        # 2. 唤醒词检测与剥离
        if wake_word.detect(text):
            command = wake_word.strip_wake_word(text)
            context.extras["wake_word_hit"] = True
            context.extras["session_active"] = True
            logger.info("命中唤醒词，纯指令: %r", command)
        else:
            command = text.strip()
            context.extras["wake_word_hit"] = False
            # demo 模式下无唤醒词也放行，但在日志记录
            if not context.extras.get("session_active"):
                logger.info("未命中唤醒词且无活跃会话（demo 放行）: %r", command)
            else:
                logger.info("未命中唤醒词，沿用活跃会话: %r", command)

        # 3. 写入转写后的纯指令文本，返回给下一层 understanding
        context.extras["asr_text"] = command
        return command

    return handler


def speak(tts: TTSProvider, text: str) -> None:
    """调用 TTS 播报文本的辅助函数（供其他层调用反馈老板）。"""
    tts.synthesize(text)


def create_default_access() -> LayerHandler:
    """用 config 里的默认 provider 构建一个开箱即用的接入层处理器。

    根据 settings.asr_provider / tts_provider 选择对应实现，
    本阶段只有 mock；未知 provider 降级为 mock 并记录告警。
    """
    settings = get_settings()

    if settings.asr_provider == "mock":
        asr = MockASRProvider()
    else:
        # 真实 provider 留待后续阶段接入，这里降级为 mock
        logger.warning("未知 asr_provider=%s，降级使用 mock", settings.asr_provider)
        asr = MockASRProvider()

    if settings.tts_provider == "mock":
        tts = MockTTSProvider()
    else:
        logger.warning("未知 tts_provider=%s，降级使用 mock", settings.tts_provider)
        tts = MockTTSProvider()

    wake_word = WakeWordDetector()
    return build_access_handler(asr, tts, wake_word)
