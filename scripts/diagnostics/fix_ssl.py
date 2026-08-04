#!/usr/bin/env python3
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"
DOMAIN = "xjloveqrj.pw"

def run(ssh, cmd, timeout=120):
    print(f"$ {cmd[:90]}...")
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
    print("=== 修复 SSL 配置 ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    try:
        # 1. 在宿主机（Ubuntu）直接生成证书，保存到 volume 目录
        print("\n[1] 在宿主机生成自签 SSL 证书...")
        cert_dir = f"{REMOTE_DIR}/certbot-certs/live/{DOMAIN}"
        run(ssh, f"mkdir -p {cert_dir}")
        gen_cert = f"""
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\
            -keyout {cert_dir}/privkey.pem \\
            -out {cert_dir}/fullchain.pem \\
            -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=BossAIGC/CN={DOMAIN}" 2>&1
        """
        code, out, err = run(ssh, gen_cert)
        run(ssh, f"ls -la {cert_dir}/")

        # 2. 检查 docker-compose 卷挂载
        print("\n[2] 确认证书卷挂载配置...")
        sftp = ssh.open_sftp()
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "r") as f:
            compose = f.read().decode()
        
        # 确保 nginx 挂载了 certbot-certs 卷
        if "certbot-certs:/etc/letsencrypt" not in compose:
            compose = compose.replace(
                "- certbot-www:/var/www/certbot",
                "- certbot-www:/var/www/certbot\n      - certbot-certs:/etc/letsencrypt"
            )
            with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "w") as f:
                f.write(compose)
            print("  -> 已添加 certbot-certs 卷挂载")
        sftp.close()

        # 3. 重启 nginx
        print("\n[3] 重启 Nginx 容器...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose up -d --force-recreate nginx", timeout=120)
        time.sleep(5)

        # 4. 测试 HTTPS
        print("\n[4] 测试 HTTPS 访问...")
        for i in range(12):
            code, out, _ = run(ssh, "curl -sk -o /dev/null -w '%{http_code}' https://localhost/api/health")
            if "200" in out:
                print(f"\n✅ HTTPS 访问成功！")
                break
            print(f"  等待... ({i+1}/12)")
            time.sleep(3)

        # 5. 查看容器状态和日志（如果失败）
        if code != 0 or "200" not in out:
            print("\n[诊断] 查看容器状态和日志:")
            run(ssh, f"cd {REMOTE_DIR} && docker compose ps")
            run(ssh, f"cd {REMOTE_DIR} && docker compose logs --tail=30 nginx")

        print("\n" + "="*60)
        print("  测试外网域名访问...")
        print("="*60)
        import subprocess
        result = subprocess.run(
            ["curl", "-sk", "-m", "10", "-o", "/dev/null", "-w", "外网HTTPS状态码: %{http_code}\\n", f"https://{DOMAIN}/api/health"],
            capture_output=True, text=True
        )
        print("  ", result.stdout.strip() or result.stderr.strip())
        
        print("\n" + "="*60)
        print("  访问地址: https://xjloveqrj.pw/platform")
        print("  账号: boss / 密码: boss123")
        print("="*60)

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
