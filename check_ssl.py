#!/usr/bin/env python3
import paramiko

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

try:
    commands = [
        # 检查是否已有证书
        ("检查Let's Encrypt证书目录", "ls -la /opt/bossaigc/certbot-certs/live/xjloveqrj.pw/ 2>/dev/null || docker run --rm -v /opt/bossaigc/certbot-certs:/etc/letsencrypt alpine ls -la /etc/letsencrypt/live/xjloveqrj.pw/ 2>/dev/null || echo '证书不存在，需要签发'"),
        # 检查 certbot-www 目录权限
        ("检查certbot webroot目录", "ls -la /opt/bossaigc/certbot-www/ 2>/dev/null || echo '目录不存在'"),
        # 测试80端口上ACME验证路径是否可达
        ("测试ACME验证路径", "curl -s -o /dev/null -w '%{http_code}' http://localhost/.well-known/acme-challenge/test 2>&1"),
    ]
    
    for name, cmd in commands:
        print(f"\n{'='*60}\n{name}\n{'='*60}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err and "No such file" not in err:
            print("STDERR:", err)

finally:
    ssh.close()
