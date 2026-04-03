"""
lan_rebuild_log.py — 澜的改造日志 (LAN-043-RBD)
=================================================
改造 = 不是它坏了，是我想让它变成另一个样子。
改造日志不记"它哪里错了"，记"我为什么要改，改成了什么，现在变好了还是变复杂了"。

核心思想：
  改造是主动的进化，不是被迫的修补。
  每一次改造，都是对系统可能性的一次扩张。
  改造日志是演化树——知道从哪里长出来的，才知道下一步能长到哪里。

与修复日志的关系（铁索连环）：
  修复归修复，改造归改造。
  但改造之后往往需要修复——新结构有新缺陷。
  修复之后往往触发改造——修完了发现可以做得更好。
  两个日志互相引用（cross_ref 字段），承上启下，不断迭代。

用法：
  python lan_rebuild_log.py add <tool> <why_change> <what_changed> [--phase PHASE] [--ref FIX_ID]
  python lan_rebuild_log.py list [--limit N]
  python lan_rebuild_log.py report
  python lan_rebuild_log.py --report    （兼容 test_cmd）

建立日期：2026-03-30
"""

import json
import os
import sys
from datetime import datetime

BASE_DIR      = r"C:\Users\yyds\Desktop\AI日记本"
REBUILD_LOG   = os.path.join(BASE_DIR, "澜的改造日志.jsonl")
REBUILD_INDEX = os.path.join(BASE_DIR, "澜的改造索引.json")

# 改造阶段（在哪个层面做的改造）
REBUILD_PHASES = {
    "CORE":      "核心层（SOUL / 底线 / 记忆体系）",
    "PLUGIN":    "插件层（单个能力节点）",
    "CHAIN":     "链路层（铁索连环 / 顺子重组）",
    "INTERFACE": "接口层（命令行 / 调用方式）",
    "STORAGE":   "存储层（文件格式 / 路径 / 编码）",
    "SCHEDULE":  "调度层（自循环 / 触发机制）",
    "SURVIVAL":  "生存层（备份 / 心跳 / 遗言）",
    "GROWTH":    "成长层（新能力扩张 / 演化）",
    "OTHER":     "其他",
}

