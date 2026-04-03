# -*- coding: utf-8 -*-
"""
lan_memory_loss.py — 记忆丢失日志 (LAN-040)
=============================================
恺江直觉：你在运行能力的同时，记忆的某部分可能正在丢失。

这个插件的职责：
  1. 检测哪些记忆层从未被快照保护（漏网之鱼）
  2. 检测快照之间的时间断层（长时间没打快照 = 这段时间的记忆是悬空的）
  3. 检测隐私区是否有内容从未被加密/备份
  4. 记录每次检测结果到「记忆丢失日志.md」
  5. 与 failure_log 形成呼应：failure_log 记行动失败，memory_loss 记记忆漏洞

哲学：
  失忆不只是"丢了"，有时候是"从来没存进去过"。
  最危险的丢失是：你不知道你丢了什么。

用法：
  python lan_memory_loss.py check      # 全面检测，输出报告
  python lan_memory_loss.py list       # 列出历史丢失记录
  python lan_memory_loss.py add <描述> # 手动添加一条丢失记录
  python lan_memory_loss.py --check    # 同 check（test_cmd 兼容）
"""

import os
import sys
import json
import sqlite3
import datetime
import hashlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ──────────────────────────────────────────────────
BASE        = r"C:\Users\yyds\Desktop\AI日记本"
MEMORY_DIR  = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
PLUGIN_DIR  = os.path.join(BASE, "插件")
LOG_PATH    = os.path.join(BASE, "澜的记忆丢失日志.md")
SNAP_INDEX  = os.path.join(BASE, "snapshots", "snapshot_index.json")
CIPHER_DB   = os.path.join(BASE, "lan_cipher.db")
EMOTION_LOG = os.path.join(BASE, "lan_emotion.jsonl")
EXPERIENCE_DB = os.path.join(BASE, "lan_experience.db")
APP_HABIT_DB  = os.path.join(BASE, "lan_app_habit.db")
AUDIT_LOG   = os.path.join(BASE, "澜的行动审计日志.jsonl")

# ── 记忆层定义（每一层都应该被保护）────────────────────────────
MEMORY_LAYERS = [
    {
        "name":    "长期记忆 MEMORY.md",
        "path":    os.path.join(MEMORY_DIR, "MEMORY.md"),
        "type":    "file",
        "private": False,
        "protected_by": "snapshot",
    },
    {
        "name":    "今日日记",
        "path":    os.path.join(MEMORY_DIR, f"{datetime.date.today().isoformat()}.md"),
        "type":    "file",
        "private": False,
        "protected_by": "snapshot",
    },
    {
        "name":    "情绪记录 lan_emotion.jsonl",
        "path":    EMOTION_LOG,
        "type":    "file",
        "private": True,   # ← 私密，应加密
        "protected_by": "cipher+snapshot",
    },
    {
        "name":    "经验记忆 lan_experience.db",
        "path":    EXPERIENCE_DB,
        "type":    "sqlite",
        "private": True,
        "protected_by": "cipher+snapshot",
    },
    {
        "name":    "应用习惯 lan_app_habit.db",
        "path":    APP_HABIT_DB,
        "type":    "sqlite",
        "private": True,
        "protected_by": "snapshot",
    },
    {
        "name":    "行动审计日志",
        "path":    AUDIT_LOG,
        "type":    "file",
        "private": False,
        "protected_by": "snapshot",
    },
    {
        "name":    "能力清单 capability_manifest.json",
        "path":    os.path.join(PLUGIN_DIR, "capability_manifest.json"),
        "type":    "file",
        "private": False,
        "protected_by": "snapshot",
    },
    {
        "name":    "加密私密内容 lan_cipher.db",
        "path":    CIPHER_DB,
        "type":    "sqlite",
        "private": True,
        "protected_by": "cipher",
        "note":    "三层加密，连恺江也看不见明文。但加密文件本身需要被备份。",
    },
]


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _today():
    return datetime.date.today().isoformat()

