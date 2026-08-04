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

### 架构概览

```
GitHub push main
    ↓
[CI] 后端测试 + 前端构建检查
    ↓
[Build & Publish] Docker 镜像构建 → 推送 GHCR
    ↓
[Deploy] SCP 配置文件 → SSH 服务器 → docker compose pull && up -d
    ↓                                        ↓
    成功 ← 健康检查 ←  服务器拉取镜像启动    失败 → 自动回滚旧镜像
```

### CI/CD 流水线

| Workflow | 文件 | 触发 | 作用 |
|----------|------|------|------|
| CI | [ci.yml](.github/workflows/ci.yml) | push/PR main | 后端测试 + 前端构建检查 |
| Build & Publish | [docker-publish.yml](.github/workflows/docker-publish.yml) | push main/tag | 构建镜像推送 GHCR |
| Deploy | [deploy.yml](.github/workflows/deploy.yml) | 镜像构建完成后 | SSH 部署 + 健康检查 + 回滚 |

### 首次部署

```bash
# 1. 在 GitHub 仓库 Settings → Secrets 配置：
#    SERVER_HOST     服务器 IP（如 47.107.160.40）
#    SERVER_USER     SSH 用户名（如 root）
#    SERVER_PASSWORD SSH 密码
#    GHCR_USER       GitHub 用户名（拉取私有镜像用，公开镜像可省略）
#    GHCR_PAT        GitHub PAT（拉取私有镜像用，公开镜像可省略）

# 2. 修改 .env.example 中的 IMAGE_NAME 为你的 GHCR 镜像地址
#    格式：ghcr.io/<GitHub用户名>/<仓库名>:latest（全小写）

# 3. 在 GitHub 仓库 Settings → Packages 设置镜像为 Public（可选）

# 4. push 代码到 main 分支，CI/CD 自动触发部署

# 5. 或手动在服务器上执行：
scp deploy.sh docker-compose.yml nginx.conf nginx/ root@服务器IP:/opt/bossaigc/
ssh root@服务器IP 'cd /opt/bossaigc && bash deploy.sh'

# 6. 签发 HTTPS 证书：
ssh root@服务器IP 'cd /opt/bossaigc && bash issue-ssl.sh'
```

### 更新部署

```bash
# 自动：push 到 main 分支，CI/CD 自动构建镜像并部署
git push origin main

# 手动：在服务器上执行
ssh root@服务器IP 'bash /opt/bossaigc/update.sh'
```

### 回滚

部署失败时自动回滚到上一个镜像。手动回滚：

```bash
# 查看历史镜像
docker images --format "{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedAt}}" | grep forbossaigc

# 用指定版本部署（在 GitHub Actions → Deploy → Run workflow 输入镜像标签）
# 或手动：
ssh root@服务器IP 'cd /opt/bossaigc && IMAGE_NAME=ghcr.io/xxx/forbossaigc:sha-abc123 docker compose up -d'
```

### 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `IMAGE_NAME` | 部署必填 | GHCR 镜像地址，如 `ghcr.io/user/repo:latest` |
| `DOMAIN` | 部署必填 | 域名，用于 Nginx 和 HTTPS 证书 |
| `SUPABASE_URL` | 是 | Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | 是 | Supabase anon 公钥 |
| `JWT_SECRET` | 生产必填 | JWT 签名密钥，`openssl rand -hex 32` 生成 |
| `BOSS_USERNAME` | 否 | 登录用户名，默认 `boss` |
| `BOSS_PASSWORD_HASH` | 生产必填 | 密码哈希，格式 `salt$sha256hash` |
| `MODELSCOPE_API_KEY` | 是 | 魔搭 API Key |
| `PLATFORM_PROVIDER` | 否 | 出图平台：`modelscope`/`nanobanana`/`mock` |
| `ALLOWED_ORIGINS` | 否 | CORS 允许来源，逗号分隔 |

### HTTPS 证书

- 首次部署使用自签证书（浏览器会警告）
- 运行 `bash issue-ssl.sh` 签发 Let's Encrypt 真实证书
- 证书 90 天有效，每月 1 日和 15 日自动检查续期
- 手动续期：`docker compose run --rm certbot renew`

### 数据库

- **Supabase**（主）：PostgreSQL，执行 `schema.sql` 建表
- **SQLite**（fallback）：未配置 Supabase 时自动降级，数据存 `data/bossaigc.db`

### 监控

- `GET /api/health` — 健康检查
- `GET /metrics` — 请求计数、会话数、运行时长
- `docker compose logs -f` — 实时日志

### 所需 GitHub Secrets

| Secret | 说明 |
|--------|------|
| `SERVER_HOST` | 服务器 IP |
| `SERVER_USER` | SSH 用户名 |
| `SERVER_PASSWORD` | SSH 密码 |
| `GHCR_USER` | GitHub 用户名（私有镜像需） |
| `GHCR_PAT` | GitHub PAT（私有镜像需，需 `read:packages` 权限）|

## 状态

当前版本：**0.3.0** — 已完成七层架构 + 9 大业务模块 + Supabase 集成 + 认证 + 容器化部署。