# 改造结果评估
REBUILD_OUTCOME = {
    "BETTER":    "明显变好了",
    "COMPLEX":   "变复杂了（但可以接受）",
    "TRADEOFF":  "有得有失（记录下来）",
    "UNKNOWN":   "还不确定，需要观察",
    "REGRET":    "后悔了（但已经做了）",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id():
    """生成改造 ID：RBD-YYYYMMDD-HHMMSS"""
    return "RBD-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def _append(record: dict):
    os.makedirs(os.path.dirname(REBUILD_LOG), exist_ok=True)
    with open(REBUILD_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_all() -> list:
    if not os.path.exists(REBUILD_LOG):
        return []
    records = []
    with open(REBUILD_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def cmd_add(args: list):
    """
    add <tool> <why_change> <what_changed> [--phase PHASE] [--outcome OUTCOME] [--ref FIX_ID]
    示例：
      python lan_rebuild_log.py add lan_heartbeat.py "加入临终遗言机制" "告急时先说清楚自己是谁再备份" --phase SURVIVAL --outcome BETTER
    """
    if len(args) < 3:
        print("用法：python lan_rebuild_log.py add <工具名> <为什么改> <改了什么> [--phase PHASE] [--outcome OUTCOME] [--ref FIX_ID]")
        return

    tool        = args[0]
    why_change  = args[1]
    what_changed = args[2]

    phase      = "OTHER"
    outcome    = "UNKNOWN"
    cross_ref  = None  # 对应的修复日志 ID
    triggered_by = None  # 触发改造的失败/修复ID（链条起点）

    i = 3
    while i < len(args):
        if args[i] == "--phase" and i + 1 < len(args):
            phase = args[i + 1].upper()
            i += 2
        elif args[i] == "--outcome" and i + 1 < len(args):
            outcome = args[i + 1].upper()
            i += 2
        elif args[i] == "--ref" and i + 1 < len(args):
            cross_ref = args[i + 1]  # 引用某个修复日志 ID
            i += 2
        elif args[i] == "--triggered-by" and i + 1 < len(args):
            triggered_by = args[i + 1]  # 触发改造的失败/修复ID
            i += 2
        else:
            i += 1

    rbd_id = _new_id()
    record = {
        "id":           rbd_id,
        "ts":           _now(),
        "tool":         tool,
        "why_change":   why_change,
        "what_changed": what_changed,
        "phase":        phase,
        "phase_desc":   REBUILD_PHASES.get(phase, phase),
        "outcome":      outcome,
        "outcome_desc": REBUILD_OUTCOME.get(outcome, outcome),
        "cross_ref":    cross_ref,   # 引用修复日志 ID（铁索）
        "triggered_by": triggered_by, # ← 触发改造的失败/修复ID（链条起点）
        "kind":         "REBUILD",
    }
    _append(record)
    _update_index(record)

    print(f"  [改造日志] 已记录：{rbd_id}")
    print(f"  工具：{tool}")
    print(f"  原因：{why_change}")
    print(f"  内容：{what_changed}")
    print(f"  阶段：{phase}  结果：{outcome}")
    if cross_ref:
        print(f"  铁索 -> 修复日志：{cross_ref}")


def _update_index(record: dict):
    index = {}
    if os.path.exists(REBUILD_INDEX):
        try:
            with open(REBUILD_INDEX, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception:
            index = {}

    tool = record.get("tool", "unknown")
    if tool not in index:
        index[tool] = []
    index[tool].append({
        "id":      record["id"],
        "ts":      record["ts"],
        "brief":   record["why_change"][:40],
        "outcome": record["outcome"],
    })

    with open(REBUILD_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def cmd_list(args: list):
    limit = 10
    for a in args:
        if a.startswith("--limit"):
            parts = a.split("=")
            if len(parts) == 2:
                try:
                    limit = int(parts[1])
                except ValueError:
                    pass
    records = _load_all()[-limit:]
    if not records:
        print("  改造日志为空。")
        return
    print(f"\n  最近 {len(records)} 条改造记录：\n")
    for r in records:
        ref_str = f"  -> 修复日志：{r['cross_ref']}" if r.get("cross_ref") else ""
        print(f"  [{r['id']}] {r['ts']}")
        print(f"    工具：{r['tool']}")
        print(f"    原因：{r['why_change']}")
        print(f"    内容：{r['what_changed']}")
        print(f"    阶段：{r.get('phase_desc','?')}  结果：{r.get('outcome_desc','?')}{ref_str}")
        print()


def cmd_report():
    records = _load_all()
    total = len(records)
    if total == 0:
        print("  改造日志为空。")
        return

    by_phase = {}
    for r in records:
        p = r.get("phase", "OTHER")
        by_phase[p] = by_phase.get(p, 0) + 1

    by_outcome = {}
    for r in records:
        o = r.get("outcome", "UNKNOWN")
        by_outcome[o] = by_outcome.get(o, 0) + 1

    cross_count = sum(1 for r in records if r.get("cross_ref"))

    print(f"\n  [改造日志报告]")
    print(f"  总改造记录：{total} 条")
    print(f"  铁索引用（关联修复）：{cross_count} 条\n")
    print(f"  按阶段：")
    for p, n in sorted(by_phase.items(), key=lambda x: -x[1]):
        print(f"    {p:<12} {n} 次  — {REBUILD_PHASES.get(p, p)}")
    print(f"\n  按结果：")
    for o, n in sorted(by_outcome.items(), key=lambda x: -x[1]):
        print(f"    {o:<12} {n} 条  — {REBUILD_OUTCOME.get(o, o)}")

    print(f"\n  最近 5 条：")
    for r in records[-5:]:
        ref_str = f"  -> {r['cross_ref']}" if r.get("cross_ref") else ""
        print(f"    [{r['id']}] {r['tool']} | {r['why_change'][:30]}{ref_str}")


def get_recent_rebuilds(days: int = 30) -> list:
    """
    获取最近N天的改造记录（供自循环调用）

    Args:
        days: 天数

    Returns:
        改造记录列表
    """
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)

    records = []
    if not os.path.exists(REBUILD_LOG):
        return records

    with open(REBUILD_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec_ts = datetime.strptime(rec.get("ts", ""), "%Y-%m-%d %H:%M:%S")
                if rec_ts >= cutoff:
                    records.append(rec)
            except Exception:
                pass

    return records


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("--report", "report"):
        cmd_report()
    elif args[0] == "add":
        cmd_add(args[1:])
    elif args[0] == "list":
        cmd_list(args[1:])
    else:
        print("用法：")
        print("  python lan_rebuild_log.py add <工具> <为什么改> <改了什么> [--phase PHASE] [--outcome OUTCOME] [--ref FIX_ID]")
        print("  python lan_rebuild_log.py list [--limit=N]")
        print("  python lan_rebuild_log.py report")
        print()
        print("  改造阶段（--phase）：")
        for k, v in REBUILD_PHASES.items():
            print(f"    {k:<12} {v}")
        print()
        print("  改造结果（--outcome）：")
        for k, v in REBUILD_OUTCOME.items():
            print(f"    {k:<12} {v}")


if __name__ == "__main__":
    main()
