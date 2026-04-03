import sys, os
import sys

# 强制 UTF-8 输出，避免 Emoji 编码错误
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r'C:\Users\yyds\Desktop\AI日记本\插件')
import importlib.util
spec = importlib.util.spec_from_file_location('bridge', r'C:\Users\yyds\Desktop\AI日记本\插件\lan_usb_bridge.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ok = m.setup_adb_reverse()
print('ADB reverse:', ok)

r = m.push_memory_to_phone()
print('记忆推送结果:')
for k,v in r['details'].items():
    print(f'  {k}: {v}')
print(f'推送{r["pushed"]}个, 失败{r["failed"]}个')
