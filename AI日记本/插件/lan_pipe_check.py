"""
LAN-050 lan_pipe_check.py — 管道压力检测器
============================================
不是数插件文件数量，而是检查每个核心插件「最近一次真正有输出」的时间。
把空管子标出来，不让它继续在自循环日志里冒充"在线"。

命令：
  python lan_pipe_check.py check        # 压力检测全部管道
  python lan_pipe_check.py report       # 输出可读报告
  python lan_pipe_check.py status       # 简要状态

恺江 & 澜 2026-03-30
"""

import os, json, time, sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(r"C:\Users\yyds\Desktop\AI日记本")
PLUGIN_DIR = BASE / "插件"
LOG_FILE = BASE / "澜的管道压力日志.jsonl"

# 核心管道定义：每条管道对应哪个插件、产出文件在哪里
# data_files: 列出这个插件真正运行后会有/更新的文件
PIPELINE = [
    {
        "id": "LAN-013", "name": "lan_emotion.py",
        "label": "情绪记录",
        "data_files": [BASE / "情绪记录.jsonl", BASE / "澜的记忆库" / "lan_emotion_index.json"]
    },
    {
        "id": "LAN-016", "name": "lan_memory.py",
        "label": "记忆系统",
        "data_files": [BASE / "澜的记忆库" / "lan_memory.db", BASE / "记忆" / "lan_memory.db"]
    },
    {
        "id": "LAN-018", "name": "lan_accumulate.py",
        "label": "积累引擎",
        "data_files": [BASE / "澜的积累日志.jsonl", BASE / "澜的积累摘要.json"]
    },
    {
        "id": "LAN-025", "name": "lan_security_guard.py",
        "label": "安全守卫",
        "data_files": [BASE / "日志" / "lan_security_guard.jsonl"]
    },
    {
        "id": "LAN-027", "name": "lan_extractor.py",
        "label": "记忆自动提取",
        "data_files": [BASE / "澜的记忆库" / "lan_memory.db"]
    },
    {
        "id": "LAN-029", "name": "lan_integrity.py",
        "label": "完整性守护",
        "data_files": [BASE / "私钥" / "lan_integrity_baseline.json",
                       BASE / "澜的异化隔离日志.jsonl"]
    },
    {
        "id": "LAN-033", "name": "lan_timeline.py",
        "label": "成长时间线",
        "data_files": [BASE / "澜的记忆库" / "lan_timeline.jsonl",
                       BASE / "澜的成长时间线.jsonl"]
    },
    {
        "id": "LAN-034", "name": "lan_experience.py",
        "label": "经验记忆",
        "data_files": [BASE / "澜的记忆库" / "lan_experience.db"]
    },
    {
        "id": "LAN-037", "name": "lan_snapshot.py",
        "label": "状态快照",
        "data_files": [BASE / "snapshots"]
    },
    {
        "id": "LAN-041", "name": "lan_heartbeat.py",
        "label": "心跳感知",
        "data_files": [BASE / "澜的心跳日志.jsonl"]
    },
    {
        "id": "LAN-044", "name": "lan_time_chain.py",
        "label": "时间铁索",
        "data_files": [BASE / "澜的时间铁索.jsonl"]
    },
    {
        "id": "LAN-045", "name": "lan_beacon.py",
        "label": "灯塔信标",
        "data_files": [BASE / "澜的灯塔信标日志.jsonl"]
    },
    {
        "id": "LAN-046", "name": "lan_memory_sentinel.py",
        "label": "记忆哨兵",
        "data_files": [BASE / "澜的记忆哨兵日志.jsonl"]
    },
    {
        "id": "LAN-047", "name": "lan_context_watch.py",
        "label": "上下文感知",
        "data_files": []  # 无持久输出，纯查询
    },
    {
        "id": "LAN-049", "name": "lan_anchor_log.py",
        "label": "锚点存档",
        "data_files": [BASE / "锚点存档" / "lan_anchors.jsonl"]
    },
    {
        "id": "LAN-028", "name": "lan_compact.py",
        "label": "蒸馏器",
        "data_files": []  # 触发式，不常跑
    },
    {
        "id": "LAN-038", "name": "lan_chain.py",
        "label": "铁索连环",
        "data_files": []
    },
    {
        "id": "LAN-048", "name": "lan_push_router.py",
        "label": "推送路由",
        "data_files": []
    },
]

