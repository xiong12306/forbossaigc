#!/bin/bash
# BossAIGC HTTPS 证书签发脚本（在服务器上执行）
# 使用 Let's Encrypt + Certbot 签发真实证书，替换自签证书
#
# 前提：
#   1. 域名已解析到本服务器 IP
#   2. 服务已通过 deploy.sh 启动（nginx 正在运行）
#   3. 80 端口可外部访问（防火墙已放行）
#
# 用法：
#   bash /opt/bossaigc/issue-ssl.sh

set -e

DEPLOY_DIR="/opt/bossaigc"
DOMAIN="${DOMAIN:-xjloveqrj.pw}"
EMAIL="${CERTBOT_EMAIL:-admin@${DOMAIN}}"

cd "$DEPLOY_DIR"

echo "=========================================="
echo "  HTTPS 证书签发"
echo "  域名: $DOMAIN, www.$DOMAIN"
echo "  邮箱: $EMAIL"
echo "=========================================="

# 1. 检查域名解析
echo "[1/4] 检查域名解析..."
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
DOMAIN_IP=$(dig +short "$DOMAIN" 2>/dev/null || nslookup "$DOMAIN" 2>/dev/null | grep -A1 "Name:" | grep "Address" | awk '{print $2}' | head -1)

if [ -z "$DOMAIN_IP" ]; then
    echo "  ⚠️  无法解析 $DOMAIN，请确保域名已解析到 $SERVER_IP"
    echo "  跳过检查继续..."
else
    echo "  域名 $DOMAIN → $DOMAIN_IP"
    echo "  本机 IP → $SERVER_IP"
    if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
        echo "  ❌ 域名解析 IP 与本机 IP 不一致！"
        echo "  请先在 DNS 服务商将 $DOMAIN 解析到 $SERVER_IP"
        exit 1
    fi
    echo "  ✅ 域名解析正确"
fi

# 2. 检查服务运行状态
echo "[2/4] 检查服务状态..."
if ! docker compose ps | grep -q "bossaigc-nginx.*running"; then
    echo "  ❌ nginx 容器未运行，请先运行 deploy.sh 启动服务"
    exit 1
fi
echo "  ✅ nginx 容器运行中"

# 3. 签发证书
echo "[3/4] 签发 Let's Encrypt 证书..."
docker compose run --rm certbot \
    certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    -d "$DOMAIN" -d "www.$DOMAIN"

echo "  ✅ 证书已签发到 /etc/letsencrypt/live/$DOMAIN/"

# 4. 重启 nginx 加载真实证书
echo "[4/4] 重启 nginx 加载真实证书..."
docker compose restart nginx
sleep 3

# 验证 HTTPS
echo ""
echo "验证 HTTPS..."
if curl -sf "https://$DOMAIN/api/health" 2>/dev/null; then
    echo ""
    echo "=========================================="
    echo "  ✅ HTTPS 证书签发成功！"
    echo "=========================================="
    echo ""
    echo "  访问地址: https://$DOMAIN"
    echo "  证书路径: /etc/letsencrypt/live/$DOMAIN/"
    echo "  有效期: 90 天（自动续期已配置）"
    echo ""
    echo "  证书将在每月1日和15日凌晨3点自动检查续期"
    echo "  手动续期: docker compose run --rm certbot renew"
    echo "=========================================="
else
    echo ""
    echo "⚠️  HTTPS 验证失败，请检查："
    echo "  docker compose logs --tail=20 nginx"
    echo "  证书文件: docker compose exec nginx ls -la /etc/letsencrypt/live/$DOMAIN/"
fi
