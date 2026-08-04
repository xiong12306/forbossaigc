#!/bin/bash
# BossAIGC 首次部署脚本（在服务器上执行）
# 基于 GHCR 镜像拉取，无需本地构建
#
# 用法：
#   scp deploy.sh docker-compose.yml nginx.conf nginx/ root@服务器IP:/opt/bossaigc/
#   ssh root@服务器IP 'cd /opt/bossaigc && bash deploy.sh'
#
# 或一键命令：
#   curl -fsSL <你的脚本URL> | bash

set -e

# ===== 配置 =====
DEPLOY_DIR="/opt/bossaigc"
DOMAIN="xjloveqrj.pw"
# GHCR 镜像地址（替换为你的实际镜像名，全小写）
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/your-github-username/forbossaigc:latest}"

echo "=========================================="
echo "  BossAIGC 首次部署（镜像拉取模式）"
echo "=========================================="

# 1. 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "[1/7] 安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    echo "[1/7] Docker 已安装: $(docker --version)"
fi

# 2. 检查 docker compose
if ! docker compose version &> /dev/null; then
    echo "[2/7] 安装 docker-compose-plugin..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
else
    echo "[2/7] Docker Compose 已就绪"
fi

# 3. 准备部署目录
echo "[3/7] 准备部署目录 $DEPLOY_DIR ..."
mkdir -p "$DEPLOY_DIR/nginx"
cd "$DEPLOY_DIR"

# 4. 检查配置文件
if [ ! -f "docker-compose.yml" ]; then
    echo "[4/7] ❌ docker-compose.yml 不存在"
    echo "  请先上传部署文件："
    echo "    scp docker-compose.yml nginx.conf nginx/ root@服务器IP:$DEPLOY_DIR/"
    exit 1
fi
echo "[4/7] 配置文件已就位"

# 5. 检查 .env 配置
if [ ! -f ".env" ]; then
    echo "[5/7] 创建 .env 配置文件..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        # 创建最小化 .env
        cat > .env << EOF
IMAGE_NAME=$IMAGE_NAME
DOMAIN=$DOMAIN
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=
JWT_SECRET=$(openssl rand -hex 32)
JWT_EXPIRE_HOURS=24
BOSS_USERNAME=boss
BOSS_PASSWORD_HASH=
ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN
PLATFORM_PROVIDER=modelscope
MODELSCOPE_API_KEY=
MODELSCOPE_MODEL=Qwen/Qwen-Image
MODELSCOPE_API_BASE=https://api-inference.modelscope.cn/v1
REQUEST_TIMEOUT_SEC=180
POLL_INTERVAL_SEC=2.0
EOF
    fi

    # 生成密码
    TEMP_PASSWORD=$(openssl rand -base64 12)
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
    echo "  ⚠️  .env 已生成，请编辑填入必要配置："
    echo "      nano $DEPLOY_DIR/.env"
    echo ""
    echo "  必填项："
    echo "    - MODELSCOPE_API_KEY（魔搭 API Key）"
    echo "    - SUPABASE_URL / SUPABASE_ANON_KEY（如使用 Supabase）"
    echo ""
    echo "  ===== 自动生成的登录信息 ====="
    echo "  用户名: boss"
    echo "  密码: $TEMP_PASSWORD"
    echo "  =============================="
    echo ""
    echo "  填好配置后，再次运行此脚本启动："
    echo "      bash $DEPLOY_DIR/deploy.sh"
    exit 0
else
    echo "[5/7] .env 配置已存在"
    # 确保 IMAGE_NAME 和 DOMAIN 在 .env 中
    if ! grep -q "^IMAGE_NAME=" .env; then
        echo "IMAGE_NAME=$IMAGE_NAME" >> .env
    fi
    if ! grep -q "^DOMAIN=" .env; then
        echo "DOMAIN=$DOMAIN" >> .env
    fi
fi

# 6. 登录 GHCR（如果有 PAT）
if [ -n "$GHCR_PAT" ] && [ -n "$GHCR_USER" ]; then
    echo "[6/7] 登录 GHCR..."
    echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
else
    echo "[6/7] 跳过 GHCR 登录（镜像需公开，或设置 GHCR_PAT/GHCR_USER 环境变量）"
fi

# 7. 拉取镜像并启动
echo "[7/7] 拉取镜像并启动服务..."
docker compose pull
docker compose up -d --remove-orphans

# 等待服务启动
echo ""
echo "等待服务启动..."
sleep 8

# 健康检查
for i in $(seq 1 15); do
    if docker compose exec -T app curl -sf http://localhost:8000/api/health 2>/dev/null; then
        echo ""
        echo "=========================================="
        echo "  ✅ 部署成功！"
        echo "=========================================="
        echo ""
        echo "  访问地址:  https://$DOMAIN"
        echo "  健康检查:  https://$DOMAIN/api/health"
        echo ""
        echo "  ⚠️  首次部署使用自签证书，浏览器会警告不安全。"
        echo "  请运行证书签发脚本获取真实 HTTPS 证书："
        echo "      bash $DEPLOY_DIR/issue-ssl.sh"
        echo ""
        echo "  常用命令:"
        echo "    查看日志:   docker compose logs -f"
        echo "    重启服务:   docker compose restart"
        echo "    停止服务:   docker compose down"
        echo "    更新部署:   bash $DEPLOY_DIR/update.sh"
        echo "=========================================="
        exit 0
    fi
    echo "  等待中... ($i/15)"
    sleep 3
done

echo ""
echo "❌ 服务启动超时，查看日志排查："
echo "   docker compose logs --tail=50"
exit 1
