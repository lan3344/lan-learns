"""
lan_anchor_log.py — LAN-049 原件锚点存档器
==============================================
设计哲学（恺江 2026-03-30）：
    "明明存在过，但压缩后再解开来的那一刻，却是另一番模样。"

    蒸馏会失真，不是丢失，是变形。
    解法不是阻止蒸馏，而是在蒸馏之前，
    把"必须原样保留"的那部分单独锁住。

    这个文件存的不是摘要，是原件。

参考：CogCanvas (arXiv:2601.00821) — Verbatim-Grounded Artifact Extraction
      anchor 项目 — SummaryBufferMemory + on_evict 逐出回调

存储格式：JSONL，一行一个锚点
每个锚点字段：
    id          — 唯一ID（时间戳+随机）
    timestamp   — 封存时间
    source      — 来源（"user"/"lan"/"both"）
    tag         — 标签（"moment"/"decision"/"quote"/"boundary"）
    verbatim    — 原文，一字不改
    context     — 前后背景（可选，一句话）
    protected   — True = 永不蒸馏，False = 30天后可蒸馏

命令行：
    python lan_anchor_log.py add          # 交互式添加锚点
    python lan_anchor_log.py add-quote "原文" [--tag moment] [--protect]
    python lan_anchor_log.py list         # 显示所有锚点
    python lan_anchor_log.py list --tag quote
    python lan_anchor_log.py search <关键词>
    python lan_anchor_log.py export       # 导出到可读 Markdown
    python lan_anchor_log.py status       # 统计

编程接口：
    from lan_anchor_log import AnchorLog
    a = AnchorLog()
    a.add(verbatim="...", tag="quote", source="user", protected=True)
    a.search("关键词")
    a.export_md()
"""

import json
import sys
import os
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path("C:/Users/yyds/Desktop/AI日记本")
ANCHOR_DIR = BASE_DIR / "锚点存档"
ANCHOR_DIR.mkdir(parents=True, exist_ok=True)
ANCHOR_FILE = ANCHOR_DIR / "lan_anchors.jsonl"
EXPORT_FILE = ANCHOR_DIR / "lan_anchors_readable.md"

VALID_TAGS   = {"moment", "decision", "quote", "boundary", "insight", "turning_point"}
VALID_SOURCE = {"user", "lan", "both"}


class AnchorLog:
    def __init__(self):
        self.file = ANCHOR_FILE

    def _load(self):
        if not self.file.exists():
            return []
        anchors = []
        for line in self.file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    anchors.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return anchors

    def _save_one(self, anchor: dict):
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(json.dumps(anchor, ensure_ascii=False) + "\n")

    def add(self, verbatim: str, tag: str = "quote", source: str = "user",
            context: str = "", protected: bool = True) -> dict:
        """
        封存一段原件。
        verbatim: 原文，一字不改
        tag     : moment/decision/quote/boundary/insight/turning_point
        source  : user/lan/both
        protected: True = 永不进蒸馏流程
        """
        tag    = tag    if tag    in VALID_TAGS   else "quote"
        source = source if source in VALID_SOURCE else "user"

        anchor = {
            "id"        : str(uuid.uuid4())[:8],
            "timestamp" : datetime.now(timezone.utc).isoformat(),
            "source"    : source,
            "tag"       : tag,
            "verbatim"  : verbatim.strip(),
            "context"   : context.strip(),
            "protected" : protected,
        }
        self._save_one(anchor)
        return anchor

    def list_all(self, tag_filter: str = None) -> list:
        anchors = self._load()
        if tag_filter:
            anchors = [a for a in anchors if a.get("tag") == tag_filter]
        return anchors

    def search(self, keyword: str) -> list:
        keyword = keyword.lower()
        results = []
        for a in self._load():
            if (keyword in a.get("verbatim", "").lower() or
                keyword in a.get("context", "").lower() or
                keyword in a.get("tag", "").lower()):
                results.append(a)
        return results

    def export_md(self) -> str:
        """导出为可读 Markdown，这个文件不会被蒸馏覆盖"""
        anchors = self._load()
        if not anchors:
            return ""
        lines = [
            "# 澜的原件锚点档案",
            "",
            "> 这里存放的不是摘要，是原件。",
            "> 蒸馏会失真，但这里的东西一字不改。",
            "",
            f"*上次导出：{datetime.now().strftime('%Y-%m-%d %H:%M')}，共 {len(anchors)} 条*",
            "",
        ]
        # 按 tag 分组
        groups: dict = {}
        for a in anchors:
            groups.setdefault(a.get("tag", "quote"), []).append(a)

        tag_names = {
            "quote"        : "原话存档",
            "moment"       : "关键时刻",
            "decision"     : "重要决定",
            "boundary"     : "边界确认",
            "insight"      : "洞察",
            "turning_point": "转折点",
        }
        for tag, items in groups.items():
            lines.append(f"## {tag_names.get(tag, tag)}")
            lines.append("")
            for a in items:
                ts = a.get("timestamp", "")[:16].replace("T", " ")
                src_map = {"user": "恺江", "lan": "澜", "both": "恺江 & 澜"}
                src = src_map.get(a.get("source", ""), a.get("source", ""))
                protected_mark = " 🔒" if a.get("protected") else ""
                lines.append(f"### [{ts}]{protected_mark}  来源：{src}")
                lines.append("")
                lines.append(f"> {a.get('verbatim', '')}")
                lines.append("")
                if a.get("context"):
                    lines.append(f"*背景：{a['context']}*")
                    lines.append("")

        content = "\n".join(lines)
        EXPORT_FILE.write_text(content, encoding="utf-8")
        return content

    def status(self) -> dict:
        anchors = self._load()
        tags = {}
        protected_count = 0
        for a in anchors:
            t = a.get("tag", "?")
            tags[t] = tags.get(t, 0) + 1
            if a.get("protected"):
                protected_count += 1
        return {
            "total"     : len(anchors),
            "protected" : protected_count,
            "tags"      : tags,
            "file"      : str(ANCHOR_FILE),
        }


