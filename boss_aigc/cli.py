"""boss_aigc.cli 老板 AI 助手可交互 REPL demo。

复用 _e2e_test 里的 build_full_pipeline 装配七层真实处理器，
循环读取老板输入，调用 pipeline.handle_user_input 后打印 Response.message
+ speak_text，模拟语音播报。

运行：.venv/bin/python -m boss_aigc.cli
退出：输入 quit / exit / 退出
"""

from __future__ import annotations

from boss_aigc._e2e_test import build_full_pipeline
from boss_aigc.pipeline import SessionContext

# 退出命令集合（不区分大小写）
_EXIT_COMMANDS = {"quit", "exit", "退出", "bye", "再见", "q"}


def _print_banner() -> None:
    """打印使用说明与示例指令。"""
    print("=" * 64)
    print("  🎙️  老板 AI 助手 (BossAIGC) · 七层全链路 Mock 交互 demo")
    print("=" * 64)
    print()
    print("  使用方式：直接输入指令，回车提交。助手会经过")
    print("  接入 → 理解 → 确认 → 编排 → 执行 → 交付 全流程。")
    print()
    print("  📌 示例指令：")
    print("    1. 小帮小帮，给保温杯出 3 张主图，轻奢暖色调")
    print("    2. 确认              （确认开始执行）")
    print("    3. 可以了            （验收通过，归档到资产库）")
    print()
    print("  其他可用指令：")
    print("    · 给马克杯出 1 张主图         （下任务）")
    print("    · 数量改成 2 张              （修改参数，仍待确认）")
    print("    · 取消                       （取消任务）")
    print("    · 出几张图                   （模糊指令触发追问）")
    print("    · 给保温杯出 3 张             （追问后补全商品）")
    print()
    print(f"  退出：输入 {' / '.join(sorted(_EXIT_COMMANDS))}")
    print("=" * 64)
    print()


def _format_artifacts_summary(result: object) -> str:
    """把 TaskResult.artifacts 概要成一行文本，便于展示。"""
    if result is None:
        return ""
    artifacts = getattr(result, "artifacts", None) or []
    if not artifacts:
        return "（无产出物）"
    # 按类型分组计数
    counts: dict[str, int] = {}
    for art in artifacts:
        kind = getattr(art, "kind", "UNKNOWN")
        counts[kind] = counts.get(kind, 0) + 1
    parts = [f"{count} {kind}" for kind, count in counts.items()]
    return "产出物：" + "、".join(parts)


def main() -> None:
    """REPL 主循环。"""
    _print_banner()

    # 装配七层全链路 Pipeline + 全新会话上下文
    pipeline, ctx = build_full_pipeline()

    while True:
        try:
            user_input = input("老板> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D / Ctrl+C 退出
            print()
            break

        if not user_input:
            continue

        if user_input.lower() in _EXIT_COMMANDS:
            print("👋 再见，老板！")
            break

        # 调用 Pipeline 处理一轮
        try:
            response = pipeline.handle_user_input(user_input, ctx)
        except Exception as e:
            print(f"⚠️ 处理出错：{e!r}")
            continue

        # 打印状态
        status_label = response.status.value if hasattr(response.status, "value") else str(response.status)
        print(f"[{status_label}] {response.message}")

        # 模拟语音播报：若 extras 有 speak_text，且与 message 不同则再展示
        speak_text = ctx.extras.get("speak_text", "")
        if speak_text and speak_text != response.message:
            print(f"🔊 (TTS) {speak_text}")

        # 若有产出物，展示概要
        result = getattr(ctx, "result", None)
        if result is not None and getattr(result, "artifacts", None):
            print(f"📦 {_format_artifacts_summary(result)}")

        # 若有追问文本（理解层），单独高亮
        follow_up = ctx.extras.get("follow_up_question")
        if follow_up and response.status.value == "understanding":
            print(f"❓ {follow_up}")

        print()  # 空行分隔每轮


if __name__ == "__main__":
    main()
