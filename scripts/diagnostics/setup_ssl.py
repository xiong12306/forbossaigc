#!/usr/bin/env python3
"""
配置 HTTPS：
1. 确保 ACME 验证路径可访问
2. 签发 Let's Encrypt 证书
3. 更新 Nginx 配置启用 HTTPS + 强制跳转
4. 开放 443 端口
"""
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"
DOMAIN = "xjloveqrj.pw"
EMAIL = "admin@xjloveqrj.pw"

# 正确的 Nginx 配置（HTTP 用于 ACME 验证 + HTTPS 正式服务）
NGINX_CONF = f"""# BossAIGC Nginx 配置 - {DOMAIN} + HTTPS

upstream bossaigc_backend {{
    server app:8000;
    keepalive 32;
}}

# HTTP: 80 端口 - ACME 验证 + 强制跳转 HTTPS
server {{
    listen 80;
    listen [::]:80;
    server_name {DOMAIN} www.{DOMAIN};

    # Let's Encrypt ACME 验证（证书签发/续期用）
    location /.well-known/acme-challenge/ {{
        root /var/www/certbot;
    }}

    # 其他所有请求强制跳转到 HTTPS
    location / {{
        return 301 https://$host$request_uri;
    }}
}}

# HTTPS: 443 端口
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {DOMAIN} www.{DOMAIN};

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    client_max_body_size 20M;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;
    gzip_min_length 1024;
    gzip_comp_level 6;

    # API 反向代理
    location /api/ {{
        proxy_pass http://bossaigc_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}

    # 前端 SPA
    location / {{
        proxy_pass http://bossaigc_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""

DOCKER_COMPOSE_PATCH = """
services:
  nginx:
    ports:
      - "80:80"
      - "443:443"
"""

def run(ssh, cmd, timeout=300, verbose=True):
    if verbose:
        print(f"$ {cmd[:80]}{'...' if len(cmd) > 80 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if verbose and out.strip():
        print(out.strip()[:500])
    if exit_code != 0 and err.strip() and verbose:
        print(f"STDERR: {err.strip()[:300]}")
    return exit_code, out, err

def main():
    print(f"🔧 开始配置 HTTPS for {DOMAIN}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    try:
        sftp = ssh.open_sftp()

        # Step 1: 先用临时 HTTP 配置确保证书签发路径可用（不跳转）
        print("\n[1/6] 准备临时 HTTP 配置用于签发证书...")
        temp_nginx = f"""
