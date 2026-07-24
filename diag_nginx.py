#!/usr/bin/env python3
import paramiko

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

try:
    commands = [
        "cd /opt/bossaigc && docker compose logs nginx 2>&1",
        "cd /opt/bossaigc && cat docker-compose.yml",
        "cd /opt/bossaigc && cat nginx.conf",
        "ls -la /opt/bossaigc/certbot-certs/live/xjloveqrj.pw/",
        "cd /opt/bossaigc && docker volume ls | grep certbot",
    ]
    for cmd in commands:
        print(f"\n{'='*60}\n$ {cmd}\n{'='*60}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err:
            print("ERR:", err)
finally:
    ssh.close()
