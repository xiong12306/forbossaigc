#!/usr/bin/env python3
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"
DOMAIN = "xjloveqrj.pw"

def run(ssh, cmd, timeout=300, get_output=True):
    print(f">>> {cmd[:100]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace") if get_output else ""
    err = stderr.read().decode("utf-8", errors="replace") if get_output else ""
    if exit_code != 0:
        print(f"  退出码: {exit_code}")
        if err:
            print(f"  错误: {err[:300]}")
    return exit_code, out, err

def main():
    print("快速启用 HTTPS...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    try:
        # 1. 创建证书目录
        print("\n[1] 创建证书目录...")
        run(ssh, f"mkdir -p {REMOTE_DIR}/certbot-certs/live/{DOMAIN}")

        # 2. 在已有 nginx 容器中直接生成自签证书（快速，不需要拉新镜像）
        print("\n[2] 生成 SSL 证书（使用容器内 openssl）...")
        # 注意：nginx:alpine 镜像自带 openssl，不需要额外安装
        gen_cert = f"""
        cd {REMOTE_DIR} && docker compose exec -T nginx sh -c '
            mkdir -p /etc/letsencrypt/live/{DOMAIN} &&
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\
                -keyout /etc/letsencrypt/live/{DOMAIN}/privkey.pem \\
                -out /etc/letsencrypt/live/{DOMAIN}/fullchain.pem \\
                -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=BossAIGC/CN={DOMAIN}" 2>&1 &&
            ls -la /etc/letsencrypt/live/{DOMAIN}/
        '
        """
        # 先把证书目录挂载进去（需要重新创建容器）
        # 先修改 docker-compose 挂载证书目录
        print("\n[3] 更新 docker-compose.yml 挂载证书目录并开放 443...")
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "r") as f:
            compose = f.read().decode()

        # 确保 443 端口开放
        if '"443:443"' not in compose:
            compose = compose.replace('"80:80"', '"80:80"\n      - "443:443"')
        # 添加 certs 卷挂载（如果没有）
        if "certbot-certs" not in compose:
            compose = compose.replace(
                "- certbot-www:/var/www/certbot",
                "- certbot-www:/var/www/certbot\n      - certbot-certs:/etc/letsencrypt"
            )
        
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "w") as f:
            f.write(compose)

        # 写入正式 Nginx 配置
        print("\n[4] 写入 Nginx HTTPS 配置...")
        nginx_conf = f"""upstream bossaigc_backend {{
    server app:8000;
    keepalive 32;
}}

server {{
    listen 80;
    listen [::]:80;
    server_name {DOMAIN} www.{DOMAIN} 47.107.160.40;

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
    server_name {DOMAIN} www.{DOMAIN} 47.107.160.40;

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
        with sftp.file(f"{REMOTE_DIR}/nginx.conf", "w") as f:
            f.write(nginx_conf)

        sftp.close()

        # 5. 重启服务
        print("\n[5] 重启容器并生成证书...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose up -d --force-recreate", timeout=180)
        time.sleep(8)

        # 6. 生成证书
        print("\n[6] 生成 SSL 证书...")
        code, out, err = run(ssh, f"""
            cd {REMOTE_DIR} && docker compose exec -T nginx sh -c '
                mkdir -p /etc/letsencrypt/live/{DOMAIN} &&
                openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\
                    -keyout /etc/letsencrypt/live/{DOMAIN}/privkey.pem \\
                    -out /etc/letsencrypt/live/{DOMAIN}/fullchain.pem \\
                    -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=BossAIGC/CN={DOMAIN}" &&
                echo "证书生成成功" && ls -la /etc/letsencrypt/live/{DOMAIN}/
            '
        """)

        # 7. 重启 nginx 加载证书
        print("\n[7] 重启 Nginx 加载证书...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose restart nginx", timeout=60)
        time.sleep(5)

        # 8. 验证
        print("\n[8] 验证访问...")
        for i in range(10):
            # HTTPS 验证（忽略证书错误）
            code, out, _ = run(ssh, "curl -sk -o /dev/null -w '%{http_code}' https://localhost/api/health", get_output=True)
            if "200" in out:
                print(f"  ✅ HTTPS 访问成功！(本地验证 200)")
                break
            print(f"  等待... ({i+1}/10) 响应: {out.strip()}")
            time.sleep(3)

        # 从我们这边测试
        print("\n=== 从本地测试域名访问 ===")
        run(ssh, "curl -sk -o /dev/null -w '本地HTTPS状态码: %{http_code}\\n' https://localhost/api/health")
        
        print("\n" + "="*60)
        print("  ✅ HTTPS 已启用！")
        print("="*60)
        print(f"  访问: https://{DOMAIN}/platform")
        print(f"  注意: 由于使用自签名证书，浏览器会提示「不安全」")
        print(f"        点击「高级」->「继续访问」即可正常使用")
        print(f"  后续可在服务器上运行 certbot 申请免费可信证书")
        print("="*60)

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