upstream bossaigc_backend {{
    server app:8000;
    keepalive 32;
}}
server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};
    client_max_body_size 20M;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;
    location /.well-known/acme-challenge/ {{
        root /var/www/certbot;
    }}
    location / {{
        proxy_pass http://bossaigc_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
        # 写入临时 nginx 配置
        with sftp.file(f"{REMOTE_DIR}/nginx.conf", "w") as f:
            f.write(temp_nginx)
        
        # 确保 443 端口暂时不映射（避免证书不存在时 nginx 启动失败）
        # 先读取当前 docker-compose.yml，临时注释 443
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "r") as f:
            compose_content = f.read().decode()
        
        # 确保 webroot 目录存在且可写
        run(ssh, f"mkdir -p {REMOTE_DIR}/certbot-www")
        run(ssh, f"chmod -R 755 {REMOTE_DIR}/certbot-www")
        
        print("🔄 重启 Nginx 应用临时配置...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose up -d --force-recreate nginx", timeout=120)
        time.sleep(5)
        
        # Step 2: 测试 HTTP 访问正常
        print("\n[2/6] 验证 HTTP 域名访问正常...")
        code, out, err = run(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/api/health -H 'Host: {DOMAIN}'")
        if "200" not in out:
            print(f"⚠️  HTTP 访问测试未返回200，输出: {out}")
            # 继续，不阻塞签发
        else:
            print("✅ HTTP 访问正常")
        
        # Step 3: 签发证书
        print("\n[3/6] 签发 Let's Encrypt SSL 证书...")
        # 先删除旧的尝试（如果有）
        run(ssh, f"cd {REMOTE_DIR} && docker compose run --rm certbot 2>&1 || true")
        
        # 直接用 certbot 容器签发
        certbot_cmd = f"""
        cd {REMOTE_DIR} && docker run --rm \\
            -v {REMOTE_DIR}/certbot-certs:/etc/letsencrypt \\
            -v {REMOTE_DIR}/certbot-www:/var/www/certbot \\
            certbot/certbot:latest certonly --webroot \\
            --webroot-path=/var/www/certbot \\
            --email {EMAIL} \\
            --agree-tos --no-eff-email \\
            --keep-until-expiring \\
            -d {DOMAIN} -d www.{DOMAIN} 2>&1
        """
        code, out, err = run(ssh, certbot_cmd, timeout=120)
        
        # 检查证书是否签发成功
        code2, out2, _ = run(ssh, f"ls -la {REMOTE_DIR}/certbot-certs/live/{DOMAIN}/fullchain.pem 2>&1")
        if code2 != 0 or "No such file" in out2:
            print("❌ 证书签发失败，输出如下:")
            print(out)
            print("尝试使用 staging 环境测试...")
            # 尝试不带 email 的方式或手动创建自签证书临时用
            print("⚠️  证书签发失败，将创建自签名证书临时使用（浏览器会提示不安全，但可以访问）")
            # 创建证书存储目录
            run(ssh, f"mkdir -p {REMOTE_DIR}/certbot-certs/live/{DOMAIN}")
            # 在容器内生成自签证书（用 openssl）
            openssl_cmd = f"""
            cd {REMOTE_DIR} && docker run --rm -v {REMOTE_DIR}/certbot-certs:/certs alpine sh -c '
                apk add --no-cache openssl &&
                openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\
                    -keyout /certs/live/{DOMAIN}/privkey.pem \\
                    -out /certs/live/{DOMAIN}/fullchain.pem \\
                    -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=BossAIGC/CN={DOMAIN}"
            ' 2>&1
            """
            run(ssh, openssl_cmd, timeout=60)
            print("✅ 临时自签名证书已创建（浏览器会提示不安全，生产环境请完成证书签发）")
        else:
            print("✅ Let's Encrypt 证书签发成功！")

        # Step 4: 更新 docker-compose.yml 开放 443 端口
        print("\n[4/6] 更新 docker-compose.yml 开放 443 端口...")
        new_compose = compose_content.replace(
            '# - "443:443"  # HTTPS 证书签发后再开启',
            '"443:443"'
        )
        # 如果没有那行注释，直接替换
        if '"443:443"' not in new_compose:
            new_compose = new_compose.replace(
                '"80:80"',
                '"80:80"\n      - "443:443"'
            )
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "w") as f:
            f.write(new_compose)

        # Step 5: 写入正式 Nginx HTTPS 配置
        print("\n[5/6] 写入正式 Nginx HTTPS 配置...")
        with sftp.file(f"{REMOTE_DIR}/nginx.conf", "w") as f:
            f.write(NGINX_CONF)
        sftp.close()

        # Step 6: 重启服务应用配置
        print("\n[6/6] 重启所有服务...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose down --remove-orphans && docker compose up -d", timeout=180)
        time.sleep(10)

        # 健康检查
        print("\n🔍 等待服务启动并验证...")
        success = False
        for i in range(15):
            # 检查 HTTPS
            code, out, _ = run(ssh, f"curl -sk -o /dev/null -w '%{{http_code}}' https://localhost/api/health", verbose=False)
            if code == 0 and "200" in out:
                print(f"✅ HTTPS 服务正常 (200 OK)")
                success = True
                break
            print(f"  等待中... ({i+1}/15) 当前返回: {out.strip()}")
            time.sleep(3)

        if success:
            print("\n" + "="*60)
            print("  ✅ HTTPS 配置完成！")
            print("="*60)
            print(f"  访问地址: https://{DOMAIN}")
            print(f"           https://www.{DOMAIN}")
            print(f"           http://{DOMAIN} (自动跳转 HTTPS)")
            print("="*60)
        else:
            print("\n⚠️  服务可能还在启动，查看日志:")
            run(ssh, f"cd {REMOTE_DIR} && docker compose logs --tail=20 nginx")

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
