# BossAIGC 多阶段构建 Dockerfile
# 阶段1：构建前端
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com && \
    (npm ci --no-audit --no-fund || npm install --no-audit --no-fund)
COPY web/ ./
RUN npm run build
# 构建产物输出到 /app/boss_aigc/static/（由 vite.config.ts outDir 控制）

# 阶段2：后端运行时
FROM python:3.12-slim AS runtime

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，使用国内 PyPI 镜像加速）
COPY requirements.txt ./
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 拷贝后端代码
COPY boss_aigc/ ./boss_aigc/
COPY schema.sql ./

# 从阶段1拷贝前端构建产物
COPY --from=frontend-builder /app/boss_aigc/static ./boss_aigc/static

# 数据目录（SQLite fallback 用）与上传目录
RUN mkdir -p /app/data /app/boss_aigc/uploads
VOLUME ["/app/data", "/app/boss_aigc/uploads"]

# 环境变量默认值（生产应通过 docker-compose / -e 覆盖）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    WEB_CONCURRENCY=1

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 生产启动：单 worker（内存会话存储，多 worker 会错乱）
CMD ["sh", "-c", "gunicorn boss_aigc.server:app -w ${WEB_CONCURRENCY} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT} --access-logfile - --error-logfile -"]
