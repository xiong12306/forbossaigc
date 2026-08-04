#!/bin/bash
# BossAIGC HTTPS/SSL 一键配置脚本
# 在服务器上执行，自动完成：证书签发 → Nginx 配置切换 → 服务重启

set -e

DEPLOY_DIR="/opt/bossaigc"
DOMAIN="xjloveqrj.pw"
WWW_DOMAIN="www.xjloveqrj.pw"
EMAIL="aDqV7@l9t404lGA.vcQ"

cd "$DEPLOY_DIR"

echo "=========================================="
echo "  BossAIGC HTTPS 配置工具"
echo "=========================================="
echo ""

# 检查是否在正确目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 错误：请先将项目部署到 $DEPLOY_DIR"
    exit 1
fi

echo "📋 步骤 0/5: 检查 Docker 服务状态..."
docker compose ps
echo ""

echo "📋 步骤 1/5: 签发 Let's Encrypt 免费 SSL 证书..."
echo "   域名: $DOMAIN, $WWW_DOMAIN"
echo "   邮箱: $EMAIL"
echo ""

# 签发证书（如果已存在会自动续期）
docker compose run --rm certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    -d "$DOMAIN" -d "$WWW_DOMAIN" \
    --keep-until-expiring --non-interactive

echo ""
echo "✅ 证书签发成功！"
echo ""

# 检查证书文件是否存在
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/$DOMAIN/privkey.pem"

echo "📋 步骤 2/5: 验证证书文件..."
if docker run --rm -v bossaigc_certbot-certs:/etc/letsencrypt alpine ls -la "$CERT_PATH" "$KEY_PATH"; then
    echo "✅ 证书文件验证通过"
else
    echo "❌ 证书文件未找到，签发可能失败"
    exit 1
fi
echo ""

echo "📋 步骤 3/5: 启用 443 端口并重启 Nginx..."
echo ""

# 确保 docker-compose.yml 中 443 端口是开启的
if grep -q '#.*- "443:443"' docker-compose.yml; then
    echo "   启用 443 端口映射..."
    sed -i 's|#.*- "443:443".*|- "443:443"|' docker-compose.yml
fi

# 重启 nginx 容器加载新配置
docker compose up -d --force-recreate nginx

echo ""
echo "⏳ 等待 Nginx 启动..."
sleep 5

# 验证 Nginx 配置是否正确
if docker compose exec -T nginx nginx -t; then
    echo "✅ Nginx 配置验证通过"
else
    echo "❌ Nginx 配置有误，请检查日志"
    docker compose logs nginx --tail=30
    exit 1
fi
echo ""

echo "📋 步骤 4/5: 设置证书自动续期..."
echo ""

# 添加续期脚本
cat > /etc/cron.d/bossaigc-ssl-renew << 'EOF'
0 */12 * * * root cd /opt/bossaigc && docker compose run --rm certbot renew --quiet && docker compose exec -T nginx nginx -s reload
EOF

chmod 644 /etc/cron.d/bossaigc-ssl-renew
echo "✅ 自动续期已配置（每12小时检查一次）"
echo ""

echo "📋 步骤 5/5: 验证 HTTPS 连接..."
echo ""

sleep 2
if curl -sI "https://$DOMAIN" | head -1; then
    echo ""
    echo "=========================================="
    echo "  🎉 HTTPS 配置成功！"
    echo "=========================================="
    echo ""
    echo "  🔒 安全访问地址:  https://$DOMAIN"
    echo "  🔒 带www:         https://$WWW_DOMAIN"
    echo ""
    echo "  HTTP 访问会自动跳转到 HTTPS"
    echo "  浏览器现在应该显示 🔒 安全锁标志了"
    echo ""
    echo "  证书有效期: 90天（自动续期）"
    echo ""
else
    echo "⚠️  连接验证失败，请检查防火墙/安全组是否开放 443 端口"
    echo "   阿里云安全组需要同时开放 TCP 80 和 443 端口"
fi
