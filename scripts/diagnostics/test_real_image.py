#!/usr/bin/env python3
import json, time, sys, requests

BASE = "http://localhost:8000"

# 1. 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username":"boss","password":"boss123"})
r.raise_for_status()
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 2. 初始对话
r = requests.post(f"{BASE}/api/chat", headers=H, json={"message":"给项链出一张主图"})
r.raise_for_status()
d = r.json()
sid = d["session_id"]
print(f"[1] 理解+确认: status={d['status']}, platform={d.get('summary',{}).get('platform')}, msg={d['message'][:40]}")

# 3. 确认 - 会真触发 ModelScope，等待时间较长
print("[2] 发送确认，等待 ModelScope 生成（可能需要60-120s）...", flush=True)
t0 = time.time()
r = requests.post(f"{BASE}/api/chat", headers=H, json={"message":"确认","session_id":sid}, timeout=200)
elapsed = time.time() - t0
d = r.json()
print(f"[3] 结果: status={d['status']}, 耗时={elapsed:.1f}s")

arts = d.get("artifacts") or []
print(f"    artifacts 数量: {len(arts)}")
for a in arts:
    print(f"    - id={a['artifact_id']}, kind={a['kind']}, url={a.get('url_or_path','')[:80]}")
    print(f"      source={a.get('metadata',{}).get('source')}")
    url = a.get("url_or_path","")
    if url and url.startswith("http"):
        print("    ✅ 真实图片URL (http开头)")
    elif url and url.startswith("mock://"):
        print("    ❌ Mock占位图 (降级了)")
