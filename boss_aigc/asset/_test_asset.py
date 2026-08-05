"""asset 层自测。

运行：`.venv/bin/python -m boss_aigc.asset._test_asset`
覆盖：
    1. BrandStyleStore.get_or_prompt 首次返回默认风格，关键词含「轻奢」
    2. ProductAssetStore.add + list_recent
    3. inject_style_lock：params 无 style 时注入品牌风格关键词
    4. TaskHistoryStore.record + search：按 product 搜索命中
    5. TaskTemplateStore.promote_to_template + get_template
    6. AssetStore 聚合 + inject_style
"""

import pytest

from boss_aigc.asset import (
    AssetStore,
    BrandStyleStore,
    ProductAssetStore,
    TaskHistoryStore,
    TaskTemplateStore,
    create_default_asset_store,
    inject_style_lock,
)
from boss_aigc.contracts.enums import PlatformKind, TaskStatus, TaskType
from boss_aigc.contracts.execution import Artifact, TaskResult
from boss_aigc.contracts.intent import TaskIntent
from boss_aigc.contracts.summary import TaskSummary


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {msg}")
    print(f"  OK  {msg}")


def test_brand_style_store() -> None:
    print("[1] BrandStyleStore.get_or_prompt")
    store = BrandStyleStore()
    style = store.get_or_prompt(
        onboarding_callback=lambda: ["轻奢", "暖色调", "大面积留白"]
    )
    _ok(style is not None, "首次返回 BrandStyle 实例")
    _ok("轻奢" in style.keywords, "关键词包含「轻奢」")
    # 再次调用应返回同一对象，不重复引导
    style2 = store.get_or_prompt()
    _ok(style2 is style, "已存在时不重复引导")
    # get_style_keywords 与风格一致
    _ok(store.get_style_keywords() == list(style.keywords), "get_style_keywords 返回正确")


def test_product_asset_store() -> None:
    print("[2] ProductAssetStore.add + list_recent")
    store = ProductAssetStore()
    store.add("保温杯", sku="CUP-001", reference_image_path="/tmp/cup.png")
    store.add("香薰", sku="INC-002", reference_image_path="/tmp/inc.png")
    recent = store.list_recent(3)
    _ok(len(recent) == 2, "加 2 个商品后 list_recent(3) 返回 2 个")
    _ok(store.get("保温杯") is not None, "按名查命中保温杯")
    _ok(store.get("不存在") is None, "未命中返回 None")
    _ok(len(store.list_all()) == 2, "list_all 返回全部 2 个")


def test_inject_style_lock() -> None:
    print("[3] inject_style_lock")
    bs = BrandStyleStore()
    bs.set_style(["轻奢", "暖色调"])
    # 无 style 时注入
    params = {"quantity": 3}
    out = inject_style_lock(params, bs)
    _ok("style" in out, "params 无 style 时注入")
    _ok("轻奢" in out["style"], "注入内容包含品牌关键词")
    _ok("style" not in params, "不修改入参 params")
    # 已有 style 不覆盖
    params2 = {"style": ["极简"]}
    out2 = inject_style_lock(params2, bs)
    _ok(out2["style"] == ["极简"], "params 已有 style 时不覆盖")
    # 空风格库时不注入（先清理 DB 中的品牌风格）
    from boss_aigc.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM brand_styles")
    bs_empty = BrandStyleStore()
    out3 = inject_style_lock({"quantity": 1}, bs_empty)
    _ok("style" not in out3, "无品牌风格时不注入")


def test_task_history_store() -> None:
    print("[4] TaskHistoryStore.record + search")
    history = TaskHistoryStore()
    intent = TaskIntent(
        intent_id="i1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        raw_text="给保温杯出 3 张主图",
    )
    summary = TaskSummary(
        summary_id="s1",
        task_type=TaskType.IMAGE_GEN,
        product="保温杯",
        params={"quantity": 3},
        platform=PlatformKind.MOCK,
    )
    result = TaskResult(
        result_id="r1",
        task_id="t1",
        artifacts=[Artifact(artifact_id="a1", kind="IMAGE")],
        status=TaskStatus.DELIVERED,
    )
    history.record(intent, summary, result)

    # 第二条：不同商品
    intent2 = intent.model_copy(update={"product": "香薰", "raw_text": "给香薰出图"})
    summary2 = summary.model_copy(update={"product": "香薰"})
    result2 = result.model_copy(update={"task_id": "t2"})
    history.record(intent2, summary2, result2)

    # 按 product 搜索
    hits = history.search(product="保温杯")
    _ok(len(hits) == 1, "按 product=保温杯 命中 1 条")
    _ok(hits[0]["product"] == "保温杯", "命中记录 product 字段正确")
    _ok(hits[0]["result_artifacts_count"] == 1, "记录中含 result_artifacts_count")
    _ok("raw_text" in hits[0], "记录中含 raw_text")
    _ok("timestamp" in hits[0], "记录中含 timestamp")

    # get_recent
    recent = history.get_recent(5)
    _ok(len(recent) == 2, "get_recent(5) 返回 2 条")
    _ok(recent[0]["task_id"] == "t2", "get_recent 按倒序返回最新在前")

    # 按 task_type 搜索
    hits2 = history.search(task_type="image_gen")
    _ok(len(hits2) == 2, "按 task_type=image_gen 命中 2 条")


def test_task_template_store() -> None:
    print("[5] TaskTemplateStore.promote_to_template + get_template")
    tpl = TaskTemplateStore()
    record = {
        "task_id": "t1",
        "task_type": "image_gen",
        "product": "保温杯",
        "raw_text": "给保温杯出 3 张主图",
        "summary": {"summary_id": "s1", "params": {"quantity": 3}},
    }
    tpl.promote_to_template(record, "保温杯主图模板")
    _ok("保温杯主图模板" in tpl.list_templates(), "list_templates 包含已沉淀模板")
    got = tpl.get_template("保温杯主图模板")
    _ok(got is not None and got["task_type"] == "image_gen", "get_template 取出含 task_type")
    _ok(got["created_from_task_id"] == "t1", "模板记录来源 task_id")
    _ok(
        tpl.suggest_template("image_gen", "保温杯") == "保温杯主图模板",
        "suggest_template 命中",
    )
    _ok(
        tpl.suggest_template("video_gen", "保温杯") is None,
        "suggest_template 未命中返回 None",
    )
    _ok(tpl.get_template("不存在") is None, "get_template 未命中返回 None")


def test_asset_store_aggregation() -> None:
    print("[6] AssetStore 聚合 + inject_style")
    store = create_default_asset_store()
    _ok(isinstance(store, AssetStore), "create_default_asset_store 返回 AssetStore 实例")
    _ok(isinstance(store.brand_style, BrandStyleStore), "聚合含 brand_style")
    _ok(isinstance(store.product_asset, ProductAssetStore), "聚合含 product_asset")
    _ok(isinstance(store.history, TaskHistoryStore), "聚合含 history")
    _ok(isinstance(store.template, TaskTemplateStore), "聚合含 template")

    store.brand_style.set_style(["轻奢"])
    out = store.inject_style({"quantity": 2})
    _ok("style" in out and "轻奢" in out["style"], "AssetStore.inject_style 注入成功")


def main() -> None:
    test_brand_style_store()
    test_product_asset_store()
    test_inject_style_lock()
    test_task_history_store()
    test_task_template_store()
    test_asset_store_aggregation()
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
