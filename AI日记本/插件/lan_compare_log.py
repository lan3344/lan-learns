# -*- coding: utf-8 -*-
"""
LAN-053 · 对比日志系统
见不贤而内自省，见贤则思齐。
记录澜的日志 vs 他人项目的对比，吸取精华，避开坑。

功能：
  1. log() - 记录对比观察
  2. query() - 查询特定主题的对比记录
  3. summary() - 输出对比总结（哪些抄了、哪些避开了）

日志格式：AI日记本/澜的对比日志.jsonl

用法：
  python lan_compare_log.py log <source> <subject> <findings> <action>
  python lan_compare_log.py query <keyword>
  python lan_compare_log.py summary

示例：
  python lan_compare_log.py log "OpenClaw" "日志格式" "JSONL带timestamp，易排序" "已采用"
  python lan_compare_log.py query "日志"
  python lan_compare_log.py summary
"""

import os
import json
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG_FILE = r"C:\Users\yyds\Desktop\AI日记本\澜的对比日志.jsonl"


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(source, subject, findings, action):
    """
    记录一次对比观察

    参数:
      source   - 来源项目/系统（如 "OpenClaw", "GitHub Issue 1234", "某博客"）
      subject  - 对比主题（如 "日志格式", "错误处理", "内存管理"）
      findings - 发现的内容（对方怎么做、效果如何）
      action   - 澜的行动（已采用/计划采用/避坑/仅记录）
    """
    entry = {
        "time": now_str(),
        "source": source,
        "subject": subject,
        "findings": findings,
        "action": action,
    }
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[对比日志] 已记录：{source} - {subject} - {action}")


def query(keyword, limit=10):
    """
    查询特定主题的对比记录
    """
    if not os.path.exists(LOG_FILE):
        print("  （尚无对比日志）")
        return

    results = []
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if keyword.lower() in str(entry).lower():
                    results.append(entry)
            except Exception:
                pass

    if not results:
        print(f"  未找到包含 '{keyword}' 的记录")
        return

    print(f"\n[对比日志] 关键词: {keyword}（找到 {len(results)} 条，显示最近 {min(limit, len(results))} 条）")
    print("=" * 70)
    for e in results[-limit:]:
        icon_map = {
            "已采用": "✅",
            "计划采用": "📋",
            "避坑": "⚠️",
            "仅记录": "📝"
        }
        icon = icon_map.get(e["action"], "•")
        print(f"\n  {icon} {e['time']}")
        print(f"     来源: {e['source']}")
        print(f"     主题: {e['subject']}")
        print(f"     发现: {e['findings'][:100]}...")
        print(f"     行动: {e['action']}")


def summary(days=30):
    """
    输出对比总结
    """
    if not os.path.exists(LOG_FILE):
        print("  （尚无对比日志）")
        return

    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    entries = []
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
                entry_time = datetime.datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                if entry_time >= cutoff:
                    entries.append(entry)
            except Exception:
                pass

    if not entries:
        print(f"  最近 {days} 天无对比记录")
        return

    # 统计
    by_action = {}
    by_source = {}
    for e in entries:
        by_action[e["action"]] = by_action.get(e["action"], 0) + 1
        by_source[e["source"]] = by_source.get(e["source"], 0) + 1

    print(f"\n[对比日志] 最近 {days} 天总结")
    print("=" * 70)
    print(f"  总记录数: {len(entries)}")
    print(f"\n  按行动分类:")
    for action, count in sorted(by_action.items(), key=lambda x: -x[1]):
        print(f"    {action}: {count} 次")
    print(f"\n  按来源分类:")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1])[:10]:
        print(f"    {source}: {count} 次")

    # 亮点提取
    adopted = [e for e in entries if e["action"] == "已采用"]
    avoided = [e for e in entries if e["action"] == "避坑"]

    if adopted:
        print(f"\n  已采纳精华（最近 5 条）:")
        for e in adopted[-5:]:
            print(f"    • {e['source']} - {e['subject']}")

    if avoided:
        print(f"\n  已避开坑（最近 5 条）:")
        for e in avoided[-5:]:
            print(f"    • {e['source']} - {e['subject']}")


# ── CLI ─────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "log" and len(sys.argv) >= 5:
        # python lan_compare_log.py log <source> <subject> <findings> <action>
        source = sys.argv[2]
        subject = sys.argv[3]
        findings = sys.argv[4]
        action = sys.argv[5] if len(sys.argv) > 5 else "仅记录"
        log(source, subject, findings, action)

    elif cmd == "query" and len(sys.argv) > 2:
        query(sys.argv[2])

    elif cmd == "summary":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        summary(days)

    else:
        print("用法:")
        print("  python lan_compare_log.py log <source> <subject> <findings> <action>")
        print("  python lan_compare_log.py query <keyword>")
        print("  python lan_compare_log.py summary [days]")
        print("\n示例:")
        print("  python lan_compare_log.py log 'OpenClaw' '日志格式' 'JSONL带timestamp' '已采用'")
        print("  python lan_compare_log.py query '日志'")
        print("  python lan_compare_log.py summary 30")
