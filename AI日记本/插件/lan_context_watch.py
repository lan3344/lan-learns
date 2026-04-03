# -*- coding: utf-8 -*-
"""
LAN-047 · 对话上下文长度感知器
防止"上下文爆炸"——对话越来越长、记忆混乱、模型开始遗忘早期内容。

感知逻辑：
  - 统计今日日记行数（越长 = 本次对话写入越多 = 上下文越重）
  - 统计今日日记字数（更准确的体量指标）
  - 检测日记里的"时间锚点"密度（锚点太少说明对话连续性差）
  - 输出四级状态：CALM / NORMAL / HEAVY / OVERFLOW

OVERFLOW 的含义：
  当日写入体量极大，说明本次对话已经很长了。
  此时建议：主动总结要点 → 写进记忆 → 开启新对话。

接入方式：
  自循环 step_state 里调用 get_context_state()
  或独立跑：python lan_context_watch.py check
"""

import os
import sys
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MEMORY_DIR = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"

# ─── 阈值（恺江调整：一半就预警，共同面对困难）───────────────────────────────
# 恺江说："我感觉我的记忆快到平顶的一半的时候呢，你就应该找我说明一下你的问题"
# 2026-03-30 17:11 调整：HEAVY 从 75% 改到 50%
THRESHOLDS = {
    # (行数, 字数) → 级别
    "CALM":     (0,    0),
    "NORMAL":   (80,   2400),
    "HEAVY":    (160,  4800),    # ← 一半就开始预警！
    "OVERFLOW": (320,  9600),
}

LEVEL_DESC = {
    "CALM":     "轻盈，上下文很短，继续",
    "NORMAL":   "正常，日记有一定体量",
    "HEAVY":    "偏重，建议适时总结写入记忆",
    "OVERFLOW": "溢出风险！建议：总结要点 → 写记忆 → 开新对话",
}

LEVEL_EMOJI = {
    "CALM": "🟢", "NORMAL": "🟡", "HEAVY": "🟠", "OVERFLOW": "🔴"
}


def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_daily_path(date_str=None):
    d = date_str or today_str()
    return os.path.join(MEMORY_DIR, f"{d}.md")


def count_file(path):
    """返回 (行数, 字数)，文件不存在返回 (0, 0)"""
    if not os.path.exists(path):
        return 0, 0
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    lines = content.count("\n")
    chars = len(content)
    return lines, chars


def count_anchors(path):
    """统计日记里 '## HH:MM' 时间锚点数量——越少说明本次对话写入越稀"""
    if not os.path.exists(path):
        return 0
    anchors = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("## ") and ":" in line:
                anchors += 1
    return anchors


def classify(lines, chars):
    level = "CALM"
    if lines >= THRESHOLDS["OVERFLOW"][0] or chars >= THRESHOLDS["OVERFLOW"][1]:
        level = "OVERFLOW"
    elif lines >= THRESHOLDS["HEAVY"][0] or chars >= THRESHOLDS["HEAVY"][1]:
        level = "HEAVY"
    elif lines >= THRESHOLDS["NORMAL"][0] or chars >= THRESHOLDS["NORMAL"][1]:
        level = "NORMAL"
    return level


def sense(date_str=None):
    """主感知函数，返回 dict"""
    path = get_daily_path(date_str)
    lines, chars = count_file(path)
    anchors = count_anchors(path)
    level = classify(lines, chars)

    anchor_density = round(anchors / max(lines, 1) * 100, 1)  # 每百行有几个锚点

    return {
        "date":           date_str or today_str(),
        "diary_path":     path,
        "exists":         os.path.exists(path),
        "lines":          lines,
        "chars":          chars,
        "anchors":        anchors,
        "anchor_density": anchor_density,
        "level":          level,
        "desc":           LEVEL_DESC[level],
    }


def get_context_state():
    """供自循环 step_state 调用，返回精简 dict"""
    r = sense()
    return {
        "context_level": r["level"],
        "diary_lines":   r["lines"],
        "diary_chars":   r["chars"],
        "anchors":       r["anchors"],
    }


def print_report(r):
    emoji = LEVEL_EMOJI[r["level"]]
    print(f"\n{emoji} [LAN-047] 上下文感知报告  {r['date']}")
    print(f"  日记路径  : {r['diary_path']}")
    print(f"  存在      : {'是' if r['exists'] else '否（今日尚未写入）'}")
    print(f"  行数      : {r['lines']}")
    print(f"  字数      : {r['chars']}")
    print(f"  时间锚点  : {r['anchors']} 个（每百行 {r['anchor_density']}）")
    print(f"  级别      : {r['level']}  —  {r['desc']}")

    if r["level"] == "OVERFLOW":
        print()
        print("  ⚠️  建议操作：")
        print("    1. 把本次对话的关键结论写入 MEMORY.md")
        print("    2. 在日记里打一个 [CHECKPOINT] 标记")
        print("    3. 开启新对话，从记忆文件重新醒来")
    elif r["level"] == "HEAVY":
        print()
        print("  📌 建议：把本轮重要决定/发现追加进今日日记，留锚点。")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        r = sense()
        print_report(r)

    elif cmd == "state":
        # 精简输出，供机器解析
        import json
        print(json.dumps(get_context_state(), ensure_ascii=False))

    elif cmd == "history":
        # 查最近7天的上下文体量趋势
        print("\n[LAN-047] 最近 7 天上下文体量趋势")
        print(f"  {'日期':<12} {'行数':>6} {'字数':>8} {'锚点':>6}  级别")
        print("  " + "-" * 50)
        base = datetime.datetime.now()
        for i in range(6, -1, -1):
            d = (base - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            r = sense(d)
            emoji = LEVEL_EMOJI[r["level"]]
            marker = " ← 今天" if i == 0 else ""
            print(f"  {d:<12} {r['lines']:>6} {r['chars']:>8} {r['anchors']:>6}  {emoji}{r['level']}{marker}")

    else:
        print(f"用法: python lan_context_watch.py [check|state|history]")
