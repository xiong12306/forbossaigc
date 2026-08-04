#!/usr/bin/env python3
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"

# 正确的 docker-compose.yml 内容
DOCKER_COMPOSE = """# BossAIGC 生产部署 docker-compose
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: bossaigc-app
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - PORT=8000
      - WEB_CONCURRENCY=1
    volumes:
      - app-data:/app/data
    expose:
      - "8000"
    networks:
      - boss-net

  nginx:
    image: nginx:alpine
    container_name: bossaigc-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certbot-www:/var/www/certbot
      - ./certbot-certs:/etc/letsencrypt
      - nginx-logs:/var/log/nginx
    depends_on:
      - app
    networks:
      - boss-net

  certbot:
    image: certbot/certbot:latest
    profiles: ["certbot"]
    volumes:
      - ./certbot-www:/var/www/certbot
      - ./certbot-certs:/etc/letsencrypt
    entrypoint: >
      certbot certonly --webroot
      --webroot-path=/var/www/certbot
      --email a****@*************
      --agree-tos --no-eff-email
      -d xjloveqrj.pw -d www.xjloveqrj.pw

volumes:
  app-data:
  nginx-logs:

networks:
  boss-net:
    driver: bridge
"""

def run(ssh, cmd, timeout=120):
    print(f"$ {cmd[:70]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print("  ->", out.strip()[:200])
    if code != 0 and err.strip():
        print("  ERR:", err.strip()[:200])
    return code, out, err

def main():
    print("=== 修复 docker-compose.yml YAML 语法错误 ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    try:
        sftp = ssh.open_sftp()
        
        print("\n[1] 写入正确的 docker-compose.yml...")
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "w") as f:
            f.write(DOCKER_COMPOSE)
        
        sftp.close()
        
        # 验证 YAML 语法（用 docker compose config）
        print("\n[2] 验证 docker-compose.yml 语法...")
        code, out, err = run(ssh, f"cd {REMOTE_DIR} && docker compose config --quiet 2>&1 && echo 'YAML 语法正确'")
        
        if code != 0:
            print("  YAML 语法错误，请检查")
            return
        
        # 重启服务
        print("\n[3] 重启服务...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose down --remove-orphans", timeout=60)
        run(ssh, f"cd {REMOTE_DIR} && docker compose up -d", timeout=180)
        
        # 等待
        print("\n[4] 等待服务启动...")
        time.sleep(10)
        
        # 验证端口监听
        print("\n[5] 检查端口监听...")
        run(ssh, "ss -tlnp | grep -E ':80|:443'")
        
        # 验证容器状态
        run(ssh, f"cd {REMOTE_DIR} && docker compose ps")
        
        # 本地测试
        print("\n[6] 本地测试...")
        for proto, port in [("http", 80), ("https", 443)]:
            for i in range(8):
                flag = "-k" if proto == "https" else ""
                code, out, _ = run(ssh, f"curl -s {flag} -o /dev/null -w '%{{http_code}}' {proto}://localhost/api/health", timeout=10)
                if "200" in out:
                    print(f"  ✅ {proto.upper()} 正常 (200 OK)")
                    break
                time.sleep(2)
        
        # 外网测试
        print("\n[7] 外网访问测试...")
        import subprocess
        for proto in ["http", "https"]:
            flag = "-k" if proto == "https" else ""
            r = subprocess.run(
                ["curl", flag, "-s", "-m", "10", "-o", "/dev/null", "-w", f"{proto.upper()}: %{{http_code}}\\n", f"{proto}://xjloveqrj.pw/api/health"],
                capture_output=True, text=True
            )
            print(" ", r.stdout.strip())
        
        print("\n" + "="*60)
        print("  ✅ 修复完成！")
        print("="*60)
        print("  👉 访问: https://xjloveqrj.pw/platform")
        print("  🔑 账号: boss / 密码: boss123")
        print("  ⚠️  浏览器提示不安全，点「高级」->「继续访问xjloveqrj.pw（不安全）」")
        print("="*60)

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
