#!/bin/bash
# BossAIGC 生产环境更新脚本（在服务器上执行）
# 基于 GHCR 镜像拉取更新，无需本地构建
# 用法：bash /opt/bossaigc/update.sh

set -e

DEPLOY_DIR="/opt/bossaigc"
LOG_FILE="$DEPLOY_DIR/update.log"

echo "==========================================" | tee -a "$LOG_FILE"
echo "  $(date '+%Y-%m-%d %H:%M:%S') 开始更新部署" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"

cd "$DEPLOY_DIR"

# 1. 确保 .env 存在
if [ ! -f ".env" ]; then
    echo "[1/4] ❌ .env 不存在，请先运行 deploy.sh" | tee -a "$LOG_FILE"
    exit 1
fi
echo "[1/4] .env 已存在" | tee -a "$LOG_FILE"

# 2. 记录当前镜像 ID（用于回滚）
OLD_IMAGE_ID=$(docker compose images app 2>/dev/null | grep app | awk '{print $3}' || echo "")
echo "[2/4] 当前镜像: ${OLD_IMAGE_ID:-无}" | tee -a "$LOG_FILE"

# 3. 拉取最新镜像并重启
echo "[3/4] 拉取最新镜像..." | tee -a "$LOG_FILE"
docker compose pull app

NEW_IMAGE_ID=$(docker compose images app 2>/dev/null | grep app | awk '{print $3}' || echo "")

# 镜像未变化则跳过
if [ -n "$OLD_IMAGE_ID" ] && [ "$OLD_IMAGE_ID" = "$NEW_IMAGE_ID" ]; then
    echo "  镜像无变化，跳过部署" | tee -a "$LOG_FILE"
    exit 0
fi

echo "  新镜像: $NEW_IMAGE_ID" | tee -a "$LOG_FILE"
echo "  重启服务..." | tee -a "$LOG_FILE"
docker compose up -d --remove-orphans

# 4. 健康检查
echo "[4/4] 健康检查..." | tee -a "$LOG_FILE"
sleep 5

for i in $(seq 1 15); do
    if docker compose exec -T app curl -sf http://localhost:8000/api/health 2>/dev/null; then
        echo "" | tee -a "$LOG_FILE"
        echo "✅ 部署成功！$(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
        echo "  访问地址: https://xjloveqrj.pw" | tee -a "$LOG_FILE"
        exit 0
    fi
    echo "  等待中... ($i/15)" | tee -a "$LOG_FILE"
    sleep 3
done

# 健康检查失败，自动回滚
echo "❌ 健康检查失败，尝试回滚..." | tee -a "$LOG_FILE"
if [ -n "$OLD_IMAGE_ID" ] && [ "$OLD_IMAGE_ID" != "$NEW_IMAGE_ID" ]; then
    echo "  回滚到旧镜像: $OLD_IMAGE_ID" | tee -a "$LOG_FILE"
    IMAGE_NAME=$(grep "^IMAGE_NAME=" .env | cut -d'=' -f2-)
    docker tag "$OLD_IMAGE_ID" "$IMAGE_NAME"
    docker compose up -d --no-deps app
    sleep 5
    if docker compose exec -T app curl -sf http://localhost:8000/api/health 2>/dev/null; then
        echo "✅ 回滚成功" | tee -a "$LOG_FILE"
        exit 0
    fi
fi

echo "❌ 回滚失败，请检查日志：" | tee -a "$LOG_FILE"
docker compose logs --tail=30 app | tee -a "$LOG_FILE"
exit 1
