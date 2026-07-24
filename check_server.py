#!/usr/bin/env python3
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"
DOMAIN = "xjloveqrj.pw"

def run(ssh, cmd, timeout=60):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.strip())
    if code != 0 and err.strip():
        print("STDERR:", err.strip())
    return code, out, err

def main():
    print("=== 服务器状态检查 ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    try:
        # 容器状态
        run(ssh, f"cd {REMOTE_DIR} && docker compose ps")
        
        # Nginx 日志
        run(ssh, f"cd {REMOTE_DIR} && docker compose logs --tail=30 nginx")
        
        # 端口监听
        run(ssh, "ss -tlnp | grep -E ':80|:443'")
        
        # 本地 curl HTTPS 详细日志
        run(ssh, "curl -skv https://localhost/api/health 2>&1")
        
        # 检查证书
        run(ssh, f"openssl x509 -in {REMOTE_DIR}/certbot-certs/live/{DOMAIN}/fullchain.pem -noout -subject -dates")

        print("\n=== 检查完成 ===")

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
