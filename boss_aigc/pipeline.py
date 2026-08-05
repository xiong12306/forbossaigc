"""boss_aigc.pipeline 层间调用总线/管道。

数据按序流经六层主链：
    access → understanding → confirmation → orchestration → execution → delivery
asset 层作为横切关注点（被各层查询/写入），不进入主链线性顺序。

设计要点：
- 每层定义为可调用处理器 LayerHandler(upstream, context) -> Any
- 支持 before_layer / after_layer 钩子用于埋点
- 暴露高层方法 handle_user_input(text, context) -> Response
- 本阶段各层处理器为占位实现，后续任务填充真实逻辑
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from boss_aigc.contracts.enums import TaskStatus, TaskType
from boss_aigc.contracts.execution import ConfirmedTask, TaskExecution, TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary
from boss_aigc.logging_setup import get_logger

logger = get_logger(__name__, layer="pipeline")

# 主链六层名称（顺序固定）
LAYER_ACCESS = "access"
LAYER_UNDERSTANDING = "understanding"
LAYER_CONFIRMATION = "confirmation"
LAYER_ORCHESTRATION = "orchestration"
LAYER_EXECUTION = "execution"
LAYER_DELIVERY = "delivery"

MAIN_LAYERS: list[str] = [
    LAYER_ACCESS,
    LAYER_UNDERSTANDING,
    LAYER_CONFIRMATION,
    LAYER_ORCHESTRATION,
    LAYER_EXECUTION,
    LAYER_DELIVERY,
]

# 停止状态集合：每层执行后若 context.status 落在此集合内，pipeline 早停，
# 不再执行后续层。这是确认锁的核心机制：
#   - AWAITING_CONFIRMATION：确认层等待老板回复，禁止进入 orchestration/execution
#   - UNDERSTANDING：理解层缺槽位需追问，禁止进入 confirmation
#   - CANCELLED：老板取消任务
#   - FAILED：执行失败
#   - ACCEPTED：验收归档完成，本轮任务结束（后续新任务由前端重置/后端自动清状态处理）
# 特殊：理解层把 AWAITING_CONFIRMATION 作为「移交确认层」的交接信号，
# 此时不应早停，需继续到确认层生成摘要（见 handle_user_input 中的特判）。
STOP_STATUSES: set[TaskStatus] = {
    TaskStatus.AWAITING_CONFIRMATION,
    TaskStatus.UNDERSTANDING,
    TaskStatus.CANCELLED,
    TaskStatus.FAILED,
    TaskStatus.ACCEPTED,
}


@runtime_checkable
class LayerHandler(Protocol):
    """层处理器协议：输入 (上一层产出, SessionContext) 返回本层产出。"""

    def __call__(self, upstream: Any, context: "SessionContext") -> Any: ...


# 钩子签名：(layer_name, upstream, context) -> None
BeforeHook = Callable[[str, Any, "SessionContext"], None]
AfterHook = Callable[[str, Any, "SessionContext"], None]


@dataclass
class SessionContext:
    """会话上下文：保存一次会话的状态，在层间流转。

    各层从 context 读取需要的状态、并把产出写回 context，
    避免层间直接耦合。

    Attributes:
        session_id: 会话 ID。
        user_input: 当前轮用户原始输入文本。
        intent: 理解层产出的当前意图。
        pending_summary: 待老板确认的任务摘要（确认前暂存）。
        confirmed_task: 已确认任务（确认锁放行后写入）。
        execution: 当前执行实例。
        result: 最新任务结果。
        status: 当前会话整体状态。
        history: 历史交互记录。
        extras: 各层可自由读写的附加字段（如风格库、商品资产句柄）。
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_input: str = ""
    intent: Optional[TaskIntent] = None
    pending_summary: Optional[TaskSummary] = None
    confirmed_task: Optional[ConfirmedTask] = None
    execution: Optional[TaskExecution] = None
    result: Optional[TaskResult] = None
    status: TaskStatus = TaskStatus.PENDING
    history: list[Any] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    """Pipeline 对外的统一响应包装。

    Attributes:
        session_id: 对应会话 ID。
        status: 当前任务状态。
        message: 给老板的反馈文本（可交给 TTS 播报）。
        payload: 附加数据（如摘要卡片 / 产出物）。
    """

    session_id: str
    status: TaskStatus
    message: str = ""
    payload: Any = None


