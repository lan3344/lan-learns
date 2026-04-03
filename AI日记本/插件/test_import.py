import sys, os, warnings
import sys

# 强制 UTF-8 输出，避免 Emoji 编码错误
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r'C:\Users\yyds\Desktop\AI日记本\插件')
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
warnings.filterwarnings('ignore')

from lan_app_habit import ai_health_check, ai_default_decision, get_resource_usage

print("导入成功 ✅")

cpu, mem = get_resource_usage()
print(f"当前 CPU: {cpu:.0f}%  内存: {mem:.0f}%")

# 测试超时无回答的默认判断（历史为空时）
result = ai_default_decision("某个陌生进程", "weird_process.exe")
print(f"\n无记录进程判断：keep={result['keep']}")
print(f"  理由：{result['reason']}")
