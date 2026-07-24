#!/usr/bin/env python3
import paramiko
import os
from pathlib import Path

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"

# 需要更新的文件
FILES_TO_UPDATE = [
    "nginx.conf",
    "docker-compose.yml",
    "update.sh",
    ".env.example",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

try:
    sftp = ssh.open_sftp()
    base_dir = Path(__file__).parent

    # 更新配置文件
    print("📤 更新配置文件...")
    for f in FILES_TO_UPDATE:
        local = base_dir / f
        remote = f"{REMOTE_DIR}/{f}"
        print(f"   上传 {f}")
        sftp.put(str(local), remote)

    # 更新服务器 .env 的 ALLOWED_ORIGINS
    print("\n⚙️  更新 .env CORS 配置...")
    stdin, stdout, stderr = ssh.exec_command(f"""
        cd {REMOTE_DIR} && \
        if grep -q '^ALLOWED_ORIGINS=' .env; then
            sed -i 's|^ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:5175,http://47.107.160.40,http://xjloveqrj.pw,https://xjloveqrj.pw|' .env
        else
            echo 'ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:5175,http://47.107.160.40,http://xjloveqrj.pw,https://xjloveqrj.pw' >> .env
        fi
    """)
    stdout.channel.recv_exit_status()

    # 检查 BOSS_PASSWORD_HASH 是否设置
    print("🔑 检查登录密码配置...")
    stdin, stdout, stderr = ssh.exec_command(f"grep '^BOSS_PASSWORD_HASH=' {REMOTE_DIR}/.env")
    pwd_line = stdout.read().decode().strip()
    if not pwd_line or pwd_line.endswith("="):
        print("   ⚠️  BOSS_PASSWORD_HASH 未设置，生成默认密码 'boss123' 的哈希...")
        # 生成密码哈希
        stdin, stdout, stderr = ssh.exec_command(f"""
            cd {REMOTE_DIR} && docker compose exec -T app python -c "
from boss_aigc.auth import _hash_password
print(_hash_password('boss123'))
" 2>/dev/null || python3 -c "
import hashlib, secrets
salt = secrets.token_hex(8)
h = hashlib.sha256(f'{{salt}}boss123'.encode()).hexdigest()
print(f'{{salt}}${{h}}')
"
        """)
        pwd_hash = stdout.read().decode().strip()
        if pwd_hash and "$" in pwd_hash:
            ssh.exec_command(f"""
                cd {REMOTE_DIR} && \
                sed -i "s|^BOSS_PASSWORD_HASH=.*|BOSS_PASSWORD_HASH={pwd_hash}|" .env
            """)
            print(f"   ✅ 已设置默认密码: boss / boss123")
        else:
            print("   ⚠️  无法生成密码哈希，请手动设置")

    sftp.close()

    # 重启服务（先只重启 nginx，如果 CORS 改了再重启 app）
    print("\n🔄 重启服务...")
    stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && docker compose up -d --force-recreate nginx", timeout=120)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("STDERR:", err)

    # 需要重启 app 让 CORS 生效
    print("🔄 重启后端应用（使 CORS 生效）...")
    stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && docker compose up -d --force-recreate app", timeout=120)
    print(stdout.read().decode())

    # 等待服务启动
    print("\n⏳ 等待服务启动...")
    import time
    time.sleep(8)

    # 健康检查
    for i in range(10):
        stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost/api/health")
        result = stdout.read().decode().strip()
        if result and "status" in result.lower() or "ok" in result.lower():
            print(f"   ✅ 服务就绪: {result}")
            break
        time.sleep(2)
    else:
        print("   ⚠️  健康检查无响应，查看日志...")
        stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && docker compose logs --tail=20 app")
        print(stdout.read().decode())

    print("\n" + "="*60)
    print("  ✅ 配置更新完成！")
    print("="*60)
    print(f"  访问地址: http://47.107.160.40")
    print(f"           http://xjloveqrj.pw")
    print(f"  用户名: boss")
    print(f"  密码: boss123")
    print("="*60)

finally:
    ssh.close()