class Pipeline:
    """七层管道：把数据按序流经主链各层。

    用法：
        p = Pipeline()
        ctx = SessionContext()
        resp = p.handle_user_input("给保温杯出 3 张主图", ctx)
    """

    def __init__(self) -> None:
        # 各层处理器（占位实现，后续任务覆写）
        self._handlers: dict[str, LayerHandler] = {
            LAYER_ACCESS: _placeholder_access,
            LAYER_UNDERSTANDING: _placeholder_understanding,
            LAYER_CONFIRMATION: _placeholder_confirmation,
            LAYER_ORCHESTRATION: _placeholder_orchestration,
            LAYER_EXECUTION: _placeholder_execution,
            LAYER_DELIVERY: _placeholder_delivery,
        }
        self._before_hooks: list[BeforeHook] = []
        self._after_hooks: list[AfterHook] = []

    # ---------- 处理器注册 ----------
    def register_layer(self, name: str, handler: LayerHandler) -> None:
        """替换某一层的处理器（可插拔）。"""
        if name not in MAIN_LAYERS:
            raise ValueError(f"未知层名: {name}，合法值: {MAIN_LAYERS}")
        self._handlers[name] = handler

    # ---------- 钩子 ----------
    def add_before_hook(self, hook: BeforeHook) -> None:
        """添加层前钩子（埋点 / 鉴权 / 上下文初始化等）。"""
        self._before_hooks.append(hook)

    def add_after_hook(self, hook: AfterHook) -> None:
        """添加层后钩子（埋点 / 指标统计 / 结果缓存等）。"""
        self._after_hooks.append(hook)

    # ---------- 默认埋点钩子 ----------
    def _default_before_logger(self, layer: str, upstream: Any, ctx: SessionContext) -> None:
        logger.info(
            "进入层 %s", layer,
            extra={"layer": layer, "task_id": ctx.session_id},
        )

    def _default_after_logger(self, layer: str, downstream: Any, ctx: SessionContext) -> None:
        logger.info(
            "离开层 %s", layer,
            extra={"layer": layer, "task_id": ctx.session_id},
        )

    # ---------- 高层入口 ----------
    def handle_user_input(self, text: str, context: SessionContext) -> Response:
        """处理一轮用户输入，数据按序流经六层主链。

        路由策略（确认锁依赖）：
            - access 总是跑（处理语音/文字 → 纯指令文本；老板用语音说「确认」也需 ASR）
            - access 之后判断 context.status 决定后续起点：
                * AWAITING_CONFIRMATION：上一轮已生成摘要等待确认，本轮直接跳到 confirmation
                  层处理老板的确认/修改/取消回复（跳过 understanding，避免把「确认」当新任务）
                * DELIVERED：上一轮已交付，本轮老板输入是验收反馈（接受/修改/重做），
                  直接跳到 delivery 层处理（跳过 understanding/confirmation/orchestration/execution，
                  避免把「可以了」当新任务）
                * UNDERSTANDING：上一轮 needs_follow_up，从 understanding 续跑
                * 其余：fresh 起点从 understanding 全链路跑
            - 每层执行后检查 context.status，若在 STOP_STATUSES 内则早停
              （但理解层把 AWAITING_CONFIRMATION 作为交接信号给确认层时不早停）

        Args:
            text: 用户原始输入（语音 ASR 后的文本或直接文字）。
            context: 会话上下文（跨轮复用）。

        Returns:
            Response 包装的最终反馈。message 反映当前状态。
        """
        context.user_input = text
        # 记录本轮入口状态，用于路由决策（access 不改 status）
        prev_status = context.status

        # ---------- Step 1: 总是跑 access 层 ----------
        # access 处理语音/文字 → 纯指令文本，老板用语音说「确认」也需走 ASR
        upstream: Any = text
        upstream = self._run_layer(LAYER_ACCESS, upstream, context)

        # ---------- Step 2: 根据入口状态决定后续层链 ----------
        # ACCEPTED是终态：验收归档完成，收到新输入自动重置上下文开始新任务
        if prev_status == TaskStatus.ACCEPTED:
            # 清空旧任务状态，回到初始PENDING状态，按新任务处理
            context.intent = None
            context.pending_summary = None
            context.confirmed_task = None
            context.execution = None
            context.result = None
            context.status = TaskStatus.PENDING
            context.extras.clear()
            prev_status = TaskStatus.PENDING

        if prev_status == TaskStatus.AWAITING_CONFIRMATION:
            # 第二+轮：老板在回复待确认摘要，直接进 confirmation 层
            # 跳过 understanding，避免「确认」被识别为新任务
            remaining_layers: list[str] = [
                LAYER_CONFIRMATION,
                LAYER_ORCHESTRATION,
                LAYER_EXECUTION,
                LAYER_DELIVERY,
            ]
        elif prev_status == TaskStatus.DELIVERED:
            # 上一轮已交付，老板本轮输入是验收反馈（可以了/改/重做），
            # 先进 delivery 层处理验收；若 delivery 处理后状态变为 CONFIRMED（重做/重新生成），
            # 需继续执行 orchestration → execution → delivery 重新生成；
            # 若变为 AWAITING_CONFIRMATION（修改任务），等下一轮老板确认；
            # 其他状态（ACCEPTED/FAILED/DELIVERED）直接返回。
            remaining_layers = [LAYER_DELIVERY]
            post_acceptance_layers: list[str] = [
                LAYER_ORCHESTRATION,
                LAYER_EXECUTION,
                LAYER_DELIVERY,
            ]
        else:
            # fresh 或 UNDERSTANDING(needs_follow_up)：从 understanding 跑全链
            remaining_layers = [
                LAYER_UNDERSTANDING,
                LAYER_CONFIRMATION,
                LAYER_ORCHESTRATION,
                LAYER_EXECUTION,
                LAYER_DELIVERY,
            ]

        # ---------- Step 3: 跑后续层 + 早停检查 ----------
        for layer_name in remaining_layers:
            upstream = self._run_layer(layer_name, upstream, context)

            # 早停检查：status 在停止集合内则 break
            if context.status in STOP_STATUSES:
                # 特判：理解层把 AWAITING_CONFIRMATION 作为「移交确认层」的交接信号，
                # 此时不应早停，需继续到确认层生成摘要
                if (
                    layer_name == LAYER_UNDERSTANDING
                    and context.status == TaskStatus.AWAITING_CONFIRMATION
                ):
                    continue
                logger.info(
                    "层 %s 执行后 status=%s，早停后续层",
                    layer_name, context.status.value,
                    extra={"layer": layer_name, "task_id": context.session_id},
                )
                break

        # 验收反馈后处理：若 delivery 处理完重做操作后状态变为 CONFIRMED，
        # 继续执行 orchestration → execution → delivery 重新生成任务
        if prev_status == TaskStatus.DELIVERED and context.status == TaskStatus.CONFIRMED:
            logger.info(
                "验收反馈触发重新生成，继续执行执行链路",
                extra={"task_id": context.session_id},
            )
            # 清理旧 result，避免前端拿到旧 artifacts
            context.result = None
            for layer_name in post_acceptance_layers:
                upstream = self._run_layer(layer_name, upstream, context)
                if context.status in STOP_STATUSES:
                    logger.info(
                        "重新生成链路：层 %s 执行后 status=%s，早停",
                        layer_name, context.status.value,
                        extra={"layer": layer_name, "task_id": context.session_id},
                    )
                    break

        # ---------- Step 4: 构造 Response ----------
        message = self._build_response_message(context)
        # payload 优先用 result，否则用 confirmed_task / pending_summary
        payload: Any = context.result
        if payload is None and context.confirmed_task is not None:
            payload = context.confirmed_task
        if payload is None and context.pending_summary is not None:
            payload = context.pending_summary

        return Response(
            session_id=context.session_id,
            status=context.status,
            message=message,
            payload=payload,
        )

    # ---------- 内部：单层执行（带钩子与日志）----------
    def _run_layer(self, layer_name: str, upstream: Any, context: SessionContext) -> Any:
        """执行单层处理器，前后触发钩子与日志埋点，返回该层产出。"""
        handler = self._handlers[layer_name]
        # before 钩子
        for hook in self._before_hooks:
            hook(layer_name, upstream, context)
        self._default_before_logger(layer_name, upstream, context)
        # 执行层
        downstream = handler(upstream, context)
        # after 钩子
        self._default_after_logger(layer_name, downstream, context)
        for hook in self._after_hooks:
            hook(layer_name, downstream, context)
        return downstream

    # ---------- 内部：根据当前状态构造 Response message ----------
    @staticmethod
    def _build_response_message(context: SessionContext) -> str:
        """根据 context.status 与 extras 构造给老板的反馈文本。"""
        # 优先用 extras['speak_text']（确认层写入的自然语言播报文本）
        speak_text = context.extras.get("speak_text")
        # 理解层的追问文本
        follow_up = context.extras.get("follow_up_question")

        status = context.status
        if status == TaskStatus.AWAITING_CONFIRMATION:
            if speak_text:
                return speak_text
            return "请确认任务摘要"
        if status == TaskStatus.UNDERSTANDING:
            return follow_up or "请补充信息"
        if status == TaskStatus.CONFIRMED:
            return speak_text or "已确认，开始执行"
        if status == TaskStatus.CANCELLED:
            return speak_text or "已取消"
        if status == TaskStatus.EXECUTING:
            return "执行中"
        if status == TaskStatus.DELIVERED:
            return "已交付，请验收"
        if status == TaskStatus.ACCEPTED:
            return "已完成"
        if status == TaskStatus.FAILED:
            return "执行失败"
        return ""


