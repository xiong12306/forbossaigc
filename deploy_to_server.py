#!/usr/bin/env python3
"""
一键部署脚本：通过 SSH 将代码上传到服务器并重新构建部署
"""
import os
import sys
import time
import paramiko
import tarfile
import io
from pathlib import Path

# 服务器配置
HOST = "47.107.160.40"
PORT = 22
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"

# 需要上传的文件/目录（排除本地缓存、venv、.git 等）
INCLUDE_PATTERNS = [
    "boss_aigc/",
    "web/",
    ".github/",
    "Dockerfile",
    "docker-compose.yml",
    "nginx.conf",
    "requirements.txt",
    "schema.sql",
    "update.sh",
    "deploy.sh",
    ".env.example",
    ".dockerignore",
]

EXCLUDE_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", 
    ".pytest_cache", "dist", "build", ".idea", ".vscode",
    "data", "logs"
}

def should_exclude(path: Path, base: Path) -> bool:
    rel = path.relative_to(base)
    for part in rel.parts:
        if part in EXCLUDE_DIRS or part.startswith("."):
            return True
    if path.is_file() and (path.name.endswith(".pyc") or path.name == ".env"):
        return True
    return False

def create_tarball(base_dir: Path) -> bytes:
    """创建内存中的 tar.gz 包"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for pattern in INCLUDE_PATTERNS:
            p = base_dir / pattern.rstrip("/")
            if p.is_file():
                if not should_exclude(p, base_dir):
                    tar.add(p, arcname=pattern)
            elif p.is_dir():
                for root, dirs, files in os.walk(p):
                    # 过滤排除目录
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
                    root_path = Path(root)
                    for f in files:
                        fp = root_path / f
                        if not should_exclude(fp, base_dir):
                            arcname = str(fp.relative_to(base_dir))
                            tar.add(fp, arcname=arcname)
    buf.seek(0)
    return buf.read()

def run_ssh_command(ssh: paramiko.SSHClient, cmd: str, timeout=300) -> tuple:
    """执行 SSH 命令并返回输出"""
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err and exit_code != 0:
        print(f"STDERR: {err}", file=sys.stderr)
    return exit_code, out, err

def main():
    base_dir = Path(__file__).parent.resolve()
    print(f"📦 打包项目文件: {base_dir}")
    tar_data = create_tarball(base_dir)
    print(f"   打包完成: {len(tar_data)/1024/1024:.2f} MB")

    print(f"\n🔌 连接服务器 {USER}@{HOST}:{PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("   连接成功")

    try:
        sftp = ssh.open_sftp()
        
        # 确保目标目录存在
        run_ssh_command(ssh, f"mkdir -p {REMOTE_DIR}")
        
        # 上传 tar 包
        remote_tar = f"{REMOTE_DIR}/update.tar.gz"
        print(f"\n📤 上传代码到 {remote_tar}...")
        with sftp.file(remote_tar, "wb") as f:
            f.set_pipelined(True)
            f.write(tar_data)
        print("   上传完成")
        
        # 解压覆盖（保留 .env 和 data/）
        print("\n📂 解压代码...")
        run_ssh_command(ssh, f"""
            cd {REMOTE_DIR} && \
            tar -xzf update.tar.gz && \
            rm -f update.tar.gz && \
            chmod +x update.sh deploy.sh
        """)
        
        # 检查 .env 是否存在
        print("\n⚙️  检查 .env 配置...")
        try:
            sftp.stat(f"{REMOTE_DIR}/.env")
            print("   .env 已存在")
        except FileNotFoundError:
            print("   ⚠️  .env 不存在，从 .env.example 创建...")
            run_ssh_command(ssh, f"""
                cd {REMOTE_DIR} && \
                cp .env.example .env && \
                JWT_SECRET=$(openssl rand -hex 32) && \
                sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
            """)
            print("   请编辑 .env 填入 SUPABASE_URL 和 SUPABASE_ANON_KEY！")
            print("   然后在服务器上执行: cd /opt/bossaigc && bash update.sh")
            return
        
        sftp.close()
        
        # 执行更新脚本
        print("\n🚀 执行更新部署...")
        exit_code, out, err = run_ssh_command(ssh, f"cd {REMOTE_DIR} && bash update.sh", timeout=600)
        
        if exit_code == 0:
            print("\n" + "="*50)
            print("  ✅ 部署成功！")
            print("="*50)
            print(f"  访问地址: https://xjloveqrj.pw")
            print(f"  健康检查: http://{HOST}/api/health")
            print("="*50)
        else:
            print(f"\n❌ 部署失败 (exit code: {exit_code})", file=sys.stderr)
            sys.exit(1)
            
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
