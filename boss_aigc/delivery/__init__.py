"""boss_aigc 交付层包。

职责：结果打包 / 多通道推送 / 老板验收-修改-重新生成-归档。

主链第六层（delivery）：
    - 第 1 轮（执行完）：执行层产出 TaskResult → 交付层打包 DeliveryPackage
      → 通过 dialog/wechat/wecom 通道推送给老板 → status=DELIVERED 等验收
    - 第 2 轮（验收反馈）：老板回复「可以了/改第2张/重做」→ 交付层 parse_acceptance
      → ACCEPT 归档 / MODIFY 构造修改任务 / REGENERATE 重新执行 / OTHER 再问一次
"""

from boss_aigc.delivery.acceptance import (
    AcceptanceAction,
    handle_acceptance,
    parse_acceptance,
)
from boss_aigc.delivery.channels import (
    DeliveryChannelBase,
    DeliveryPusher,
    DialogChannel,
    WecomChannel,
    WechatChannel,
    create_default_pusher,
)
from boss_aigc.delivery.handler import (
    build_delivery_handler,
    create_default_delivery,
)
from boss_aigc.delivery.packager import (
    DeliveryPackage,
    package_result,
)

__all__ = [
    # 打包
    "DeliveryPackage",
    "package_result",
    # 通道
    "DeliveryChannelBase",
    "DeliveryPusher",
    "DialogChannel",
    "WechatChannel",
    "WecomChannel",
    "create_default_pusher",
    # 验收
    "AcceptanceAction",
    "parse_acceptance",
    "handle_acceptance",
    # 处理器
    "build_delivery_handler",
    "create_default_delivery",
]