# ---------- 安全占位处理器 ----------
# 直接实例化 Pipeline() 会使用这些占位处理器，仅用于链路冒烟测试。
# 生产环境必须通过 build_full_pipeline() 注册真实处理器（server.py 已正确使用）。
# 占位处理器抛出 RuntimeError，避免误用导致"静默成功"的假象。

def _placeholder_access(upstream: Any, context: SessionContext) -> str:
    raise RuntimeError(
        "access 层未注册真实处理器。请使用 build_full_pipeline() 构造 Pipeline，"
        "或调用 pipeline.register_layer('access', build_access_handler(...))。"
    )


def _placeholder_understanding(upstream: Any, context: SessionContext) -> TaskIntent:
    raise RuntimeError(
        "understanding 层未注册真实处理器。请使用 build_full_pipeline() 构造 Pipeline，"
        "或调用 pipeline.register_layer('understanding', build_understanding_handler(...))。"
    )


def _placeholder_confirmation(upstream: Any, context: SessionContext) -> TaskSummary:
    raise RuntimeError(
        "confirmation 层未注册真实处理器。请使用 build_full_pipeline() 构造 Pipeline。"
    )


def _placeholder_orchestration(upstream: Any, context: SessionContext) -> TaskExecution:
    raise RuntimeError(
        "orchestration 层未注册真实处理器。请使用 build_full_pipeline() 构造 Pipeline。"
    )


def _placeholder_execution(upstream: Any, context: SessionContext) -> TaskResult:
    raise RuntimeError(
        "execution 层未注册真实处理器。请使用 build_full_pipeline() 构造 Pipeline。"
    )


def _placeholder_delivery(upstream: Any, context: SessionContext) -> Response:
    raise RuntimeError(
        "delivery 层未注册真实处理器。请使用 build_full_pipeline() 构造 Pipeline。"
    )
