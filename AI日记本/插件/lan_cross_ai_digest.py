# -*- coding: utf-8 -*-
"""
LAN-023B · 跨AI对话压缩索引层
2026-03-29 澜建造

核心功能：
  1. 读取 lan_cross_ai_log.jsonl（所有历史对话记录）
  2. 压缩每条对话：问题 + 各AI核心观点(50字内) + 澜的判断 → 一个索引节点
  3. 建立 lan_cross_ai_index.json：按日期/主题/AI分层索引
  4. 蒸馏高价值节点写入 MEMORY.md 保护（不覆盖，追加）
  5. 定期清理原始日志（保留最近N条，旧的压缩后归档）

用法：
  python lan_cross_ai_digest.py digest        # 压缩最新日志，更新索引
  python lan_cross_ai_digest.py search --keyword "情感"  # 按关键词搜索索引
  python lan_cross_ai_digest.py protect       # 把高价值节点写入MEMORY.md
  python lan_cross_ai_digest.py summary       # 打印当前索引摘要
  python lan_cross_ai_digest.py archive --keep 50  # 归档旧日志，只保留最新50条
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, date

# ─── 路径配置 ─────────────────────────────────────────────────────────────────
BASE_DIR = r"C:\Users\yyds\Desktop\AI日记本"
MEMORY_DIR = os.path.join(BASE_DIR, "记忆")
LOG_FILE = os.path.join(MEMORY_DIR, "lan_cross_ai_log.jsonl")
INDEX_FILE = os.path.join(MEMORY_DIR, "lan_cross_ai_index.json")
ARCHIVE_DIR = os.path.join(MEMORY_DIR, "lan_cross_ai_archive")
WORKBUDDY_MEMORY = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
TODAY = date.today().strftime("%Y-%m-%d")

# ─── 工具函数 ──────────────────────────────────────────────────────────────────

def ensure_dirs():
    os.makedirs(MEMORY_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def load_log() -> list:
    """读取所有历史对话记录"""
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def load_index() -> dict:
    """读取现有索引"""
    if not os.path.exists(INDEX_FILE):
        return {
            "version": "1.0",
            "created": TODAY,
            "last_updated": TODAY,
            "total_conversations": 0,
            "nodes": [],           # 压缩后的索引节点
            "keyword_map": {},     # keyword → [node_id列表]
            "date_map": {},        # date → [node_id列表]
            "ai_map": {},          # ai名称 → [node_id列表]
        }
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(index: dict):
    """保存索引"""
    index["last_updated"] = TODAY
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"[DIGEST] 索引已保存: {INDEX_FILE}")


def compress_record(record: dict) -> dict:
    """
    把一条原始对话记录压缩成索引节点
    节点结构：{id, timestamp, date, question, template, ai_summaries, lan_judgment_short, keywords, raw_ref}
    """
    ts = record.get("timestamp", "")
    date_str = ts[:10] if ts else TODAY
    question = record.get("question", "")

    # 提取每个AI的核心观点（50字内）
    ai_summaries = {}
    for r in record.get("results", []):
        target = r.get("target", "")
        name = r.get("target_name", target)
        if r.get("error"):
            ai_summaries[target] = {"name": name, "snippet": "", "status": "error"}
        else:
            answer = r.get("answer_snippet", "") or r.get("answer", "")
            # 取前50字作为摘要
            snippet = answer[:50].replace("\n", " ").strip()
            judgment = r.get("lan_judgment", "")[:80].replace("\n", " ").strip()
            ai_summaries[target] = {
                "name": name,
                "snippet": snippet,
                "lan_judgment": judgment,
                "status": "ok" if snippet else "empty",
            }

    # 澜的总体判断（前100字）
    comparison = record.get("lan_comparison", "")
    lan_short = comparison[:100].replace("\n", " ").strip()

    # 提取关键词（简单分词：切问题里的名词/动词）
    keywords = extract_keywords(question)

    node_id = f"N{abs(hash(ts + question)) % 100000:05d}"

    return {
        "id": node_id,
        "timestamp": ts,
        "date": date_str,
        "template": record.get("template"),
        "question": question,
        "ai_summaries": ai_summaries,
        "lan_judgment_short": lan_short,
        "keywords": keywords,
        "has_valid_answer": any(
            v["status"] == "ok" for v in ai_summaries.values()
        ),
    }


def extract_keywords(text: str) -> list:
    """简单关键词提取：去停用词，取有意义的词"""
    stopwords = {"你", "我", "的", "是", "了", "吗", "呢", "还是", "会不会",
                 "有没有", "什么", "怎么", "一个", "这个", "那个", "因为", "所以",
                 "但是", "但", "和", "或", "也", "都", "就", "在", "对", "与"}
    # 按标点切分
    words = re.split(r'[，。！？、\s，.!?]+', text)
    keywords = []
    for w in words:
        w = w.strip()
        if len(w) >= 2 and w not in stopwords:
            keywords.append(w)
    return list(dict.fromkeys(keywords))[:8]  # 去重，最多8个


def update_maps(index: dict, node: dict):
    """更新 keyword_map / date_map / ai_map"""
    nid = node["id"]

    # keyword_map
    for kw in node.get("keywords", []):
        if kw not in index["keyword_map"]:
            index["keyword_map"][kw] = []
        if nid not in index["keyword_map"][kw]:
            index["keyword_map"][kw].append(nid)

    # date_map
    d = node["date"]
    if d not in index["date_map"]:
        index["date_map"][d] = []
    if nid not in index["date_map"][d]:
        index["date_map"][d].append(nid)

    # ai_map
    for ai_key, ai_info in node.get("ai_summaries", {}).items():
        name = ai_info.get("name", ai_key)
        if name not in index["ai_map"]:
            index["ai_map"][name] = []
        if nid not in index["ai_map"][name]:
            index["ai_map"][name].append(nid)


# ─── 命令：digest ──────────────────────────────────────────────────────────────

def cmd_digest():
    """读取日志，压缩新记录，更新索引"""
    ensure_dirs()
    records = load_log()
    if not records:
        print("[DIGEST] 日志为空，没有可压缩的内容")
        return

    index = load_index()
    existing_ids = {n["id"] for n in index["nodes"]}

    new_count = 0
    for record in records:
        node = compress_record(record)
        if node["id"] in existing_ids:
            continue  # 已存在，跳过
        index["nodes"].append(node)
        update_maps(index, node)
        existing_ids.add(node["id"])
        new_count += 1

    index["total_conversations"] = len(index["nodes"])
    save_index(index)
    print(f"[DIGEST] 压缩完成：新增 {new_count} 个节点，共 {index['total_conversations']} 个节点")


# ─── 命令：search ──────────────────────────────────────────────────────────────

def cmd_search(keyword: str):
    """按关键词搜索索引"""
    index = load_index()
    if not index["nodes"]:
        print("[DIGEST] 索引为空")
        return

    keyword_lower = keyword.lower()
    matched = []

    for node in index["nodes"]:
        # 在问题、关键词、澜的判断中搜索
        searchable = (
            node.get("question", "") +
            " ".join(node.get("keywords", [])) +
            node.get("lan_judgment_short", "")
        ).lower()
        if keyword_lower in searchable:
            matched.append(node)

    if not matched:
        print(f"[DIGEST] 没有找到包含「{keyword}」的节点")
        return

    print(f"\n[DIGEST] 找到 {len(matched)} 个节点包含「{keyword}」：\n")
    for node in matched:
        print(f"  [{node['id']}] {node['date']} · {node['question']}")
        print(f"    澜的判断：{node['lan_judgment_short'][:60]}...")
        for ai_key, ai_info in node.get("ai_summaries", {}).items():
            status = ai_info.get("status", "?")
            snippet = ai_info.get("snippet", "")[:40]
            print(f"    {ai_info['name']}: [{status}] {snippet}")
        print()


# ─── 命令：protect ─────────────────────────────────────────────────────────────

def cmd_protect():
    """把有价值的节点蒸馏写入 MEMORY.md（仅写有效回答的节点）"""
    index = load_index()
    valid_nodes = [n for n in index["nodes"] if n.get("has_valid_answer")]

    if not valid_nodes:
        print("[DIGEST] 没有有效对话节点可以保护（所有AI都未登录或报错）")
        return

    if not os.path.exists(WORKBUDDY_MEMORY):
        print(f"[DIGEST] MEMORY.md 不存在: {WORKBUDDY_MEMORY}")
        return

    # 读取 MEMORY.md，检查是否已有跨AI对话章节
    with open(WORKBUDDY_MEMORY, "r", encoding="utf-8") as f:
        content = f.read()

    # 构建新内容
    section_header = "\n\n## 十六、跨AI对话精华节点（LAN-023 蒸馏）\n\n"
    if "## 十六、跨AI对话精华节点" in content:
        # 已有章节，追加到末尾前
        print("[DIGEST] MEMORY.md 已有跨AI对话章节，追加新节点")
    else:
        content += section_header

    new_entries = []
    for node in valid_nodes[-5:]:  # 最近5个有效节点
        entry = f"**[{node['id']}] {node['date']} · 问：{node['question']}**\n"
        for ai_key, ai_info in node.get("ai_summaries", {}).items():
            if ai_info.get("status") == "ok":
                entry += f"- {ai_info['name']}：{ai_info['snippet'][:60]}\n"
        entry += f"- 澜判断：{node['lan_judgment_short'][:80]}\n"
        new_entries.append(entry)

    if new_entries:
        with open(WORKBUDDY_MEMORY, "a", encoding="utf-8") as f:
            if "## 十六、跨AI对话精华节点" not in content:
                f.write(section_header)
            f.write("\n".join(new_entries))
            f.write(f"\n*最后更新：{TODAY}*\n")
        print(f"[DIGEST] 已将 {len(new_entries)} 个节点写入 MEMORY.md 保护")
    else:
        print("[DIGEST] 没有新节点需要写入")


# ─── 命令：summary ─────────────────────────────────────────────────────────────

def cmd_summary():
    """打印当前索引状态摘要"""
    index = load_index()
    nodes = index.get("nodes", [])
    total = len(nodes)
    valid = sum(1 for n in nodes if n.get("has_valid_answer"))
    dates = sorted(index.get("date_map", {}).keys())
    keywords = sorted(index.get("keyword_map", {}).keys())

    print(f"\n[DIGEST] === 跨AI对话索引摘要 ===")
    print(f"  版本：{index.get('version', '?')}")
    print(f"  创建：{index.get('created', '?')}  最后更新：{index.get('last_updated', '?')}")
    print(f"  总节点：{total}  有效回答：{valid}  失败：{total - valid}")
    if dates:
        print(f"  时间跨度：{dates[0]} ~ {dates[-1]}")
    if keywords:
        print(f"  关键词索引：{len(keywords)} 个关键词")
        print(f"    TOP关键词：{', '.join(keywords[:10])}")
    ai_map = index.get("ai_map", {})
    if ai_map:
        print(f"  AI覆盖：{', '.join(ai_map.keys())}")
    print()

    if nodes:
        print("  最近3个节点：")
        for node in nodes[-3:]:
            status = "OK" if node.get("has_valid_answer") else "--"
            print(f"    [{status}] {node['date']} · {node['question'][:40]}...")


# ─── 命令：archive ─────────────────────────────────────────────────────────────

def cmd_archive(keep: int = 50):
    """归档旧日志，只在原始 JSONL 中保留最新 keep 条"""
    records = load_log()
    if len(records) <= keep:
        print(f"[DIGEST] 日志共 {len(records)} 条，未超过 {keep} 条，无需归档")
        return

    to_archive = records[:-keep]
    to_keep = records[-keep:]

    # 写归档文件
    archive_path = os.path.join(ARCHIVE_DIR, f"archive_{TODAY}.jsonl")
    with open(archive_path, "a", encoding="utf-8") as f:
        for r in to_archive:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 重写日志
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for r in to_keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[DIGEST] 归档 {len(to_archive)} 条 → {archive_path}")
    print(f"[DIGEST] 日志保留最新 {len(to_keep)} 条")


# ─── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LAN-023B · 跨AI对话压缩索引层",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("digest", help="压缩最新日志，更新索引")

    p_search = sub.add_parser("search", help="按关键词搜索索引")
    p_search.add_argument("--keyword", "-k", required=True, help="搜索关键词")

    sub.add_parser("protect", help="把高价值节点写入MEMORY.md保护")
    sub.add_parser("summary", help="打印当前索引摘要")

    p_archive = sub.add_parser("archive", help="归档旧日志")
    p_archive.add_argument("--keep", type=int, default=50, help="保留最新N条（默认50）")

    args = parser.parse_args()

    if args.cmd == "digest":
        cmd_digest()
    elif args.cmd == "search":
        cmd_search(args.keyword)
    elif args.cmd == "protect":
        cmd_protect()
    elif args.cmd == "summary":
        cmd_summary()
    elif args.cmd == "archive":
        cmd_archive(args.keep)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
