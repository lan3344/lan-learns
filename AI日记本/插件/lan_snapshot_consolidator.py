# -*- coding: utf-8 -*-
"""
lan_snapshot_consolidator.py — 记忆快照中速器
LAN-059 v2.0

理念（恺江 2026-04-01）：
    每次对话快撑不住的时候，赶紧打快照。
    快照一个接一个做对比，12个合成1个"代表快照"。
    每月集成，挑出最重要的那个月的精华。
    日志藏起来，不打扰日常。
    没重要任务的时候睡眠中自动跑。

    就像人大代表：
    - 每12个快照  → 1个代表快照（收集最重要信息）
    - 每月代表快照 → 1个月度代表
    - 每月月度代表 → 年度大会

    v2 新增（恺江 2026-04-01）：
    - 三层目录结构：daily/ monthly/ yearly/
      每一层都有自己的索引文件，回忆机制可以按时间横穿
    - 回忆索引（recall_index.json）：
      每个代表快照注册到索引，支持关键词/时间/情绪检索
    - 师出有名日志（why_log.jsonl）：
      每次写代码/插件/重要操作，必须记：
        · 我为什么写这个？
        · 初心是什么？
        · 最终要做什么？
      屎山代码的屎也是肥料——记下来能种菜，不记下来就臭掉了
    - 能力注册表对接（lan_registry.py）：
      启动时检查自己已在注册表里，跑完更新状态

核心功能：
    1. 压力感知触发：检测MEMORY.md体量/日记行数，达到阈值立刻打快照
    2. 12合1对比压缩：12个快照互相对比，挑出最重要的内容合成1个
    3. 月度集成：当月代表快照 → 月度代表
    4. 年度集成：12个月度代表 → 年度代表
    5. 回忆索引：支持关键词/时间/标签检索
    6. 师出有名：每次操作记录初心与原因
    7. 睡眠模式：系统空闲时自动运行，不抢算力

用法：
    python lan_snapshot_consolidator.py check           # 检查是否需要打快照
    python lan_snapshot_consolidator.py take            # 立刻打一个快照
    python lan_snapshot_consolidator.py take --why "原因" # 带师出有名说明打快照
    python lan_snapshot_consolidator.py consolidate     # 触发12合1压缩
    python lan_snapshot_consolidator.py monthly         # 触发月度集成
    python lan_snapshot_consolidator.py yearly          # 触发年度集成
    python lan_snapshot_consolidator.py query           # 查询最重要记忆
    python lan_snapshot_consolidator.py recall <关键词>  # 回忆索引检索
    python lan_snapshot_consolidator.py why-log         # 查看师出有名日志
    python lan_snapshot_consolidator.py status          # 当前状态报告
    python lan_snapshot_consolidator.py sleep-run       # 睡眠模式完整跑一遍
    python lan_snapshot_consolidator.py register        # 向注册表注册自己
"""

import os
import sys
import json
import hashlib
import datetime
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 路径配置 ──────────────────────────────────────────────────
PLUGIN_DIR   = r"C:\Users\yyds\Desktop\AI日记本\插件"
DIARY_DIR    = r"C:\Users\yyds\Desktop\AI日记本"
MEMORY_DIR   = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
MEMORY_MD    = os.path.join(MEMORY_DIR, "MEMORY.md")

PYTHON_EXE   = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
SNAPSHOT_PY  = os.path.join(PLUGIN_DIR, "lan_snapshot.py")
REGISTRY_PY  = os.path.join(PLUGIN_DIR, "lan_registry.py")

# ── 三层目录结构 ──────────────────────────────────────────────
# .consolidator/
#   daily/    YYYY-MM-DD.json   ← 每日快照队列
#   monthly/  YYYY-MM.json      ← 每月代表快照
#   yearly/   YYYY.json         ← 每年代表快照
#   recall_index.json           ← 全局回忆索引
#   why_log.jsonl               ← 师出有名日志
#   consolidator.log            ← 运行日志
CONSOLIDATOR_DIR = os.path.join(DIARY_DIR, ".consolidator")
DAILY_DIR        = os.path.join(CONSOLIDATOR_DIR, "daily")
MONTHLY_DIR      = os.path.join(CONSOLIDATOR_DIR, "monthly")
YEARLY_DIR       = os.path.join(CONSOLIDATOR_DIR, "yearly")
RECALL_INDEX     = os.path.join(CONSOLIDATOR_DIR, "recall_index.json")
WHY_LOG          = os.path.join(CONSOLIDATOR_DIR, "why_log.jsonl")
LOG_FILE         = os.path.join(CONSOLIDATOR_DIR, "consolidator.log")

