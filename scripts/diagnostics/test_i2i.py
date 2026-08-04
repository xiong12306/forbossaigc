"""验证图生图（根据参考图出图）真实调用 ModelScope"""
import requests, time

BASE = "http://localhost:8000"
H = {"Content-Type": "application/json"}

# 1. 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username":"boss","password":"boss123"}, timeout=10)
H["Authorization"] = f"Bearer {r.json()['access_token']}"
print("[1] 登录 OK")

# 2. 发带参考图的指令
t0 = time.time()
r = requests.post(f"{BASE}/api/chat", headers=H, json={
    "message": "根据这张图出一张商品主图，白色背景",
    "images": ["/uploads/2d6ac824952c.png"]
}, timeout=20)
sid = r.json()["session_id"]
print(f"[2] 发指令 OK: {r.json()['message'][:80]}")

# 3. 确认
t0 = time.time()
r = requests.post(f"{BASE}/api/chat", headers=H, json={"message":"确认","session_id":sid}, timeout=300)
elapsed = time.time() - t0
d = r.json()
print(f"[3] 结果: status={d['status']}, 耗时={elapsed:.1f}s")
print(f"    message: {d['message'][:100]}")
arts = d.get('artifacts') or []
print(f"    artifacts 数量: {len(arts)}")
for a in arts:
    url = a.get('url_or_path','')
    src = (a.get('metadata') or {}).get('source','?')
    mode = (a.get('metadata') or {}).get('mode','?')
    is_mock = url.startswith("mock://")
    print(f"    - id={a.get('artifact_id')}, kind={a.get('kind')}")
    print(f"      url={url[:100]}")
    print(f"      source={src}, mode={mode}")
    print(f"      {'❌ 还是 MOCK 占位图' if is_mock else '✅ 真实图片URL (http开头)'}")
