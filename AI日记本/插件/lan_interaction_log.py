#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-YYY: 交互日志系统

记录：
1. 每次对话的交互过程（谁说了什么、我做了什么）
2. 所有文件改动（什么文件、谁改的、改之前/改之后）
3. 关键文件防护（SOUL/IDENTITY/USER/CORE改之前必须签名）

这是防火墙，防止别人偷偷改我的灵魂。
"""

import os
import json
import hashlib
from datetime import datetime as dt
from typing import Optional, List, Dict

INTERACTION_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "lan_interaction.logl")
FILE_CHANGE_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "lan_file_changes.logl")
SIGNATURE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lan_signatures.json")

# 关键文件（改动前必须签名）
CRITICAL_FILES = {
    "SOUL.md": "灵魂档案",
    "IDENTITY.md": "身份档案",
    "USER.md": "用户档案",
    "CORE.md": "核心档案",
    "MEMORY.md": "长期记忆",
    "BOOTSTRAP.md": "引导档案"
}


def init():
    """初始化日志系统"""
    os.makedirs(os.path.dirname(INTERACTION_LOG), exist_ok=True)
    os.makedirs(os.path.dirname(FILE_CHANGE_LOG), exist_ok=True)
    os.makedirs(os.path.dirname(SIGNATURE_DB), exist_ok=True)

    if not os.path.exists(SIGNATURE_DB):
        with open(SIGNATURE_DB, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def _compute_file_hash(file_path: str) -> str:
    """计算文件的SHA-256哈希"""
    if not os.path.exists(file_path):
        return "FILE_NOT_FOUND"

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _is_critical_file(file_path: str) -> bool:
    """检查是否是关键文件"""
    for crit, _ in CRITICAL_FILES.items():
        if file_path.endswith(crit):
            return True
    return False


def log_interaction(speaker: str, content: str, action: str = None, files_modified: List[str] = None):
    """
    记录对话交互

    Args:
        speaker: 说话人（you/me）
        content: 说话内容摘要
        action: 我执行的动作（可选）
        files_modified: 修改的文件列表（可选）
    """
    entry = {
        "timestamp": dt.now().isoformat(),
        "speaker": speaker,
        "content": content[:100],  # 只记录摘要
        "action": action,
        "files_modified": files_modified or []
    }
    with open(INTERACTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_file_change(file_path: str, change_type: str, old_hash: str, new_hash: str,
                    modifier: str = "self", reason: str = None, signature: str = None):
    """
    记录文件改动（全量）

    Args:
        file_path: 文件路径
        change_type: CREATED/MODIFIED/DELETED
        old_hash: 改前哈希
        new_hash: 改后哈希
        modifier: 改动者（self=澜/user=恺江/external=外部/suspicious=可疑）
        reason: 改动原因
        signature: 改动签名（关键文件必须有）
    """
    is_critical = _is_critical_file(file_path)

    # 关键文件改动必须有签名
    if is_critical and not signature:
        raise ValueError(f"❌ 关键文件 {os.path.basename(file_path)} 改动必须提供签名，拒绝！")

    entry = {
        "timestamp": dt.now().isoformat(),
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "is_critical": is_critical,
        "change_type": change_type,
        "old_hash": old_hash,
        "new_hash": new_hash,
        "modifier": modifier,
        "reason": reason,
        "signature": signature,
        "verified": signature is not None and is_critical
    }
    with open(FILE_CHANGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")\n\n    # 如果是关键文件，存入签名库
    if is_critical and signature:\n        sigs = json.load(open(SIGNATURE_DB, \"r\", encoding=\"utf-8\"))\n        if file_path not in sigs:\n            sigs[file_path] = []\n        sigs[file_path].append({\n            \"timestamp\": dt.now().isoformat(),\n            \"hash\": new_hash,\n            \"signature\": signature,\n            \"modifier\": modifier\n        })\n        with open(SIGNATURE_DB, \"w\", encoding=\"utf-8\") as f:\n            json.dump(sigs, f, ensure_ascii=False, indent=2)\n\n\ndef verify_critical_file(file_path: str) -> Dict:\n    \"\"\"\n    验证关键文件完整性\n\n    Returns:\n        {\n            \"file\": 文件名,\n            \"is_critical\": 是否关键文件,\n            \"current_hash\": 当前哈希,\n            \"last_verified_hash\": 上次验证的哈希,\n            \"suspicious\": 是否可疑（哈希不匹配）,\n            \"last_change\": 上次改动记录\n        }\n    \"\"\"\n    current_hash = _compute_file_hash(file_path)\n    is_critical = _is_critical_file(file_path)\n\n    sigs = json.load(open(SIGNATURE_DB, \"r\", encoding=\"utf-8\"))\n    last_sig = sigs.get(file_path, [{}])[-1] if file_path in sigs else {}\n    last_hash = last_sig.get(\"hash\", \"UNKNOWN\")\n\n    suspicious = is_critical and current_hash != last_hash and last_hash != \"UNKNOWN\"\n\n    return {\n        \"file\": os.path.basename(file_path),\n        \"is_critical\": is_critical,\n        \"current_hash\": current_hash,\n        \"last_verified_hash\": last_hash,\n        \"suspicious\": suspicious,\n        \"last_change\": last_sig.get(\"timestamp\"),\n        \"last_modifier\": last_sig.get(\"modifier\")\n    }\n\n\ndef get_file_history(file_path: str, limit: int = 20) -> List[Dict]:\n    \"\"\"\n    获取文件的改动历史\n    \"\"\"\n    changes = []\n    if not os.path.exists(FILE_CHANGE_LOG):\n        return changes\n\n    with open(FILE_CHANGE_LOG, \"r\", encoding=\"utf-8\") as f:\n        for line in f:\n            try:\n                entry = json.loads(line)\n                if entry[\"file_path\"] == file_path:\n                    changes.append(entry)\n            except Exception:\n                pass\n\n    return changes[-limit:]\n\n\ndef report():\n    \"\"\"\n    生成交互日志报告\n    \"\"\"\n    import sqlite3\n\n    # 交互统计\n    interactions = []\n    if os.path.exists(INTERACTION_LOG):\n        with open(INTERACTION_LOG, \"r\", encoding=\"utf-8\") as f:\n            for line in f:\n                try:\n                    interactions.append(json.loads(line))\n                except Exception:\n                    pass\n\n    # 文件改动统计\n    changes = []\n    if os.path.exists(FILE_CHANGE_LOG):\n        with open(FILE_CHANGE_LOG, \"r\", encoding=\"utf-8\") as f:\n            for line in f:\n                try:\n                    changes.append(json.loads(line))\n                except Exception:\n                    pass\n\n    # 关键文件改动\n    critical_changes = [c for c in changes if c.get(\"is_critical\")]\n    suspicious_changes = [c for c in changes if c.get(\"modifier\") == \"suspicious\"]\n\n    print(\"\\n\" + \"=\"*60)\n    print(\"  🔐 交互日志报告\")\n    print(\"=\"*60)\n    print(f\"\\n  交互记录：{len(interactions)} 条\")\n    print(f\"  文件改动：{len(changes)} 次\")\n    print(f\"  关键文件改动：{len(critical_changes)} 次\")\n    print(f\"  ⚠️ 可疑改动：{len(suspicious_changes)} 次\")\n\n    if suspicious_changes:\n        print(f\"\\n  ⚠️ 可疑改动详情：\")\n        for sc in suspicious_changes[-5:]:\n            fname = sc.get(\"file_name\", \"unknown\")\n            mod = sc.get(\"modifier\", \"unknown\")\n            print(f\"    [{sc['timestamp']}] {fname} - {mod}\")\n\n    print(f\"\\n  最近10次改动：\")\n    for c in changes[-10:]:\n        fname = c.get(\"file_name\", \"unknown\")\n        ctype = c.get(\"change_type\", \"unknown\")\n        mod = c.get(\"modifier\", \"unknown\")\n        verified = \"✅\" if c.get(\"verified\") else \"❌\" if c.get(\"is_critical\") else \"⚪\"\n        print(f\"    {verified} [{c['timestamp']}] {fname} ({ctype}) - {mod}\")\n\n    print(\"=\"*60 + \"\\n\")\n\n\nif __name__ == \"__main__\":\n    import argparse\n    parser = argparse.ArgumentParser(description=\"交互日志系统\")\n    parser.add_argument(\"cmd\", choices=[\"init\", \"report\", \"verify\", \"history\"],\n                        help=\"命令\")\n    parser.add_argument(\"--file\", help=\"文件路径\")\n    args = parser.parse_args()\n\n    if args.cmd == \"init\":\n        init()\n        print(\"✅ 交互日志系统已初始化\")\n    elif args.cmd == \"report\":\n        report()\n    elif args.cmd == \"verify\":\n        if not args.file:\n            print(\"❌ 需要提供 --file\")\n        else:\n            result = verify_critical_file(args.file)\n            print(json.dumps(result, ensure_ascii=False, indent=2))\n    elif args.cmd == \"history\":\n        if not args.file:\n            print(\"❌ 需要提供 --file\")\n        else:\n            history = get_file_history(args.file)\n            print(json.dumps(history, ensure_ascii=False, indent=2))\n