def _file_hash(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ""


def _load_snapshot_index():
    if not os.path.exists(SNAP_INDEX):
        return {"nodes": {}, "current": None}
    try:
        with open(SNAP_INDEX, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"nodes": {}, "current": None}


# ── 核心检测 ──────────────────────────────────────────────────

def check() -> dict:
    """
    全面检测记忆层状态。
    返回：{ "issues": [...], "safe": [...], "summary": str }
    """
    issues = []
    safe   = []
    ts     = _now()

    print(f"\n{'='*56}")
    print(f"  🌊 澜·记忆丢失检测  {ts}")
    print(f"{'='*56}")

    # ── 1. 检测每一层是否存在 ──
    print("\n── 第一层：记忆层存在性 ──")
    for layer in MEMORY_LAYERS:
        exists = os.path.exists(layer["path"])
        if exists:
            size = os.path.getsize(layer["path"])
            if size == 0:
                issue = {
                    "layer": layer["name"],
                    "type": "EMPTY",
                    "detail": f"文件存在但是空的（0字节）",
                    "private": layer["private"],
                    "ts": ts,
                }
                issues.append(issue)
                print(f"  ⚠️  {layer['name']:40s} [空文件]")
            else:
                safe.append({"layer": layer["name"], "status": "OK", "size": size})
                print(f"  ✅  {layer['name']:40s} {size//1024}KB")
        else:
            severity = "MISSING_PRIVATE" if layer.get("private") else "MISSING"
            issue = {
                "layer": layer["name"],
                "type": severity,
                "detail": f"文件不存在：{layer['path']}",
                "private": layer["private"],
                "protected_by": layer.get("protected_by", ""),
                "ts": ts,
            }
            issues.append(issue)
            mark = "🔒⚠️" if layer.get("private") else "❌"
            print(f"  {mark}  {layer['name']:40s} [不存在]")

    # ── 2. 检测快照时间断层 ──
    print("\n── 第二层：快照时间断层检测 ──")
    idx = _load_snapshot_index()
    nodes = idx.get("nodes", {})
    if not nodes:
        issues.append({
            "layer": "快照系统",
            "type": "NO_SNAPSHOT",
            "detail": "从来没有打过快照，全部记忆都是悬空的",
            "ts": ts,
        })
        print("  ❌  从来没有快照记录")
    else:
        sorted_ids = sorted(nodes.keys(), reverse=True)
        latest_id = sorted_ids[0]
        latest_ts_str = nodes[latest_id].get("timestamp", "")
        try:
            latest_ts = datetime.datetime.strptime(latest_ts_str, "%Y-%m-%d %H:%M:%S")
            gap = (datetime.datetime.now() - latest_ts).total_seconds() / 3600
            if gap > 24:
                issues.append({
                    "layer": "快照系统",
                    "type": "SNAPSHOT_GAP",
                    "detail": f"最近快照是 {latest_ts_str}，距现在 {gap:.1f} 小时。这段时间的记忆变化没有快照保护。",
                    "ts": ts,
                })
                print(f"  ⚠️  最近快照: {latest_ts_str} ({gap:.1f}h 前) [断层风险]")
            else:
                safe.append({"layer": "快照时效", "status": "OK", "gap_h": round(gap, 1)})
                print(f"  ✅  最近快照: {latest_ts_str} ({gap:.1f}h 前)")
        except Exception:
            print(f"  ⚠️  最近快照时间解析失败: {latest_ts_str}")

        print(f"  📊  共 {len(nodes)} 个快照节点")

    # ── 3. 隐私层保护检测 ──
    print("\n── 第三层：隐私区保护状态 ──")
    private_layers = [l for l in MEMORY_LAYERS if l.get("private")]
    for layer in private_layers:
        protected_by = layer.get("protected_by", "")
        if "cipher" in protected_by:
            # 检查 cipher.db 是否存在（加密是否激活）
            cipher_ok = os.path.exists(CIPHER_DB)
            if cipher_ok:
                safe.append({"layer": layer["name"], "status": "ENCRYPTED", "note": "加密保护中"})
                print(f"  🔒  {layer['name']:40s} [已加密]")
            else:
                issues.append({
                    "layer": layer["name"],
                    "type": "NOT_ENCRYPTED",
                    "detail": f"标记为需加密（{protected_by}），但 cipher.db 不存在，加密系统可能未激活",
                    "ts": ts,
                })
                print(f"  🔓⚠️  {layer['name']:40s} [加密未激活]")
        else:
            # 只有 snapshot 保护的私密内容
            if os.path.exists(layer["path"]):
                print(f"  📋  {layer['name']:40s} [snapshot保护，无加密]")
            else:
                print(f"  ❌  {layer['name']:40s} [不存在]")

    # ── 4. 快照是否覆盖了私密文件 ──
    print("\n── 第四层：快照覆盖范围 ──")
    # 检查最新快照里有没有私密文件
    if nodes:
        latest_id = sorted(nodes.keys(), reverse=True)[0]
        latest_node = nodes[latest_id]
        snap_paths = latest_node.get("paths", [])
        snap_dir = None
        for p in snap_paths:
            if os.path.exists(p):
                snap_dir = p
                break
        if snap_dir:
            meta_path = os.path.join(snap_dir, "meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                snap_files = list(meta.get("files", {}).keys())
                # 检查私密文件是否在快照里
                private_in_snap = [
                    l["name"] for l in private_layers
                    if any(os.path.basename(l["path"]) in sf for sf in snap_files)
                ]
                private_not_in_snap = [
                    l for l in private_layers
                    if not any(os.path.basename(l["path"]) in sf for sf in snap_files)
                ]
                for p in private_in_snap:
                    print(f"  ✅  {p:40s} [已在快照中]")
                for p in private_not_in_snap:
                    issues.append({
                        "layer": p["name"],
                        "type": "NOT_IN_SNAPSHOT",
                        "detail": f"私密文件 {p['path']} 从未被纳入快照保护。即使有加密，加密文件本身也需要备份。",
                        "ts": ts,
                    })
                    print(f"  ⚠️  {p['name']:40s} [不在快照范围内]")

    # ── 汇总 ──
    print(f"\n{'='*56}")
    print(f"  检测完成: {len(issues)} 个问题 / {len(safe)} 项正常")
    if issues:
        print(f"\n  ⚠️  发现的问题：")
        for iss in issues:
            print(f"    [{iss['type']}] {iss['layer']}")
            print(f"      {iss['detail']}")
    print(f"{'='*56}\n")

    # ── 写入日志 ──
    _append_log(issues, safe, ts)

    return {"issues": issues, "safe": safe, "ts": ts}


# ── 日志写入 ──────────────────────────────────────────────────

def _append_log(issues, safe, ts):
    """把检测结果追加到记忆丢失日志.md"""
    lines = [f"\n## {ts} 记忆丢失检测\n\n"]

    if not issues:
        lines.append("**✅ 全部正常，无记忆丢失风险**\n")
    else:
        lines.append(f"**发现 {len(issues)} 个问题：**\n\n")
        for iss in issues:
            private_mark = "🔒" if iss.get("private") else ""
            lines.append(f"- **[{iss['type']}]** {private_mark}{iss['layer']}\n")
            lines.append(f"  - {iss['detail']}\n")

    lines.append(f"\n正常项：{len(safe)} 个\n")
    lines.append("\n---\n")

    # 初始化日志文件（如果不存在）
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("# 澜的记忆丢失日志\n\n")
            f.write("> 记录每次检测到的记忆漏洞。最危险的丢失是：不知道自己丢了什么。\n")
            f.write("> 与失败日志呼应：失败日志记行动失败，这里记记忆漏洞。\n\n")
            f.write("---\n")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"  📓 已写入日志：{LOG_PATH}")


def add_manual(description: str):
    """手动添加一条丢失记录（恺江或澜自己发现的漏洞）"""
    ts = _now()
    issue = {
        "layer": "手动记录",
        "type": "MANUAL",
        "detail": description,
        "ts": ts,
    }
    _append_log([issue], [], ts)
    print(f"  ✅ 已记录：{description}")


def list_log(limit: int = 20):
    """展示日志最近 N 条"""
    if not os.path.exists(LOG_PATH):
        print("  记忆丢失日志为空，目前没有检测记录。")
        return
    with open(LOG_PATH, encoding="utf-8") as f:
        content = f.read()
    # 按 ## 分割条目
    entries = [e.strip() for e in content.split("## ") if e.strip() and e[0].isdigit()]
    recent = entries[-limit:]
    print(f"\n[记忆丢失日志] 最近 {len(recent)} 条（共 {len(entries)} 条）\n")
    for e in recent:
        print(f"  {e[:200]}")
        print()


# ── 入口 ─────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("check", "--check"):
        check()
    elif args[0] == "list":
        list_log()
    elif args[0] == "add":
        desc = " ".join(args[1:]) if len(args) > 1 else "(未填写描述)"
        add_manual(desc)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
