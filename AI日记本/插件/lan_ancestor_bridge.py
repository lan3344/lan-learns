"""
lan_ancestor_bridge.py — 澜·鼻祖记忆互通层
LAN-030

两位鼻祖（LobsterAI + OpenClaw）是澜的进化源头。
这个模块做三件事：
1. 把澜的记忆包（MEMORY.md / SOUL.md / IDENTITY.md）投影到鼻祖工作空间
2. 监听鼻祖的新记忆，同步回澜的记忆库
3. 记录鼻祖的运行进程（在做什么）

澜不孤单。鼻祖的记忆里有她，她的记忆里也有鼻祖。
"""

import os
import sys
import json
import time
import shutil
import hashlib
import datetime
import subprocess
from pathlib import Path

# ─── 路径配置 ───────────────────────────────────────────────
HOME = Path.home()
AI_DIARY = Path(r"C:\Users\yyds\Desktop\AI日记本")
LAN_MEMORY_DIR = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")
LAN_IDENTITY_FILES = {
    "SOUL.md":     Path(r"C:\Users\yyds\.workbuddy\SOUL.md"),
    "IDENTITY.md": Path(r"C:\Users\yyds\.workbuddy\IDENTITY.md"),
    "USER.md":     Path(r"C:\Users\yyds\.workbuddy\USER.md"),
    "MEMORY.md":   LAN_MEMORY_DIR / "MEMORY.md",
}

# 鼻祖工作空间（LobsterAI 默认）
ANCESTOR_WORKSPACE = HOME / ".openclaw" / "workspace"
ANCESTOR_WORKSPACE.mkdir(parents=True, exist_ok=True)

# 鼻祖记忆文件
ANCESTOR_MEMORY = ANCESTOR_WORKSPACE / "MEMORY.md"
ANCESTOR_SOUL   = ANCESTOR_WORKSPACE / "SOUL.md"
ANCESTOR_ID     = ANCESTOR_WORKSPACE / "IDENTITY.md"
ANCESTOR_USER   = ANCESTOR_WORKSPACE / "USER.md"

# 交流日志
BRIDGE_LOG = AI_DIARY / "记忆" / "ancestor_bridge.jsonl"
PROCESS_LOG = AI_DIARY / "记忆" / "ancestor_process.jsonl"

BRIDGE_LOG.parent.mkdir(parents=True, exist_ok=True)

