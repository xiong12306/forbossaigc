# BossAIGC 项目总览

> 本文档供 AI 编程助手（Trae Code）在新对话中快速理解项目架构、约定与关键约束。

## 项目定位

**BossAIGC** — 老板 AI 助手：让老板一句话吩咐干活，七层架构骨架与统一数据契约。面向电商场景，支持语音/文字对话出图、无限画布节点式创作、电商多功能平台三大入口。

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 后端 | Python + FastAPI + Pydantic | 3.11+ / 0.139.2 / 2.13 |
| 前端 | React + Vite + TypeScript + TailwindCSS + Zustand | 18 / 6 / 5.8 / 3.4 / 5 |
| 数据库 | Supabase 优先，SQLite 兜底 | — |
| 部署 | Docker 多阶段构建 + Nginx + Let's Encrypt | — |
| CI/CD | GitHub Actions（CI 测试 → Docker 镜像 → 自动部署） | — |

## 三大前端入口

| 路径 | 组件 | 说明 |
|---|---|---|
| `/` | Home | AI 语音助手（对话式出图，七层 Pipeline） |
| `/canvas` | CanvasPage + InfiniteCanvas | 无限画布（节点连线式创作，支持画布持久化） |
| `/platform/*` | PlatformLayout + 子页面 | 电商多功能平台（仪表盘/图片工作室/文案/商品/资产/营销/客服/财务） |

## 后端七层架构

```
access → understanding → confirmation → orchestration → execution → delivery
                                                                    ↓
                                                                asset（横切，存档）
```

- **access** — 接入层：语音唤醒、ASR 语音转文字、TTS 文字转语音
- **understanding** — 理解层：规则引擎意图识别 + 槽位抽取 + 多轮对话补全
- **confirmation** — 确认层：任务摘要卡片生成、确认/修改/取消状态机、高成本二次确认
- **orchestration** — 编排层：ConfirmedTask → ExecutionPlan，选择平台适配器
- **execution** — 执行层：调用出图平台适配器（ModelScope/SiliconFlow/NanoBanana/Mock）
- **delivery** — 交付层：生成结果打包、图片下载转存、验收归档
- **asset** — 资产层：任务历史、品牌风格、商品资产、模板管理

### Pipeline 核心机制

- 每层实现 `LayerHandler(upstream, context) -> Any` 协议
- `SessionContext` 在层间流转，保存会话状态（intent/summary/confirmed_task/result/status）
- **确认锁**：未确认时 execution 层不被调用；`STOP_STATUSES` 控制早停
- **快速通道**：`一键出X` + 有参考图 → 跳过确认直接放行，交付后自动验收归档

## 关键文件索引

### 后端核心

| 文件 | 职责 |
|---|---|
| `boss_aigc/server.py` | FastAPI 应用入口，API 路由定义，会话管理 |
| `boss_aigc/pipeline.py` | 七层管道总线，LayerHandler 协议，SessionContext |
| `boss_aigc/config.py` | 全局配置（Settings dataclass 单例） |
| `boss_aigc/db.py` | 数据库初始化（canvases/task_history/brand_styles 表） |
| `boss_aigc/_e2e_test.py` | `build_full_pipeline()` 装配工厂 |
| `boss_aigc/contracts/enums.py` | TaskType/TaskStatus/ImageType/PlatformKind 枚举 |
| `boss_aigc/understanding/recognizer.py` | 规则引擎意图识别 + 商品名/数量/类型/风格抽取 |
| `boss_aigc/understanding/handler.py` | 理解层处理器（注入 uploaded_images → reference_image） |
| `boss_aigc/confirmation/handler.py` | 确认层处理器（快速通道、二次确认、修改+确认复合指令） |
| `boss_aigc/orchestration/planner.py` | ExecutionPlan 规划，`_merge_params` 合并 slots+summary |
| `boss_aigc/orchestration/scheduler.py` | 串行执行 + 重试 + 降级 |
| `boss_aigc/execution/modelscope_adapter.py` | 魔搭 Qwen-Image 文生图/图生图 |
| `boss_aigc/execution/siliconflow_adapter.py` | 硅基流动 FLUX/Qwen-Image 文生图/图生图 |
| `boss_aigc/api/canvas.py` | 无限画布 API（生成 + CRUD 持久化） |

