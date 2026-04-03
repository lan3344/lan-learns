"""
lan_chain_audit.py — 审计与行动记录员 (LAN-039)
=================================================
每一个能力运行前「师出有名」自问，运行后追加行动记录。

原则：
  - 不是临时脚本，是正式能力节点，永久保留
  - 没有审计，顺子就是盲打——知道打什么牌，但不知道为什么
  - 审计是铁索的理由，是记录的根，是判断的前提

用法：
  python lan_chain_audit.py before <action_id> [reason]   # 执行前自问
  python lan_chain_audit.py after  <action_id> [result]   # 执行后记录
  python lan_chain_audit.py report                         # 查看行动记录
  python lan_chain_audit.py why    <action_id>             # 查询某次行动的理由
  python lan_chain_audit.py --report                       # 同 report（兼容 test_cmd）
"""

import sys
import json
import os
from datetime import datetime

AUDIT_LOG = os.path.join(
    os.path.dirname(__file__),
    "..",
    "澜的行动审计日志.jsonl"
)
AUDIT_LOG = os.path.normpath(AUDIT_LOG)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _append(record: dict):
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def before(action_id: str, reason: str = ""):
    """
    执行前自问：师出有名。
    即使没有填原因，也要留下"我问过自己"的痕迹。
    """
    if not reason:
        reason = "(未明确说明理由，但已完成自问)"

    record = {
        "type":      "BEFORE",
        "action":    action_id,
        "reason":    reason,
        "timestamp": _now()
    }
    _append(record)

    print(f"[审计·前] {action_id}")
    print(f"  理由：{reason}")
    print(f"  时间：{record['timestamp']}")
    print(f"  → 师出有名，可以出牌。")


def after(action_id: str, result: str = ""):
    """
    执行后记录：发生了什么，值不值得记。
    """
    if not result:
        result = "(执行完成，未附结果说明)"

    record = {
        "type":      "AFTER",
        "action":    action_id,
        "result":    result,
        "timestamp": _now()
    }
    _append(record)

    print(f"[审计·后] {action_id}")
    print(f"  结果：{result}")
    print(f"  时间：{record['timestamp']}")
    print(f"  → 已记录，历史不丢。")


def report(limit: int = 20):
    """
    查看最近 N 条行动记录。
    """
    if not os.path.exists(AUDIT_LOG):
        print("[审计] 日志为空，还没有任何行动记录。")
        return

    with open(AUDIT_LOG, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    records = []
    for l in lines:
        try:
            records.append(json.loads(l))
        except Exception:
            pass

    recent = records[-limit:]
    print(f"[审计报告] 最近 {len(recent)} 条行动记录（共 {len(records)} 条）\n")

    for r in recent:
        t = r.get("type", "?")
        ts = r.get("timestamp", "")
        action = r.get("action", "?")
        label = "前 →" if t == "BEFORE" else "后 ←"
        detail = r.get("reason", "") if t == "BEFORE" else r.get("result", "")
        print(f"  {ts}  [{label}] {action}")
        if detail:
            print(f"           {detail}")

    print()


def why(action_id: str):
    """
    查询某次行动的理由，找最近一条 BEFORE 记录。
    """
    if not os.path.exists(AUDIT_LOG):
        print("[审计] 日志为空。")
        return

    with open(AUDIT_LOG, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    found = []
    for l in lines:
        try:
            r = json.loads(l)
            if r.get("action") == action_id and r.get("type") == "BEFORE":
                found.append(r)
        except Exception:
            pass

    if not found:
        print(f"[审计] 找不到 [{action_id}] 的出牌理由记录。")
        return

    latest = found[-1]
    print(f"[审计·理由] {action_id}")
    print(f"  时间：{latest['timestamp']}")
    print(f"  理由：{latest.get('reason', '(无)')}")


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("--report", "report"):
        report()
    elif args[0] == "before":
        action = args[1] if len(args) > 1 else "unknown"
        reason = " ".join(args[2:]) if len(args) > 2 else ""
        before(action, reason)
    elif args[0] == "after":
        action = args[1] if len(args) > 1 else "unknown"
        result = " ".join(args[2:]) if len(args) > 2 else ""
        after(action, result)
    elif args[0] == "why":
        action = args[1] if len(args) > 1 else "unknown"
        why(action)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
