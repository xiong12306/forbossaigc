# 接入魔搭（ModelScope）免费文生图 — 设计方案

- 日期：2026-07-25
- 状态：已评审通过，待写实现计划
- 范围：执行层新增 ModelScope 文生图适配器，替换/并存现有 NanoBanana，用魔搭免费 API 出图

## 1. 背景与目标

当前出图链路默认走 `MockAdapter`（占位图）。真实出图原本设计走 NanoBanana（付费，通过 Ace Data Cloud），但存在两个问题：

1. `config.py` 的 `nanobanana_api_key` / `use_real_platform` **写死默认值、未从环境变量读取**，导致即使在 `.env` 配置也永不生效——真实出图永远走不通。
2. NanoBanana 需付费 key。

目标：接入**魔搭 ModelScope 免费文生图 API**（每日 2000 次免费额度）作为默认真实出图平台，同时修掉上述配置读取 bug，并保留通过环境变量切换平台的能力。

## 2. 魔搭 API 事实依据（调研确认）

- 免费额度：注册用户 2000 次/天，单模型 500 次/天。
- 鉴权：`MODELSCOPE_SDK_TOKEN`，放 `Authorization: Bearer <token>`。
- 调用为**真·异步**：
  1. 提交：`POST https://api-inference.modelscope.cn/v1/images/generations`
     - 头：`Authorization: Bearer <token>`、`Content-Type: application/json`、`X-ModelScope-Async-Mode: true`、`X-ModelScope-Task-Type: text-to-image-generation`
     - body：`{"model": <id>, "prompt": <str>, "size": "1024x1024", "negative_prompt"?: <str>, "steps"?: <int>, "guidance"?: <float>}`
     - 返回：`{"task_id": <str>}`
  2. 轮询：`GET https://api-inference.modelscope.cn/v1/tasks/{task_id}`
     - 头：`Authorization: Bearer <token>`、`X-ModelScope-Task-Type: image_generation`
     - 返回：`{"task_status": "PENDING|RUNNING|SUCCEED|FAILED", "output_images": [<url>, ...]}`
     - 成功从 `output_images[0]` 取图片 URL。
- 默认模型：`Qwen/Qwen-Image`（中文 prompt 友好、含中文文字渲染强，适合电商主图/海报）。

来源：
- 魔搭免费图片生成 API 说明：https://www.80aj.com/2026/01/24/modelscope-free-image-api/
- ComfyUI-ModelScope-API 实现：https://github.com/hujuying/ComfyUI-ModelScope-API
- modelscope-image-mcp：https://github.com/zym9863/modelscope-image-mcp

## 3. 架构定位

只改**执行层的平台绑定**。七层主链、层间契约、确认锁逻辑**全不动**。魔搭的异步 `submit→poll` 天然贴合现有 `PlatformAdapter` 抽象接口。

```
understanding → confirmation →（老板确认）→ orchestration.select_platform
   └─ 读 config.platform_provider → 选中 PlatformKind.MODELSCOPE
      └─ execution: registry.get(MODELSCOPE) → ModelScopeAdapter.submit/poll → Artifact
```

平台选择由环境变量 `PLATFORM_PROVIDER`（`mock` | `modelscope` | `nanobanana`）显式决定，取代当前有 bug 的 `use_real_platform` 布尔开关。

## 4. 改动清单

### ① `boss_aigc/contracts/enums.py`
`PlatformKind` 新增枚举值：`MODELSCOPE = "modelscope"`。

### ② `boss_aigc/config.py`
修复环境变量读取 bug，并新增魔搭配置，全部从 `os.environ` 读取：

```python
platform_provider: str   = os.environ.get("PLATFORM_PROVIDER", "mock")   # mock|modelscope|nanobanana
modelscope_api_key: str  = os.environ.get("MODELSCOPE_API_KEY", "")
modelscope_api_base: str = os.environ.get("MODELSCOPE_API_BASE", "https://api-inference.modelscope.cn/v1")
modelscope_model: str    = os.environ.get("MODELSCOPE_MODEL", "Qwen/Qwen-Image")
# 同时修复现存 bug：以下两项改为从 env 读取
nanobanana_api_key: str  = os.environ.get("NANOBANANA_API_KEY", "")
use_real_platform: bool  = os.environ.get("USE_REAL_PLATFORM", "").lower() in ("true", "1", "yes")
```

说明：`platform_provider` 是平台选择的唯一真源。`use_real_platform` 仅为向后兼容保留（修好 env 读取），planner 不再依赖它做主判断。

### ③ `boss_aigc/execution/modelscope_adapter.py`（新增）
`ModelScopeAdapter(PlatformAdapter)`，`kind = PlatformKind.MODELSCOPE`：

