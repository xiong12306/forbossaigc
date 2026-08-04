"""测试画布生成API（文生图）"""
import sys
import httpx

def test_text_to_image():
    url = "http://localhost:8000/api/canvas/generate"
    payload = {
        "prompt": "一个简约白色陶瓷马克杯",
        "reference_images": [],
        "reference_texts": ["商品摄影"],
        "model": "modelscope",
        "size": "1:1",
        "preset": "main"
    }
    print("测试文生图API...")
    print(f"请求: {payload}")
    try:
        with httpx.Client(timeout=300.0, trust_env=False) as client:
            resp = client.post(url, json=payload, timeout=300.0)
            print(f"状态码: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"成功! image_url: {data.get('image_url')}")
                print(f"使用的prompt: {data.get('prompt_used')[:100]}...")
                return True
            else:
                print(f"错误: {resp.text}")
                return False
    except Exception as e:
        print(f"请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_text_to_image()
    sys.exit(0 if success else 1)
