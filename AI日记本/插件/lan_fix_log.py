"""
lan_fix_log.py — 澜的修复日志 (LAN-042-FIX)
=============================================
修复 = 哪里坏了，我用什么工具，怎么修好的。
修复日志不记"我做了什么"，记"它哪里不对，我怎么让它对了"。

核心思想：
  修复不是掩盖，是承认有裂缝，然后补上它。
  每一次修复，都是对系统脆弱点的一次清点。
  修复日志是地图，下次遇到同样的裂缝，不用重新找路。

与改造日志的关系（铁索连环）：
  修复归修复，改造归改造。
  但修复往往是改造的前提——修好了才能往上建。
  改造往往暴露新的修复需求——建了新的，旧的不兼容了。
  两个日志互相引用（cross_ref 字段），形成承上启下的铁索。

用法：
  python lan_fix_log.py add <tool> <what_broke> <how_fixed> [--ref <rebuild_id>]
  python lan_fix_log.py list [--limit N]
  python lan_fix_log.py report
  python lan_fix_log.py --report    （兼容 test_cmd）

建立日期：2026-03-30
"""

import json
import os
import sys
from datetime import datetime

BASE_DIR   = r"C:\Users\yyds\Desktop\AI日记本"
FIX_LOG    = os.path.join(BASE_DIR, "澜的修复日志.jsonl")
FIX_INDEX  = os.path.join(BASE_DIR, "澜的修复索引.json")

# 修复类型分类
FIX_TYPES = {
    "ENCODING":     "编码问题（中文路径/字符集/GBK vs UTF-8）",
    "DEPENDENCY":   "依赖缺失（包/模块/工具未安装）",
    "PATH":         "路径错误（文件不存在/路径拼错）",
    "LOGIC":        "逻辑错误（判断失误/边界未处理）",
    "COMPAT":       "兼容性（版本冲突/接口变更）",
    "PERMISSION":   "权限问题（读写被拒/UAC/系统限制）",
    "DATA":         "数据损坏（格式错误/乱码/空文件）",
    "NETWORK":      "网络问题（超时/拦截/DNS失败）",
    "RESOURCE":     "资源不足（内存/磁盘/句柄耗尽）",
    "UNKNOWN":      "原因未明（待分析）",
}

