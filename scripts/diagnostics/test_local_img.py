"""验证图片下载到本地"""
import requests, time

BASE = "http://localhost:8000"
H = {"Content-Type": "application/json"}

r = requests.post(f"{BASE}/api/auth/login", json={"username":"boss","password":"boss123"}, timeout=10)
H["Authorization"] = f"Bearer {r.json()['access_token']}"
print("[1] 登录 OK")

# reset
requests.post(f"{BASE}/api/reset", headers=H, timeout=10)

# 发送指令
r = requests.post(f"{BASE}/api/chat", headers=H, json={
    "message": "给金项链出一张商品主图"
}, timeout=20)
sid = r.json()["session_id"]
print("[2] 发指令 OK")

# 确认
t0 = time.time()
r = requests.post(f"{BASE}/api/chat", headers=H, json={"message":"确认","session_id":sid}, timeout=300)
elapsed = time.time() - t0
d = r.json()
print(f"[3] 结果: status={d['status']}, 耗时={elapsed:.1f}s")
arts = d.get('artifacts') or []
print(f"    artifacts 数量: {len(arts)}")
for a in arts:
    url = a.get('url_or_path','')
    src = (a.get('metadata') or {}).get('source','?')
    is_mock = url.startswith("mock://")
    is_local = url.startswith("/uploads/")
    print(f"    - url={url[:80]}")
    print(f"      source={src}, local={is_local}")
    if is_local:
        # 验证本地 URL 可访问
        img_resp = requests.head(f"{BASE}{url}", timeout=10)
        print(f"      本地访问: {img_resp.status_code}, size={img_resp.headers.get('Content-Length','?')}")
    print(f"      {'❌ MOCK' if is_mock else '✅ 真实图片'}")
