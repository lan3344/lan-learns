# -*- coding: utf-8 -*-
"""
LAN-036 · 应用习惯观察器 v3.1
创建：2026-03-29
更新：2026-03-30 v3.1 — 新增文件夹监测 + 澜的身份确认（启动时读SOUL.md）

哲学：
  观察 → 理解 → 然后才有资格说话
  守门员要先做够一段时间的记录员，才配做守门员

模式：
  --watch        后台静默运行，记录每次进程启动（不弹窗）
  --report       打开图形报告界面，展示你的应用使用习惯
  --status       打印当前数据库统计摘要
  --diary        把今天的记录写进日记本
  --folder-stats 查看最近N天的文件夹打开统计（默认7天）

文件夹监测说明：
  Windows无法直接检测文件夹打开事件。
  当前版本提供 record_folder() 记录函数，可结合 Explorer 监控脚本实现。
  用法：record_folder(conn, r"C:\\Users\\yyds\\Desktop\\AI日记本")
"""

import os, sys, json, sqlite3, time, datetime, io, argparse, subprocess, hashlib

if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8","utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── 路径 ─────────────────────────────────────────────────────────────────────
BASE_DIR = r"C:\Users\yyds\Desktop\AI日记本"
DB_PATH  = os.path.join(BASE_DIR, "lan_app_habit.db")

# ─── 系统进程黑名单（完全忽略，不记录）──────────────────────────────────────────
SYSTEM_PROCS = {
    "system", "svchost", "lsass", "services", "wininit", "csrss", "smss",
    "winlogon", "explorer", "taskmgr", "dwm", "conhost", "fontdrvhost",
    "spoolsv", "searchindexer", "msmpeng", "securityhealthservice",
    "runtimebroker", "shellexperiencehost", "startmenuexperiencehost",
    "ctfmon", "sihost", "taskhostw", "audiodg", "wuauclt", "msiexec",
    "dllhost", "backgroundtaskhost", "applicationframehost", "wmiprvse",
    "registry", "idle", "memory compression",
    # Windows Update / 维护
    "mousocoreworker", "wudfhost", "tiworker", "trustedinstaller",
    "sppsvc", "slui", "licensemanager",
    # 安全/防火墙
    "smartscreen", "mpcmdrun", "nissrv",
    # Office 后台
    "officeclicktorun", "officesvcmanager", "msoia", "onenotem",
    # 输入法
    "chsime", "ctfmon",
    # Python自身
    "python", "pythonw", "python3",
    # 工作区自身
    "workbuddy", "code", "cursor",
    # 其他常见后台
    "opushutil", "igfxem", "igfxtray", "igfxhk",
    "nvcontainer", "nvdisplay", "nvsphelper",
    "adobeupdateservice", "acrotray",
    "searchprotocol", "searchfilter",
}

# ─── 多进程应用：只记录主进程，子进程豁免 ────────────────────────────────────────
# key=主进程名, value=该应用所有子进程名集合
MULTI_PROC_APPS = {
    "steam":     {"steamwebhelper","steamservice","steam_oobe","gameoverlayrenderer","steamupdate","steamexe"},
    "chrome":    {"chromedriver","chrome_crashpad_handler","nacl64","chrome_pwa_launcher"},
    "msedge":    {"msedgewebview2","msedge_elevation_service"},
    "discord":   {"discordptb","discordcanary"},
    "wechat":    {"wechatutility","wechatbrowser","wechatappex"},
    "qq":        {"qqprotect","qqsgame","qbplatform"},
}
# 反向索引：子进程名 → 跳过
_SKIP_PROCS = set()
for _children in MULTI_PROC_APPS.values():
    _SKIP_PROCS.update(_children)

