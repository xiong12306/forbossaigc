# 老板 AI 助手 (BossAIGC)

让老板像使唤小爱同学一样，**一句话吩咐干活**，助手负责理解、确认、调用平台、交付结果。把「打开即梦 → 写 Prompt → 等出图 → 下载 → 再发到店铺」这条手动链路，压缩成「语音吩咐 → 确认 → 收图」三步。

## 七层架构

数据按序流经六层主链，资产层作为横切关注点：

```
接入 → 理解 → 确认 → 编排 → 执行 → 交付
                              （资产与记忆层 横切各层）
```

- **接入层 (access)**：语音唤醒 / ASR / TTS / 文字输入 / 卡片渲染
- **理解层 (understanding)**：意图识别 / 槽位抽取 / 多轮追问
- **确认层 (confirmation)**：任务摘要 / 确认状态机 / 确认锁（Human-in-the-Loop）
- **编排层 (orchestration)**：任务规划 / DAG / 调度
- **执行层 (execution)**：统一适配器接口 + Mock + 注册（即梦 / 通义万相 后续接入）
- **交付层 (delivery)**：结果打包 / 多通道推送 / 验收归档
- **资产与记忆层 (asset)**：品牌风格库 / 商品资产库 / 历史 / 模板

各层通过 `boss_aigc.contracts` 中的统一数据契约（`TaskIntent` / `TaskSummary` / `ConfirmedTask` / `TaskExecution` / `TaskResult`）通信，契约定义在独立模块，各层引用而非各自定义。

## 安装

```bash
# 后端依赖
pip install -r requirements.txt

# 开发依赖（含 pytest）
pip install -r requirements-dev.txt

# 前端依赖
cd web && npm install
```

## 本地开发

```bash
# 1. 启动后端（开发模式，热重载）
.venv/bin/uvicorn boss_aigc.server:app --reload --port 8000

# 2. 启动前端（另一个终端）
cd web && npm run dev
# 访问 http://localhost:5173

# 3. 冒烟测试
python -m boss_aigc._smoke_test

# 4. 运行 pytest
.venv/bin/pytest boss_aigc/ -v
```

## 生产部署

### 方式一：Docker Compose（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 Supabase、JWT、NanoBanana 等配置

# 2. 生成密码哈希
python -c "from boss_aigc.auth import _hash_password; print(_hash_password('你的密码'))"
# 将输出填入 .env 的 BOSS_PASSWORD_HASH

# 3. 生成 JWT 密钥
openssl rand -hex 32
# 将输出填入 .env 的 JWT_SECRET

# 4. 一键启动
docker compose up -d --build

# 5. 访问
# http://localhost（经 Nginx 反代）
```

### 方式二：直接部署

```bash
# 1. 构建前端
cd web && npm run build
# 产物自动输出到 boss_aigc/static/

# 2. 启动后端（gunicorn 生产模式）
gunicorn boss_aigc.server:app \
  -w 1 \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -

# 3. Nginx 反代（参考 nginx.conf）
```

### 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `SUPABASE_URL` | 是 | Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | 是 | Supabase anon 公钥 |
| `JWT_SECRET` | 生产必填 | JWT 签名密钥，`openssl rand -hex 32` 生成 |
| `BOSS_USERNAME` | 否 | 登录用户名，默认 `boss` |
| `BOSS_PASSWORD_HASH` | 生产必填 | 密码哈希，格式 `salt$sha256hash` |
| `NANOBANANA_API_KEY` | 否 | NanoBanana 出图 API Key |
| `USE_REAL_PLATFORM` | 否 | `True`=真实出图，`False`=Mock |
| `ALLOWED_ORIGINS` | 否 | CORS 允许来源，逗号分隔 |

### 数据库

- **Supabase**（主）：PostgreSQL，执行 `schema.sql` 建表
- **SQLite**（fallback）：未配置 Supabase 时自动降级，数据存 `data/boss_aigc.db`

### 监控

- `GET /api/health` — 健康检查
- `GET /metrics` — 请求计数、会话数、运行时长

### HTTPS

生产建议通过 Nginx + Let's Encrypt 配置 HTTPS，参考 `nginx.conf` 中注释。

## 状态

当前版本：**0.3.0** — 已完成七层架构 + 9 大业务模块 + Supabase 集成 + 认证 + 容器化部署。
