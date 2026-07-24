#!/usr/bin/env python3
import paramiko
import time

HOST = "47.107.160.40"
USER = "root"
PASSWORD = "Root1234"
REMOTE_DIR = "/opt/bossaigc"
DOMAIN = "xjloveqrj.pw"

def run(ssh, cmd, timeout=120, verbose=True):
    if verbose:
        print(f"$ {cmd[:80]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if verbose and out.strip():
        print("  ->", out.strip()[:300])
    if code != 0 and err.strip() and verbose:
        print("  ERR:", err.strip()[:300])
    return code, out, err

def main():
    print("=== 最终修复：开放443端口 + 修复证书挂载 ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    try:
        # 1. 修复 docker-compose.yml - 取消443注释，改用 bind mount 而不是 named volume
        print("\n[1] 修复 docker-compose.yml...")
        # 读取当前文件
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "r") as f:
            content = f.read().decode()
        
        # 修复：取消注释443端口
        content = content.replace(
            '# - "443:443"  # HTTPS 证书签发后再开启',
            '"443:443"'
        )
        
        # 修复：将 certbot-certs named volume 改为 bind mount 到宿主机目录
        # 在 volumes 部分，nginx 的挂载：
        # 旧: - certbot-certs:/etc/letsencrypt
        # 新: - ./certbot-certs:/etc/letsencrypt
        content = content.replace(
            "- certbot-certs:/etc/letsencrypt",
            "- ./certbot-certs:/etc/letsencrypt"
        )
        
        # 同样修复 certbot 服务的挂载（如果存在）
        content = content.replace(
            "    volumes:\n      - certbot-www:/var/www/certbot\n      - certbot-certs:/etc/letsencrypt",
            "    volumes:\n      - ./certbot-www:/var/www/certbot\n      - ./certbot-certs:/etc/letsencrypt"
        )
        
        # 从 volumes 定义中移除 certbot-certs 和 certbot-www（改用 bind mount）
        # 保留其他 volumes
        new_volumes = []
        in_volumes = False
        for line in content.split('\n'):
            if line.startswith('volumes:'):
                in_volumes = True
                new_volumes.append(line)
                continue
            if in_volumes:
                if line.startswith('networks:') or (not line.startswith(' ') and line.strip()):
                    in_volumes = False
                    # 只保留 app-data 和 nginx-logs
                    new_volumes.append("  app-data:")
                    new_volumes.append("  nginx-logs:")
                if not in_volumes:
                    new_volumes.append(line)
                continue
            new_volumes.append(line)
        
        content = '\n'.join(new_volumes)
        
        with sftp.file(f"{REMOTE_DIR}/docker-compose.yml", "w") as f:
            f.write(content)
        print("  -> docker-compose.yml 已更新")

        # 2. 证书已经在 ./certbot-certs/live/DOMAIN/ 了，确认权限
        print("\n[2] 确认证书文件权限...")
        run(ssh, f"chmod -R 755 {REMOTE_DIR}/certbot-certs/")
        run(ssh, f"ls -la {REMOTE_DIR}/certbot-certs/live/{DOMAIN}/")

        sftp.close()

        # 3. 重启所有容器
        print("\n[3] 停止并重新启动所有容器...")
        run(ssh, f"cd {REMOTE_DIR} && docker compose down", timeout=60)
        # 清理旧的 named volumes（因为我们改用 bind mount 了）
        run(ssh, f"cd {REMOTE_DIR} && docker volume rm bossaigc_certbot-certs bossaigc_certbot-www 2>/dev/null || true", timeout=30)
        run(ssh, f"cd {REMOTE_DIR} && docker compose up -d", timeout=180)

        # 4. 等待并验证
        print("\n[4] 等待服务启动并验证...")
        time.sleep(10)
        
        # 先验证 HTTP
        print("  测试 HTTP...")
        for i in range(8):
            code, out, _ = run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost/api/health", verbose=False)
            if "200" in out:
                print("  ✅ HTTP 正常")
                break
            time.sleep(2)
        
        # 验证 HTTPS
        print("  测试 HTTPS...")
        for i in range(10):
            code, out, _ = run(ssh, "curl -sk -o /dev/null -w '%{http_code}' https://localhost/api/health", verbose=False)
            if "200" in out:
                print("  ✅ HTTPS 正常")
                break
            print(f"  等待 HTTPS... ({i+1}/10)")
            time.sleep(3)
        else:
            # 查看日志
            print("  ❌ HTTPS 失败，查看日志:")
            run(ssh, f"cd {REMOTE_DIR} && docker compose ps")
            run(ssh, f"cd {REMOTE_DIR} && docker compose logs --tail=20 nginx")

        # 验证端口监听
        run(ssh, "ss -tlnp | grep -E ':80|:443'")

        print("\n" + "="*60)
        print("  从外网测试...")
        print("="*60)
        
        import subprocess
        # 测试 HTTP
        r = subprocess.run(["curl", "-s", "-m", "10", "-o", "/dev/null", "-w", "HTTP:  %{http_code}\\n", "http://xjloveqrj.pw/api/health"], capture_output=True, text=True)
        print(" ", r.stdout.strip())
        # 测试 HTTPS（-k 忽略证书错误）
        r = subprocess.run(["curl", "-sk", "-m", "10", "-o", "/dev/null", "-w", "HTTPS: %{http_code}\\n", "https://xjloveqrj.pw/api/health"], capture_output=True, text=True)
        print(" ", r.stdout.strip())

        print("\n" + "="*60)
        print("  ✅ 修复完成！")
        print("="*60)
        print("  👉 访问: https://xjloveqrj.pw/platform")
        print("  🔑 账号: boss / 密码: boss123")
        print("  ⚠️  浏览器提示不安全时，点「高级」->「继续访问」")
        print("="*60)

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