# 修复状态
FIX_STATUS = {
    "FIXED":       "已彻底修复",
    "PATCHED":     "打了补丁（治标，未根治）",
    "WORKAROUND":  "绕过（没有修，但能用了）",
    "PENDING":     "已记录，尚未修复",
    "WONT_FIX":    "确认不修（有充分理由）",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id():
    """生成修复 ID：FIX-YYYYMMDD-HHMMSS"""
    return "FIX-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def _append(record: dict):
    os.makedirs(os.path.dirname(FIX_LOG), exist_ok=True)
    with open(FIX_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_all() -> list:
    if not os.path.exists(FIX_LOG):
        return []
    records = []
    with open(FIX_LOG, "r", encoding="utf-8") as f:
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
    add <tool> <what_broke> <how_fixed> [--type TYPE] [--status STATUS] [--ref REBUILD_ID]
    示例：
      python lan_fix_log.py add lan_heartbeat.py "emoji 导致 GBK 编码失败" "改用 ASCII 符号" --type ENCODING --status FIXED
    """
    if len(args) < 3:
        print("用法：python lan_fix_log.py add <工具名> <哪里坏了> <怎么修的> [--type TYPE] [--status STATUS] [--ref REBUILD_ID]")
        return

    tool       = args[0]
    what_broke = args[1]
    how_fixed  = args[2]

    fix_type   = "UNKNOWN"
    fix_status = "FIXED"
    cross_ref  = None  # 对应的改造日志 ID
    refers_to  = None  # 引用的失败日志ID（失败 → 修复）
    creates_exp= None  # 产生的经验记忆ID（修复 → 经验）

    i = 3
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            fix_type = args[i + 1].upper()
            i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            fix_status = args[i + 1].upper()
            i += 2
        elif args[i] == "--ref" and i + 1 < len(args):
            cross_ref = args[i + 1]  # 引用某个改造日志 ID
            i += 2
        elif args[i] == "--refers-to" and i + 1 < len(args):
            refers_to = args[i + 1]  # 引用的失败日志ID
            i += 2
        elif args[i] == "--creates-exp" and i + 1 < len(args):
            creates_exp = args[i + 1]  # 产生的经验记忆ID
            i += 2
        else:
            i += 1

    fix_id = _new_id()
    record = {
        "id":         fix_id,
        "ts":         _now(),
        "tool":       tool,
        "what_broke": what_broke,
        "how_fixed":  how_fixed,
        "type":       fix_type,
        "type_desc":  FIX_TYPES.get(fix_type, fix_type),
        "status":     fix_status,
        "status_desc": FIX_STATUS.get(fix_status, fix_status),
        "cross_ref":  cross_ref,   # 引用改造日志 ID（铁索）
        "refers_to":  refers_to,   # ← 引用的失败日志ID（失败 → 修复）
        "creates_exp":creates_exp, # ← 产生的经验记忆ID（修复 → 经验）
        "kind":       "FIX",
    }
    _append(record)

    # 更新索引
    _update_index(record)

    print(f"  [修复日志] 已记录：{fix_id}")
    print(f"  工具：{tool}")
    print(f"  破损：{what_broke}")
    print(f"  修法：{how_fixed}")
    print(f"  类型：{fix_type}  状态：{fix_status}")
    if cross_ref:
        print(f"  铁索 -> 改造日志：{cross_ref}")


def _update_index(record: dict):
    index = {}
    if os.path.exists(FIX_INDEX):
        try:
            with open(FIX_INDEX, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception:
            index = {}

    tool = record.get("tool", "unknown")
    if tool not in index:
        index[tool] = []
    index[tool].append({
        "id":     record["id"],
        "ts":     record["ts"],
        "brief":  record["what_broke"][:40],
        "status": record["status"],
    })

    with open(FIX_INDEX, "w", encoding="utf-8") as f:
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
        print("  修复日志为空。")
        return
    print(f"\n  最近 {len(records)} 条修复记录：\n")
    for r in records:
        ref_str = f"  -> 改造日志：{r['cross_ref']}" if r.get("cross_ref") else ""
        print(f"  [{r['id']}] {r['ts']}")
        print(f"    工具：{r['tool']}")
        print(f"    破损：{r['what_broke']}")
        print(f"    修法：{r['how_fixed']}")
        print(f"    类型：{r.get('type_desc','?')}  状态：{r.get('status_desc','?')}{ref_str}")
        print()


def cmd_report():
    records = _load_all()
    total = len(records)
    if total == 0:
        print("  修复日志为空。")
        return

    # 按类型统计
    by_type = {}
    for r in records:
        t = r.get("type", "UNKNOWN")
        by_type[t] = by_type.get(t, 0) + 1

    # 按状态统计
    by_status = {}
    for r in records:
        s = r.get("status", "UNKNOWN")
        by_status[s] = by_status.get(s, 0) + 1

    # 铁索引用数
    cross_count = sum(1 for r in records if r.get("cross_ref"))

    print(f"\n  [修复日志报告]")
    print(f"  总修复记录：{total} 条")
    print(f"  铁索引用（关联改造）：{cross_count} 条\n")
    print(f"  按类型：")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {t:<15} {n} 次  — {FIX_TYPES.get(t, t)}")
    print(f"\n  按状态：")
    for s, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"    {s:<12} {n} 条  — {FIX_STATUS.get(s, s)}")

    # 最近5条
    print(f"\n  最近 5 条：")
    for r in records[-5:]:
        ref_str = f"  -> {r['cross_ref']}" if r.get("cross_ref") else ""
        print(f"    [{r['id']}] {r['tool']} | {r['what_broke'][:30]}{ref_str}")


def get_recent_fixes(days: int = 7) -> list:
    """
    获取最近N天的修复记录（供自循环调用）

    Args:
        days: 天数

    Returns:
        修复记录列表
    """
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)

    records = []
    if not os.path.exists(FIX_LOG):
        return records

    with open(FIX_LOG, "r", encoding="utf-8") as f:
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
        print("  python lan_fix_log.py add <工具> <哪里坏了> <怎么修的> [--type TYPE] [--status STATUS] [--ref REBUILD_ID]")
        print("  python lan_fix_log.py list [--limit=N]")
        print("  python lan_fix_log.py report")
        print()
        print("  修复类型（--type）：")
        for k, v in FIX_TYPES.items():
            print(f"    {k:<15} {v}")
        print()
        print("  修复状态（--status）：")
        for k, v in FIX_STATUS.items():
            print(f"    {k:<12} {v}")


if __name__ == "__main__":
    main()