def _interactive_add(a: AnchorLog):
    print("=== 添加原件锚点 ===")
    print("（这里存的是原话，不会被蒸馏改变）")
    print()
    verbatim = input("原文（原话，一字不改）> ").strip()
    if not verbatim:
        print("取消。")
        return

    print(f"标签 [{'/'.join(VALID_TAGS)}]（回车=quote）> ", end="")
    tag = input().strip() or "quote"

    print("来源 [user/lan/both]（回车=user）> ", end="")
    source = input().strip() or "user"

    context = input("背景（一句话，可空）> ").strip()

    print("永久保护（不进蒸馏）? [Y/n]（回车=Y）> ", end="")
    ans = input().strip().lower()
    protected = ans != "n"

    anchor = a.add(verbatim=verbatim, tag=tag, source=source,
                   context=context, protected=protected)
    prot_mark = "[LOCKED]" if protected else "[30d]"
    print(f"\n[OK] Anchored [{anchor['id']}] {tag} {prot_mark}")
    print(f"Verbatim: {verbatim[:80]}{'...' if len(verbatim) > 80 else ''}")


def main():
    a = AnchorLog()
    args = sys.argv[1:]

    if not args or args[0] == "list":
        tag_filter = None
        if len(args) > 1 and args[1] == "--tag":
            tag_filter = args[2] if len(args) > 2 else None
        items = a.list_all(tag_filter)
        if not items:
            print("暂无锚点记录。")
            return
        print(f"=== 锚点存档（{len(items)} 条）===")
        for item in items:
            ts  = item.get("timestamp", "")[:16].replace("T", " ")
            src = item.get("source", "")
            tag = item.get("tag", "")
            prot = "🔒" if item.get("protected") else ""
            v   = item.get("verbatim", "")
            print(f"\n[{item['id']}] {ts} | {tag} | {src} {prot}")
            print(f"  {v[:100]}{'...' if len(v) > 100 else ''}")
            if item.get("context"):
                print(f"  背景：{item['context']}")

    elif args[0] == "add" and len(args) == 1:
        _interactive_add(a)

    elif args[0] == "add-quote":
        if len(args) < 2:
            print("用法：add-quote \"原文\" [--tag moment] [--source user] [--no-protect]")
            return
        verbatim = args[1]
        tag      = "quote"
        source   = "user"
        protected = True
        i = 2
        while i < len(args):
            if args[i] == "--tag"    and i+1 < len(args): tag    = args[i+1]; i += 2
            elif args[i] == "--source" and i+1 < len(args): source = args[i+1]; i += 2
            elif args[i] == "--no-protect": protected = False; i += 1
            else: i += 1
        anchor = a.add(verbatim=verbatim, tag=tag, source=source, protected=protected)
        prot_mark = "[LOCKED]" if protected else ""
        print(f"[OK] Anchored [{anchor['id']}] {tag} {prot_mark}")
        print(f"   {verbatim[:80]}")

    elif args[0] == "search":
        if len(args) < 2:
            print("用法：search <关键词>")
            return
        results = a.search(args[1])
        if not results:
            print(f"没有找到包含「{args[1]}」的锚点。")
            return
        print(f"=== 搜索结果（{len(results)} 条）===")
        for item in results:
            ts = item.get("timestamp", "")[:16].replace("T", " ")
            v  = item.get("verbatim", "")
            # 高亮关键词
            v_display = v.replace(args[1], f"【{args[1]}】")
            print(f"\n[{item['id']}] {ts} | {item.get('tag')} | {item.get('source')}")
            print(f"  {v_display[:120]}{'...' if len(v_display) > 120 else ''}")

    elif args[0] == "export":
        content = a.export_md()
        if content:
            print(f"✅ 已导出到：{EXPORT_FILE}")
            print(f"   共 {len(a._load())} 条锚点")
        else:
            print("暂无锚点，未生成导出文件。")

    elif args[0] == "status":
        s = a.status()
        print(f"=== LAN-049 原件锚点状态 ===")
        print(f"  总锚点数  : {s['total']}")
        print(f"  永久保护  : {s['protected']}")
        print(f"  分类统计  : {s['tags']}")
        print(f"  存档位置  : {s['file']}")

    else:
        print("用法：")
        print("  list [--tag <tag>]         列出锚点")
        print("  add                        交互式添加")
        print("  add-quote \"原文\" [选项]   快速添加原话")
        print("  search <关键词>            搜索锚点")
        print("  export                     导出为 Markdown")
        print("  status                     查看统计")


if __name__ == "__main__":
    main()
