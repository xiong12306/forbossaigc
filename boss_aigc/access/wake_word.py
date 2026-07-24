"""boss_aigc.access.wake_word 唤醒词检测。

参考小爱同学的交互范式：老板先说唤醒词激活助手，再说指令。
本模块负责检测唤醒词并剥离前缀，得到纯指令文本。
"""

from __future__ import annotations

from boss_aigc.config import get_settings


class WakeWordDetector:
    """唤醒词检测器：检测文本是否以唤醒词开头，并支持剥离唤醒词。

    默认唤醒词「小帮小帮」，可通过构造参数或 config 覆写。
    """

    def __init__(self, wake_word: str | None = None) -> None:
        if wake_word is None:
            wake_word = get_settings().wake_word
        self.wake_word = wake_word

    def detect(self, text: str) -> bool:
        """检测文本是否以唤醒词开头。

        允许文本前有少量空白；唤醒词需出现在最前面才算命中。
        """
        if not text:
            return False
        return text.lstrip().startswith(self.wake_word)

    def strip_wake_word(self, text: str) -> str:
        """剥离唤醒词前缀，返回纯指令文本。

        同时去掉唤醒词后紧跟的常见分隔符（中英文逗号/句号/空格/冒号等）。
        若文本不含唤醒词，则返回原文本去空白后的结果。
        """
        stripped = text.lstrip()
        if stripped.startswith(self.wake_word):
            remainder = stripped[len(self.wake_word):]
            # 去掉唤醒词后的分隔符
            return remainder.lstrip("，,。. :：、").strip()
        return text.strip()
