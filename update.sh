#!/bin/bash
# BossAIGC 生产环境更新脚本
# 在服务器上执行：从 Git 拉取最新代码，重新构建部署
# 用法：bash /opt/bossaigc/update.sh
# 也可通过 CI/CD 远程调用：ssh root@SERVER_IP 'bash /opt/bossaigc/update.sh'

set -e

DEPLOY_DIR="/opt/bossaigc"
LOG_FILE="$DEPLOY_DIR/update.log"

echo "==========================================" | tee -a "$LOG_FILE"
echo "  $(date '+%Y-%m-%d %H:%M:%S') 开始更新部署" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"

cd "$DEPLOY_DIR"

# 1. 从 Git 拉取最新代码（如果是 Git 仓库）
if [ -d ".git" ]; then
    echo "[1/4] 从 Git 拉取最新代码..." | tee -a "$LOG_FILE"
    git fetch origin
    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || echo "  无 main/master 分支，跳过 git pull"
else
    echo "[1/4] 非 Git 仓库，跳过拉取（请通过 scp 上传代码）" | tee -a "$LOG_FILE"
fi

# 2. 确保存在 .env
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[2/4] 创建 .env 配置..." | tee -a "$LOG_FILE"
    cp .env.example .env
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
    echo "  请编辑 .env 填入必要配置后重新运行" | tee -a "$LOG_FILE"
    exit 1
else
    echo "[2/4] .env 已存在" | tee -a "$LOG_FILE"
fi

# 3. 重新构建并启动
echo "[3/4] 重新构建并启动服务..." | tee -a "$LOG_FILE"
docker compose down --remove-orphans
docker compose up -d --build

# 4. 健康检查
echo "[4/4] 等待服务启动..." | tee -a "$LOG_FILE"
sleep 5

# 通过 docker exec 直接在容器内检查，避免端口/HTTPS 重定向问题
for i in {1..15}; do
    if docker compose exec -T app curl -sf http://localhost:8000/api/health &> /dev/null; then
        echo "" | tee -a "$LOG_FILE"
        echo "✅ 部署成功！$(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        echo "  访问地址: https://xjloveqrj.pw" | tee -a "$LOG_FILE"
        exit 0
    fi
    echo "  等待中... ($i/15)" | tee -a "$LOG_FILE"
    sleep 3
done

echo "❌ 服务启动超时，查看日志：docker compose logs --tail=50" | tee -a "$LOG_FILE"
docker compose logs --tail=30 app | tee -a "$LOG_FILE"
exit 1
