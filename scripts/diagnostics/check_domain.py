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
        # 1. 用域名 Host 头在服务器本地访问
        ("服务器本地带域名 Host 访问", "curl -s -H 'Host: xjloveqrj.pw' http://localhost/api/health"),
        # 2. 查看 Nginx 访问日志
        ("Nginx 最近访问日志", "cd /opt/bossaigc && docker compose logs --tail=20 nginx 2>&1 | head -30"),
        # 3. 检查 DNS 解析（服务器上）
        ("服务器上 DNS 解析", "nslookup xjloveqrj.pw 2>/dev/null || dig +short xjloveqrj.pw 2>/dev/null || ping -c 1 xjloveqrj.pw 2>&1 | head -5"),
        # 4. 检查是否有其他服务占 80
        ("检查所有 80 端口相关进程", "netstat -tlnp 2>/dev/null | grep :80 || ss -tlnp | grep :80"),
    ]
    
    for name, cmd in commands:
        print(f"\n{'='*60}\n{name}\n{'='*60}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err and "command not found" not in err:
            print("STDERR:", err)

finally:
    ssh.close()