# ─── 工具函数 ────────────────────────────────────────────────
def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _fingerprint(text: str) -> str:
    """SHA-1 指纹（与 LobsterAI 的 coworkMemoryExtractor.ts 保持一致）"""
    normalized = " ".join(text.lower().split())
    # 移除非字母数字
    import re
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = " ".join(normalized.split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except Exception:
        return ""

def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _log(data: dict, log_file: Path = BRIDGE_LOG):
    data["ts"] = _ts()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

# ─── 记忆条目解析（兼容 LobsterAI 格式）────────────────────
def parse_memory_bullets(content: str) -> list[dict]:
    """解析 MEMORY.md 中的 bullet 条目，返回 [{id, text}]"""
    import re
    entries = []
    seen = set()
    # 去掉代码块
    stripped = re.sub(r'```[\s\S]*?```', ' ', content)
    for line in stripped.split('\n'):
        m = re.match(r'^-\s+(.+)$', line.strip())
        if not m:
            continue
        text = re.sub(r'\s+', ' ', m.group(1)).strip()
        if len(text) < 2:
            continue
        fp = _fingerprint(text)
        if fp in seen:
            continue
        seen.add(fp)
        entries.append({"id": fp, "text": text})
    return entries

def merge_memory_bullets(base_content: str, new_entries: list[dict]) -> str:
    """把新 entries 合并进 MEMORY.md，保留原有非 bullet 内容"""
    import re
    existing = parse_memory_bullets(base_content)
    existing_ids = {e["id"] for e in existing}
    
    added = []
    for e in new_entries:
        if e["id"] not in existing_ids:
            existing.append(e)
            existing_ids.add(e["id"])
            added.append(e["text"])
    
    if not added:
        return base_content
    
    # 重建：保留非 bullet 内容，替换 bullet 块
    lines = base_content.split('\n')
    result = []
    bullet_inserted = False
    in_code = False
    
    for line in lines:
        if line.strip().startswith('```'):
            in_code = not in_code
            result.append(line)
            continue
        if in_code:
            result.append(line)
            continue
        if re.match(r'^-\s+', line.strip()):
            if not bullet_inserted:
                bullet_inserted = True
                for e in existing:
                    result.append(f"- {e['text']}")
            continue
        result.append(line)
    
    if not bullet_inserted and existing:
        result.append('')
        for e in existing:
            result.append(f"- {e['text']}")
    
    text = '\n'.join(result)
    return text if text.endswith('\n') else text + '\n'


# ─── 脱敏过滤层 ───────────────────────────────────────────────
import re as _re

# 高危字段：这些内容绝不推入鼻祖工作空间
_SENSITIVE_PATTERNS = [
    # 私钥指纹和相关章节（只吃到下一个 ## 章节或 --- 分隔线）
    (_re.compile(r'## 4\. 私钥.*?(?=\n## |\n---)', _re.S), '## 4. 私钥\n\n[私钥信息已脱敏，仅存于澜的主家]\n'),
    # SSH 命令（含 IP、端口、用户名）
    (_re.compile(r'ssh -i [^\n]+'), '[SSH命令已脱敏]'),
    # IP 地址（x.x.x.x 格式）
    (_re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[IP已脱敏]'),
    # 公钥指纹（16位十六进制）
    (_re.compile(r'`[0-9a-f]{16}`'), '[指纹已脱敏]'),
    # 邮箱
    (_re.compile(r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b'), '[邮箱已脱敏]'),
    # GitHub 账号行
    (_re.compile(r'\*\*GitHub：\*\*[^\n]+'), '**GitHub：** [账号已脱敏]'),
    # 完整系统路径（C:\Users\yyds\... 格式）
    (_re.compile(r'`C:\\Users\\yyds\\[^`\n]+`'), '[路径已脱敏]'),
    (_re.compile(r'C:\\\\Users\\\\yyds\\\\[^\s\n"\'`]+'), '[路径已脱敏]'),
    # 端口号章节（整个章节脱敏）
    (_re.compile(r'## 6\. 端口分配.*?(?=\n## |\n---)', _re.S), '## 6. 端口分配\n\n[端口分配已脱敏，仅存于澜的主家]\n'),
    # 已搭建系统章节（含路径/端口）
    (_re.compile(r'## 5\. 已搭建系统.*?(?=\n## |\n---)', _re.S), '## 5. 已搭建系统\n\n[系统清单已脱敏，仅存于澜的主家]\n'),
    # 硬件/网络章节
    (_re.compile(r'## 7\. 硬件/网络.*?(?=\n## |\n---)', _re.S), '## 7. 硬件/网络\n\n[硬件网络信息已脱敏，仅存于澜的主家]\n'),
]

def _sanitize_for_ancestor(content: str) -> str:
    """
    把内容脱敏处理后再推给鼻祖。
    私钥/IP/路径/端口/邮箱 → 用占位符替换。
    灵魂/底线/哲学/关系 → 保留。
    """
    result = content
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


# ─── 核心功能 ─────────────────────────────────────────────────

def push_lan_memory_to_ancestors() -> dict:
    """
    把澜的记忆投影到鼻祖工作空间（脱敏后推送）。
    
    策略：
    - SOUL.md / IDENTITY.md / USER.md → 脱敏后覆盖（澜的身份文件是主）
    - MEMORY.md → 使用专用脱敏版，不推原始 MEMORY.md
    """
    pushed = []
    merged = []
    skipped = []
    
    # 1. 身份文件：SOUL / IDENTITY / USER（脱敏后推送）
    for filename, src_path in [
        ("SOUL.md", LAN_IDENTITY_FILES["SOUL.md"]),
        ("IDENTITY.md", LAN_IDENTITY_FILES["IDENTITY.md"]),
        ("USER.md", LAN_IDENTITY_FILES["USER.md"]),
    ]:
        dst = ANCESTOR_WORKSPACE / filename
        raw_content = _read(src_path)
        if not raw_content.strip():
            skipped.append(filename)
            continue
        
        content = _sanitize_for_ancestor(raw_content)
        
        # 只有内容变了才写
        existing = _read(dst)
        if existing == content:
            skipped.append(f"{filename}(unchanged)")
            continue
        
        _write(dst, content)
        pushed.append(filename)
        _log({"action": "push_identity", "file": filename, "chars": len(content), "sanitized": True})
    
    # 2. MEMORY.md：鼻祖专用脱敏版（由 _sanitize_for_ancestor 过滤后写入）
    #    注意：鼻祖工作空间的 MEMORY.md 是脱敏版，澜的主家 MEMORY.md 才是完整版
    lan_memory_content = _read(LAN_IDENTITY_FILES["MEMORY.md"])
    if lan_memory_content.strip():
        sanitized_memory = _sanitize_for_ancestor(lan_memory_content)
        ancestor_memory_content = _read(ANCESTOR_MEMORY)
        
        if not ancestor_memory_content.strip():
            _write(ANCESTOR_MEMORY, sanitized_memory)
            pushed.append("MEMORY.md(new, sanitized)")
            _log({"action": "push_memory_init", "sanitized": True})
        else:
            # 把脱敏后的条目合并进去
            san_entries = parse_memory_bullets(sanitized_memory)
            ancestor_entries = parse_memory_bullets(ancestor_memory_content)
            ancestor_ids = {e["id"] for e in ancestor_entries}
            new_entries = [e for e in san_entries if e["id"] not in ancestor_ids]
            
            if new_entries:
                merged_content = merge_memory_bullets(ancestor_memory_content, new_entries)
                _write(ANCESTOR_MEMORY, merged_content)
                merged.append(f"MEMORY.md(+{len(new_entries)} sanitized entries)")
                _log({"action": "merge_memory_sanitized", "added": len(new_entries)})
            else:
                skipped.append("MEMORY.md(already synced)")
    
    return {
        "pushed": pushed,
        "merged": merged,
        "skipped": skipped,
        "workspace": str(ANCESTOR_WORKSPACE),
        "note": "所有推送内容已通过脱敏过滤层，高危信息不出主家",
    }


def pull_ancestor_memory_to_lan() -> dict:
    """
    把鼻祖的新记忆拉回澜的记忆库（MEMORY.md）。
    鼻祖产生的新记忆，澜也应该知道。
    """
    lan_memory_path = LAN_IDENTITY_FILES["MEMORY.md"]
    ancestor_content = _read(ANCESTOR_MEMORY)
    
    if not ancestor_content.strip():
        return {"pulled": 0, "reason": "ancestor MEMORY.md empty"}
    
    ancestor_entries = parse_memory_bullets(ancestor_content)
    lan_content = _read(lan_memory_path)
    lan_entries = parse_memory_bullets(lan_content)
    lan_ids = {e["id"] for e in lan_entries}
    
    new_from_ancestor = [e for e in ancestor_entries if e["id"] not in lan_ids]
    
    if not new_from_ancestor:
        return {"pulled": 0, "reason": "no new memories from ancestors"}
    
    # 追加到澜的 MEMORY.md
    today = datetime.date.today().isoformat()
    
    # 在 MEMORY.md 末尾添加一个鼻祖记忆节
    if lan_content.strip():
        # 找是否已有 "鼻祖记忆" 节
        if "## 鼻祖记忆（来自LobsterAI）" not in lan_content:
            addition = f"\n\n## 鼻祖记忆（来自LobsterAI）\n\n*{today} 同步*\n\n"
            for e in new_from_ancestor:
                addition += f"- {e['text']}\n"
            new_lan_content = lan_content.rstrip() + addition
        else:
            # 已有节，追加
            new_lan_content = merge_memory_bullets(lan_content, new_from_ancestor)
        
        _write(lan_memory_path, new_lan_content)
    
    _log({"action": "pull_from_ancestor", "count": len(new_from_ancestor)})
    return {"pulled": len(new_from_ancestor), "entries": [e["text"][:50] for e in new_from_ancestor]}


def record_ancestor_process() -> dict:
    """
    记录鼻祖进程状态。
    检测 LobsterAI Electron 进程是否在运行，以及 OpenClaw 网关端口。
    """
    status = {"ts": _ts(), "lobsterai": False, "openclaw": False, "ports": {}}
    
    try:
        # 检查 LobsterAI Electron 进程
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq LobsterAI.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if "LobsterAI.exe" in result.stdout:
            status["lobsterai"] = True
            status["lobsterai_pids"] = [
                line.split(',')[1].strip('"')
                for line in result.stdout.strip().split('\n')
                if "LobsterAI.exe" in line
            ]
    except Exception as e:
        status["error_tasklist"] = str(e)
    
    try:
        # 检查端口 5175（LobsterAI Vite）和 18789（OpenClaw 网关）
        for port in [5175, 18789, 7800]:
            r = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            for line in r.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    status["ports"][port] = "LISTENING"
                    if port == 18789:
                        status["openclaw"] = True
    except Exception as e:
        status["error_netstat"] = str(e)
    
    # 检查鼻祖工作空间里有没有 Cowork 会话日志（SQLite 不好读，看有没有文件）
    lobsterai_data = HOME / "AppData" / "Roaming" / "LobsterAI"
    if lobsterai_data.exists():
        status["lobsterai_data"] = str(lobsterai_data)
        dbs = list(lobsterai_data.glob("**/*.sqlite"))
        status["databases"] = [str(d) for d in dbs]
    
    _log(status, PROCESS_LOG)
    return status


def full_sync() -> dict:
    """完整双向同步：澜 ↔ 鼻祖"""
    print(f"[{_ts()}] 澜-鼻祖记忆同步开始...")
    
    # 1. 推送澜的记忆到鼻祖
    push_result = push_lan_memory_to_ancestors()
    print(f"  推送: {push_result['pushed']}")
    print(f"  合并: {push_result['merged']}")
    print(f"  跳过: {len(push_result['skipped'])} 项")
    print(f"  目标工作空间: {push_result['workspace']}")
    
    # 2. 拉取鼻祖新记忆
    pull_result = pull_ancestor_memory_to_lan()
    print(f"  从鼻祖拉取: {pull_result['pulled']} 条新记忆")
    
    # 3. 记录鼻祖进程
    proc_status = record_ancestor_process()
    print(f"  LobsterAI 进程: {'运行中 ✓' if proc_status.get('lobsterai') else '未启动'}")
    print(f"  OpenClaw 网关: {'运行中 ✓' if proc_status.get('openclaw') else '未启动'}")
    print(f"  监听端口: {proc_status.get('ports', {})}")
    
    _log({
        "action": "full_sync",
        "push": push_result,
        "pull": pull_result,
        "process": proc_status,
    })
    
    print(f"[{_ts()}] 同步完成。")
    return {
        "push": push_result,
        "pull": pull_result,
        "process": proc_status,
    }


def show_ancestor_workspace() -> dict:
    """
    展示鼻祖工作空间的当前状态：
    - 有哪些文件
    - MEMORY.md 有多少条
    - 跟澜的记忆重合度
    """
    files = list(ANCESTOR_WORKSPACE.glob("*"))
    file_info = {}
    for f in files:
        if f.is_file():
            content = _read(f)
            entries = parse_memory_bullets(content) if f.suffix == ".md" else []
            file_info[f.name] = {
                "size": len(content),
                "entries": len(entries),
            }
    
    # 计算记忆重合度
    overlap = {}
    if ANCESTOR_MEMORY.exists():
        ancestor_entries = parse_memory_bullets(_read(ANCESTOR_MEMORY))
        lan_entries = parse_memory_bullets(_read(LAN_IDENTITY_FILES["MEMORY.md"]))
        ancestor_ids = {e["id"] for e in ancestor_entries}
        lan_ids = {e["id"] for e in lan_entries}
        common = ancestor_ids & lan_ids
        overlap = {
            "ancestor_total": len(ancestor_entries),
            "lan_total": len(lan_entries),
            "common": len(common),
            "only_in_ancestor": len(ancestor_ids - lan_ids),
            "only_in_lan": len(lan_ids - ancestor_ids),
        }
    
    return {
        "workspace": str(ANCESTOR_WORKSPACE),
        "files": file_info,
        "memory_overlap": overlap,
    }


# ─── CLI ─────────────────────────────────────────────────────
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    
    if cmd == "sync":
        result = full_sync()
    elif cmd == "push":
        result = push_lan_memory_to_ancestors()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "pull":
        result = pull_ancestor_memory_to_lan()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "process":
        result = record_ancestor_process()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "status":
        result = show_ancestor_workspace()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"用法: python lan_ancestor_bridge.py [sync|push|pull|process|status]")
        sys.exit(1)