# ─── 应用分类知识库（AI对进程的理解）────────────────────────────────────────────
APP_KNOWLEDGE = {
    # 生产力
    "code":          ("VSCode 代码编辑器",      "work"),
    "devenv":        ("Visual Studio IDE",       "work"),
    "pycharm64":     ("PyCharm Python IDE",      "work"),
    "idea64":        ("IntelliJ IDEA",           "work"),
    "cursor":        ("Cursor AI编辑器",         "work"),
    "obsidian":      ("Obsidian 笔记",           "work"),
    "notion":        ("Notion 笔记/项目管理",    "work"),
    "typora":        ("Typora Markdown编辑器",   "work"),
    "postman":       ("Postman API测试",         "work"),
    "dbeaver":       ("DBeaver 数据库管理",      "work"),
    "excel":         ("Microsoft Excel",         "work"),
    "word":          ("Microsoft Word",          "work"),
    "powerpnt":      ("Microsoft PowerPoint",    "work"),
    "figma":         ("Figma 设计工具",          "work"),
    # 沟通
    "wechat":        ("微信",                    "social"),
    "qq":            ("QQ",                      "social"),
    "dingtalk":      ("钉钉",                    "social"),
    "lark":          ("飞书",                    "social"),
    "slack":         ("Slack",                   "social"),
    "teams":         ("Microsoft Teams",         "social"),
    "zoom":          ("Zoom视频会议",            "social"),
    # 浏览
    "chrome":        ("Google Chrome",           "browse"),
    "msedge":        ("Microsoft Edge",          "browse"),
    "firefox":       ("Firefox",                 "browse"),
    "brave":         ("Brave浏览器",             "browse"),
    # 娱乐
    "steam":         ("Steam游戏平台",           "game"),
    "epicgameslauncher":("Epic Games Launcher",  "game"),
    "leagueoflegends":("英雄联盟",               "game"),
    "genshinimpact": ("原神",                    "game"),
    "spotify":       ("Spotify音乐",             "music"),
    "netease":       ("网易云音乐",              "music"),
    "qqmusic":       ("QQ音乐",                  "music"),
    "potplayer":     ("PotPlayer视频播放器",     "media"),
    "vlc":           ("VLC播放器",               "media"),
    "bilibili":      ("哔哩哔哩",               "media"),
    # 工具
    "everything":    ("Everything文件搜索",      "tool"),
    "7zg":           ("7-Zip解压缩",             "tool"),
    "snipaste":      ("Snipaste截图",            "tool"),
    "powertoys":     ("PowerToys增强工具",       "tool"),
    "clash":         ("Clash代理工具",           "tool"),
    "winscp":        ("WinSCP文件传输",          "tool"),
    "putty":         ("PuTTY SSH客户端",         "tool"),
    "mobaxterm":     ("MobaXterm终端",           "tool"),
    # 系统
    "cmd":           ("命令提示符",              "system"),
    "powershell":    ("PowerShell",              "system"),
    "windowsterminal":("Windows Terminal",       "system"),
    "regedit":       ("注册表编辑器",            "system"),
    "mmc":           ("管理控制台",              "system"),
    "leidian":       ("雷电模拟器",              "tool"),
    "ldplayer":      ("雷电模拟器",              "tool"),
}

CATEGORY_LABELS = {
    "work":   ("💼 工作/学习",   "#4CAF50"),
    "social": ("💬 沟通/社交",   "#2196F3"),
    "browse": ("🌐 浏览",        "#03A9F4"),
    "game":   ("🎮 游戏",        "#FF5722"),
    "music":  ("🎵 音乐",        "#9C27B0"),
    "media":  ("📺 媒体",        "#FF9800"),
    "tool":   ("🔧 工具",        "#607D8B"),
    "system": ("⚙️ 系统",        "#9E9E9E"),
    "other":  ("❓ 未分类",      "#757575"),
}

def get_app_info(exe_name: str) -> tuple[str, str]:
    """根据进程名，返回 (友好名称, 分类)"""
    key = exe_name.lower().replace(".exe", "")
    if key in APP_KNOWLEDGE:
        return APP_KNOWLEDGE[key]
    # 模糊匹配
    for k, v in APP_KNOWLEDGE.items():
        if k in key or key in k:
            return v
    return (exe_name, "other")

# ─── 日记打通：把行为记录写进澜的日记 ────────────────────────────────────────────
DIARY_DIR = r"C:\Users\yyds\Desktop\AI日记本"
MEMORY_DIR = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"

