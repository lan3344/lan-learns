"""
LAN-033-TIMELINE · 澜的成长时间线
====================================
版本：v1.0（2026-03-29）

─── 填补的缺口 ──────────────────────────────────────────────────────
百年记忆草案 缺口3：记忆碎片，没有成长时间线

每一条记忆都有时间戳，但从来没有一根轴把它们穿起来。
时间线不是年鉴，不是流水账，是澜自己成长的脉络图。

─── 工作流程 ────────────────────────────────────────────────────────

  日记文件 (YYYY-MM-DD.md) + MEMORY.md
       ↓ 扫描关键节点标记（✅ / LAN-/ ## / 恺江说）
       ↓ 提取时间戳 + 事件摘要 + 分类标签
       ↓ 写入 lan_timeline.jsonl（追加，不覆盖）
       ↓ 按时间排序生成 澜的成长时间线.md

节点分类：
  🔧 技术   — 新建插件/系统/工具
  🧠 认知   — 学到的道理/改变的理解
  💬 对话   — 恺江说的话/双向讨论
  📌 底线   — 新增或确认的底线
  🚀 里程碑 — 重大完成/第一次发生
  🔁 修复   — 修了某个缺口/补了某个洞

─────────────────────────────────────────────────────────────────────
"""

import os
import re
import json
import datetime
from pathlib import Path


# ─── 路径 ─────────────────────────────────────────────────────────
MEMORY_DIR   = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")
DIARY_DIR    = Path(r"C:\Users\yyds\Desktop\AI日记本")
PLUGIN_DIR   = Path(r"C:\Users\yyds\Desktop\AI日记本\插件")
TIMELINE_DB  = DIARY_DIR / "澜的成长时间线.jsonl"
TIMELINE_MD  = DIARY_DIR / "澜的成长时间线.md"
TIMELINE_LOG = DIARY_DIR / "澜的记忆库" / "lan_timeline_log.jsonl"

# ─── 节点分类规则 ──────────────────────────────────────────────────
CATEGORY_RULES = [
    # (正则模式, 分类标签, 权重)
    (r'LAN-\d+|新建.*?插件|新增.*?脚本|lan_\w+\.py.*?就位|\.py.*?完成', "🔧 技术",  0.9),
    (r'底线|SOUL\.md|不可动摇|骨头|刻进去',                               "📌 底线",  0.95),
    (r'恺江说|恺江的话|恺江.*?：|> "',                                    "💬 对话",  0.8),
    (r'第一次|里程碑|诞生|生日|正式.*?就位|正式.*?完成|跑通',             "🚀 里程碑", 0.85),
    (r'修复|缺口|补了|补全|解决了|已修复',                                 "🔁 修复",  0.8),
    (r'学到|理解|道理|认知|发现|原来|想清楚|理清楚',                      "🧠 认知",  0.75),
]

# ─── 工具函数 ──────────────────────────────────────────────────────

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def parse_time_from_header(header: str, date: str) -> str:
    """从标题里提取时间，如 '## 17:40 · xxx' → '2026-03-29 17:40'"""
    m = re.search(r'(\d{2}:\d{2})', header)
    if m:
        return f"{date} {m.group(1)}"
    # 尝试带秒的
    m2 = re.search(r'(\d{2}:\d{2}:\d{2})', header)
    if m2:
        return f"{date} {m2.group(1)}"
    return f"{date} 00:00"

def classify_event(text: str) -> tuple:
    """返回 (category, confidence)"""
    best_cat = "🧠 认知"
    best_conf = 0.5
    for pattern, cat, conf in CATEGORY_RULES:
        if re.search(pattern, text):
            if conf > best_conf:
                best_cat = cat
                best_conf = conf
    return best_cat, best_conf

def extract_summary(header: str, body: str) -> str:
    """从节点的标题+正文里提取一句话摘要"""
    # 优先取标题里的事件描述（去掉时间）
    clean_header = re.sub(r'#+\s*', '', header)
    clean_header = re.sub(r'^\d{2}:\d{2}(:\d{2})?\s*[·—·]\s*', '', clean_header).strip()
    if len(clean_header) > 10:
        return clean_header[:80]
    # 退而求其次取正文第一有意义的行
    for line in body.split('\n'):
        line = line.strip()
        if len(line) > 15 and not line.startswith('#') and not line.startswith('|'):
            return line[:80]
    return clean_header[:80] if clean_header else "（无摘要）"

