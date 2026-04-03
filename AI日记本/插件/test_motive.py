import sys
import sys

# 强制 UTF-8 输出，避免 Emoji 编码错误
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r'C:\Users\yyds\Desktop\AI日记本\插件')
from lan_app_habit_motive import check_ask_threshold, generate_ask_phrase

result = check_ask_threshold('ima.copilot', 5)
print(f'结果: {result}')
print(f'文案: {generate_ask_phrase("ima.copilot", result["last_motive"], result["last_time"])}')