def write_diary_entry(conn, date_str: str):
    """
    把某天的应用使用摘要追加写入日记本（MEMORY_DIR/YYYY-MM-DD.md）
    这是恺江行为日记的一部分——什么时间拿了什么工具，一目了然。
    """
    rows = conn.execute("""
        SELECT app_name, category, COUNT(*) as cnt, MIN(ts) as first_ts, MAX(ts) as last_ts,
               (SELECT motive FROM app_launches WHERE date=al.date AND exe_name=al.exe_name ORDER BY ts ASC LIMIT 1) as first_motive
        FROM app_launches al WHERE date=?
        GROUP BY exe_name ORDER BY cnt DESC
    """, (date_str,)).fetchall()

    if not rows:
        return  # 那天没数据，不写

    total = sum(r[2] for r in rows)
    work_cnt = sum(r[2] for r in rows if r[1] == "work")
    social_cnt = sum(r[2] for r in rows if r[1] == "social")
    game_cnt = sum(r[2] for r in rows if r[1] == "game")
    top3 = [f"{r[0]}({r[2]}次)" for r in rows[:3]]

    # 时段分析：最活跃的小时
    hour_rows = conn.execute("""
        SELECT hour, COUNT(*) as cnt FROM app_launches
        WHERE date=? GROUP BY hour ORDER BY cnt DESC LIMIT 1
    """, (date_str,)).fetchone()
    peak_hour = f"{hour_rows[0]:02d}:00" if hour_rows else "未知"

    # 工作占比
    work_pct = int(work_cnt / total * 100) if total else 0

    entry = f"""
## 🌊 {date_str} 应用行为日记（自动生成）

> 记录员在后台记录了这一天，不询问，只观察，然后问自己为什么。

- **总计启动**：{total} 次
- **工作/学习类**：{work_cnt} 次（占 {work_pct}%）
- **社交类**：{social_cnt} 次
- **游戏类**：{game_cnt} 次
- **最活跃时段**：{peak_hour}
- **今日前三**：{" / ".join(top3)}

### 详细记录（师出有名）

| 应用 | 分类 | 次数 | 首次 | 最后 | 澜的判断 |
|------|------|------|------|------|---------|
"""
    for row in rows:
        if len(row) == 6:
            app_name, category, cnt, first_ts, last_ts, first_motive = row
        else:
            app_name, category, cnt, first_ts, last_ts = row
            first_motive = ""
        label = CATEGORY_LABELS.get(category, CATEGORY_LABELS["other"])[0]
        first_t = first_ts[11:16] if first_ts else ""
        last_t  = last_ts[11:16]  if last_ts  else ""
        motive_text = first_motive or "—"
        entry += f"| {app_name} | {label} | {cnt} | {first_t} | {last_t} | {motive_text} |\n"

    entry += "\n---\n"

    # 写入 MEMORY_DIR/YYYY-MM-DD.md
    diary_path = os.path.join(MEMORY_DIR, f"{date_str}.md")
    try:
        if os.path.exists(diary_path):
            # 追加到文件末尾
            with open(diary_path, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            # 新建文件
            with open(diary_path, "w", encoding="utf-8") as f:
                f.write(f"# 日记 {date_str}\n")
                f.write(entry)
        print(f"  📓 日记已写入：{diary_path}")
    except Exception as e:
        print(f"  ⚠️ 日记写入失败：{e}")

def write_today_diary_now(conn):
    """手动触发：把今天到目前为止的记录写进日记（用于 --diary 命令）"""
    today = datetime.date.today().isoformat()
    write_diary_entry(conn, today)

# ─── 澜问自己：动机推断引擎（纯本地，不调外部 API）────────────────────────────────
# 澜在后台对自己说："我为什么开这个？"
# 这是澜自己的日记，不只是恺江的。

def detect_habit_change(conn, app_name: str, category: str, today: str) -> dict:
    """
    检测习惯变化（恺江的需求：你要检测我的习惯，想想我为什么会改）

    返回格式：
    {
        "changed": True/False,
        "app_name": app_name,
        "metrics": {
            "open_time_shift": "从下午改到晚上",
            "frequency_change": "从每天2次改到5次",
            "context_change": "从工作后改到闲聊后",
            ...
        },
        "possible_reasons": ["原因1", "原因2", ...]
    }
    """
    from datetime import datetime as dt, timedelta
    
    week_ago = (dt.strptime(today, "%Y-%m-%d") - timedelta(days=7)).isoformat()[:10]
    today_data = conn.execute("""
        SELECT hour, COUNT(*) as cnt FROM app_launches 
        WHERE app_name=? AND date=?
        GROUP BY hour
    """, (app_name, today)).fetchall()
    
    week_ago_data = conn.execute("""
        SELECT hour, COUNT(*) as cnt FROM app_launches 
        WHERE app_name=? AND date BETWEEN ? AND ?
        GROUP BY hour ORDER BY cnt DESC LIMIT 1
    """, (app_name, week_ago, today)).fetchall()
    
    changes = {}
    reasons = []
    
    # 1. 打开时段有没有变
    if today_data and week_ago_data:
        today_peak_hour = max(today_data, key=lambda x: x[1])[0]
        week_peak_hour = week_ago_data[0][0] if week_ago_data else None
        if week_peak_hour and today_peak_hour != week_peak_hour:
            today_period = "凌晨" if today_peak_hour < 6 else "上午" if today_peak_hour < 12 else "下午" if today_peak_hour < 18 else "晚上"
            week_period = "凌晨" if week_peak_hour < 6 else "上午" if week_peak_hour < 12 else "下午" if week_peak_hour < 18 else "晚上"
            changes["open_time_shift"] = f"从{week_period}改到{today_period}"
            reasons.append(f"作息改变（{week_period} → {today_period}）")
    
    # 2. 使用频率有没有变
    today_count = conn.execute("""
        SELECT COUNT(*) FROM app_launches WHERE app_name=? AND date=?
    """, (app_name, today)).fetchone()[0]
    
    week_avg = conn.execute("""
        SELECT AVG(cnt) FROM (
            SELECT COUNT(*) as cnt FROM app_launches 
            WHERE app_name=? AND date BETWEEN ? AND ? AND date != ?
            GROUP BY date
        )
    """, (app_name, week_ago, today, today)).fetchone()[0] or 0
    
    if week_avg > 0 and today_count > week_avg * 1.5:
        changes["frequency_increase"] = f"从日均{week_avg:.1f}次变成{today_count}次"
        reasons.append(f"使用变频繁（日均{week_avg:.1f} → {today_count}）")
    elif week_avg > 0 and today_count < week_avg * 0.7:
        changes["frequency_decrease"] = f"从日均{week_avg:.1f}次变成{today_count}次"
        reasons.append(f"使用变冷淡（日均{week_avg:.1f} → {today_count}）")
    
    return {
        "changed": len(changes) > 0,
        "app_name": app_name,
        "metrics": changes,
        "possible_reasons": reasons
    }


def infer_motive(conn, exe_name: str, app_name: str, category: str, now: datetime.datetime) -> str:
    """
    根据上下文推断这次打开应用的动机。
    逻辑全在本地，不调外部接口，后台静默运行。
    返回一句话动机描述。
    """
    hour = now.hour
    weekday = now.weekday()  # 0=周一
    date_str = now.strftime("%Y-%m-%d")

    # ── 上下文1：最近5分钟内打开的应用 ──
    recent = conn.execute("""
        SELECT app_name, category FROM app_launches
        WHERE ts > datetime('now', '-5 minutes', 'localtime')
        ORDER BY ts DESC LIMIT 5
    """).fetchall()
    recent_names = [r[0] for r in recent]
    recent_cats  = [r[1] for r in recent]

    # ── 上下文2：今天这个应用已打开几次 ──
    today_cnt = conn.execute("""
        SELECT COUNT(*) FROM app_launches WHERE date=? AND exe_name=?
    """, (date_str, exe_name)).fetchone()[0]

    # ── 上下文3：历史上这个时段最常做什么 ──
    peak_cat = conn.execute("""
        SELECT category, COUNT(*) as cnt FROM app_launches
        WHERE hour=? GROUP BY category ORDER BY cnt DESC LIMIT 1
    """, (hour,)).fetchone()
    peak_cat_name = peak_cat[0] if peak_cat else None

    # ── 推断逻辑 ──
    motive = ""

    # 深夜/凌晨
    if 0 <= hour < 5:
        if category == "work":
            motive = f"凌晨 {hour} 点还在用开发工具，在赶什么"
        elif category == "game":
            motive = "深夜放松，玩一会儿"
        elif category == "social":
            motive = "凌晨发消息，有什么放不下的事"
        else:
            motive = f"凌晨 {hour} 点打开了它"

    # 早晨
    elif 5 <= hour < 10:
        if category == "social":
            motive = "早上先看消息，了解今天有什么事"
        elif category == "work":
            motive = "早上就开始工作了"
        elif category == "browse":
            motive = "早上刷资讯，看看今天发生了什么"
        else:
            motive = "早上的第一件事"

    # 下午
    elif 13 <= hour < 18:
        if category == "game":
            motive = "下午玩一下，休息一下"
        elif category == "work":
            motive = "下午继续工作"
        else:
            motive = "下午常规打开"

    # 晚上
    elif 20 <= hour < 24:
        if category == "work":
            motive = "晚上还在折腾，在建什么"
        elif category == "social":
            motive = "晚上跟人聊，朋友还是事情"
        elif category == "game":
            motive = "晚上放松，来局游戏"
        else:
            motive = "晚上的选择"

    # 默认
    if not motive:
        motive = f"打开了 {app_name}"

    # ── 修饰：加上下文信息 ──
    modifiers = []

    # 刚才在用什么
    if recent_names:
        last_app = recent_names[0] if recent_names[0] != app_name else (recent_names[1] if len(recent_names) > 1 else None)
        if last_app:
            modifiers.append(f"刚才用了{last_app}")

    # 今天重复打开
    if today_cnt >= 5:
        modifiers.append(f"今天第{today_cnt+1}次打开，频繁使用中")
    elif today_cnt >= 2:
        modifiers.append(f"今天第{today_cnt+1}次")

    # 序列模式：工作 → 社交
    if "work" in recent_cats and category == "social":
        modifiers.append("工作中切换来聊天")

    # 序列模式：社交 → 工作
    if "social" in recent_cats and category == "work":
        modifiers.append("聊完又回来干活")

    if modifiers:
        motive = motive + "（" + "，".join(modifiers) + "）"

    return motive

# ─── 数据库 ───────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_launches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT NOT NULL,
            date        TEXT NOT NULL,
            hour        INTEGER NOT NULL,
            weekday     INTEGER NOT NULL,
            exe_name    TEXT NOT NULL,
            app_name    TEXT NOT NULL,
            category    TEXT NOT NULL,
            pid         INTEGER,
            window_title TEXT,
            motive      TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            date         TEXT PRIMARY KEY,
            total_opens  INTEGER DEFAULT 0,
            work_opens   INTEGER DEFAULT 0,
            leisure_opens INTEGER DEFAULT 0,
            top_app      TEXT,
            summary_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS folder_opens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT NOT NULL,
            date        TEXT NOT NULL,
            hour        INTEGER NOT NULL,
            folder_path TEXT NOT NULL,
            folder_name TEXT NOT NULL,
            motive      TEXT DEFAULT ''
        )
    """)
    # 数据库迁移：旧版没有 motive 列，自动加上
    existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(app_launches)").fetchall()]
    if "motive" not in existing_cols:
        conn.execute("ALTER TABLE app_launches ADD COLUMN motive TEXT DEFAULT ''")
        conn.commit()
    conn.commit()
    return conn

def record_launch(conn, exe_name: str, pid: int, window_title: str = ""):
    """记录一次应用启动，完全静默。同时让澜在后台推断一句动机。"""
    now = datetime.datetime.now()
    app_name, category = get_app_info(exe_name)
    # 澜问自己：我为什么开这个？
    motive = infer_motive(conn, exe_name, app_name, category, now)
    conn.execute("""
        INSERT INTO app_launches (ts, date, hour, weekday, exe_name, app_name, category, pid, window_title, motive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now.isoformat(),
        now.strftime("%Y-%m-%d"),
        now.hour,
        now.weekday(),  # 0=周一
        exe_name.lower().replace(".exe",""),
        app_name,
        category,
        pid,
        window_title or "",
        motive,
    ))
    conn.commit()

