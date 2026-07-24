#!/bin/bash
# 1. 配置 Docker 镜像加速器
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'DOCKEREOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://docker.1panel.live"
  ]
}
DOCKEREOF
systemctl restart docker
echo "DOCKER_RESTARTED"

# 2. 修复 .env 中 $ 转义问题
cd /opt/bossaigc
python3 << 'PYEOF'
import hashlib, secrets
salt = secrets.token_hex(8)
password = 'boss123'
h = hashlib.sha256(f'{salt}{password}'.encode()).hexdigest()
jwt_secret = secrets.token_hex(32)
with open('.env', 'w') as f:
    f.write('SUPABASE_URL=https://fkmudnfwkrruojltxwmx.supabase.co\n')
    f.write('SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZrbXVkbmZ3a3JydW9qbHR4d214Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NTk4NjUsImV4cCI6MjEwMDQzNTg2NX0.eBTRi29MGpZ75CC2HT8uxq6msQK3Ue6Q5BAoKW-e6nw\n')
    f.write('NANOBANANA_API_KEY=\n')
    f.write(f'JWT_SECRET={jwt_secret}\n')
    f.write('JWT_EXPIRE_HOURS=24\n')
    f.write('BOSS_USERNAME=boss\n')
    # docker compose: $$ 表示字面 $
    f.write(f'BOSS_PASSWORD_HASH={salt}$${h}\n')
    f.write('ALLOWED_ORIGINS=http://47.107.160.40,http://localhost\n')
    f.write('USE_REAL_PLATFORM=False\n')
print('ENV_FIXED')
PYEOF
echo '--- .env ---'
cat .env
