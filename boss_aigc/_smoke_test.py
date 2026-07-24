"""boss_aigc._smoke_test 冒烟测试。

实例化各契约、注册 Mock 适配器、跑通 Pipeline 主链。
运行：python -m boss_aigc._smoke_test
不报错即通过。
"""

from __future__ import annotations

from boss_aigc.contracts import (
    Artifact,
    BrandStyle,
    ConfirmedTask,
    ProductAsset,
    SlotValue,
    TaskExecution,
    TaskIntent,
    TaskResult,
    TaskStep,
    TaskSummary,
)
from boss_aigc.contracts.enums import (
    ConfirmationAction,
    DeliveryChannel,
    PlatformKind,
    TaskStatus,
    TaskType,
)
from boss_aigc.execution import MockAdapter, get_registry
from boss_aigc.pipeline import Pipeline, SessionContext


def main() -> None:
    # 1. 枚举可访问
    assert TaskType.IMAGE_GEN == "image_gen"
    assert TaskStatus.PENDING == "pending"
    assert ConfirmationAction.CONFIRM == "confirm"
    assert PlatformKind.MOCK == "mock"
    assert DeliveryChannel.DIALOG == "dialog"
    print("[1/6] 枚举 OK")

    # 2. 契约类可实例化
    intent = TaskIntent(
        intent_id="i1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        slots={"quantity": SlotValue(name="quantity", value=3, confidence=0.95)},
        raw_text="给保温杯出 3 张主图",
        confidence=0.9,
    )
    summary = TaskSummary(
        summary_id="s1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        params={"quantity": 3, "style": "轻奢暖色调"},
        platform=PlatformKind.MOCK,
        estimated_duration_sec=180,
        estimated_cost=15,
        delivery_channel=DeliveryChannel.DIALOG,
        is_high_cost=False,
    )
    confirmed = ConfirmedTask(
        task_id="t1",
        intent=intent,
        summary=summary,
    )
    step = TaskStep(step_id="st1", name="出主图", platform=PlatformKind.MOCK)
    execution = TaskExecution(
        execution_id="e1",
        task_id="t1",
        platform=PlatformKind.MOCK,
        steps=[step],
        progress=50,
    )
    artifact = Artifact(
        artifact_id="a1",
        kind="IMAGE",
        url_or_path="mock://image/1.png",
        thumbnail_path="mock://thumb/1.png",
    )
    result = TaskResult(
        result_id="r1",
        task_id="t1",
        artifacts=[artifact],
    )
    brand = BrandStyle(style_id="b1", keywords=["轻奢", "暖色调"])
    asset = ProductAsset(asset_id="pa1", product_name="保温杯", sku="SKU001")
    print("[2/6] 契约实例化 OK")
    print(f"      intent={intent.intent_id} summary={summary.summary_id} "
          f"confirmed={confirmed.task_id} exec={execution.execution_id} "
          f"result={result.result_id} brand={brand.style_id} asset={asset.asset_id}")

    # 3. 适配器注册 + 取用
    registry = get_registry()
    mock = MockAdapter()
    registry.register(PlatformKind.MOCK, mock)
    assert registry.get(PlatformKind.MOCK) is mock
    assert mock.submit({"x": 1}).startswith("mock-task-")
    assert mock.cancel("x") is True
    print(f"[3/6] 适配器注册 OK，已注册平台: {registry.list_kinds()}")

    # 4. Pipeline 可实例化
    pipeline = Pipeline()
    print("[4/6] Pipeline 实例化 OK")

    # 5. Pipeline 跑通主链
    ctx = SessionContext()
    resp = pipeline.handle_user_input("给保温杯出 3 张主图，轻奢暖色调", ctx)
    assert resp.status == TaskStatus.ACCEPTED, f"预期 ACCEPTED，实际 {resp.status}"
    print(f"[5/6] Pipeline 主链跑通 OK，最终状态={resp.status.value}")

    # 6. 钩子可注入
    seen: list[str] = []
    pipeline.add_before_hook(lambda layer, up, c: seen.append(f"before:{layer}"))
    pipeline.add_after_hook(lambda layer, down, c: seen.append(f"after:{layer}"))
    ctx2 = SessionContext()
    pipeline.handle_user_input("再出 2 张", ctx2)
    assert any("before:delivery" in s for s in seen), "before 钩子未触发"
    assert any("after:access" in s for s in seen), "after 钩子未触发"
    print(f"[6/6] 钩子注入 OK，共触发 {len(seen)} 次")

    print("\n全部冒烟测试通过 ✅")


if __name__ == "__main__":
    main()
