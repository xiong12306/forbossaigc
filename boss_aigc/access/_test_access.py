"""接入层（access）冒烟测试。

运行：`.venv/bin/python -m boss_aigc.access._test_access`

覆盖：
    1. MockASRProvider 把 bytes 解码为文本，confidence 达标
    2. WakeWordDetector 检测「小帮小帮，出图」命中并剥离为「出图」
    3. build_access_handler 处理 str 输入（文字降级）和 bytes 输入（语音）都能返回纯指令文本
    4. MockTTSProvider.synthesize 不报错且打印播报日志
"""

from __future__ import annotations

from boss_aigc.access import (
    MockASRProvider,
    MockTTSProvider,
    WakeWordDetector,
    build_access_handler,
    create_default_access,
    speak,
)
from boss_aigc.pipeline import SessionContext


def test_mock_asr() -> None:
    """1. MockASRProvider 把 bytes 解码为文本，confidence 达标。"""
    asr = MockASRProvider()
    result = asr.transcribe("出图".encode("utf-8"))
    assert result.text == "出图", f"转写文本不符: {result.text!r}"
    assert result.confidence >= 0.6, f"confidence 过低: {result.confidence}"
    assert result.is_low_confidence is False, "不应为低置信度"
    print("[OK] test_mock_asr")


def test_wake_word() -> None:
    """2. WakeWordDetector 检测「小帮小帮，出图」命中并剥离为「出图」。"""
    det = WakeWordDetector()
    text = "小帮小帮，出图"
    assert det.detect(text) is True, "应命中唤醒词"
    stripped = det.strip_wake_word(text)
    assert stripped == "出图", f"剥离结果不符: {stripped!r}"
    # 无唤醒词不应命中
    assert det.detect("出图") is False
    # 无唤醒词时剥离返回原文去空白
    assert det.strip_wake_word("出图") == "出图"
    print("[OK] test_wake_word")


def test_handler_str_input() -> None:
    """3a. build_access_handler 处理 str 输入（文字降级）返回纯指令文本。"""
    asr = MockASRProvider()
    tts = MockTTSProvider()
    ww = WakeWordDetector()
    handler = build_access_handler(asr, tts, ww)

    ctx = SessionContext()
    # 含唤醒词的文本输入
    out = handler("小帮小帮，给保温杯出 3 张主图", ctx)
    assert out == "给保温杯出 3 张主图", f"纯指令不符: {out!r}"
    assert ctx.extras.get("asr_text") == "给保温杯出 3 张主图"
    assert ctx.extras.get("wake_word_hit") is True
    assert ctx.extras.get("asr_low_confidence") is False
    print("[OK] test_handler_str_input")


def test_handler_bytes_input() -> None:
    """3b. build_access_handler 处理 bytes 输入（语音）返回纯指令文本。"""
    asr = MockASRProvider()
    tts = MockTTSProvider()
    ww = WakeWordDetector()
    handler = build_access_handler(asr, tts, ww)

    ctx = SessionContext()
    # bytes 输入（语音通道）
    out = handler("小帮小帮，出图".encode("utf-8"), ctx)
    assert out == "出图", f"纯指令不符: {out!r}"
    assert ctx.extras.get("asr_text") == "出图"
    assert ctx.extras.get("asr_low_confidence") is False
    assert ctx.extras.get("asr_confidence") == 0.95
    print("[OK] test_handler_bytes_input")


def test_handler_low_confidence() -> None:
    """3c. ASR 低置信度时标记 asr_low_confidence=True。"""
    asr = MockASRProvider(confidence=0.3)  # 低于阈值 0.6
    tts = MockTTSProvider()
    ww = WakeWordDetector()
    handler = build_access_handler(asr, tts, ww)

    ctx = SessionContext()
    out = handler("小帮小帮，出图".encode("utf-8"), ctx)
    assert ctx.extras.get("asr_low_confidence") is True, "应标记低置信度"
    # 低置信度仍应返回剥离唤醒词后的指令
    assert out == "出图", f"纯指令不符: {out!r}"
    print("[OK] test_handler_low_confidence")


def test_handler_no_wake_word_demo_passthrough() -> None:
    """3d. 无唤醒词在 demo 模式下放行，返回原文本。"""
    asr = MockASRProvider()
    tts = MockTTSProvider()
    ww = WakeWordDetector()
    handler = build_access_handler(asr, tts, ww)

    ctx = SessionContext()
    out = handler("直接出图", ctx)
    assert out == "直接出图", f"放行结果不符: {out!r}"
    assert ctx.extras.get("wake_word_hit") is False
    print("[OK] test_handler_no_wake_word_demo_passthrough")


def test_mock_tts() -> None:
    """4. MockTTSProvider.synthesize 不报错且打印播报日志。"""
    tts = MockTTSProvider()
    result = tts.synthesize("已开始出图，请稍候")
    assert isinstance(result.audio_bytes, bytes), "audio_bytes 应为 bytes"
    assert result.format == "mock", f"format 不符: {result.format!r}"
    assert result.audio_bytes == "已开始出图，请稍候".encode("utf-8")
    print("[OK] test_mock_tts")


def test_speak_helper() -> None:
    """speak 辅助函数可正常调用，不报错。"""
    tts = MockTTSProvider()
    speak(tts, "测试播报")
    print("[OK] test_speak_helper")


def test_create_default_access() -> None:
    """create_default_access 返回可用的处理器，开箱即用。"""
    handler = create_default_access()
    ctx = SessionContext()
    out = handler("小帮小帮，出图", ctx)
    assert out == "出图", f"默认处理器输出不符: {out!r}"
    assert ctx.extras.get("asr_text") == "出图"
    print("[OK] test_create_default_access")


def main() -> None:
    print("运行接入层测试...")
    test_mock_asr()
    test_wake_word()
    test_handler_str_input()
    test_handler_bytes_input()
    test_handler_low_confidence()
    test_handler_no_wake_word_demo_passthrough()
    test_mock_tts()
    test_speak_helper()
    test_create_default_access()
    print("全部测试通过 ✅")


if __name__ == "__main__":
    main()
