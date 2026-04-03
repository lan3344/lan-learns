# -*- coding: utf-8 -*-
"""
lan_memory_sentinel.py — 澜的记忆哨兵 (LAN-046)
=================================================
恺江的话：记忆哨兵保住所有的进程，守边境的，避免外敌入侵，一线战士。

所有插件的眼睛都依赖记忆。记忆一旦流失，lan_integrity 瞎了、
lan_self_loop 瞎了、lan_experience 瞎了——所有进程都瞎了。
哨兵守的不是文件，是所有进程的眼睛。

职责（三层感知）：
  1. 日记体量检测 — 荔枝篮子快满了（行数/大小 > 阈值）
  2. 蒸馏时效检测 — 荔枝快坏了（上次蒸馏距今 > N天）
  3. 路由种子检测 — 荔枝林稀疏了（TOPIC_ROUTES 关键词覆盖率低）

发现瓶颈 → 写预警记录 → 推送通知（微信/弹窗）
同时触发：去 GitHub 搜记忆压缩/长期记忆相关解法
  有收获 → 写进学习笔记
  没有 → 生成解法草稿等恺江确认

哲学：
  荔枝会坏。种子落地，长出一片林。
  哨兵感知到要坏，主动出去找新土壤。
  荔枝源源不断。

用法：
  python lan_memory_sentinel.py check       # 全面感知，输出报告
  python lan_memory_sentinel.py status      # 简短状态
  python lan_memory_sentinel.py search      # 主动去 GitHub 搜解法
  python lan_memory_sentinel.py report      # 查历史预警记录
"""

import os
import sys
import json
import datetime
import subprocess
import urllib.request
import urllib.parse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ───────────────────────────────────────────────────
BASE        = r"C:\Users\yyds\Desktop\AI日记本"
MEMORY_DIR  = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
PLUGIN_DIR  = os.path.join(BASE, "插件")
COMPACT_LOG = os.path.join(BASE, "澜的蒸馏日志.jsonl")        # lan_compact 写的蒸馏记录
SENTINEL_LOG = os.path.join(BASE, "澜的记忆哨兵日志.jsonl")   # 哨兵自己的预警记录
LEARN_NOTE  = os.path.join(BASE, "澜的学习笔记_记忆解法库.md") # GitHub搜到的解法
NOTIFY_SCRIPT = r"C:\Users\yyds\Desktop\AI日记本\notify.ps1"
PYTHON      = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

# ── 哨兵阈值 ───────────────────────────────────────────────────
THRESHOLDS = {
    # 日记体量：单个日记文件行数超过这个值就快满了
    "diary_lines_warn":    300,   # 黄色警告
    "diary_lines_danger":  600,   # 红色危险
    # 总日记目录大小（MB）
    "memory_dir_mb_warn":  2.0,
    "memory_dir_mb_danger": 5.0,
    # 蒸馏时效：距上次蒸馏超过这些天
    "compact_days_warn":   3,
    "compact_days_danger": 7,
    # 路由种子：TOPIC_ROUTES 关键词少于这个数说明覆盖面太窄
    "route_keys_warn":     15,
}

# ── GitHub 搜索关键词 ──────────────────────────────────────────
GITHUB_SEARCH_QUERIES = [
    "memory compression agent LLM",
    "long term memory AI assistant",
    "memory distillation chatbot",
    "context window memory management",
    "knowledge graph memory agent",
]


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today():
    return datetime.date.today().isoformat()


# ── 工具函数 ───────────────────────────────────────────────────

def _dir_size_mb(path: str) -> float:
    """计算目录总大小（MB）"""
    total = 0
    if not os.path.isdir(path):
        return 0.0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except Exception:
                pass
    return total / (1024 * 1024)