- `__init__(api_key=None, api_base=None, model=None, timeout=None)`：缺省从 `get_settings()` 取；无 key 记 warning。
- `submit(params) -> str`：
  - 解析 `quantity`（默认 1，clamp 1–8）、`product`、`image_type`、`style`、`prompt`。
  - 构建电商 prompt（复用现有图片类型映射，适配器内自带一份，保持模块自洽）。
  - 按数量循环：`POST /images/generations`（async 头）拿 `task_id` → **内部轮询** `GET /tasks/{task_id}`，间隔 `poll_interval_sec`，累计不超过 `request_timeout_sec`，直到 `SUCCEED`/`FAILED`。
  - `SUCCEED`：从 `output_images[0]` 构 `Artifact(kind="IMAGE", url_or_path=url, metadata={source:"modelscope", model, prompt, size, task_id, image_type, product})`。
  - 全部成功 → 缓存 `DELIVERED`；任一失败/超时/无图 → 缓存 `FAILED` + 明确 `error_message`。
- `poll(platform_task_id) -> (TaskStatus, Optional[list[Artifact]])`：返回 submit 已缓存的结果（**同步包装模式**，与现有 NanoBanana 一致，使调度器 `run_step_with_retry` 无需改动）。
- `cancel(platform_task_id) -> bool`：仅标记内存状态（同步请求无法真正取消）。
- `normalize_result(raw) -> Artifact`：字段映射。

### ④ `boss_aigc/orchestration/planner.py` — `select_platform`
```python
if task_type == TaskType.IMAGE_GEN:
    if settings.platform_provider == "modelscope" and settings.modelscope_api_key:
        return PlatformKind.MODELSCOPE
    if settings.platform_provider == "nanobanana" and settings.nanobanana_api_key:
        return PlatformKind.NANOBANANA
return PlatformKind.MOCK
```

### ⑤ `boss_aigc/execution/registry.py` — `register_default_adapters`
- 始终注册 `MockAdapter`（供 `PLATFORM_PROVIDER=mock` 显式使用）。
- `platform_provider == "modelscope"` 且有 key → 注册 `ModelScopeAdapter`。
- `platform_provider == "nanobanana"` 且有 key → 注册 `NanoBananaAdapter`。

### ⑥ `.env.example`
新增并注释：
```
# 出图平台：mock（占位图）| modelscope（魔搭免费）| nanobanana（付费）
PLATFORM_PROVIDER=modelscope
# 魔搭 SDK Token：modelscope.cn 账号设置页获取
MODELSCOPE_API_KEY=
# 魔搭文生图模型（默认 Qwen/Qwen-Image）
MODELSCOPE_MODEL=Qwen/Qwen-Image
MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1
```
旧的 `NANOBANANA_API_KEY` / `USE_REAL_PLATFORM` 保留并标注为可选/兼容。

### 测试
- 新增 `boss_aigc/execution/_test_modelscope.py`：monkeypatch `requests.post`/`requests.get`，覆盖
  1. SUCCEED：submit→poll 得到图片 URL；
  2. FAILED：`task_status=FAILED` → 状态 FAILED；
  3. 无 key：submit 直接 FAILED；
  4. `_extract` / `output_images` URL 提取。
- planner 选平台测试：`provider=modelscope`+key → MODELSCOPE；无 key → MOCK；`provider=nanobanana`+key → NANOBANANA。
- 现有 Mock 版 `_e2e_test` / 各层 `_test_*` 保持绿。

## 5. 错误处理原则（遵循全局「不擅自加兜底」规约）

- **运行时 API 失败**（超时 / `task_status=FAILED` / 无 `output_images`）→ 直接返回 `TaskStatus.FAILED`，让错误快速暴露（前端显示"执行失败"），**不静默降级到 Mock**。
- **Mock 仅在 `PLATFORM_PROVIDER=mock` 显式选择时使用**，不作隐藏兜底。
- **`provider=modelscope` 却未配 key** → 视为配置错误，`submit` 直接置 FAILED 并记明确日志，不偷偷回退。
- 因此本次实现**不为真实平台路径挂 Mock fallback_adapter**。

## 6. 数据流 / 契约

主链契约不变。`Artifact.metadata` 补充溯源字段：`source="modelscope"`、`model`、`prompt`、`size`、`task_id`。交付层与前端渲染逻辑不变，出真图后自动显示。

## 7. 明确不做（YAGNI）

- 改图 `IMAGE_EDIT`（Qwen-Image-Edit）、LoRA、seed 复现——留后续。
- 不动前端。
- 不碰确认锁、计费阈值、交付通道逻辑。
- 不并行多步；数量>1 时串行提交多个 task。

## 8. 验收标准

1. 配好 `PLATFORM_PROVIDER=modelscope` + `MODELSCOPE_API_KEY` 后，"给保温杯出 1 张主图"→确认→能返回真实图片 URL，状态 DELIVERED。
2. 未配 key 时该路径返回 FAILED（不静默出占位图）。
3. `PLATFORM_PROVIDER=mock`（或不配）时仍走 Mock，现有 e2e 全绿。
4. 新增单测 + 现有测试全部通过。