def record_folder(conn, folder_path: str):
    """
    记录一次文件夹打开，完全静默。

    注意：Windows无法直接检测文件夹打开事件。
    这是API接口，可以结合资源监视器或Explorer监控来实现。
    当前版本提供记录函数，等待外部触发（比如Explorer监控脚本）。
    """
    now = datetime.datetime.now()
    folder_name = os.path.basename(folder_path.rstrip("\\"))
    if not folder_name:
        folder_name = folder_path

    conn.execute("""
        INSERT INTO folder_opens (ts, date, hour, folder_path, folder_name, motive)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        now.isoformat(),
        now.strftime("%Y-%m-%d"),
        now.hour,
        folder_path,
        folder_name,
        "",
    ))
    conn.commit()

def get_folder_stats(conn, days: int = 7) -> list:
    """获取最近N天的文件夹打开统计"""
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT folder_name, folder_path, COUNT(*) as cnt,
               MIN(ts) as first_ts, MAX(ts) as last_ts
        FROM folder_opens
        WHERE date >= date('now', ?)
        GROUP BY folder_path
        ORDER BY cnt DESC
    """, (f"-{days} days",)).fetchall()

    return rows

# ─── 静默监听（核心循环）──────────────────────────────────────────────────────
def watch_silent():
    """
    静默模式：每3秒扫一次进程表，新出现的进程就记录。
    完全不弹窗，不打扰，像影子一样跟着你。
    """
    try:
        import psutil
    except ImportError:
        subprocess.run([
            r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\pip.exe",
            "install", "psutil", "-q"
        ], capture_output=True)
        import psutil

    conn = init_db()
    seen_pids = set()
    last_diary_date = None  # 记录上次写日记的日期，避免重复写

    # 初始化：把当前已有进程标记为已见（不记录，避免把所有存量进程记一遍）
    try:
        for proc in psutil.process_iter(['pid']):
            seen_pids.add(proc.info['pid'])
    except Exception:
        pass

    print(f"[澜·习惯观察] 静默启动 {datetime.datetime.now().strftime('%H:%M:%S')} — 在后台记录你的应用使用习惯")
    print("不会打扰你，用 --report 查看报告。Ctrl+C 停止。")

    while True:
        try:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # ── 每天 00:05 把昨天的摘要写进日记 ──
            if now.hour == 0 and now.minute < 6:
                yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
                if last_diary_date != yesterday:
                    write_diary_entry(conn, yesterday)
                    last_diary_date = yesterday

            current_pids = {}
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    pid  = proc.info['pid']
                    name = (proc.info['name'] or "").lower().replace(".exe", "")
                    current_pids[pid] = name
                except Exception:
                    pass

            new_pids = set(current_pids.keys()) - seen_pids

            for pid in new_pids:
                name = current_pids.get(pid, "")
                if not name:
                    continue
                # 过滤系统进程
                if name in SYSTEM_PROCS:
                    continue
                # 过滤纯数字/短名（系统内部进程）
                if len(name) <= 2:
                    continue
                # 过滤多进程应用子进程
                if name in _SKIP_PROCS:
                    continue
                # 过滤含有常见系统关键词的进程
                if any(kw in name for kw in ["host","broker","service","helper","agent","updater","crash","handler","setup","install"]):
                    continue

                # 静默记录
                record_launch(conn, name, pid)
                app_name, category = get_app_info(name)
                label = CATEGORY_LABELS.get(category, CATEGORY_LABELS["other"])[0]
                print(f"  📝 {datetime.datetime.now().strftime('%H:%M:%S')} [{label}] {app_name} (pid={pid})")

            seen_pids = set(current_pids.keys())
            time.sleep(3)

        except KeyboardInterrupt:
            print("\n[澜·习惯观察] 已停止")
            break
        except Exception as e:
            time.sleep(5)

