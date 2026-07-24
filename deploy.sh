#!/bin/bash
# BossAIGC 一键部署脚本（在服务器上执行）
# 用法：
#   curl -fsSL <你的脚本URL> | bash
# 或：
#   scp deploy.sh root@服务器IP:/opt/ && ssh root@服务器IP 'cd /opt && bash deploy.sh'

set -e

# ===== 配置 =====
DEPLOY_DIR="/opt/bossaigc"
SERVICE_NAME="bossaigc"

echo "=========================================="
echo "  BossAIGC 一键部署"
echo "=========================================="

# 1. 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "[1/6] 安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    echo "[1/6] Docker 已安装: $(docker --version)"
fi

# 2. 检查 docker compose
if ! docker compose version &> /dev/null; then
    echo "[2/6] 安装 docker-compose-plugin..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
else
    echo "[2/6] Docker Compose 已就绪"
fi

# 3. 创建部署目录
echo "[3/6] 准备部署目录 $DEPLOY_DIR ..."
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# 4. 检查是否已有项目代码
if [ ! -f "docker-compose.yml" ]; then
    echo "[4/6] 项目代码不存在，请通过以下方式之一上传代码："
    echo ""
    echo "  方式A - 从本地 scp 上传（在你的 Mac 上执行）："
    echo "    cd /Users/admin/Documents/Trae/forBossAIGC"
    echo "    scp -r * deploy.sh root@服务器IP:$DEPLOY_DIR/"
    echo ""
    echo "  方式B - 从 Git 仓库克隆（若已推送）："
    echo "    git clone <你的仓库地址> $DEPLOY_DIR"
    echo ""
    echo "  上传完成后，再次运行此脚本：bash $DEPLOY_DIR/deploy.sh"
    exit 0
else
    echo "[4/6] 项目代码已就位"
fi

# 5. 检查 .env 配置
if [ ! -f ".env" ]; then
    echo "[5/6] 创建 .env 配置文件..."
    cp .env.example .env

    # 自动生成 JWT_SECRET
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env

    # 生成临时密码
    TEMP_PASSWORD=$(openssl rand -base64 12)
    # 注意：这里需要 Python 算哈希，若服务器无 Python 则用简单方式
    if command -v python3 &> /dev/null; then
        PASSWORD_HASH=$(python3 -c "
import hashlib, secrets
salt = secrets.token_hex(8)
h = hashlib.sha256(f'{salt}{\"$TEMP_PASSWORD\"}'.encode()).hexdigest()
print(f'{salt}\${h}')
")
        sed -i "s|^BOSS_PASSWORD_HASH=.*|BOSS_PASSWORD_HASH=$PASSWORD_HASH|" .env
    fi

    echo ""
    echo "  ⚠️  .env 已生成，请编辑填入 Supabase 配置："
    echo "      nano $DEPLOY_DIR/.env"
    echo ""
    echo "  ===== 自动生成的登录信息 ====="
    echo "  用户名: boss"
    echo "  密码: $TEMP_PASSWORD"
    echo "  =============================="
    echo ""
    echo "  填好 Supabase 配置后，再次运行此脚本启动："
    echo "      bash $DEPLOY_DIR/deploy.sh"
    exit 0
else
    echo "[5/6] .env 配置已存在"
fi

# 6. 启动服务
echo "[6/6] 构建并启动服务..."
docker compose up -d --build

# 等待服务启动
echo ""
echo "等待服务启动..."
sleep 8

# 健康检查
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
HEALTH_URL="http://localhost:8000/api/health"

for i in {1..10}; do
    if curl -sf "$HEALTH_URL" &> /dev/null; then
        echo ""
        echo "=========================================="
        echo "  ✅ 部署成功！"
        echo "=========================================="
        echo ""
        echo "  访问地址:  http://$SERVER_IP"
        echo "  健康检查:  http://$SERVER_IP/api/health"
        echo "  监控指标:  http://$SERVER_IP/metrics"
        echo ""
        echo "  常用命令:"
        echo "    查看日志:   docker compose logs -f"
        echo "    重启服务:   docker compose restart"
        echo "    停止服务:   docker compose down"
        echo "    更新部署:   git pull && docker compose up -d --build"
        echo "=========================================="
        exit 0
    fi
    echo "  等待中... ($i/10)"
    sleep 3
done

echo ""
echo "❌ 服务启动超时，查看日志排查："
echo "   docker compose logs --tail=50"
exit 1
