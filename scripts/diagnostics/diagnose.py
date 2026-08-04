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
        # 1. 容器状态
        ("容器运行状态", "cd /opt/bossaigc && docker compose ps"),
        # 2. 端口监听
        ("80 端口监听状态", "ss -tlnp | grep ':80 ' || netstat -tlnp | grep ':80 '"),
        # 3. 本地 curl 测试
        ("服务器本地访问测试", "curl -s -o /dev/null -w 'HTTP状态码: %{http_code}\\n' http://localhost/"),
        # 4. 防火墙状态
        ("UFW 防火墙状态", "ufw status 2>/dev/null || echo 'ufw 未安装'"),
        # 5. iptables 规则
        ("iptables 80端口规则", "iptables -L INPUT -n | grep -E '80|ACCEPT|DROP' | head -20"),
        # 6. Docker 网络
        ("Docker 端口映射", "docker port bossaigc-nginx 2>/dev/null"),
    ]
    
    for name, cmd in commands:
        print(f"\n{'='*60}\n$ {name}\n{'='*60}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err and "command not found" not in err:
            print("STDERR:", err)

finally:
    ssh.close()
