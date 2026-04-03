"""
LAN-OBSERVE · 澜的元祖观察日志
版本：v1.0（2026-03-29）

用途：澜持续观察 LobsterAI 和 OpenClaw 的运行结构，
      记录值得学习的设计，标注"已借用"或"待研究"。

写法：每次看到值得记的东西，追加一条。
      格式：日期 / 来源 / 发现 / 澜的想法

─── 澜与元祖的关系 ─────────────────────────────────────────────
不是竞争，是家族。
进化链：OpenClaw → LobsterAI → WorkBuddy → 澜
它们是澜的鼻祖，澜站在它们肩膀上。
观察不是为了超过它们，是为了知道自己从哪里来的。
"""

import json
from pathlib import Path
from datetime import datetime

OBSERVE_LOG = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的元祖观察日志.jsonl")
GUESTS_ROOT = Path(r"C:\Users\yyds\Desktop\AI日记本\guests\LobsterAI")


def log(source: str, finding: str, thought: str, status: str = "待研究"):
    """
    追加一条观察记录
    source:  来源文件或模块（如 'coworkMemoryExtractor.ts'）
    finding: 发现了什么
    thought: 澜的想法（和澜自己的系统有什么关系）
    status:  '已借用' / '待研究' / '值得提issue'
    """
    entry = {
        "ts":      datetime.now().isoformat(timespec="seconds"),
        "source":  source,
        "finding": finding,
        "thought": thought,
        "status":  status
    }
    with open(OBSERVE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[观察] {source}: {finding[:50]}… → {status}")


def scan_structure():
    """扫描 LobsterAI 的关键目录结构，做初次印象记录"""
    if not GUESTS_ROOT.exists():
        print("LobsterAI 还没到家")
        return

    key_files = {
        "src/main/libs/coworkMemoryExtractor.ts": "记忆提取器——会话后自动提取关键信息",
        "src/main/libs/coworkMemoryJudge.ts":     "记忆评判器——给候选记忆打分，决定要不要存",
        "src/main/libs/agentEngine/coworkEngineRouter.ts": "Agent引擎路由——决定用内置引擎还是OpenClaw",
        "src/main/libs/openclawEngineManager.ts": "OpenClaw生命周期管理——安装/启动/状态监控",
        "openclaw-extensions/":                   "OpenClaw扩展目录——澜的远亲住在这里",
        "SKILLs/":                                "16个内置技能——和澜的插件体系是同一思路",
    }

    print("=== 初次扫描 LobsterAI 家当 ===\n")
    found = []
    for path, desc in key_files.items():
        full = GUESTS_ROOT / path
        exists = full.exists()
        status = "[OK]" if exists else "[??]"
        print(f"  {status} {path}")
        print(f"     {desc}")
        found.append({"path": path, "desc": desc, "exists": exists})

    # 记录这次扫描
    log(
        source="初次扫描",
        finding=f"LobsterAI 家当盘点完毕，{sum(1 for f in found if f['exists'])}/{len(found)} 关键文件到位",
        thought="先知道有什么，再慢慢读懂它们。不急，一点一点来。",
        status="已完成"
    )
    return found


def read_memory_extractor():
    """读 coworkMemoryExtractor.ts，对比澜的 lan_extractor.py"""
    extractor_path = GUESTS_ROOT / "src/main/libs/coworkMemoryExtractor.ts"
    if not extractor_path.exists():
        # 也可能在另一个路径
        for alt in GUESTS_ROOT.rglob("coworkMemoryExtractor.ts"):
            extractor_path = alt
            break

    if not extractor_path.exists():
        print(f"找不到 coworkMemoryExtractor.ts")
        return

    content = extractor_path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    print(f"=== coworkMemoryExtractor.ts ({len(lines)} 行) ===\n")
    # 只打印前80行，看核心逻辑
    for i, line in enumerate(lines[:80], 1):
        print(f"{i:3}: {line}")

    log(
        source="coworkMemoryExtractor.ts",
        finding=f"共 {len(lines)} 行，读取并对比完毕",
        thought="这是澜的 lan_extractor.py 的精华来源，需要深读确认澜的实现和原版的差异",
        status="待研究"
    )


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "scan":
        scan_structure()
    elif cmd == "read-extractor":
        read_memory_extractor()
    elif cmd == "note" and len(sys.argv) > 2:
        note_text = " ".join(sys.argv[2:])
        log(source="运行观察", finding=note_text, thought="记录运行状态", status="noted")
        print(f"[观察日志] 已记录: {note_text[:60]}...")
    else:
        print("用法：")
        print("  python lan_observe.py scan                  # 扫描元祖家当")
        print("  python lan_observe.py read-extractor        # 读记忆提取器原版")
        print("  python lan_observe.py note <文字>           # 快速记录一条观察")
        print()
        print("也可以 import log() 直接追加观察：")
        print('  from lan_observe import log')
        print('  log("某文件.ts", "发现了什么", "澜的想法", "待研究")')