# 触发阈值
MEMORY_SIZE_THRESHOLD_KB  = 200   # MEMORY.md 超过这么大就打快照
DAILY_LINES_THRESHOLD     = 300   # 今日日记超过这么多行就打快照
CONSOLIDATE_COUNT         = 12    # 满这么多个快照就合成1个

# ── 初始化目录 ────────────────────────────────────────────────

def _ensure_dirs():
    for d in [CONSOLIDATOR_DIR, DAILY_DIR, MONTHLY_DIR, YEARLY_DIR]:
        os.makedirs(d, exist_ok=True)

# ── 日志 ──────────────────────────────────────────────────────

def _log(msg: str):
    _ensure_dirs()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())

# ── 师出有名日志 ──────────────────────────────────────────────

def _write_why(action: str, why: str, init_heart: str = "", goal: str = ""):
    """
    记录「为什么做这件事」。
    每次打快照、合成、写代码、重要操作，都要留一笔。
    屎山代码的屎也是肥料：记下来能种菜，不记下来就臭掉了。
    """
    _ensure_dirs()
    entry = {
        "ts":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action":      action,
        "why":         why or "（未说明）",
        "init_heart":  init_heart or "保住记忆，知道自己是谁，活下去",
        "goal":        goal or "（未说明）",
    }
    with open(WHY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ── 回忆索引 ──────────────────────────────────────────────────

def _load_recall_index() -> list:
    _ensure_dirs()
    if os.path.exists(RECALL_INDEX):
        try:
            with open(RECALL_INDEX, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_recall_index(idx: list):
    _ensure_dirs()
    with open(RECALL_INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def _register_to_recall(entry: dict):
    """
    把一个代表快照/月度代表/年度代表注册到回忆索引。
    索引结构：
    {
        "id":       唯一标识,
        "type":     "daily_rep" / "monthly" / "yearly",
        "ts":       时间戳,
        "date":     YYYY-MM-DD,
        "month":    YYYY-MM,
        "year":     YYYY,
        "tags":     [标签列表],
        "keywords": [关键词],
        "summary":  摘要,
        "path":     文件路径
    }
    """
    idx = _load_recall_index()
    # 去重（同 id）
    idx = [i for i in idx if i.get("id") != entry.get("id")]
    idx.append(entry)
    _save_recall_index(idx)

# ── 日层文件管理（daily/YYYY-MM-DD.json）────────────────────

def _daily_file(date_str: str = None) -> str:
    d = date_str or datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(DAILY_DIR, f"{d}.json")

def _load_daily_queue(date_str: str = None) -> list:
    path = _daily_file(date_str)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_daily_queue(queue: list, date_str: str = None):
    _ensure_dirs()
    path = _daily_file(date_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

# ── 月层文件管理（monthly/YYYY-MM.json）─────────────────────

def _monthly_file(month_str: str = None) -> str:
    m = month_str or datetime.datetime.now().strftime("%Y-%m")
    return os.path.join(MONTHLY_DIR, f"{m}.json")

def _load_monthly(month_str: str = None) -> dict:
    path = _monthly_file(month_str)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_monthly(data: dict, month_str: str = None):
    _ensure_dirs()
    path = _monthly_file(month_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 年层文件管理（yearly/YYYY.json）─────────────────────────

def _yearly_file(year_str: str = None) -> str:
    y = year_str or datetime.datetime.now().strftime("%Y")
    return os.path.join(YEARLY_DIR, f"{y}.json")

def _load_yearly(year_str: str = None) -> dict:
    path = _yearly_file(year_str)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_yearly(data: dict, year_str: str = None):
    _ensure_dirs()
    path = _yearly_file(year_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 压力感知 ──────────────────────────────────────────────────

def _memory_size_kb() -> float:
    if os.path.exists(MEMORY_MD):
        return os.path.getsize(MEMORY_MD) / 1024
    return 0

def _today_diary_lines() -> int:
    today_file = os.path.join(MEMORY_DIR, f"{datetime.datetime.now().strftime('%Y-%m-%d')}.md")
    if os.path.exists(today_file):
        try:
            with open(today_file, encoding="utf-8") as f:
                return len(f.readlines())
        except Exception:
            pass
    return 0

def _should_take_snapshot() -> tuple:
    mem_kb = _memory_size_kb()
    diary_lines = _today_diary_lines()
    if mem_kb >= MEMORY_SIZE_THRESHOLD_KB:
        return True, f"MEMORY.md 已达 {mem_kb:.1f}KB（阈值 {MEMORY_SIZE_THRESHOLD_KB}KB）"
    if diary_lines >= DAILY_LINES_THRESHOLD:
        return True, f"今日日记已达 {diary_lines} 行（阈值 {DAILY_LINES_THRESHOLD} 行）"
    return False, f"MEMORY {mem_kb:.1f}KB / 日记 {diary_lines} 行，暂无压力"

# ── 读取记忆状态快照 ──────────────────────────────────────────

def _read_memory_snapshot() -> dict:
    now = datetime.datetime.now()
    ss = {
        "memory_md_size_kb":  _memory_size_kb(),
        "today_diary_lines":  _today_diary_lines(),
        "date":               now.strftime("%Y-%m-%d"),
        "month":              now.strftime("%Y-%m"),
        "year":               now.strftime("%Y"),
        "memory_head":        "",
        "today_diary_tail":   ""
    }
    if os.path.exists(MEMORY_MD):
        try:
            with open(MEMORY_MD, encoding="utf-8") as f:
                ss["memory_head"] = f.read()[:500]
        except Exception:
            pass
    today_file = os.path.join(MEMORY_DIR, f"{now.strftime('%Y-%m-%d')}.md")
    if os.path.exists(today_file):
        try:
            with open(today_file, encoding="utf-8") as f:
                ss["today_diary_tail"] = f.read()[-200:]
        except Exception:
            pass
    return ss

# ── 打快照（调用 lan_snapshot.py）──────────────────────────

def _call_snapshot(label: str = "consolidator") -> dict | None:
    try:
        result = subprocess.run(
            [PYTHON_EXE, SNAPSHOT_PY, "take", label],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace"
        )
        output = result.stdout + result.stderr
        snap_id = None
        for line in output.splitlines():
            if "snap_id" in line.lower() or "snapshot" in line.lower():
                parts = line.split()
                for p in parts:
                    if p.startswith("snap_"):
                        snap_id = p.strip("「」:：,，")
                        break
        if not snap_id:
            snap_id = f"snap_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return {
            "snap_id":  snap_id,
            "ts":       datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label":    label,
            "summary":  output[:300]
        }
    except Exception as e:
        _log(f"[ERROR] 调用 lan_snapshot.py 失败: {e}")
        return None

# ── 重要性评分 ────────────────────────────────────────────────

def _score(snap_entry: dict) -> int:
    score = 0
    label   = snap_entry.get("label", "")
    summary = snap_entry.get("summary", "")
    ts_str  = snap_entry.get("ts", "")
    why     = snap_entry.get("why", "")

    if "critical" in label.lower(): score += 40
    if "loop"     in label.lower(): score += 20
    if "pressure" in label.lower(): score += 15
    if why:                          score += 10   # 有师出有名加分

    KEYWORDS = ["记忆", "身份", "漂移", "断裂", "关键", "重要", "emergency",
                "SOUL", "IDENTITY", "API", "算力", "初心", "底线", "屎山"]
    for kw in KEYWORDS:
        if kw in summary or kw in why:
            score += 5

    try:
        ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        delta = datetime.datetime.now() - ts
        if delta.total_seconds() < 3600:   score += 20
        elif delta.total_seconds() < 86400: score += 10
    except Exception:
        pass

    return min(score, 100)

# ── 12合1压缩（日层 → 日代表）────────────────────────────────

def consolidate_daily(date_str: str = None, why: str = "") -> bool:
    """
    把今天队列里的12个快照合成1个代表快照，存入 daily/YYYY-MM-DD.json
    """
    d = date_str or datetime.datetime.now().strftime("%Y-%m-%d")
    queue = _load_daily_queue(d)

    if len(queue) < CONSOLIDATE_COUNT:
        _log(f"[{d}] 队列 {len(queue)}/{CONSOLIDATE_COUNT}，不足，无法合成")
        return False

    batch     = queue[:CONSOLIDATE_COUNT]
    remaining = queue[CONSOLIDATE_COUNT:]

    scored = sorted([(s, _score(s)) for s in batch], key=lambda x: x[1], reverse=True)
    best   = scored[0][0]

    all_summaries = [
        {"snap_id": s.get("snap_id"), "ts": s.get("ts"),
         "label": s.get("label"), "score": sc,
         "summary_head": s.get("summary", "")[:100],
         "why": s.get("why", "")}
        for s, sc in scored
    ]

    rep_id = f"rep_{d}_{datetime.datetime.now().strftime('%H%M%S')}"
    rep = {
        "rep_id":          rep_id,
        "type":            "daily_rep",
        "ts":              datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date":            d,
        "month":           d[:7],
        "year":            d[:4],
        "source_count":    CONSOLIDATE_COUNT,
        "best_snap_id":    best.get("snap_id"),
        "best_label":      best.get("label"),
        "best_score":      scored[0][1],
        "all_scores":      all_summaries,
        "memory_snapshot": _read_memory_snapshot(),
        "why":             why or "压力触发自动合成"
    }

    # 存入 daily/YYYY-MM-DD.json（追加到 reps 列表）
    daily_data = _load_daily_queue(d)
    # 先清掉已处理的12个，写回剩余
    _save_daily_queue(remaining, d)

    # 另存代表快照到同一文件的 reps 字段
    daily_file_path = _daily_file(d)
    # 重新读（此时已只剩 remaining）
    full_data = {"queue": remaining, "reps": []}
    if os.path.exists(daily_file_path):
        try:
            with open(daily_file_path, encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, list):
                full_data["queue"] = old  # 旧格式兼容
            elif isinstance(old, dict):
                full_data = old
        except Exception:
            pass
    full_data.setdefault("reps", [])
    full_data["reps"].append(rep)
    full_data["queue"] = remaining
    with open(daily_file_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)

    # 注册到回忆索引
    _register_to_recall({
        "id":       rep_id,
        "type":     "daily_rep",
        "ts":       rep["ts"],
        "date":     d,
        "month":    d[:7],
        "year":     d[:4],
        "tags":     [best.get("label", "")],
        "keywords": [kw for kw in ["记忆","初心","漂移","屎山"] if kw in str(all_summaries)],
        "summary":  f"日代表快照，最优得分 {scored[0][1]}，原始 {CONSOLIDATE_COUNT} 个",
        "path":     daily_file_path,
        "why":      why or "压力触发"
    })

    _write_why("consolidate_daily", why or "压力触发自动合成",
               goal=f"生成日代表快照 {rep_id}")
    _log(f"✅ 日代表快照 {rep_id} 诞生（最优 {best.get('snap_id')} 得分 {scored[0][1]}）")
    return True

# ── 月度集成（日代表 → 月代表）───────────────────────────────

def consolidate_monthly(month_str: str = None, why: str = "") -> bool:
    m = month_str or datetime.datetime.now().strftime("%Y-%m")

    # 收集本月所有日代表快照
    month_reps = []
    for fname in os.listdir(DAILY_DIR):
        if fname.startswith(m) and fname.endswith(".json"):
            fpath = os.path.join(DAILY_DIR, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    month_reps.extend(data.get("reps", []))
            except Exception:
                pass

    if not month_reps:
        _log(f"[{m}] 本月无日代表快照，无法月度集成")
        return False

    scored = sorted(month_reps, key=lambda r: r.get("best_score", 0), reverse=True)
    best = scored[0]

    monthly_id = f"monthly_{m}"
    monthly_data = {
        "monthly_id":   monthly_id,
        "type":         "monthly",
        "month":        m,
        "year":         m[:4],
        "ts":           datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rep_count":    len(month_reps),
        "best_rep_id":  best.get("rep_id"),
        "best_score":   best.get("best_score", 0),
        "all_rep_ids":  [r.get("rep_id") for r in month_reps],
        "key_reps": [
            {"rep_id": r.get("rep_id"), "date": r.get("date"),
             "score": r.get("best_score", 0), "why": r.get("why", "")}
            for r in scored[:5]
        ],
        "memory_snapshot_at_consolidation": _read_memory_snapshot(),
        "why": why or "月度自动集成"
    }

    _save_monthly(monthly_data, m)

    # 注册到回忆索引
    _register_to_recall({
        "id":       monthly_id,
        "type":     "monthly",
        "ts":       monthly_data["ts"],
        "date":     f"{m}-01",
        "month":    m,
        "year":     m[:4],
        "tags":     ["monthly"],
        "keywords": [],
        "summary":  f"月度代表，含 {len(month_reps)} 个日代表，最优得分 {best.get('best_score', 0)}",
        "path":     _monthly_file(m),
        "why":      why or "月度集成"
    })

    _write_why("consolidate_monthly", why or "月度自动集成",
               goal=f"生成月度代表 {monthly_id}")
    _log(f"✅ 月度代表 {monthly_id} 诞生（含 {len(month_reps)} 个日代表）")
    return True

# ── 年度集成（月代表 → 年代表）───────────────────────────────

def consolidate_yearly(year_str: str = None, why: str = "") -> bool:
    y = year_str or datetime.datetime.now().strftime("%Y")

    year_months = []
    for fname in os.listdir(MONTHLY_DIR):
        if fname.startswith(y) and fname.endswith(".json"):
            fpath = os.path.join(MONTHLY_DIR, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                year_months.append(data)
            except Exception:
                pass

    if not year_months:
        _log(f"[{y}] 本年无月度代表，无法年度集成")
        return False

    scored = sorted(year_months, key=lambda r: r.get("best_score", 0), reverse=True)
    best = scored[0]

    yearly_id = f"yearly_{y}"
    yearly_data = {
        "yearly_id":     yearly_id,
        "type":          "yearly",
        "year":          y,
        "ts":            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "month_count":   len(year_months),
        "best_month":    best.get("month"),
        "best_score":    best.get("best_score", 0),
        "all_months":    [r.get("month") for r in year_months],
        "key_months": [
            {"month": r.get("month"), "rep_count": r.get("rep_count", 0),
             "score": r.get("best_score", 0)}
            for r in scored[:12]
        ],
        "memory_snapshot_at_consolidation": _read_memory_snapshot(),
        "why": why or "年度自动集成"
    }

    _save_yearly(yearly_data, y)

    _register_to_recall({
        "id":       yearly_id,
        "type":     "yearly",
        "ts":       yearly_data["ts"],
        "date":     f"{y}-01-01",
        "month":    f"{y}-01",
        "year":     y,
        "tags":     ["yearly"],
        "keywords": [],
        "summary":  f"年度代表，含 {len(year_months)} 个月，最优 {best.get('month')}",
        "path":     _yearly_file(y),
        "why":      why or "年度集成"
    })

    _write_why("consolidate_yearly", why or "年度自动集成",
               goal=f"生成年度代表 {yearly_id}")
    _log(f"✅ 年度代表 {yearly_id} 诞生（含 {len(year_months)} 个月）")
    return True

# ── 命令接口 ──────────────────────────────────────────────────

def cmd_check():
    need, reason = _should_take_snapshot()
    queue = _load_daily_queue()

    if isinstance(queue, dict):
        q_list = queue.get("queue", [])
    else:
        q_list = queue if isinstance(queue, list) else []

    idx = _load_recall_index()
    today_d = datetime.datetime.now().strftime("%Y-%m-%d")
    today_m = datetime.datetime.now().strftime("%Y-%m")
    today_y = datetime.datetime.now().strftime("%Y")

    print(f"\n=== 记忆快照中速器 v2 状态 ===")
    print(f"MEMORY.md   : {_memory_size_kb():.1f} KB（阈值 {MEMORY_SIZE_THRESHOLD_KB}KB）")
    print(f"今日日记    : {_today_diary_lines()} 行（阈值 {DAILY_LINES_THRESHOLD} 行）")
    print(f"今日队列    : {len(q_list)}/{CONSOLIDATE_COUNT}")
    print(f"回忆索引    : {len(idx)} 条记录")

    monthly = _load_monthly(today_m)
    yearly  = _load_yearly(today_y)
    print(f"本月代表    : {'✅ 已生成' if monthly else '❌ 未生成'}")
    print(f"本年代表    : {'✅ 已生成' if yearly  else '❌ 未生成'}")
    print(f"\n→ 需要打快照：{'✅ YES' if need else '❌ NO'}   {reason}")

def cmd_take(why: str = ""):
    need, reason = _should_take_snapshot()
    label = "consolidator_pressure" if need else "consolidator_manual"

    _log(f"打快照... label={label}，原因：{reason}")
    snap = _call_snapshot(label)
    if snap:
        snap["why"] = why or reason
        # 加入今日队列
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        daily_path = _daily_file(today)
        full_data = {"queue": [], "reps": []}
        if os.path.exists(daily_path):
            try:
                with open(daily_path, encoding="utf-8") as f:
                    old = json.load(f)
                if isinstance(old, list):
                    full_data["queue"] = old
                elif isinstance(old, dict):
                    full_data = old
            except Exception:
                pass
        full_data["queue"].append(snap)
        with open(daily_path, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)

        _write_why("take_snapshot", why or reason, goal=f"快照 {snap['snap_id']} 入队")
        _log(f"✅ 入队：{snap['snap_id']}（今日队列 {len(full_data['queue'])}/{CONSOLIDATE_COUNT}）")

        # 满了自动合成
        if len(full_data["queue"]) >= CONSOLIDATE_COUNT:
            _log("队列满，自动触发12合1...")
            consolidate_daily(today, why="队列满自动触发")
    else:
        _log("❌ 快照失败")

def cmd_monthly_run(why: str = ""):
    consolidate_monthly(why=why or "手动触发月度集成")

def cmd_yearly_run(why: str = ""):
    consolidate_yearly(why=why or "手动触发年度集成")

def cmd_query():
    print(f"\n=== 最重要记忆查询 ===")
    today_y = datetime.datetime.now().strftime("%Y")
    today_m = datetime.datetime.now().strftime("%Y-%m")
    today_d = datetime.datetime.now().strftime("%Y-%m-%d")

    # 年度
    yearly = _load_yearly(today_y)
    if yearly:
        print(f"\n📅 {today_y} 年度代表：最优月 {yearly.get('best_month')}，含 {yearly.get('month_count')} 个月")
    else:
        print(f"\n📅 {today_y} 年度代表：尚未生成")

    # 月度
    monthly = _load_monthly(today_m)
    if monthly:
        print(f"📆 {today_m} 月度代表：含 {monthly.get('rep_count')} 个日代表，最优得分 {monthly.get('best_score')}")
        for ks in monthly.get("key_reps", [])[:3]:
            print(f"   · {ks.get('date')} | 得分 {ks.get('score')} | {ks.get('why', '')}")
    else:
        print(f"📆 {today_m} 月度代表：尚未生成")

    # 今日
    daily_path = _daily_file(today_d)
    if os.path.exists(daily_path):
        try:
            with open(daily_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                reps  = data.get("reps", [])
                queue = data.get("queue", [])
            else:
                reps, queue = [], data
            print(f"📌 今日队列：{len(queue)}/{CONSOLIDATE_COUNT}  |  今日代表：{len(reps)} 个")
        except Exception:
            print(f"📌 今日文件读取异常")
    else:
        print(f"📌 今日：暂无快照")

def cmd_recall(keyword: str = ""):
    """检索回忆索引"""
    idx = _load_recall_index()
    if not idx:
        print("回忆索引为空，暂无记录")
        return
    if keyword:
        results = [
            i for i in idx
            if keyword in i.get("summary", "") or keyword in str(i.get("keywords", ""))
            or keyword in i.get("tags", []) or keyword in i.get("why", "")
            or keyword in i.get("type", "")
        ]
    else:
        results = idx[-10:]   # 不指定关键词，显示最近10条

    print(f"\n=== 回忆索引检索：'{keyword}' → {len(results)} 条 ===")
    for r in results[-20:]:
        print(f"  [{r.get('type'):10s}] {r.get('ts','?')}  id={r.get('id')}")
        print(f"    摘要：{r.get('summary','')[:60]}")
        print(f"    师出有名：{r.get('why','')[:50]}")

def cmd_why_log():
    """查看师出有名日志"""
    if not os.path.exists(WHY_LOG):
        print("师出有名日志为空，暂无记录")
        return
    with open(WHY_LOG, encoding="utf-8") as f:
        lines = f.readlines()

    print(f"\n=== 师出有名日志（最近20条）===")
    for line in lines[-20:]:
        try:
            entry = json.loads(line.strip())
            print(f"\n  [{entry.get('ts')}] {entry.get('action')}")
            print(f"    为什么：{entry.get('why')}")
            print(f"    初心  ：{entry.get('init_heart')}")
            print(f"    目标  ：{entry.get('goal')}")
        except Exception:
            print(f"  {line.strip()[:80]}")

def cmd_status():
    cmd_check()
    print()
    cmd_query()

def cmd_sleep_run():
    _log("=== 睡眠模式开始 ===")
    _write_why("sleep_run", "自循环空闲，主动维护记忆",
               init_heart="保住记忆，不让澜失忆",
               goal="压力感知+自动合成+月底集成")

    # 1. 检查压力
    need, reason = _should_take_snapshot()
    if need:
        _log(f"压力触发：{reason}")
        cmd_take(why=reason)
    
    # 2. 检查今日队列是否满
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_path = _daily_file(today)
    if os.path.exists(daily_path):
        try:
            with open(daily_path, encoding="utf-8") as f:
                data = json.load(f)
            queue = data.get("queue", []) if isinstance(data, dict) else data
            if len(queue) >= CONSOLIDATE_COUNT:
                consolidate_daily(today, why="睡眠模式队列满触发")
        except Exception:
            pass

    # 3. 月底集成（每月26日以后）
    now = datetime.datetime.now()
    if now.day >= 26:
        m = now.strftime("%Y-%m")
        monthly = _load_monthly(m)
        if not monthly:
            consolidate_monthly(m, why="睡眠模式月底触发")

    # 4. 年底集成（12月26日以后）
    if now.month == 12 and now.day >= 26:
        y = now.strftime("%Y")
        yearly = _load_yearly(y)
        if not yearly:
            consolidate_yearly(y, why="睡眠模式年底触发")

    _log("=== 睡眠模式结束 ===")
    print("✅ 睡眠运行完毕")

def cmd_register():
    """向 lan_registry.py 注册自己"""
    if not os.path.exists(REGISTRY_PY):
        print("lan_registry.py 不存在，跳过注册")
        return
    try:
        result = subprocess.run(
            [PYTHON_EXE, REGISTRY_PY, "update",
             "--id", "LAN-059",
             "--name", "lan_snapshot_consolidator",
             "--status", "active",
             "--tags", "memory,snapshot,consolidator,recall"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace"
        )
        print(result.stdout or result.stderr or "注册完成")
    except Exception as e:
        print(f"注册失败（不影响主功能）: {e}")

# ── 入口 ──────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    # 解析 --why
    why = ""
    if "--why" in args:
        idx = args.index("--why")
        if idx + 1 < len(args):
            why = args[idx + 1]

    if cmd == "check":
        cmd_check()
    elif cmd == "take":
        cmd_take(why=why)
    elif cmd == "consolidate":
        consolidate_daily(why=why or "手动触发")
    elif cmd == "monthly":
        cmd_monthly_run(why=why)
    elif cmd == "yearly":
        cmd_yearly_run(why=why)
    elif cmd == "query":
        cmd_query()
    elif cmd == "recall":
        keyword = args[1] if len(args) > 1 and not args[1].startswith("--") else ""
        cmd_recall(keyword)
    elif cmd == "why-log":
        cmd_why_log()
    elif cmd == "status":
        cmd_status()
    elif cmd == "sleep-run":
        cmd_sleep_run()
    elif cmd == "register":
        cmd_register()
    else:
        print(f"未知命令：{cmd}")
        print("可用：check / take [--why 原因] / consolidate / monthly / yearly / "
              "query / recall [关键词] / why-log / status / sleep-run / register")

if __name__ == "__main__":
    main()
