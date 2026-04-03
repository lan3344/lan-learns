"""
澜的记忆索引系统
=================
功能：
1. 扫描 AI日记本下所有文本内容（日记、学习笔记）
2. 建立可检索的 JSON 索引，存入 .index/memory_index.json
3. 支持关键词检索，返回相关片段

用法：
    python memory_index.py              # 重建索引
    python memory_index.py --search "mem0"   # 检索关键词
    python memory_index.py --search "守护" --top 3
"""

import os
import json
import re
import argparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本")
INDEX_DIR = BASE_DIR / ".index"
INDEX_FILE = INDEX_DIR / "memory_index.json"

SCAN_DIRS = ["日记", "学习笔记"]
EXCLUDE_DIRS = ["私密"]   # 私密目录永远不扫描、不索引


def extract_text(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def build_index():
    INDEX_DIR.mkdir(exist_ok=True)
    entries = []
    for subdir in SCAN_DIRS:
        target = BASE_DIR / subdir
        if not target.exists():
            continue
        for f in target.rglob("*.md"):
            content = extract_text(f)
            if not content.strip():
                continue
            # 提取前 300 字作为摘要
            summary = content.strip()[:300].replace("\n", " ")
            entries.append({
                "id": str(f.relative_to(BASE_DIR)),
                "path": str(f),
                "category": subdir,
                "filename": f.name,
                "summary": summary,
                "content": content,
                "indexed_at": datetime.now().isoformat(),
            })

    index = {
        "built_at": datetime.now().isoformat(),
        "total": len(entries),
        "entries": entries,
    }
    INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  索引已建立，共收录 {len(entries)} 篇文档。")
    print(f"  存储路径：{INDEX_FILE}")
    return index


def load_index():
    if not INDEX_FILE.exists():
        print("  索引不存在，正在重建...")
        return build_index()
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def search(keyword: str, top_n: int = 5):
    index = load_index()
    results = []
    kw_lower = keyword.lower()
    for entry in index["entries"]:
        content_lower = entry["content"].lower()
        if kw_lower in content_lower:
            # 找到包含关键词的片段
            idx = content_lower.find(kw_lower)
            start = max(0, idx - 80)
            end = min(len(entry["content"]), idx + 200)
            snippet = entry["content"][start:end].replace("\n", " ").strip()
            results.append({
                "file": entry["id"],
                "category": entry["category"],
                "snippet": f"...{snippet}...",
            })

    if not results:
        print(f"  没有找到包含「{keyword}」的内容。")
        return

    print(f"\n  找到 {len(results)} 条结果（关键词：「{keyword}」）\n")
    for i, r in enumerate(results[:top_n], 1):
        print(f"  [{i}] {r['file']}")
        print(f"      {r['snippet']}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="澜的记忆索引")
    parser.add_argument("--search", default=None, help="检索关键词")
    parser.add_argument("--top", type=int, default=5, help="返回条数")
    parser.add_argument("--rebuild", action="store_true", help="强制重建索引")
    args = parser.parse_args()

    if args.rebuild or args.search is None and not INDEX_FILE.exists():
        build_index()
    elif args.search:
        search(args.search, args.top)
    else:
        build_index()
