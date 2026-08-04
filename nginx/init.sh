#!/bin/sh
# Nginx 启动前初始化：检测 SSL 证书，不存在则生成临时自签证书
# 这样首次部署时 443 端口即可启动，certbot 签发真实证书后替换并 reload
set -e

DOMAIN="${DOMAIN:-xjloveqrj.pw}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
CERT_FILE="${CERT_DIR}/fullchain.pem"
KEY_FILE="${CERT_DIR}/privkey.pem"
SELF_SIGNED_DIR="/etc/nginx/ssl"
SELF_SIGNED_CERT="${SELF_SIGNED_DIR}/selfsigned.crt"
SELF_SIGNED_KEY="${SELF_SIGNED_DIR}/selfsigned.key"

mkdir -p "${SELF_SIGNED_DIR}"

if [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ]; then
    echo "[init] 使用 Let's Encrypt 证书: ${CERT_FILE}"
    # 拷贝到 nginx ssl 目录，确保权限正确
    cp "${CERT_FILE}" "${SELF_SIGNED_DIR}/live.crt"
    cp "${KEY_FILE}" "${SELF_SIGNED_DIR}/live.key"
    chmod 644 "${SELF_SIGNED_DIR}/live.crt"
    chmod 600 "${SELF_SIGNED_DIR}/live.key"
else
    echo "[init] Let's Encrypt 证书不存在，生成临时自签证书..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${SELF_SIGNED_KEY}" \
        -out "${SELF_SIGNED_CERT}" \
        -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN},DNS:www.${DOMAIN}" 2>/dev/null
    cp "${SELF_SIGNED_CERT}" "${SELF_SIGNED_DIR}/live.crt"
    cp "${SELF_SIGNED_KEY}" "${SELF_SIGNED_DIR}/live.key"
    chmod 644 "${SELF_SIGNED_DIR}/live.crt"
    chmod 600 "${SELF_SIGNED_DIR}/live.key"
    echo "[init] 临时自签证书已生成，请尽快运行 certbot 签发真实证书"
    echo "[init] 命令: docker compose run --rm certbot"
fi

echo "[init] 启动 nginx..."
exec nginx -g "daemon off;"
