# -*- coding: utf-8 -*-
"""测试健康判断层"""
import sys, os
sys.path.insert(0, r'C:\Users\yyds\Desktop\AI日记本\插件')
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

import warnings
warnings.filterwarnings('ignore')

from lan_app_habit import ai_health_check, ai_score_reason

cases = [
    ("浏览器",    "最近有点冲动，想去打打飞机，生理需求"),
    ("抖音",      "无聊，刷刷视频，打发时间"),
    ("BeamNG",    "玩玩赛车，休息一下，玩半小时"),
    ("DevEco",    "开发鸿蒙应用，这是我的主要工作项目"),
    ("FL Studio", "今天要做一首新歌，创作用"),
    ("某游戏",    "不知道为什么，就是想点开，停不下来那种感觉"),
    ("微信",      "和朋友聊天，看看有没有消息"),
]

print("=" * 70)
print("健康判断层测试")
print("=" * 70)

for app, reason in cases:
    importance, ai_comment = ai_score_reason(reason)
    health = ai_health_check(reason, app)

    stars = "★" * importance + "☆" * (5 - importance)
    limit = health["time_limit"]
    force = "强制关" if health["force_close"] else ("建议限时" if limit > 0 else "不限时")

    print(f"\n📱 {app}")
    print(f"   你说：{reason[:40]}")
    print(f"   重要程度：{stars} {importance}/5")
    print(f"   健康标签：【{health['risk_label']}】")
    print(f"   限时：{limit}分钟 / {force}")
    print(f"   AI说：{health['ai_advice'][:60]}")
    if health["your_words"]:
        yw = health['your_words']
        print(f"   关闭时会说：你自己说了\"{yw}\"……")

print("\n" + "=" * 70)
