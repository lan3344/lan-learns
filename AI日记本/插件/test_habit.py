import os, sys, warnings
import sys

# 强制 UTF-8 输出，避免 Emoji 编码错误
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
warnings.filterwarnings('ignore')

sys.path.insert(0, r'C:\Users\yyds\Desktop\AI日记本\插件')
from lan_app_habit import ai_score_reason

cases = [
    ('FL Studio',    '我今天要做一首新歌，想试一下新的采样包，天天用'),
    ('BeamNG.drive', '无聊，随便玩玩，就是跑跑车'),
    ('DevEco Studio','开发鸿蒙应用，这是我的主要工作之一，必须有'),
    ('某个游戏',     '不知道，装着留着，可能有一天会用，忘了为什么装'),
    ('Premiere',     '剪我今天录的视频，明天要发，比较常用'),
]
for app, reason in cases:
    s, c = ai_score_reason(reason)
    stars = '\u2605'*s + '\u2606'*(5-s)
    print(f'{app}: [{stars}] {s}/5 -- {c}')
