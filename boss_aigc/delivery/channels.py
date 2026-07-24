"""boss_aigc.delivery.channels 多通道推送框架。

定义统一的 DeliveryChannelBase 抽象接口，并实现三个具体通道：
- DialogChannel：默认对话通道，把摘要写入 context.extras['speak_text'] 供 TTS 播报
- WechatChannel：微信通道（存根，本阶段仅打日志）
- WecomChannel：企业微信通道（存根，本阶段仅打日志）

DeliveryPusher 按 channel 标识选择对应推送器执行推送。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from boss_aigc.config import get_settings
from boss_aigc.logging_setup import get_logger
from boss_aigc.pipeline import SessionContext

from boss_aigc.delivery.packager import DeliveryPackage

logger = get_logger(__name__, layer="delivery")

# context.extras 中标记 TTS 播报文本的 key（与 confirmation 层保持一致）
EXTRA_SPEAK_TEXT = "speak_text"


class DeliveryChannelBase(ABC):
    """推送通道抽象基类：所有通道实现统一的 push 接口。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """通道唯一标识（如 'dialog' / 'wechat' / 'wecom'）。"""

    @abstractmethod
    def push(self, package: DeliveryPackage, context: SessionContext) -> bool:
        """把交付包推送给老板。

        Args:
            package: 已打包的交付包。
            context: 当前会话上下文（可写入 extras 供下游使用）。

        Returns:
            True 表示推送成功，False 表示推送失败。
        """


class DialogChannel(DeliveryChannelBase):
    """对话通道（默认）：把 summary_text 写入 context.extras['speak_text'] 供 TTS 播报。

    本阶段不渲染卡片，仅产出播报文本；后续可扩展为同时返回卡片 payload。
    """

    @property
    def name(self) -> str:
        return "dialog"

    def push(self, package: DeliveryPackage, context: SessionContext) -> bool:
        if not package.summary_text:
            logger.warning("DialogChannel 收到空 summary_text，仍写入 extras")
        context.extras[EXTRA_SPEAK_TEXT] = package.summary_text
        logger.info(
            "对话通道推送完成: result_id=%s, speak_text=%r",
            package.result_id, package.summary_text,
        )
        return True


class WechatChannel(DeliveryChannelBase):
    """微信通道（存根）：本阶段不真发，仅打日志记录推送意图。"""

    @property
    def name(self) -> str:
        return "wechat"

    def push(self, package: DeliveryPackage, context: SessionContext) -> bool:
        logger.info(
            "[微信推送] result_id=%s, task_id=%s, artifacts=%d, summary=%r",
            package.result_id, package.task_id,
            len(package.artifacts), package.summary_text,
        )
        return True


class WecomChannel(DeliveryChannelBase):
    """企业微信通道（存根）：本阶段不真发，仅打日志记录推送意图。"""

    @property
    def name(self) -> str:
        return "wecom"

    def push(self, package: DeliveryPackage, context: SessionContext) -> bool:
        logger.info(
            "[企业微信推送] result_id=%s, task_id=%s, artifacts=%d, summary=%r",
            package.result_id, package.task_id,
            len(package.artifacts), package.summary_text,
        )
        return True


class DeliveryPusher:
    """推送器：按 channel 标识选择对应通道执行推送。

    Attributes:
        channels: 已注册的通道字典，key 为 channel.name。
        default_channel_name: 默认通道名（未指定 channel 时使用）。
    """

    def __init__(
        self,
        channels: Optional[list[DeliveryChannelBase]] = None,
        default_channel_name: Optional[str] = None,
    ) -> None:
        self.channels: dict[str, DeliveryChannelBase] = {}
        # 默认注册三个内置通道
        for ch in (DialogChannel(), WechatChannel(), WecomChannel()):
            self.channels[ch.name] = ch
        # 追加自定义通道（可覆盖同名）
        if channels:
            for ch in channels:
                self.channels[ch.name] = ch

        # 默认通道：优先使用参数指定的，否则从 config 读取
        if default_channel_name is not None:
            self.default_channel_name = default_channel_name
        else:
            settings = get_settings()
            self.default_channel_name = getattr(
                settings, "default_delivery_channel", "dialog"
            )

    def push(
        self,
        package: DeliveryPackage,
        channel: Optional[str] = None,
        context: Optional[SessionContext] = None,
    ) -> bool:
        """按 channel 选择推送器执行推送。

        Args:
            package: 已打包的交付包。
            channel: 通道名；None 时用 default_channel_name。
            context: 会话上下文；None 时新建临时 context（仅供存根通道使用）。

        Returns:
            True 表示推送成功。
        """
        ch_name = channel or self.default_channel_name
        ch = self.channels.get(ch_name)
        if ch is None:
            logger.error(
                "未注册的推送通道: %s，回退到默认通道 %s",
                ch_name, self.default_channel_name,
            )
            ch = self.channels.get(self.default_channel_name)
            if ch is None:
                logger.error("默认通道 %s 也未注册，推送失败", self.default_channel_name)
                return False

        # context 兜底：存根通道无需 context，但 DialogChannel 需要
        if context is None:
            context = SessionContext()

        logger.info(
            "DeliveryPusher 推送: channel=%s, result_id=%s",
            ch.name, package.result_id,
        )
        return ch.push(package, context)


def create_default_pusher() -> DeliveryPusher:
    """构造一个开箱即用的 DeliveryPusher（默认 DialogChannel）。"""
    return DeliveryPusher()