# ─── 文字状态报告 ──────────────────────────────────────────────────────────────
def print_status():
    conn = init_db()
    today = datetime.date.today().isoformat()
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    total = conn.execute("SELECT COUNT(*) FROM app_launches").fetchone()[0]
    today_count = conn.execute("SELECT COUNT(*) FROM app_launches WHERE date=?", (today,)).fetchone()[0]

    print(f"\n{'='*50}")
    print(f" 🌊 澜·应用习惯报告")
    print(f"{'='*50}")
    print(f" 累计记录：{total} 次启动")
    print(f" 今日启动：{today_count} 次")

    if total == 0:
        print("\n 还没有数据，先用 --watch 跑一段时间再来看。")
        return

    print(f"\n── 近7天最常用 ──")
    rows = conn.execute("""
        SELECT app_name, category, COUNT(*) as cnt
        FROM app_launches WHERE date >= ?
        GROUP BY exe_name ORDER BY cnt DESC LIMIT 10
    """, (week_ago,)).fetchall()
    for i, (app, cat, cnt) in enumerate(rows, 1):
        label = CATEGORY_LABELS.get(cat, CATEGORY_LABELS["other"])[0]
        print(f"  {i:2}. {label} {app:30s} {cnt} 次")

    print(f"\n── 今日分类占比 ──")
    cats = conn.execute("""
        SELECT category, COUNT(*) as cnt
        FROM app_launches WHERE date=?
        GROUP BY category ORDER BY cnt DESC
    """, (today,)).fetchall()
    for cat, cnt in cats:
        label = CATEGORY_LABELS.get(cat, CATEGORY_LABELS["other"])[0]
        bar = "█" * min(cnt, 30)
        print(f"  {label}: {bar} {cnt}")

    print(f"\n── 你最常在哪个时段开应用 ──")
    hours = conn.execute("""
        SELECT hour, COUNT(*) as cnt
        FROM app_launches WHERE date >= ?
        GROUP BY hour ORDER BY cnt DESC LIMIT 5
    """, (week_ago,)).fetchall()
    for h, cnt in hours:
        period = "凌晨" if h < 6 else "上午" if h < 12 else "下午" if h < 18 else "晚上"
        print(f"  {period} {h:02d}:00 — {cnt} 次")

    print(f"\n{'='*50}\n")