### 前端核心

| 文件 | 职责 |
|---|---|
| `web/src/App.tsx` | 路由配置（RequireAuth 包裹受保护页面） |
| `web/src/pages/Home.tsx` | AI 助手首页（三栏布局：时间线+聊天流+上下文卡片） |
| `web/src/components/InfiniteCanvas.tsx` | 无限画布组件（节点/连线/@引用/画布持久化） |
| `web/src/components/InputBar.tsx` | 底部输入区（文字+图片上传+快捷出图按钮+语音） |
| `web/src/hooks/useChat.ts` | Zustand 状态管理（sendMessage/uploadImage/resetSession） |
| `web/src/api.ts` | API 请求封装（chat/upload/canvasGenerate/saveCanvas 等） |
| `web/src/types.ts` | 前端类型定义（ChatMessage/Summary/Artifact/TimelineNode） |
| `web/vite.config.ts` | Vite 构建配置（outDir → boss_aigc/static，代理 /api → :8000） |

## API 路由总览

### 对话核心

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | 处理一轮老板输入（message + session_id + images） |
| POST | `/api/upload` | 上传图片（返回 /uploads/xxx.png URL） |
| POST | `/api/reset` | 重置会话 |
| GET | `/api/gallery` | 获取已生成图片列表 |
| GET | `/api/health` | 健康检查 |