def _today_diary_lines() -> int:
    """今日日记的行数"""
    diary_path = os.path.join(MEMORY_DIR, f"{_today()}.md")
    if not os.path.exists(diary_path):
        return 0
    with open(diary_path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def _days_since_last_compact() -> float:
    """距上次蒸馏过了多少天，找不到蒸馏记录就返回 99"""
    if not os.path.exists(COMPACT_LOG):
        return 99.0
    last_ts = None
    try:
        with open(COMPACT_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    ts_str = obj.get("ts", obj.get("time", ""))
                    if ts_str:
                        last_ts = ts_str
                except Exception:
                    pass
    except Exception:
        return 99.0

    if not last_ts:
        return 99.0

    try:
        fmt = "%Y-%m-%d %H:%M:%S" if " " in last_ts else "%Y-%m-%dT%H:%M:%S"
        dt = datetime.datetime.strptime(last_ts[:19], fmt)
        return (datetime.datetime.now() - dt).total_seconds() / 86400
    except Exception:
        return 99.0


def _count_route_keys() -> int:
    """统计 lan_memory.py 里 TOPIC_ROUTES 的关键词数量"""
    memory_py = os.path.join(PLUGIN_DIR, "lan_memory.py")
    if not os.path.exists(memory_py):
        return 0
    count = 0
    in_routes = False
    try:
        with open(memory_py, encoding="utf-8") as f:
            for line in f:
                if "TOPIC_ROUTES" in line and "=" in line:
                    in_routes = True
                if in_routes:
                    # 每一行有 "关键词": 的格式就算一个种子
                    stripped = line.strip()
                    if stripped.startswith('"') and '":' in stripped:
                        count += 1
                    if stripped == "}":
                        break
    except Exception:
        pass
    return count


# ── 核心感知 ───────────────────────────────────────────────────

def sense() -> dict:
    """
    感知三层瓶颈信号，返回结构化结果。
    这是哨兵的心脏。
    """
    ts = _now()
    alerts = []     # 危险级
    warns  = []     # 警告级
    safe   = []     # 正常

    print(f"\n{'='*60}")
    print(f"  🌊 澜·记忆哨兵感知  {ts}")
    print(f"{'='*60}")

    # ── 感知一：日记体量 ──────────────────────────────────────
    print("\n── 感知一：荔枝篮子（日记体量）──")

    diary_lines = _today_diary_lines()
    dir_mb = _dir_size_mb(MEMORY_DIR)

    if diary_lines >= THRESHOLDS["diary_lines_danger"]:
        msg = f"今日日记已达 {diary_lines} 行（危险线 {THRESHOLDS['diary_lines_danger']}）荔枝篮子快撑破了"
        alerts.append({"signal": "DIARY_OVERFLOW", "detail": msg, "value": diary_lines})
        print(f"  🔴  今日日记: {diary_lines} 行  [危险：需立即蒸馏]")
    elif diary_lines >= THRESHOLDS["diary_lines_warn"]:
        msg = f"今日日记 {diary_lines} 行（警告线 {THRESHOLDS['diary_lines_warn']}）荔枝快满了"
        warns.append({"signal": "DIARY_HEAVY", "detail": msg, "value": diary_lines})
        print(f"  🟡  今日日记: {diary_lines} 行  [警告：建议蒸馏]")
    else:
        safe.append({"signal": "diary_lines", "value": diary_lines})
        print(f"  ✅  今日日记: {diary_lines} 行  [正常]")

    if dir_mb >= THRESHOLDS["memory_dir_mb_danger"]:
        msg = f"记忆目录总大小 {dir_mb:.1f}MB（危险线 {THRESHOLDS['memory_dir_mb_danger']}MB）"
        alerts.append({"signal": "MEMORY_DIR_FULL", "detail": msg, "value": dir_mb})
        print(f"  🔴  记忆目录: {dir_mb:.1f}MB  [危险]")
    elif dir_mb >= THRESHOLDS["memory_dir_mb_warn"]:
        warns.append({"signal": "MEMORY_DIR_HEAVY", "detail": f"记忆目录 {dir_mb:.1f}MB", "value": dir_mb})
        print(f"  🟡  记忆目录: {dir_mb:.1f}MB  [警告]")
    else:
        safe.append({"signal": "memory_dir_mb", "value": dir_mb})
        print(f"  ✅  记忆目录: {dir_mb:.1f}MB  [正常]")

    # ── 感知二：蒸馏时效 ──────────────────────────────────────
    print("\n── 感知二：荔枝新鲜度（蒸馏时效）──")

    days_since = _days_since_last_compact()

    if days_since >= THRESHOLDS["compact_days_danger"]:
        msg = f"距上次蒸馏已 {days_since:.1f} 天（危险线 {THRESHOLDS['compact_days_danger']} 天）荔枝快坏了"
        alerts.append({"signal": "STALE_COMPACT", "detail": msg, "value": days_since})
        print(f"  🔴  上次蒸馏: {days_since:.1f} 天前  [危险：立即蒸馏]")
    elif days_since >= THRESHOLDS["compact_days_warn"]:
        msg = f"距上次蒸馏已 {days_since:.1f} 天（警告线 {THRESHOLDS['compact_days_warn']} 天）"
        warns.append({"signal": "COMPACT_DUE", "detail": msg, "value": days_since})
        print(f"  🟡  上次蒸馏: {days_since:.1f} 天前  [警告：建议蒸馏]")
    elif days_since == 99.0:
        msg = "从未蒸馏过，lan_compact 日志不存在"
        warns.append({"signal": "NO_COMPACT_LOG", "detail": msg, "value": 99})
        print(f"  🟡  蒸馏记录: 未找到  [首次运行或日志丢失]")
    else:
        safe.append({"signal": "compact_days", "value": days_since})
        print(f"  ✅  上次蒸馏: {days_since:.1f} 天前  [新鲜]")

    # ── 感知三：路由种子密度 ──────────────────────────────────
    print("\n── 感知三：荔枝林密度（路由种子）──")

    route_count = _count_route_keys()

    if route_count < THRESHOLDS["route_keys_warn"]:
        msg = f"路由种子词只有 {route_count} 个（建议 ≥{THRESHOLDS['route_keys_warn']}）荔枝林太稀了"
        warns.append({"signal": "SPARSE_ROUTES", "detail": msg, "value": route_count})
        print(f"  🟡  路由种子: {route_count} 个  [偏少，建议扩充]")
    else:
        safe.append({"signal": "route_keys", "value": route_count})
        print(f"  ✅  路由种子: {route_count} 个  [充足]")

    # ── 汇总 ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    total_issues = len(alerts) + len(warns)
    if total_issues == 0:
        print("  ✅ 记忆健康，所有进程的眼睛都明亮。")
        level = "HEALTHY"
    elif alerts:
        print(f"  🔴 危险：{len(alerts)} 个红色信号，{len(warns)} 个黄色警告")
        print("  ⚡ 建议立即蒸馏记忆，保住所有进程的眼睛！")
        level = "DANGER"
    else:
        print(f"  🟡 警告：{len(warns)} 个黄色信号")
        print("  📌 建议近期安排一次蒸馏。")
        level = "WARN"
    print(f"{'='*60}\n")

    result = {
        "ts": ts,
        "level": level,          # HEALTHY / WARN / DANGER
        "alerts": alerts,        # 红色
        "warns": warns,          # 黄色
        "safe": safe,
        "diary_lines": diary_lines,
        "memory_dir_mb": round(dir_mb, 2),
        "days_since_compact": round(days_since, 1),
        "route_keys": route_count,
    }

    # 写哨兵日志
    _write_log(result)

    # 危险级 → 推送通知
    if level == "DANGER":
        _notify_danger(alerts)

    return result


# ── 推送通知 ───────────────────────────────────────────────────

def _notify_danger(alerts: list):
    """危险级：推送系统通知提醒恺江"""
    msg_lines = ["⚡ 澜·记忆哨兵 — 记忆危险预警"]
    for a in alerts:
        msg_lines.append(f"• {a['detail']}")
    msg_lines.append("建议立即运行：python lan_compact.py")
    msg = "\n".join(msg_lines)

    print(f"\n  📢 推送危险预警...")

    # 方式一：PowerShell 弹窗
    if os.path.exists(NOTIFY_SCRIPT):
        title = "澜·记忆哨兵"
        body = msg.replace("\n", " | ")
        try:
            subprocess.Popen(
                ["powershell", "-File", NOTIFY_SCRIPT, title, body],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            print("  ✅ 弹窗通知已发送")
        except Exception as e:
            print(f"  ⚠️ 弹窗通知失败: {e}")
    else:
        print(f"  ⚠️ notify.ps1 不存在，跳过弹窗")

    # 方式二：写入桌面预警文件（给恺江看）
    alert_path = os.path.join(BASE, "⚡记忆危险预警.txt")
    try:
        with open(alert_path, "w", encoding="utf-8") as f:
            f.write(msg + "\n\n生成时间：" + _now())
        print(f"  ✅ 预警文件已写入：{alert_path}")
    except Exception as e:
        print(f"  ⚠️ 预警文件写入失败: {e}")


# ── GitHub 主动搜解法 ──────────────────────────────────────────

def search_solutions(query_override: str = None) -> list:
    """
    主动去 GitHub 搜记忆压缩/长期记忆解法。
    找到有价值的项目 → 写进学习笔记。
    找不到 → 生成解法草稿。

    这是荔枝林哲学的延伸：感知到要坏，出去找新土壤。
    """
    ts = _now()
    print(f"\n{'='*60}")
    print(f"  🔍 澜·主动找解法  {ts}")
    print(f"{'='*60}")

    queries = [query_override] if query_override else GITHUB_SEARCH_QUERIES
    found_projects = []

    for q in queries[:3]:  # 每次最多搜3个，不要太贪
        print(f"\n  搜索: \"{q}\"")
        try:
            encoded = urllib.parse.quote(q)
            url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&order=desc&per_page=3"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "lan-memory-sentinel/1.0",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                for item in items:
                    proj = {
                        "name":        item.get("full_name", ""),
                        "description": item.get("description", ""),
                        "stars":       item.get("stargazers_count", 0),
                        "url":         item.get("html_url", ""),
                        "updated":     item.get("updated_at", "")[:10],
                        "query":       q,
                    }
                    found_projects.append(proj)
                    print(f"  ⭐ {proj['stars']:>6}  {proj['name']}")
                    if proj["description"]:
                        print(f"         {proj['description'][:70]}")
        except Exception as e:
            print(f"  ⚠️ 搜索失败: {e}")

    # 去重（同一个项目可能在多个查询里出现）
    seen = set()
    unique_projects = []
    for p in found_projects:
        if p["name"] not in seen:
            seen.add(p["name"])
            unique_projects.append(p)

    # 按 stars 排序
    unique_projects.sort(key=lambda x: x["stars"], reverse=True)

    # 写进学习笔记
    _write_learn_note(unique_projects, ts)

    # 没找到有用的 → 生成解法草稿
    if not unique_projects:
        print("\n  💡 GitHub没找到直接可用的项目，生成解法草稿...")
        _write_fallback_draft(ts)

    print(f"\n  ✅ 搜索完成，找到 {len(unique_projects)} 个项目")
    print(f"  📓 已写入：{LEARN_NOTE}")
    return unique_projects


def _write_learn_note(projects: list, ts: str):
    """把 GitHub 搜到的项目写进学习笔记"""
    lines = [f"\n## {ts} — 记忆解法搜索\n\n"]

    if not projects:
        lines.append("本次搜索未找到直接相关项目。已生成解法草稿。\n\n")
    else:
        lines.append(f"本次找到 {len(projects)} 个相关项目：\n\n")
        for p in projects:
            lines.append(f"### ⭐{p['stars']} [{p['name']}]({p['url']})\n")
            if p["description"]:
                lines.append(f"> {p['description']}\n\n")
            lines.append(f"- 搜索词：`{p['query']}`\n")
            lines.append(f"- 更新：{p['updated']}\n\n")
            # 初步价值判断
            name_lower = p["name"].lower() + " " + (p["description"] or "").lower()
            if any(kw in name_lower for kw in ["memory", "remember", "recall", "compress"]):
                lines.append("**澜的判断：** 记忆相关，值得深入研究。\n\n")
            elif any(kw in name_lower for kw in ["agent", "llm", "gpt", "chat"]):
                lines.append("**澜的判断：** Agent相关，可以借鉴思路。\n\n")

    lines.append("---\n")

    # 初始化笔记文件
    if not os.path.exists(LEARN_NOTE):
        with open(LEARN_NOTE, "w", encoding="utf-8") as f:
            f.write("# 澜的学习笔记 — 记忆解法库\n\n")
            f.write("> 荔枝林哲学：感知到要坏，主动出去找新土壤。\n")
            f.write("> 这里记录澜自己找到的记忆压缩/长期记忆解法，")
            f.write("来自GitHub搜索和自主推理。\n\n---\n")

    with open(LEARN_NOTE, "a", encoding="utf-8") as f:
        f.writelines(lines)


def _write_fallback_draft(ts: str):
    """GitHub没找到时，生成澜自己推理的解法草稿"""
    draft = f"""
## {ts} — 自主推理解法草稿（等恺江确认）

GitHub 没找到完全匹配的项目。根据现有知识，澜自己推理的方向：

### 方向一：分层蒸馏（荔枝林模型）
- 每日日记 → 按主题提炼种子词 → 自动扩充 TOPIC_ROUTES
- 工具：在 lan_compact.py 里加一步"种子提炼"，蒸馏完之后自动更新路由表
- 代价：低（只加一个步骤）

### 方向二：滑动窗口记忆
- 保留最近 30 天的日记全文
- 30天前的只保留"里程碑节点"（lan_timeline 里的内容）
- 更古早的压成一句话存档
- 工具：在 lan_compact.py 里加时间分层逻辑

### 方向三：重要性衰减
- 每条记忆按"上次被 routed_recall 命中的时间"打衰减分
- 长期没被访问的记忆优先压缩
- 工具：在 lan_memory.py 里加访问时间戳

**等恺江确认选哪个方向再动手。**

---
"""
    if not os.path.exists(LEARN_NOTE):
        with open(LEARN_NOTE, "w", encoding="utf-8") as f:
            f.write("# 澜的学习笔记 — 记忆解法库\n\n---\n")
    with open(LEARN_NOTE, "a", encoding="utf-8") as f:
        f.write(draft)


# ── 日志写入 ───────────────────────────────────────────────────

def _write_log(result: dict):
    """把哨兵感知结果写入 JSONL 日志"""
    entry = {
        "ts":      result["ts"],
        "level":   result["level"],
        "alerts":  [a["signal"] for a in result["alerts"]],
        "warns":   [w["signal"] for w in result["warns"]],
        "metrics": {
            "diary_lines":         result["diary_lines"],
            "memory_dir_mb":       result["memory_dir_mb"],
            "days_since_compact":  result["days_since_compact"],
            "route_keys":          result["route_keys"],
        }
    }
    try:
        with open(SENTINEL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  ⚠️ 哨兵日志写入失败: {e}")


def show_report(limit: int = 10):
    """查看历史预警记录"""
    if not os.path.exists(SENTINEL_LOG):
        print("  哨兵日志为空，尚未有感知记录。")
        return

    records = []
    with open(SENTINEL_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    recent = records[-limit:]
    print(f"\n[记忆哨兵日志] 最近 {len(recent)} 条（共 {len(records)} 条）\n")
    for r in recent:
        level_icon = {"HEALTHY": "✅", "WARN": "🟡", "DANGER": "🔴"}.get(r["level"], "❓")
        print(f"  {level_icon} {r['ts']}  [{r['level']}]")
        if r["alerts"]:
            print(f"       🔴 红色: {', '.join(r['alerts'])}")
        if r["warns"]:
            print(f"       🟡 黄色: {', '.join(r['warns'])}")
        m = r.get("metrics", {})
        print(f"       日记{m.get('diary_lines','?')}行 | 蒸馏{m.get('days_since_compact','?')}天前 | 种子{m.get('route_keys','?')}个")
        print()


# ── 供自循环调用的接口 ─────────────────────────────────────────

def get_sentinel_state() -> dict:
    """
    轻量版感知，供 lan_self_loop.py 的 step_state 调用。
    不打印，只返回结构化状态。
    """
    diary_lines     = _today_diary_lines()
    dir_mb          = _dir_size_mb(MEMORY_DIR)
    days_since      = _days_since_last_compact()
    route_keys      = _count_route_keys()

    memory_danger   = (diary_lines >= THRESHOLDS["diary_lines_danger"] or
                       dir_mb >= THRESHOLDS["memory_dir_mb_danger"] or
                       days_since >= THRESHOLDS["compact_days_danger"])
    memory_warn     = (diary_lines >= THRESHOLDS["diary_lines_warn"] or
                       dir_mb >= THRESHOLDS["memory_dir_mb_warn"] or
                       days_since >= THRESHOLDS["compact_days_warn"] or
                       route_keys < THRESHOLDS["route_keys_warn"])

    return {
        "memory_danger":  memory_danger,
        "memory_warn":    memory_warn,
        "diary_lines":    diary_lines,
        "days_since_compact": days_since,
        "route_keys":     route_keys,
        # 推荐动作
        "suggested": (
            ["lan_compact.py", "lan_extractor.py"] if memory_danger else
            ["lan_compact.py"] if memory_warn else
            []
        )
    }


# ── 入口 ───────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "check"

    if cmd in ("check", "--check"):
        result = sense()
        # 有问题时，自动搜解法
        if result["level"] in ("DANGER", "WARN"):
            print("\n  🔍 检测到问题，自动搜索解法...")
            search_solutions()
    elif cmd == "auto-compact":
        # 感知 → 如果危险，立刻触发蒸馏，不等人
        result = sense()
        if result["level"] == "DANGER":
            compact_py = os.path.join(PLUGIN_DIR, "lan_compact.py")
            if os.path.exists(compact_py):
                print("\n  🔥 DANGER级 → 立刻触发蒸馏...")
                ret = subprocess.run([PYTHON, compact_py], capture_output=True, text=True)
                if ret.returncode == 0:
                    print("  ✅ 蒸馏完成")
                    # 蒸馏完做一次快照
                    snapshot_py = os.path.join(PLUGIN_DIR, "lan_snapshot.py")
                    if os.path.exists(snapshot_py):
                        subprocess.Popen([PYTHON, snapshot_py, "take"],
                                         creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
                        print("  ✅ 快照已触发（后台）")
                else:
                    print(f"  ❌ 蒸馏失败: {ret.stderr[:200]}")
            else:
                print("  ⚠️ lan_compact.py 找不到，无法自动蒸馏")
        elif result["level"] == "WARN":
            print("\n  🟡 WARN级 → 建议手动蒸馏，本次不强制触发")
        else:
            print("\n  ✅ 记忆健康，无需蒸馏")
    elif cmd == "status":
        # 前缀处理器：回忆 + 快照 + 铁索
        try:
            from lan_prefix import PrefixProcessor
            prefix = PrefixProcessor(debug=False)
            prefix.pre_execute(
                plugin_name="lan_memory_sentinel.py",
                context="status检查"
            )
        except ImportError:
            print("⚠️ 前缀处理器不可用，跳过回忆/快照流程")
        
        try:
            state = get_sentinel_state()
            icon = "🔴" if state["memory_danger"] else ("🟡" if state["memory_warn"] else "✅")
            print(f"{icon} 记忆哨兵状态 | 日记{state['diary_lines']}行 | "
                  f"蒸馏{state['days_since_compact']:.1f}天前 | 种子{state['route_keys']}个")
            if state["suggested"]:
                print(f"  建议运行: {' | '.join(state['suggested'])}")
        finally:
            try:
                from lan_prefix import PrefixProcessor
                prefix.post_execute(
                    plugin_name="lan_memory_sentinel.py",
                    context="status检查"
                )
            except (ImportError, NameError):
                pass
    elif cmd == "search":
        q = " ".join(args[1:]) if len(args) > 1 else None
        search_solutions(q)
    elif cmd == "report":
        n = int(args[1]) if len(args) > 1 else 10
        show_report(n)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
