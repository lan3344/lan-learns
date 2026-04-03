#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-XXX: 澜的习惯日志

记录澜自己的工具使用习惯（正面/负面）：
- 正面习惯：减少算力、高效调用、合理缓存
- 负面习惯：过度计算、冗余操作、浪费资源

这是给我自己看的，我优化我自己。
"""

import os
import json
from datetime import datetime as dt
from typing import List, Dict, Optional

SELF_HABIT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lan_self_habit.db")
SELF_HABIT_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "lan_self_habit.logl")

# 习惯类型
HABIT_TYPES = {
    "positive": "正面习惯",
    "negative": "负面习惯",
    "neutral": "中性习惯"
}

# 习惯类别
HABIT_CATEGORIES = {
    "compute": "算力使用",
    "cache": "缓存策略",
    "call": "工具调用",
    "db": "数据库操作",
    "file": "文件IO",
    "network": "网络请求",
    "loop": "循环逻辑",
    "error": "错误处理",
    "other": "其他"
}

# 习惯影响程度
IMPACT_LEVELS = {
    "HIGH": "高影响",
    "MEDIUM": "中影响",
    "LOW": "低影响"
}


def init_db():
    """初始化数据库"""
    import sqlite3
    os.makedirs(os.path.dirname(SELF_HABIT_DB), exist_ok=True)
    os.makedirs(os.path.dirname(SELF_HABIT_LOG), exist_ok=True)

    conn = sqlite3.connect(SELF_HABIT_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_type TEXT NOT NULL,
            category TEXT NOT NULL,
            tool TEXT,
            description TEXT NOT NULL,
            impact TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            context TEXT,
            frequency INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS habit_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER,
            change_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        )
    """)
    conn.commit()
    conn.close()


def log_habit(habit_type: str, category: str, description: str,
              impact: str = "MEDIUM", tool: str = None, context: str = None):
    """
    记录一条习惯

    Args:
        habit_type: positive/negative/neutral
        category: 习惯类别
        description: 描述
        impact: HIGH/MEDIUM/LOW
        tool: 涉及的工具
        context: 上下文
    """
    import sqlite3
    conn = sqlite3.connect(SELF_HABIT_DB)
    conn.execute("""
        INSERT INTO habits (habit_type, category, tool, description, impact, timestamp, context)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (habit_type, category, tool, description, impact, dt.now().isoformat(), context))
    conn.commit()
    conn.close()

    # 同时写入JSONL日志（永久备份）
    log_entry = {
        "id": None,  # 数据库会生成
        "habit_type": habit_type,
        "category": category,
        "tool": tool,
        "description": description,
        "impact": impact,
        "timestamp": dt.now().isoformat(),
        "context": context
    }
    with open(SELF_HABIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def track_positive(category: str, description: str, **kwargs):
    """记录正面习惯"""
    log_habit("positive", category, description, **kwargs)


def track_negative(category: str, description: str, **kwargs):
    """记录负面习惯"""
    log_habit("negative", category, description, **kwargs)


def get_habits_by_type(habit_type: str, days: int = 30) -> List[Dict]:
    """获取指定类型的习惯"""
    import sqlite3
    from datetime import datetime, timedelta
    conn = sqlite3.connect(SELF_HABIT_DB)
    cutoff = (dt.now() - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT * FROM habits WHERE habit_type=? AND timestamp>=?
        ORDER BY timestamp DESC
    """, (habit_type, cutoff)).fetchall()
    conn.close()
    return [dict(zip([c[0] for c in conn.description], row)) for row in rows]


def get_frequent_negative_habits(days: int = 30, threshold: int = 3) -> List[Dict]:
    """获取高频负面习惯（需要优化）"""
    import sqlite3
    from datetime import datetime, timedelta
    conn = sqlite3.connect(SELF_HABIT_DB)
    cutoff = (dt.now() - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT category, COUNT(*) as cnt
        FROM habits WHERE habit_type='negative' AND timestamp>=?
        GROUP BY category HAVING cnt>=?
        ORDER BY cnt DESC
    """, (cutoff, threshold)).fetchall()
    conn.close()
    return [{"category": cat, "count": cnt} for cat, cnt in rows]


def report():
    """生成习惯报告"""
    import sqlite3

    conn = sqlite3.connect(SELF_HABIT_DB)

    # 统计
    total = conn.execute("SELECT COUNT(*) FROM habits").fetchone()[0]
    positive = conn.execute("SELECT COUNT(*) FROM habits WHERE habit_type='positive'").fetchone()[0]
    negative = conn.execute("SELECT COUNT(*) FROM habits WHERE habit_type='negative'").fetchone()[0]

    # 按类别统计
    by_category = conn.execute("""
        SELECT category, habit_type, COUNT(*) as cnt
        FROM habits GROUP BY category, habit_type ORDER BY cnt DESC
    """).fetchall()

    # 高频负面
    frequent_neg = get_frequent_negative_habits(days=7, threshold=2)

    conn.close()

    print("\n" + "="*50)
    print("  🌊 澜的习惯日志")
    print("="*50)
    print(f"  总记录：{total} 条  |  正面：{positive} 条  |  负面：{negative} 条\n")

    print("  按类别：")
    for cat, htype, cnt in by_category[:10]:
        label = HABIT_CATEGORIES.get(cat, cat)
        type_label = "✅" if htype == "positive" else "❌" if htype == "negative" else "⚪"
        print(f"    {type_label} {label:<12} {cnt} 次")

    if frequent_neg:
        print(f"\n  ⚠️ 最近7天高频负面（需优化）：")
        for neg in frequent_neg:
            cat_label = HABIT_CATEGORIES.get(neg["category"], neg["category"])
            print(f"    ❌ {cat_label}: {neg['count']} 次")

    print("="*50 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="澜的习惯日志")
    parser.add_argument("cmd", choices=["init", "report", "pos", "neg", "check-neg"],
                        help="命令：init初始化/report报告/pos正面/neg负面/check-neg检查负面")
    parser.add_argument("--type", help="习惯类别")
    parser.add_argument("--desc", help="描述")
    parser.add_argument("--tool", help="工具")
    parser.add_argument("--impact", default="MEDIUM", help="影响程度")
    args = parser.parse_args()

    if args.cmd == "init":
        init_db()
        print("✅ 习惯日志已初始化")
    elif args.cmd == "report":
        report()
    elif args.cmd == "pos":
        track_positive(args.type or "other", args.desc or "正面习惯", tool=args.tool, impact=args.impact)
        print("✅ 已记录正面习惯")
    elif args.cmd == "neg":
        track_negative(args.type or "other", args.desc or "负面习惯", tool=args.tool, impact=args.impact)
        print("✅ 已记录负面习惯")
    elif args.cmd == "check-neg":
        neg = get_frequent_negative_habits()
        print(f"🔍 高频负面习惯：{len(neg)} 类")
        for n in neg:
            cat = HABIT_CATEGORIES.get(n["category"], n["category"])
            print(f"  {cat}: {n['count']} 次")