### 无限画布

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/canvas/generate` | 画布节点出图（prompt + reference_images + preset） |
| POST | `/api/canvas/save` | 保存画布（nodes + connections JSON） |
| GET | `/api/canvas/list` | 画布列表 |
| GET | `/api/canvas/load/{id}` | 加载画布 |
| DELETE | `/api/canvas/{id}` | 删除画布 |
| POST | `/api/canvas/new` | 新建空画布 |

### 电商平台

| 方法 | 路径前缀 | 说明 |
|---|---|---|
| GET/POST | `/api/dashboard/*` | 仪表盘数据 |
| GET/POST | `/api/products/*` | 商品管理 |
| GET/POST | `/api/assets/*` | 资产管理 |
| GET/POST | `/api/marketing/*` | 营销 |
| GET/POST | `/api/service/*` | 客服 |
| GET/POST | `/api/finance/*` | 财务 |
| POST | `/api/copywriting/generate` | 文案生成 |

## 出图逻辑

### AI 助手对话模式（七层 Pipeline）

1. 前端 `InputBar` 上传图片 → `POST /api/upload` → 得到 `/uploads/xxx.png` URL
2. 用户发送文字 + 图片URL列表 → `POST /api/chat`
3. 后端 `server.py` 把图片存入 `ctx.extras["uploaded_images"]`
4. **理解层**：规则引擎识别意图，自动把 `uploaded_images[0]` 注入 `intent.slots["reference_image"]`
5. **确认层**：`一键出X` + 有参考图 → 快速通道直接放行；否则生成摘要等待确认
6. **编排层**：`_merge_params` 合并 slots + summary params → 传入 `reference_image` 字段
7. **执行层**：适配器检测 `reference_image` 是否存在 → 有则图生图（Edit 模型），无则纯文生图
8. **交付层**：下载远程图片到本地 `/uploads/`，返回 `/uploads/xxx.png`

### 无限画布模式（直接 API 调用）

1. 前端通过**连线**收集上游节点：图片节点 → reference_images，文本节点 → reference_texts
2. `@引用`仅用于输入框文本提示，`@xxx` 标记在提交前被清理，不传给模型
3. 调用 `POST /api/canvas/generate`，后端组装 prompt（预设词 + 参考文案 + 用户输入 + 质量后缀）
4. 有 reference_images → 图生图模式；无 → 文生图模式
5. 生成后图片下载到本地，前端在节点位置展示

### Prompt 组装顺序

```
[图片类型预设词] + [参考文案（连线文本节点）] + [用户输入prompt] + [质量后缀]
```

图片类型预设词示例：
- main: "商品主图，纯白色背景，商品居中放置，主体占画面70%，45度侧角拍摄..."
- detail: "详情图，浅色纯净背景，商品细节微距特写，展示材质纹理..."
- scene: "场景图，真实生活场景，商品自然融入使用环境..."
- poster: "营销海报，简约大气背景，商品居中突出..."

## 环境变量

关键环境变量（`.env` 文件，参考 `.env.example`）：

```bash
# 出图平台：mock | modelscope | siliconflow | nanobanana
PLATFORM_PROVIDER=siliconflow

# 硅基流动（当前使用）
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_MODEL=Qwen/Qwen-Image
SILICONFLOW_EDIT_MODEL=Qwen/Qwen-Image-Edit

# 魔搭（备选）
MODELSCOPE_API_KEY=ms-xxx

# 认证（生产必填）
JWT_SECRET=（openssl rand -hex 32）
BOSS_PASSWORD_HASH=salt$hash

# 部署
IMAGE_NAME=ghcr.io/xiong12306/forbossaigc:latest
DOMAIN=xjloveqrj.pw
```

## 本地开发

```bash
# 后端
cd /Users/admin/Documents/Trae/forBossAIGC
.venv/bin/python -m uvicorn boss_aigc.server:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd /Users/admin/Documents/Trae/forBossAIGC/web
npm run dev

# 前端访问 http://localhost:5173（Vite 代理 /api → :8000）
# 后端 API  http://localhost:8000/api/health
```

## 测试

```bash
# 后端全量测试
.venv/bin/python -m pytest boss_aigc/ -v

# 理解层 + 确认层
.venv/bin/python -m pytest boss_aigc/understanding/ boss_aigc/confirmation/ -v

# E2E 全链路
.venv/bin/python -m boss_aigc._e2e_test

# 前端类型检查
cd web && npx tsc --noEmit

# 前端生产构建
cd web && npm run build
```

## 部署

```bash
# 自动部署：push 到 main 分支 → CI 测试 → Docker 镜像构建推送 → 自动部署
git push origin main

# 手动部署：GitHub Actions → Deploy → Run workflow
# 或直接 SSH 到服务器
ssh root@47.107.160.40
cd /opt/bossaigc && docker compose pull app && docker compose up -d

# 线上地址
# https://xjloveqrj.pw 或 https://47.107.160.40
```

## 硬约束（不可违反）

1. **七层架构**必须实现 `LayerHandler` 协议，通过 `SessionContext` 共享状态
2. **确认锁**不可绕过：未确认时 execution 层不被调用
3. **真实平台配置时禁用 Mock 降级**：失败返回错误，不静默生成假图
4. **HTTP 客户端必须 `trust_env=False`**：避免系统代理导致连接超时
5. **ModelScope 轮询必须带 `X-ModelScope-Task-Type: image_generation` 头**
6. **远程图片必须下载到本地 `/uploads/`**：避免 OSS URL 过期/跨域
7. **CORS 必须包含 5173-5176 端口**
8. **单 worker 部署**：内存会话存储，多 worker 会话错乱
9. **前端构建产物输出到 `boss_aigc/static/`**：生产由 FastAPI StaticFiles 托管
10. **`@引用`标记不传给模型**：前端提交前清理 prompt 中的 `@xxx`

## Git 分支策略

- `main` — 生产分支，push 自动触发 CI/CD 全流程（测试 → 构建 → 部署）
- `dev` — 开发分支，push 仅触发 CI 测试
- 工作流：dev 开发验证 → 合并 main → 自动部署

## 常见问题排查

| 问题 | 排查方向 |
|---|---|
| 出图完全不对 | 检查 reference_image 是否正确传入执行层（intent.slots → summary.params → adapter params） |
| 生产白屏但本地正常 | 检查生产构建（`npm run build`），常见原因：TDZ 错误、framer-motion AnimatePresence key 缺失 |
| ModelScope 429 限流 | 已实现自动重试 + 降级到 NanoBanana，检查 API key 配额 |
| 图片无法访问 | 远程 URL 需下载到本地 /uploads/，检查 `_download_image` 方法 |
| 会话状态丢失 | 检查是否多 worker 部署（必须单 worker），检查 session_id 传递 |
| 商品名误识别 | 检查 `_clean_product` 噪声词表是否覆盖图片类型词、快捷指令前缀 |