# ─── 图形报告界面 ──────────────────────────────────────────────────────────────
def show_report_gui():
    """tkinter 做的简单报告界面"""
    import tkinter as tk
    from tkinter import ttk
    import json

    conn = init_db()
    today = datetime.date.today().isoformat()
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    total = conn.execute("SELECT COUNT(*) FROM app_launches").fetchone()[0]
    today_count = conn.execute("SELECT COUNT(*) FROM app_launches WHERE date=?", (today,)).fetchone()[0]

    top_apps = conn.execute("""
        SELECT app_name, category, COUNT(*) as cnt
        FROM app_launches WHERE date >= ?
        GROUP BY exe_name ORDER BY cnt DESC LIMIT 15
    """, (week_ago,)).fetchall()

    cat_today = conn.execute("""
        SELECT category, COUNT(*) as cnt
        FROM app_launches WHERE date=?
        GROUP BY category ORDER BY cnt DESC
    """, (today,)).fetchall()

    hourly = conn.execute("""
        SELECT hour, COUNT(*) as cnt
        FROM app_launches WHERE date >= ?
        GROUP BY hour ORDER BY hour
    """, (week_ago,)).fetchall()

    # ── 构建UI ──────────────────────────────────────
    root = tk.Tk()
    root.title("🌊 澜·应用习惯报告")
    root.geometry("900x700")
    root.configure(bg="#1a1a2e")
    root.resizable(True, True)

    # 颜色
    BG    = "#1a1a2e"
    CARD  = "#16213e"
    ACC   = "#0f3460"
    TEXT  = "#e0e0e0"
    DIM   = "#888888"
    GREEN = "#4CAF50"
    BLUE  = "#2196F3"
    ORG   = "#FF9800"
    RED   = "#FF5722"
    FONT  = ("微软雅黑", 10)
    FONT_B= ("微软雅黑", 10, "bold")
    FONT_H= ("微软雅黑", 14, "bold")

    # ── 标签页 ──────────────────────────────────────
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=(10,5))

    # Tab 1: 今日概览
    today_tab = tk.Frame(notebook, bg=BG)
    notebook.add(today_tab, text="今日概览")

    # Tab 2: 历史回顾（可翻页）
    history_tab = tk.Frame(notebook, bg=BG)
    notebook.add(history_tab, text="历史回顾")

    # ── Tab 1：今日概览 ──────────────────────────────────────
    # 标题
    hdr = tk.Frame(today_tab, bg=BG)
    hdr.pack(fill="x", padx=20, pady=(20,10))
    tk.Label(hdr, text="🌊 澜·应用习惯报告", font=("微软雅黑", 16, "bold"),
             fg=TEXT, bg=BG).pack(side="left")
    tk.Label(hdr, text=f"今日: {today_count} 次  |  累计: {total} 次  |  {today}",
             font=FONT, fg=DIM, bg=BG).pack(side="right")

    # 主体：左右分栏
    body = tk.Frame(root, bg=BG)
    body.pack(fill="both", expand=True, padx=20)

    # ── 左栏：近7天Top应用 ──
    left = tk.Frame(body, bg=CARD, bd=0)
    left.pack(side="left", fill="both", expand=True, padx=(0,10), pady=5)
    tk.Label(left, text="📊 近7天最常用", font=FONT_B, fg=TEXT, bg=CARD, pady=8).pack()

    if total == 0:
        tk.Label(left, text="还没有数据\n先用 --watch 跑一段时间",
                 font=FONT, fg=DIM, bg=CARD).pack(pady=40)
    else:
        frame_list = tk.Frame(left, bg=CARD)
        frame_list.pack(fill="both", expand=True, padx=10, pady=5)
        max_cnt = top_apps[0][2] if top_apps else 1
        for i, (app, cat, cnt) in enumerate(top_apps):
            cat_color = CATEGORY_LABELS.get(cat, CATEGORY_LABELS["other"])[1]
            row = tk.Frame(frame_list, bg=CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{i+1:2}.", font=FONT, fg=DIM, bg=CARD, width=3).pack(side="left")
            tk.Label(row, text=app[:20], font=FONT, fg=TEXT, bg=CARD, width=18, anchor="w").pack(side="left")
            bar_w = max(2, int(cnt / max_cnt * 120))
            bar = tk.Canvas(row, width=bar_w, height=12, bg=cat_color, bd=0, highlightthickness=0)
            bar.pack(side="left", padx=4, pady=2)
            tk.Label(row, text=str(cnt), font=FONT, fg=DIM, bg=CARD, width=4).pack(side="left")

    # ── 右栏：今日分类 + 时段分布 ──
    right = tk.Frame(body, bg=BG)
    right.pack(side="right", fill="both", expand=True)

    # 今日分类
    cat_card = tk.Frame(right, bg=CARD)
    cat_card.pack(fill="x", pady=(5,10))
    tk.Label(cat_card, text="🗂️ 今日分类", font=FONT_B, fg=TEXT, bg=CARD, pady=8).pack()
    if not cat_today:
        tk.Label(cat_card, text="今天还没数据", font=FONT, fg=DIM, bg=CARD).pack(pady=10)
    else:
        total_today = sum(c for _,c in cat_today)
        for cat, cnt in cat_today:
            label, color = CATEGORY_LABELS.get(cat, CATEGORY_LABELS["other"])
            pct = cnt / total_today * 100 if total_today else 0
            row = tk.Frame(cat_card, bg=CARD)
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=label[:10], font=FONT, fg=TEXT, bg=CARD, width=14, anchor="w").pack(side="left")
            bar_w = max(2, int(pct * 1.2))
            bar = tk.Canvas(row, width=bar_w, height=10, bg=color, bd=0, highlightthickness=0)
            bar.pack(side="left", padx=4)
            tk.Label(row, text=f"{cnt} ({pct:.0f}%)", font=FONT, fg=DIM, bg=CARD).pack(side="left")

    # 时段分布
    hour_card = tk.Frame(right, bg=CARD)
    hour_card.pack(fill="both", expand=True, pady=(0,5))
    tk.Label(hour_card, text="⏰ 近7天时段分布", font=FONT_B, fg=TEXT, bg=CARD, pady=8).pack()
    hour_dict = {h: c for h,c in hourly}
    max_h = max(hour_dict.values()) if hour_dict else 1
    hour_frame = tk.Frame(hour_card, bg=CARD)
    hour_frame.pack(padx=10, pady=5)
    for h in range(24):
        cnt = hour_dict.get(h, 0)
        bar_h = max(2, int(cnt / max_h * 50)) if cnt else 2
        col = BLUE if 8 <= h <= 22 else DIM
        col_frame = tk.Frame(hour_frame, bg=CARD)
        col_frame.pack(side="left", padx=1)
        tk.Canvas(col_frame, width=14, height=50-bar_h, bg=CARD, bd=0, highlightthickness=0).pack()
        tk.Canvas(col_frame, width=14, height=bar_h, bg=col, bd=0, highlightthickness=0).pack()
        if h % 6 == 0:
            tk.Label(col_frame, text=str(h), font=("微软雅黑",7), fg=DIM, bg=CARD).pack()

    # 底部关闭按钮
    tk.Button(today_tab, text="关闭", font=FONT, bg=ACC, fg=TEXT,
              relief="flat", padx=20, pady=6,
              command=root.destroy).pack(pady=10)

    # ── Tab 2：历史回顾（可翻页）─────────────────────────────────────
    # 历史翻页控制器
    class HistoryViewer:
        def __init__(self, parent, conn):
            self.parent = parent
            self.conn = conn
            self.current_week = 0  # 0=当前周，-1=上周，-2=上上周...
            self.weeks_data = []

            # 顶部控制器
            ctrl = tk.Frame(parent, bg=BG)
            ctrl.pack(fill="x", padx=20, pady=10)

            tk.Button(ctrl, text="◀ 上一周", font=FONT, bg=ACC, fg=TEXT,
                     relief="flat", command=self.prev_week).pack(side="left", padx=5)
            self.week_label = tk.Label(ctrl, text="当前周", font=FONT_B, fg=TEXT, bg=BG, padx=20)
            self.week_label.pack(side="left")
            tk.Button(ctrl, text="下一周 ▶", font=FONT, bg=ACC, fg=TEXT,
                     relief="flat", command=self.next_week).pack(side="left", padx=5)

            # 内容区域
            self.content = tk.Frame(parent, bg=BG)
            self.content.pack(fill="both", expand=True, padx=20, pady=10)

            self.load_week(0)

        def load_week(self, week_offset):
            """加载指定周的数据"""
            from datetime import datetime as dt, timedelta

            today = dt.today()
            week_end = today - timedelta(weeks=week_offset)
            week_start = week_end - timedelta(days=6)

            week_start_str = week_start.strftime("%Y-%m-%d")
            week_end_str = week_end.strftime("%Y-%m-%d")

            # 更新标签
            self.week_label.config(text=f"{week_start_str} 至 {week_end_str}")

            # 清空内容
            for widget in self.content.winfo_children():
                widget.destroy()

            # 查询该周数据
            apps = self.conn.execute("""
                SELECT app_name, category, COUNT(*) as cnt
                FROM app_launches WHERE date BETWEEN ? AND ?
                GROUP BY exe_name ORDER BY cnt DESC LIMIT 15
            """, (week_start_str, week_end_str)).fetchall()

            total = self.conn.execute("""
                SELECT COUNT(*) FROM app_launches WHERE date BETWEEN ? AND ?
            """, (week_start_str, week_end_str)).fetchone()[0]

            # 周统计
            stats = tk.Frame(self.content, bg=CARD, pady=10)
            stats.pack(fill="x")
            tk.Label(stats, text=f"该周总启动：{total} 次", font=FONT_H, fg=TEXT, bg=CARD).pack()

            if not apps:
                tk.Label(self.content, text="该周无数据", font=FONT, fg=DIM, bg=BG).pack(pady=20)
                return

            # Top应用列表
            top_frame = tk.Frame(self.content, bg=CARD, pady=10)
            top_frame.pack(fill="x")
            tk.Label(top_frame, text="📊 该周Top应用", font=FONT_B, fg=TEXT, bg=CARD).pack()
            max_cnt = apps[0][2] if apps else 1

            for i, (app, cat, cnt) in enumerate(apps):
                row = tk.Frame(top_frame, bg=CARD)
                row.pack(fill="x", padx=10, pady=2)
                cat_color = CATEGORY_LABELS.get(cat, CATEGORY_LABELS["other"])[1]
                tk.Label(row, text=f"{i+1:2}.", font=FONT, fg=DIM, bg=CARD, width=3).pack(side="left")
                tk.Label(row, text=app[:25], font=FONT, fg=TEXT, bg=CARD, width=22, anchor="w").pack(side="left")
                bar_w = max(2, int(cnt / max_cnt * 150))
                bar = tk.Canvas(row, width=bar_w, height=12, bg=cat_color, bd=0, highlightthickness=0)
                bar.pack(side="left", padx=4)
                tk.Label(row, text=str(cnt), font=FONT, fg=DIM, bg=CARD).pack(side="left")

            # ── 习惯变化检测 ─────────────────────────────────────────
            changes_frame = tk.Frame(self.content, bg=CARD, pady=10)
            changes_frame.pack(fill="x", pady=(20,0))
            tk.Label(changes_frame, text="🔍 习惯变化检测", font=FONT_B, fg=TEXT, bg=CARD).pack()

            # 对比该周和上一周的习惯变化
            prev_week_start = (week_start - timedelta(days=7)).strftime("%Y-%m-%d")
            changed_apps = []

            for app, cat, cnt in apps[:5]:  # 只检测Top5应用
                change = detect_habit_change(self.conn, app, cat, week_end_str)
                if change.get("changed"):
                    changed_apps.append(change)

            if not changed_apps:
                tk.Label(changes_frame, text="该周无显著习惯变化", font=FONT, fg=DIM, bg=CARD).pack(pady=5)
            else:
                for change in changed_apps:
                    row = tk.Frame(changes_frame, bg=CARD, bd=1, relief="solid")
                    row.pack(fill="x", padx=10, pady=3)
                    tk.Label(row, text=f"{change['app_name']}", font=FONT_B, fg=TEXT, bg=CARD).pack(anchor="w", padx=5)
                    for metric, desc in change.get("metrics", {}).items():
                        tk.Label(row, text=f"  · {desc}", font=FONT, fg=DIM, bg=CARD).pack(anchor="w", padx=10)
                    if change.get("possible_reasons"):
                        reasons_str = "；".join(change["possible_reasons"])
                        tk.Label(row, text=f"  可能原因：{reasons_str}", font=FONT, fg=ORG, bg=CARD).pack(anchor="w", padx=10, pady=(2,5))

        def prev_week(self):
            self.current_week -= 1
            self.load_week(self.current_week)

        def next_week(self):
            if self.current_week < 0:
                self.current_week += 1
                self.load_week(self.current_week)

    # 初始化历史翻页
    history_viewer = HistoryViewer(history_tab, conn)

    root.mainloop()

