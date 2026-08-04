"""快速测 ModelScope 文生图并输出 URL"""
import sys, time
sys.path.insert(0, '.')
from boss_aigc.execution.modelscope_adapter import ModelScopeAdapter
a = ModelScopeAdapter()
tid = a.submit({
    'product': '金项链',
    'image_type': 'main',
    'quantity': 1,
    'size': '1024x1024',
})
print('task_id:', tid)
# submit 是同步阻塞的，完成后直接 poll
for _ in range(30):
    status, arts = a.poll(tid)
    if status.value in ('delivered', 'failed', 'cancelled'):
        print('status:', status)
        if arts:
            for art in arts:
                print('URL:', art.url_or_path)
                print('starts with http:', art.url_or_path.startswith('http'))
        break
    time.sleep(2)
