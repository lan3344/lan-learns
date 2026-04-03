#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
LAN-036-MOBILE · 澜·应用习惯记录器（手机端）
创建：2026-03-29

用法（Termux 里运行）：
  python lan_app_habit_mobile.py --log <应用名> <理由>
  python lan_app_habit_mobile.py --report
  python lan_app_habit_mobile.py --sync   # 推送到和电脑共用的 habit.json

也可以做成 Termux 快捷方式，在手机桌面一键触发。

Termux 获取当前前台应用的方式（需要 ROOT 或 adb 权限）：
  dumpsys activity | grep mCurrentFocus
可以配合 Tasker 或 AutoInput 实现自动触发。
"""

import os
import sys
import json
import sqlite3
import argparse
import datetime

# ─── 路径 ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.expanduser("~/storage/shared/AI日记本")
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.expanduser("~/lan_habit")

os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "lan_app_habit_mobile.db")
EXPORT_PATH = os.path.join(BASE_DIR, "habit_mobile.json")

# ─── 关键词打分（手机端不加载大模型，轻量规则）────────────────────────────────
def score_reason(reason: str) -> tuple[int, str]:
    r = reason.lower()

    high   = ["每天", "必须", "工作", "重要", "离不开", "核心", "必需", "天天", "主要"]
    medium = ["有时", "偶尔", "可能", "备用", "需要", "用来", "比较", "经常"]
    low    = ["不知道", "忘了", "随便", "没什么", "以防万一", "忘记", "不确定", "不知"]

    for kw in high:
        if kw in r:
            return 4, "包含高频使用关键词，看起来是重要应用"
    for kw in low:
        if kw in r:
            return 2, "理由比较模糊，可能可以清理"
    for kw in medium:
        if kw in r:
            return 3, "偶尔使用，中等优先级"
    if len(reason.strip()) < 5:
        return 1, "理由太短，说明不了这个应用的价值"
    return 3, "说明了用途，中等重要程度"


# ─── 数据库 ────────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_usage (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name     TEXT NOT NULL,
            platform     TEXT DEFAULT 'android',
            reason       TEXT,
            how_to_use   TEXT,
            importance   INTEGER DEFAULT 3,
            ai_comment   TEXT,
            opened_at    TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_record(app_name, reason, how_to_use, importance, ai_comment):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO app_usage (app_name, platform, reason, how_to_use, importance, ai_comment, opened_at)
        VALUES (?, 'android', ?, ?, ?, ?, ?)
    """, (app_name, reason, how_to_use, importance, ai_comment,
          datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()


# ─── 命令 ─────────────────────────────────────────────────────────────────────
def cmd_log_interactive():
    """交互式记录（无参数时进入）"""
    print("澜·应用习惯记录（手机端）")
    print("-" * 30)

    app_name = input("打开了哪个应用？> ").strip()
    if not app_name:
        print("已取消")
        return

    reason = input(f"今天打开 {app_name} 是为了什么？> ").strip()
    if not reason:
        print("已取消")
        return

    how = input("打算怎么用（可选，直接回车跳过）？> ").strip()

    importance, comment = score_reason(reason + " " + how)
    save_record(app_name, reason, how, importance, comment)

    stars = "★" * importance + "☆" * (5 - importance)
    print(f"\n已记录: {app_name}")
    print(f"重要程度: [{stars}] {importance}/5")
    print(f"澜的判断: {comment}")


def cmd_log_quick(args):
    """快速记录：--log <应用名> <理由> [用法]"""
    app = args[0] if len(args) > 0 else "unknown"
    reason = args[1] if len(args) > 1 else ""
    how = args[2] if len(args) > 2 else ""

    importance, comment = score_reason(reason + " " + how)
    save_record(app, reason, how, importance, comment)

    stars = "★" * importance + "☆" * (5 - importance)
    print(f"已记录: {app} [{stars}] {importance}/5 — {comment}")


def cmd_report():
    """查看习惯报告"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT app_name, COUNT(*) as cnt,
               AVG(importance) as avg_imp,
               MAX(opened_at) as last_opened
        FROM app_usage
        GROUP BY app_name
        ORDER BY avg_imp DESC, cnt DESC
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("暂无记录。运行脚本记录几条先。")
        return

    print("\n📊 手机端应用习惯报告")
    print("-" * 50)
    print(f"{'应用名':<20} {'次数':>5} {'重要程度':>10} {'最近打开'}")
    print("-" * 50)
    for row in rows:
        name, cnt, avg_imp, last = row
        stars = "★" * round(avg_imp) + "☆" * (5 - round(avg_imp))
        last_d = last[:10] if last else "未知"
        print(f"  {name:<18} {cnt:>5}次  [{stars}]  {last_d}")


def cmd_sync():
    """导出 JSON，方便同步到 GitHub"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM app_usage ORDER BY opened_at DESC")
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    conn.close()

    data = [dict(zip(cols, r)) for r in rows]
    with open(EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.datetime.now().isoformat(),
            "platform": "android",
            "total_records": len(data),
            "records": data
        }, f, ensure_ascii=False, indent=2)

    print(f"已导出 {len(data)} 条记录到: {EXPORT_PATH}")
    print("可用 Termux 的 git 或 scp 推送到 GitHub")


# ─── 主入口 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()

    parser = argparse.ArgumentParser(description="澜·应用习惯记录器（手机端）")
    parser.add_argument("--log",    nargs="*", help="快速记录: --log <应用> <理由> [用法]")
    parser.add_argument("--report", action="store_true", help="查看报告")
    parser.add_argument("--sync",   action="store_true", help="导出 JSON 供同步")

    args = parser.parse_args()

    if args.log is not None:
        if args.log:
            cmd_log_quick(args.log)
        else:
            cmd_log_interactive()
    elif args.report:
        cmd_report()
    elif args.sync:
        cmd_sync()
    else:
        # 无参数：交互模式
        cmd_log_interactive()
