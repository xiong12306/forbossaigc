#!/usr/bin/env python3
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"
DOMAIN = "xjloveqrj.pw"

def run(ssh, cmd, timeout=120, verbose=True):
    if verbose:
        print(f"$ {cmd[:90]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if verbose and out.strip():
        print("  ->", out.strip()[:400])
    if code != 0 and err.strip() and verbose:
        print("  ERR:", err.strip()[:300])
    return code, out, err

def main():
    print("=== 签发正式 Let's Encrypt SSL 证书 ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    try:
        # 1. 先修改 Nginx 配置，临时移除 HSTS，使用 HTTP 签发证书
        print("\n[1] 更新 Nginx 配置（支持 ACME 验证）...")
        nginx_conf = f"""upstream bossaigc_backend {{
    server app:8000;
    keepalive 32;
}}

server {{
    listen 80;
    listen [::]:80;
    server_name {DOMAIN} www.{DOMAIN};

    location /.well-known/acme-challenge/ {{
        root /var/www/certbot;
    }}

    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {DOMAIN} www.{DOMAIN};

    ssl_certificate /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 20M;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;
    gzip_min_length 1024;

    location /api/ {{
        proxy_pass http://bossaigc_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
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
        # 如果 Let's Encrypt 签发失败，先用这个配置（不带 HSTS），自签证书也能访问
        with sftp.file(f"{REMOTE_DIR}/nginx.conf", "w") as f:
            f.write(nginx_conf)
        sftp.close()

        # 2. 确保 webroot 目录存在
        print("\n[2] 准备 ACME webroot 目录...")
        run(ssh, f"mkdir -p {REMOTE_DIR}/certbot-www/.well-known/acme-challenge")
        run(ssh, f"chmod -R 755 {REMOTE_DIR}/certbot-www/")
        
        # 重启 nginx 应用配置
        print("\n[3] 重启 Nginx...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose up -d --force-recreate nginx", timeout=60)
        time.sleep(5)

        # 3. 测试 HTTP 访问是否正常（ACME 验证需要 HTTP 访问）
        print("\n[4] 测试 HTTP 域名访问...")
        # 从外网测试 HTTP 是否可访问
        import subprocess
        for i in range(5):
            r = subprocess.run(["curl", "-s", "-m", "10", "-o", "/dev/null", "-w", "%{http_code}", f"http://{DOMAIN}/.well-known/acme-challenge/test"], capture_output=True, text=True)
            print(f"  HTTP 测试: {r.stdout.strip()}")
            if r.stdout.strip() in ["404", "200", "301"]:
                print("  ✅ HTTP 可访问")
                break
            time.sleep(3)
        else:
            print("  ⚠️  HTTP 访问有问题，继续尝试签发...")

        # 4. 签发证书
        print("\n[5] 签发 Let's Encrypt 证书...")
        # 用 certbot 容器，通过 webroot 方式签发
        # 先确保有最新的 certbot 镜像
        certbot_cmd = f"""
        cd {REMOTE_DIR} && docker run --rm \\
            -v {REMOTE_DIR}/certbot-certs:/etc/letsencrypt \\
            -v {REMOTE_DIR}/certbot-www:/var/www/certbot \\
            certbot/certbot:latest certonly --webroot \\
            --webroot-path=/var/www/certbot \\
            --email a****@************* \\
            --agree-tos --no-eff-email \\
            --non-interactive \\
            --keep-until-expiring \\
            -d {DOMAIN} -d www.{DOMAIN} 2>&1
        """
        code, out, err = run(ssh, certbot_cmd, timeout=180)
        
        # 检查证书是否签发成功
        print("\n[6] 检查证书...")
        code2, out2, _ = run(ssh, f"ls -la {REMOTE_DIR}/certbot-certs/live/{DOMAIN}/fullchain.pem 2>&1")
        
        cert_ok = False
        if code2 == 0 and "No such file" not in out2 and "fullchain.pem" in out2:
            print("✅ Let's Encrypt 证书签发成功！")
            cert_ok = True
        else:
            print("⚠️  Let's Encrypt 签发失败，保留自签证书")
            print("   输出:", out[-500:] if out else "")
            # 重新生成自签证书（之前可能已存在）
            run(ssh, f"mkdir -p {REMOTE_DIR}/certbot-certs/live/{DOMAIN}")
            run(ssh, f"""
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\
                -keyout {REMOTE_DIR}/certbot-certs/live/{DOMAIN}/privkey.pem \\
                -out {REMOTE_DIR}/certbot-certs/live/{DOMAIN}/fullchain.pem \\
                -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=BossAIGC/CN={DOMAIN}" 2>&1
            """)

        # 5. 重启 nginx 加载新证书
        print("\n[7] 重启 Nginx 加载证书...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose restart nginx", timeout=60)
        time.sleep(5)

        # 6. 验证
        print("\n[8] 验证访问...")
        for proto in ["http", "https"]:
            flag = "-k" if proto == "https" and not cert_ok else ""
            r = subprocess.run(
                ["curl", flag, "-s", "-m", "10", "-o", "/dev/null", "-w", f"{proto.upper()}: %{{http_code}}\\n", f"{proto}://{DOMAIN}/api/health"],
                capture_output=True, text=True
            )
            print(" ", r.stdout.strip())

        print("\n" + "="*60)
        if cert_ok:
            print("  ✅ HTTPS 配置完成！正式证书已签发")
            print("  浏览器地址栏会显示安全锁🔒")
        else:
            print("  ⚠️  使用自签名证书")
            print("  Chrome 访问问题解决方法：")
            print("  1. 在当前错误页面，直接键盘输入 thisisunsafe （盲打，页面不显示）")
            print("  2. 或者用 Firefox/Safari 访问，可以点「高级」→「继续访问」")
            print("  3. 或者访问 http://xjloveqrj.pw （自动跳转但你可以回退）")
        print("="*60)
        print(f"  👉 访问: https://{DOMAIN}/platform")
        print("  🔑 账号: boss / 密码: boss123")
        print("="*60)

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