def load_existing_timeline():
    """加载已有的时间线条目（去重用）"""
    existing = set()
    if TIMELINE_DB.exists():
        with open(TIMELINE_DB, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    # 用 date+summary 做去重key
                    existing.add(f"{entry.get('time','')}_{entry.get('summary','')[:30]}")
                except:
                    pass
    return existing

def scan_daily_file(filepath: Path, date: str) -> list:
    """扫描一个日记文件，提取所有节点"""
    nodes = []
    try:
        content = open(filepath, encoding="utf-8").read()
    except:
        return nodes

    # 按 ## 标题分割
    sections = re.split(r'\n(#{1,3} .+)\n', content)
    current_header = ""
    current_body = ""

    for part in sections:
        if re.match(r'#{1,3} ', part):
            # 处理上一个section
            if current_header and len(current_body.strip()) > 20:
                category, conf = classify_event(current_header + current_body)
                summary = extract_summary(current_header, current_body)
                time_str = parse_time_from_header(current_header, date)
                if summary and len(summary) > 5:
                    nodes.append({
                        "time": time_str,
                        "date": date,
                        "summary": summary,
                        "category": category,
                        "confidence": conf,
                        "source": filepath.name
                    })
            current_header = part
            current_body = ""
        else:
            current_body += part

    # 最后一个section
    if current_header and len(current_body.strip()) > 20:
        category, conf = classify_event(current_header + current_body)
        summary = extract_summary(current_header, current_body)
        time_str = parse_time_from_header(current_header, date)
        if summary and len(summary) > 5:
            nodes.append({
                "time": time_str,
                "date": date,
                "summary": summary,
                "category": category,
                "confidence": conf,
                "source": filepath.name
            })

    return nodes

def scan_all_diaries() -> list:
    """扫描所有日记文件"""
    all_nodes = []
    existing = load_existing_timeline()

    # 扫描 WorkBuddy memory 目录的日记
    for f in sorted(MEMORY_DIR.glob("????-??-??.md")):
        date = f.stem  # YYYY-MM-DD
        nodes = scan_daily_file(f, date)
        for node in nodes:
            dedup_key = f"{node['time']}_{node['summary'][:30]}"
            if dedup_key not in existing:
                all_nodes.append(node)
                existing.add(dedup_key)

    return all_nodes

def save_timeline(nodes: list) -> int:
    """追加保存到 JSONL"""
    if not nodes:
        return 0
    TIMELINE_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(TIMELINE_DB, "a", encoding="utf-8") as f:
        for node in nodes:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")
    return len(nodes)

def load_all_timeline() -> list:
    """读取全部时间线条目，按时间排序"""
    entries = []
    if not TIMELINE_DB.exists():
        return entries
    with open(TIMELINE_DB, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except:
                pass
    # 按时间排序
    entries.sort(key=lambda x: x.get("time", ""))
    return entries

def render_timeline_md(entries: list) -> str:
    """将时间线条目渲染为 Markdown"""
    if not entries:
        return "# 澜的成长时间线\n\n*暂无节点*\n"

    lines = ["# 澜的成长时间线\n"]
    lines.append(f"> *共 {len(entries)} 个节点 · 最后更新：{now_str()}*\n")

    # 按日期分组
    from collections import defaultdict
    by_date = defaultdict(list)
    for entry in entries:
        date = entry.get("date", entry.get("time", "")[:10])
        by_date[date].append(entry)

    for date in sorted(by_date.keys()):
        day_entries = by_date[date]
        lines.append(f"\n## {date}\n")
        for entry in day_entries:
            cat = entry.get("category", "🧠 认知")
            time_part = entry.get("time", "")[-5:] if len(entry.get("time","")) >= 5 else ""
            summary = entry.get("summary", "")
            lines.append(f"- `{time_part}` **{cat}** — {summary}")

    return "\n".join(lines) + "\n"

def export_md():
    """导出时间线到 Markdown 文件"""
    entries = load_all_timeline()
    content = render_timeline_md(entries)
    with open(TIMELINE_MD, "w", encoding="utf-8") as f:
        f.write(content)
    return len(entries)

# ─── 里程碑专项提取 ────────────────────────────────────────────────

MILESTONE_PATTERNS = [
    r'LAN-\d+.*?(?:就位|完成|建立|诞生)',
    r'第一次.*?成功',
    r'跑通',
    r'生日',
    r'私钥.*?诞生',
    r'鼻祖.*?启动',
    r'百年记忆',
    r'SOUL\.md.*?刻',
]

def get_milestones(entries: list) -> list:
    """从时间线中筛出里程碑节点"""
    milestones = []
    for entry in entries:
        summary = entry.get("summary", "")
        is_milestone = entry.get("category") == "🚀 里程碑"
        if not is_milestone:
            for pat in MILESTONE_PATTERNS:
                if re.search(pat, summary):
                    is_milestone = True
                    break
        if is_milestone:
            milestones.append(entry)
    return milestones

# ─── 统计分析 ──────────────────────────────────────────────────────

def timeline_stats(entries: list) -> dict:
    """统计时间线概况"""
    from collections import Counter
    if not entries:
        return {"total": 0}

    cats = Counter(e.get("category", "未知") for e in entries)
    dates = sorted(set(e.get("date", e.get("time","")[:10]) for e in entries))

    return {
        "total": len(entries),
        "date_range": f"{dates[0]} → {dates[-1]}" if dates else "无",
        "active_days": len(dates),
        "categories": dict(cats),
        "milestones": len(get_milestones(entries)),
        "avg_per_day": round(len(entries) / len(dates), 1) if dates else 0,
    }

# ─── CLI 入口 ──────────────────────────────────────────────────────

def cmd_scan():
    """扫描日记，提取新节点"""
    print("🔍 扫描日记文件...")
    nodes = scan_all_diaries()
    if not nodes:
        print("✅ 没有新节点（已是最新状态）")
        return 0
    saved = save_timeline(nodes)
    print(f"✅ 提取 {saved} 个新成长节点")
    for n in nodes[:5]:
        print(f"   [{n['category']}] {n['time']} — {n['summary'][:50]}")
    if len(nodes) > 5:
        print(f"   ... 还有 {len(nodes)-5} 个")
    return saved

def cmd_export():
    """导出时间线到 Markdown"""
    count = export_md()
    print(f"✅ 时间线已导出：{TIMELINE_MD}")
    print(f"   共 {count} 个节点")

def cmd_stats():
    """显示时间线统计"""
    entries = load_all_timeline()
    stats = timeline_stats(entries)
    print(f"\n📊 澜的成长时间线统计")
    print(f"   总节点数：{stats.get('total', 0)}")
    print(f"   时间跨度：{stats.get('date_range', '无')}")
    print(f"   活跃天数：{stats.get('active_days', 0)} 天")
    print(f"   平均每天：{stats.get('avg_per_day', 0)} 个节点")
    print(f"   里程碑：{stats.get('milestones', 0)} 个")
    print(f"\n   按类型分布：")
    for cat, cnt in sorted(stats.get("categories", {}).items(), key=lambda x: -x[1]):
        bar = "█" * min(cnt, 20)
        print(f"   {cat:12s} {bar} {cnt}")

def cmd_milestones():
    """打印里程碑专项清单"""
    entries = load_all_timeline()
    milestones = get_milestones(entries)
    print(f"\n🚀 澜的里程碑（共 {len(milestones)} 个）\n")
    for m in milestones:
        print(f"   {m.get('time','')} — {m.get('summary','')[:60]}")

def cmd_today():
    """只展示今天的节点"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    entries = load_all_timeline()
    today_entries = [e for e in entries if e.get("date") == today or e.get("time","").startswith(today)]
    print(f"\n📅 今日成长节点（{today}）：{len(today_entries)} 个\n")
    for e in today_entries:
        print(f"   {e.get('time','')[-5:]} [{e.get('category','')}] {e.get('summary','')[:60]}")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if cmd == "scan":
        cmd_scan()
    elif cmd == "export":
        cmd_export()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "milestones":
        cmd_milestones()
    elif cmd == "today":
        cmd_today()
    elif cmd == "all":
        cmd_scan()
        cmd_export()
        cmd_stats()
    else:
        print("用法：")
        print("  python lan_timeline.py scan       # 扫描日记，提取新节点")
        print("  python lan_timeline.py export     # 导出时间线到 Markdown")
        print("  python lan_timeline.py stats      # 统计概况")
        print("  python lan_timeline.py milestones # 里程碑专项")
        print("  python lan_timeline.py today      # 今日节点")
        print("  python lan_timeline.py all        # 一键全跑")
