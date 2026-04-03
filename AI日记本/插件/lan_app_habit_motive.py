# -*- coding: utf-8 -*-
"""
lan_app_habit_motive.py — 澜的动机记录接口
给用户提供一个简单的方式，记录"为什么开这个软件"
"""

import os, sys, sqlite3, datetime, io

# 强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB_PATH = r"C:\Users\yyds\Desktop\AI日记本\lan_app_habit.db"

def add_motive(exe_name: str, motive: str):
    """为某次启动记录动机"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    today = datetime.date.today().strftime("%Y-%m-%d")

    # 查找今天最近一次启动（支持模糊匹配）
    c.execute("""
        SELECT id, exe_name FROM app_launches
        WHERE exe_name LIKE ? AND date=?
        ORDER BY ts DESC LIMIT 1
    """, (f"%{exe_name}%", today))

    row = c.fetchone()

    if row:
        launch_id = row[0]
        c.execute("""
            UPDATE app_launches SET motive=? WHERE id=?
        """, (motive, launch_id))
        print(f"✅ 已记录：{exe_name} 的动机是「{motive}」")
    else:
        print(f"⚠️ 今天没找到 {exe_name} 的启动记录")

    conn.commit()
    conn.close()

def get_recent_launches(limit=10):
    """获取最近启动的应用（用于聊天时智能询问）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT exe_name, ts, motive
        FROM app_launches
        ORDER BY ts DESC LIMIT ?
    """, (limit,))

    rows = c.fetchall()
    conn.close()

    return rows

def check_ask_threshold(exe_name: str, threshold: int = 5) -> dict:
    """
    检查是否达到询问阈值

    返回：
    {
        "should_ask": bool,  # 是否应该询问
        "count": int,        # 今天开了多少次
        "last_motive": str,  # 上次动机
        "last_time": str     # 上次时间
    }
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    today = datetime.date.today().strftime("%Y-%m-%d")

    # 查询今天启动次数
    c.execute("""
        SELECT COUNT(*) FROM app_launches
        WHERE exe_name LIKE ? AND date=?
    """, (f"%{exe_name}%", today))

    count = c.fetchone()[0]

    if count < threshold:
        conn.close()
        return {
            "should_ask": False,
            "count": count,
            "last_motive": None,
            "last_time": None
        }

    # 查询上次动机和时间
    c.execute("""
        SELECT motive, ts FROM app_launches
        WHERE exe_name LIKE ? AND motive != ''
        ORDER BY ts DESC LIMIT 1
    """, (f"%{exe_name}%",))

    row = c.fetchone()
    conn.close()

    if row:
        last_motive, last_time = row
        return {
            "should_ask": True,
            "count": count,
            "last_motive": last_motive,
            "last_time": last_time
        }
    else:
        return {
            "should_ask": False,  # 没有动机记录，不问
            "count": count,
            "last_motive": None,
            "last_time": None
        }

def generate_ask_phrase(exe_name: str, last_motive: str, last_time: str) -> str:
    """
    生成询问文案（澜的感性表达）

    示例：
    - "你上次开 VSCode 是写澜的打包脚本，这次又开，是不是要继续？"
    - "你上次开 Steam 是玩游戏，今天 20:10 又开，又要放松一下？"
    """
    app_name = exe_name.split(".")[0].title()

    if last_motive and last_time:
        last_hour = last_time[11:16]
        return f"你上次开 {app_name} 是「{last_motive}」，今天 {last_hour} 又开，这次还是吗？"
    elif last_motive:
        return f"你上次开 {app_name} 是「{last_motive}」，这次又开，是不是继续？"
    else:
        return f"你今天开 {app_name} 已经不少次了，这次想做什么？"

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="澜的动机记录接口")
    parser.add_argument("--add", nargs=2, metavar=("EXE", "MOTIVE"), help="添加动机")
    parser.add_argument("--recent", type=int, default=10, help="查看最近启动")
    args = parser.parse_args()

    if args.add:
        exe, motive = args.add
        add_motive(exe, motive)
    elif args.recent:
        rows = get_recent_launches(args.recent)
        print("\n最近启动的应用：\n")
        for exe, ts, motive in rows:
            motive_text = motive or "未记录"
            print(f"  {ts} · {exe} → {motive_text}")
    else:
        parser.print_help()