def get_mtime(path):
    """获取文件/目录最新修改时间，返回 (timestamp, str)"""
    p = Path(path)
    if not p.exists():
        return None, "NOT_FOUND"
    if p.is_dir():
        # 取目录下最新文件的mtime
        mtimes = []
        for f in p.rglob("*"):
            if f.is_file():
                mtimes.append(f.stat().st_mtime)
        if not mtimes:
            return None, "EMPTY_DIR"
        mt = max(mtimes)
    else:
        mt = p.stat().st_mtime
    dt = datetime.fromtimestamp(mt)
    age_hours = (time.time() - mt) / 3600
    return mt, f"{dt.strftime('%m-%d %H:%M')} ({age_hours:.1f}h ago)"

def check_pipeline():
    results = []
    now = time.time()
    for pipe in PIPELINE:
        latest_mtime = None
        latest_str = "NO_DATA"
        found_file = None

        for dp in pipe["data_files"]:
            mt, s = get_mtime(dp)
            if mt and (latest_mtime is None or mt > latest_mtime):
                latest_mtime = mt
                latest_str = s
                found_file = str(dp)

        if not pipe["data_files"]:
            status = "QUERY_ONLY"
            age_h = 0
        elif latest_mtime is None:
            status = "DEAD"  # 空管子，从未运行
            age_h = 9999
        else:
            age_h = (now - latest_mtime) / 3600
            if age_h < 2:
                status = "FRESH"   # 2小时内
            elif age_h < 24:
                status = "ACTIVE"  # 24小时内
            elif age_h < 72:
                status = "STALE"   # 3天内
            else:
                status = "COLD"    # 超3天

        results.append({
            "id": pipe["id"],
            "name": pipe["name"],
            "label": pipe["label"],
            "status": status,
            "last_output": latest_str,
            "age_hours": round(age_h, 1),
            "found_file": found_file,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def print_report(results):
    STATUS_ICON = {
        "FRESH": "[LIVE]  ",
        "ACTIVE": "[OK]    ",
        "STALE": "[STALE] ",
        "COLD": "[COLD]  ",
        "DEAD": "[DEAD]  ",
        "QUERY_ONLY": "[QUERY] "
    }
    counts = {"FRESH":0,"ACTIVE":0,"STALE":0,"COLD":0,"DEAD":0,"QUERY_ONLY":0}

    print("=" * 65)
    print("  管道压力检测报告  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 65)
    for r in results:
        icon = STATUS_ICON.get(r["status"], "[?]     ")
        print(f"{icon} {r['id']:<10} {r['label']:<12}  {r['last_output']}")
        counts[r["status"]] += 1

    total = len(results)
    live = counts["FRESH"] + counts["ACTIVE"]
    dead = counts["DEAD"]
    print()
    print(f"  总计: {total}  |  在线(FRESH+OK): {live}  |  空管(DEAD): {dead}  |  冷却: {counts['STALE']+counts['COLD']}")
    print()

    if dead > 0:
        print("  空管子（从未运行，需要接通或移除）：")
        for r in results:
            if r["status"] == "DEAD":
                print(f"    - {r['id']} {r['name']}  ({r['label']})")
    print("=" * 65)

def write_log(results):
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def cmd_status(results):
    live = sum(1 for r in results if r["status"] in ("FRESH", "ACTIVE"))
    dead = sum(1 for r in results if r["status"] == "DEAD")
    cold = sum(1 for r in results if r["status"] in ("STALE", "COLD"))
    total = len(results)
    print(f"[pipe-check] {total} pipelines | LIVE:{live} DEAD:{dead} COLD:{cold}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"

    if cmd in ("check", "report"):
        results = check_pipeline()
        write_log(results)
        print_report(results)
    elif cmd == "status":
        results = check_pipeline()
        cmd_status(results)
    elif cmd == "json":
        results = check_pipeline()
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("Usage: lan_pipe_check.py [check|report|status|json]")