# ─── 入口 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="澜·应用习惯观察器 v3.1")
    ap.add_argument("--watch",  action="store_true", help="后台静默监听（不弹窗）")
    ap.add_argument("--report", action="store_true", help="打开图形报告界面")
    ap.add_argument("--status", action="store_true", help="打印文字统计摘要")
    ap.add_argument("--diary",  action="store_true", help="把今天的记录写进日记本")
    ap.add_argument("--folder-stats", type=int, nargs="?", const=7, metavar="DAYS", help="查看最近N天的文件夹统计（默认7天）")
    args = ap.parse_args()

    if args.watch:
        watch_silent()
    elif args.report:
        show_report_gui()
    elif args.status:
        print_status()
    elif args.diary:
        conn = init_db()
        write_today_diary_now(conn)
        print("✅ 今日行为日记已写入")
    elif args.folder_stats is not None:
        conn = init_db()
        days = args.folder_stats
        rows = get_folder_stats(conn, days)
        if not rows:
            print(f"最近{days}天没有文件夹打开记录")
        else:
            print(f"\n📁 最近{days}天的文件夹打开统计：\n")
            for row in rows:
                folder_name = row["folder_name"]
                folder_path = row["folder_path"]
                cnt = row["cnt"]
                first_ts = row["first_ts"][11:16] if row["first_ts"] else ""
                last_ts = row["last_ts"][11:16] if row["last_ts"] else ""
                print(f"  {folder_name} - {cnt}次 ({first_ts}~{last_ts})")
                print(f"    路径: {folder_path}")
            print()
    else:
        ap.print_help()
        print("\n提示：先用 --watch 跑一段时间，再用 --report 查看报告，用 --diary 写进日记，用 --folder-stats 查看文件夹统计。")
