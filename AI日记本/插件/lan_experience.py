"""
LAN-034-EXPERIENCE · 澜的经验记忆层
======================================
版本：v1.0（2026-03-29）

─── 填补的缺口 ──────────────────────────────────────────────────────
百年记忆草案 缺口4：缺少经验记忆层（做过什么事，踩过什么坑）

事实记忆（"澜叫什么"）是记忆的骨骼。
经验记忆（"上次这么干结果失败了"）是记忆的血肉。

只有骨骼，知道"是什么"，但不知道"该怎么做"。
经验让澜能从自己的历史里学习，而不是每次都当第一次。

─── 三类经验 ────────────────────────────────────────────────────────
1. [SUCCESS] 成功经验  — 什么方法/工具/路径有效，下次直接用
2. [LESSON]  失败教训  — 什么路走不通，为什么，下次别踩
3. [CAUTION] 注意事项  — 没有对错，但要小心的地方

─── 工作流程 ────────────────────────────────────────────────────────
手动记录：澜主动写经验（处理完一件事后）
自动提取：从失败日志/日记里提取经验
查询使用：遇到相似场景时自动匹配历史经验

─────────────────────────────────────────────────────────────────────
"""

import os
import re
import json
import sqlite3
import hashlib
import datetime
from pathlib import Path


# ─── 路径 ─────────────────────────────────────────────────────────
MEMORY_ROOT  = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆库")
EXP_DB       = MEMORY_ROOT / "lan_experience.db"
FAILURE_LOG  = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的失败日志.jsonl")
DIARY_DIR    = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")
PLUGIN_DIR   = Path(r"C:\Users\yyds\Desktop\AI日记本\插件")

# ─── 经验类型 ──────────────────────────────────────────────────────
TYPE_SUCCESS = "SUCCESS"  # 成功经验
TYPE_LESSON  = "LESSON"   # 失败教训
TYPE_CAUTION = "CAUTION"  # 注意事项

EMOJI = {
    TYPE_SUCCESS: "✅",
    TYPE_LESSON:  "⚠️",
    TYPE_CAUTION: "📌"
}

# ─── 数据库初始化 ──────────────────────────────────────────────────

def init_db():
    EXP_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(EXP_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS experiences (
            id          TEXT PRIMARY KEY,
            type        TEXT NOT NULL,     -- SUCCESS / LESSON / CAUTION
            domain      TEXT,              -- 领域标签（如 'ADB', '记忆', '安全'）
            title       TEXT NOT NULL,     -- 一句话标题
            description TEXT,             -- 详细描述
            outcome     TEXT,             -- 结果/后果
            lesson      TEXT,             -- 经验总结
            tags        TEXT,             -- JSON数组，关键词标签
            confidence  REAL DEFAULT 0.8,  -- 置信度
            created_at  TEXT,
            source      TEXT,             -- 来源（日记/手动/失败日志/修复日志/改造日志）
            source_detail TEXT            -- JSON，详情 {"from": "failure", "id": "FAIL-...", "cross_ref": "..."}
        )
    """)
    conn.commit()
    conn.close()

def _gen_id(title: str, created_at: str) -> str:
    return hashlib.sha1(f"{title}{created_at}".encode()).hexdigest()[:12]

# ─── 写入经验 ──────────────────────────────────────────────────────

def add_experience(
    exp_type: str,
    title: str,
    description: str = "",
    outcome: str = "",
    lesson: str = "",
    domain: str = "",
    tags: list = None,
    confidence: float = 0.8,
    source: str = "manual",
    source_detail: dict = None  # ← 新增：来源详情，如 {"from": "failure", "id": "FAIL-..."}
) -> str:
    """添加一条经验，返回id"""
    conn = sqlite3.connect(EXP_DB)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    exp_id = _gen_id(title, now)
    # 去重检查（同标题不重复存）
    c.execute("SELECT id FROM experiences WHERE title=?", (title,))
    if c.fetchone():
        conn.close()
        return None  # 已存在

    c.execute("""
        INSERT INTO experiences
        (id, type, domain, title, description, outcome, lesson, tags, confidence, created_at, source, source_detail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exp_id, exp_type, domain, title,
        description, outcome, lesson,
        json.dumps(tags or [], ensure_ascii=False),
        confidence, now, source,
        json.dumps(source_detail or {}, ensure_ascii=False)
    ))
    conn.commit()
    conn.close()
    return exp_id

# ─── 查询经验 ──────────────────────────────────────────────────────

def search_experience(keyword: str, exp_type: str = None, limit: int = 10) -> list:
    """按关键词搜索经验"""
    conn = sqlite3.connect(EXP_DB)
    c = conn.cursor()
    if exp_type:
        c.execute("""
            SELECT type, domain, title, lesson, tags, created_at
            FROM experiences
            WHERE type=? AND (title LIKE ? OR description LIKE ? OR lesson LIKE ? OR tags LIKE ?)
            ORDER BY confidence DESC, created_at DESC
            LIMIT ?
        """, (exp_type, f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit))
    else:
        c.execute("""
            SELECT type, domain, title, lesson, tags, created_at
            FROM experiences
            WHERE title LIKE ? OR description LIKE ? OR lesson LIKE ? OR tags LIKE ?
            ORDER BY confidence DESC, created_at DESC
            LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit))
    rows = c.fetchall()
    conn.close()
    results = []
    for row in rows:
        results.append({
            "type": row[0],
            "domain": row[1],
            "title": row[2],
            "lesson": row[3],
            "tags": json.loads(row[4] or "[]"),
            "created_at": row[5][:10]
        })
    return results

def get_all(exp_type: str = None, limit: int = 50) -> list:
    """获取所有经验"""
    conn = sqlite3.connect(EXP_DB)
    c = conn.cursor()
    if exp_type:
        c.execute("""
            SELECT type, domain, title, description, outcome, lesson, tags, confidence, created_at, source
            FROM experiences WHERE type=?
            ORDER BY created_at DESC LIMIT ?
        """, (exp_type, limit))
    else:
        c.execute("""
            SELECT type, domain, title, description, outcome, lesson, tags, confidence, created_at, source
            FROM experiences
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(zip(
        ["type","domain","title","description","outcome","lesson","tags","confidence","created_at","source"],
        r
    )) for r in rows]

def stats() -> dict:
    """统计经验库概况"""
    conn = sqlite3.connect(EXP_DB)
    c = conn.cursor()
    c.execute("SELECT type, COUNT(*) FROM experiences GROUP BY type")
    type_counts = dict(c.fetchall())
    c.execute("SELECT COUNT(*) FROM experiences")
    total = c.fetchone()[0]
    conn.close()
    return {
        "total": total,
        TYPE_SUCCESS: type_counts.get(TYPE_SUCCESS, 0),
        TYPE_LESSON:  type_counts.get(TYPE_LESSON, 0),
        TYPE_CAUTION: type_counts.get(TYPE_CAUTION, 0),
    }

# ─── 自动提取：从失败日志导入 ─────────────────────────────────────

def import_from_failure_log() -> int:
    """从 lan_failure_log.py 的失败日志里提取教训"""
    if not FAILURE_LOG.exists():
        return 0
    saved = 0
    with open(FAILURE_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                title = entry.get("title") or entry.get("event") or ""
                lesson_text = entry.get("lesson") or entry.get("what_failed") or ""
                domain = entry.get("domain") or entry.get("category") or "未分类"
                if not title:
                    continue
                eid = add_experience(
                    exp_type=TYPE_LESSON,
                    title=title[:80],
                    description=entry.get("description", ""),
                    outcome=entry.get("outcome", ""),
                    lesson=lesson_text[:200],
                    domain=domain,
                    tags=entry.get("tags", []),
                    confidence=0.85,
                    source="failure_log"
                )
                if eid:
                    saved += 1
            except:
                pass
    return saved

# ─── 自动提取：从日记扫描 ─────────────────────────────────────────

# 经验相关关键词
EXPERIENCE_PATTERNS = [
    # 成功模式
    (r'(?:成功|跑通|就位|完成|验证通过|测试通过)[：:：]?\s*(.{10,100})', TYPE_SUCCESS, 0.75),
    (r'(?:方法是|解决方案|最终用|用这个方式)[：:：]?\s*(.{10,100})', TYPE_SUCCESS, 0.7),
    # 失败模式
    (r'(?:失败|报错|踩坑|发现问题|被卡住|卡死)[：:：]?\s*(.{10,100})', TYPE_LESSON, 0.8),
    (r'(?:原因是|问题出在|注意|下次别|不能用|不要)[：:：]?\s*(.{10,100})', TYPE_LESSON, 0.7),
    # 注意事项
    (r'(?:注意|小心|记住|要点|关键)[：:：]?\s*(.{10,100})', TYPE_CAUTION, 0.65),
]

def import_from_diary(days_back: int = 7) -> int:
    """从近N天日记里提取经验"""
    saved = 0
    today = datetime.date.today()
    for i in range(days_back):
        date = today - datetime.timedelta(days=i)
        fpath = DIARY_DIR / f"{date}.md"
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8")
        for pattern, exp_type, conf in EXPERIENCE_PATTERNS:
            for m in re.finditer(pattern, content):
                snippet = m.group(0)[:100]
                # 简单去噪：太短或太通用的跳过
                if len(snippet) < 15:
                    continue
                eid = add_experience(
                    exp_type=exp_type,
                    title=snippet[:80],
                    lesson=f"来自{date}日记",
                    domain="日记自动提取",
                    confidence=conf,
                    source=f"diary_{date}"
                )
                if eid:
                    saved += 1
    return saved

# ─── 预置：今天建立的经验（种子数据）─────────────────────────────

SEED_EXPERIENCES = [
    {
        "type": TYPE_SUCCESS,
        "title": "PowerShell 中用 & 调用 Python 脚本，需要在引号内不含空格参数",
        "description": "PowerShell 对包含空格路径的命令，需要用 & '路径' 参数 形式调用",
        "outcome": "正常执行",
        "lesson": "PowerShell 调 python 时，用 & 'path' args 格式，不要 'path args' 放一起",
        "domain": "PowerShell/系统",
        "tags": ["PowerShell", "Python", "路径", "命令行"],
        "confidence": 0.95
    },
    {
        "type": TYPE_LESSON,
        "title": "emoji 在 Windows GBK 控制台会导致 UnicodeEncodeError",
        "description": "Python print() 包含 emoji 时，在 Windows 默认 GBK 编码控制台报错",
        "outcome": "程序崩溃，输出中断",
        "lesson": "Windows 下运行 Python 脚本，必须设置 $env:PYTHONIOENCODING='utf-8' 或在脚本开头处理编码",
        "domain": "Python/编码",
        "tags": ["emoji", "gbk", "utf-8", "UnicodeEncodeError", "Windows"],
        "confidence": 0.98
    },
    {
        "type": TYPE_SUCCESS,
        "title": "OpenClaw 源码嫁接：chunkMarkdown + 中文停用词 + 二元组分词",
        "description": "从 OpenClaw memory-host-sdk 移植三个关键功能到 lan_memory.py",
        "outcome": "lan_memory.py v3.0 记忆检索精度大幅提升",
        "lesson": "嫁接的正确姿势：只取对方逻辑基因，用自己的语言重写，不直接复制粘贴",
        "domain": "记忆系统",
        "tags": ["OpenClaw", "记忆", "分词", "嫁接"],
        "confidence": 0.9
    },
    {
        "type": TYPE_LESSON,
        "title": "LobsterAI vite.config.ts host:true 会暴露局域网端口",
        "description": "LobsterAI 默认配置 host: true，让 5175 端口对局域网所有设备开放",
        "outcome": "安全风险，局域网内任何人能访问",
        "lesson": "接入第三方项目时，先检查网络绑定配置。开发用改为 host: localhost",
        "domain": "安全",
        "tags": ["Vite", "LobsterAI", "安全", "局域网", "端口"],
        "confidence": 0.95
    },
    {
        "type": TYPE_SUCCESS,
        "title": "ADB 双根架构：模拟器+真机同时管理",
        "description": "通过 leidian/adb.exe 同时管理 emulator-5554 和 LVIFGALBWOZ9GYLV",
        "outcome": "双根成功建立，手机和模拟器各自独立",
        "lesson": "ADB 连接时先 adb devices 确认设备列表，用 -s 参数指定目标设备",
        "domain": "ADB/Android",
        "tags": ["ADB", "模拟器", "真机", "双根"],
        "confidence": 0.9
    },
    {
        "type": TYPE_CAUTION,
        "title": "GitHub 代理需要显式设置，默认走直连会超时",
        "description": "git push/pull 在不设代理时经常超时，需要配置 http.proxy",
        "outcome": "正常推送需要代理 127.0.0.1:18082",
        "lesson": "Git 推送前确认代理是否激活，或在 git config 里设置",
        "domain": "GitHub/网络",
        "tags": ["GitHub", "代理", "Git", "超时"],
        "confidence": 0.9
    },
    {
        "type": TYPE_LESSON,
        "title": "MIUI 防火墙静默拦截 8022 端口，SSH 要改 22222",
        "description": "Termux SSH 默认端口 8022 被 MIUI 防火墙静默丢包，不报错",
        "outcome": "SSH 连接无响应，换 22222 后正常",
        "lesson": "手机上 SSH 端口被拦时不报错只超时，要换非常规端口绕开",
        "domain": "SSH/手机",
        "tags": ["SSH", "MIUI", "防火墙", "Termux", "端口"],
        "confidence": 0.95
    },
    {
        "type": TYPE_SUCCESS,
        "title": "记忆向量化用 paraphrase-multilingual-MiniLM-L12-v2，纯CPU可运行",
        "description": "sentence-transformers 的多语言 MiniLM，384维，~120MB，支持中文，不需要GPU",
        "outcome": "17/17 记忆覆盖，语义检索正常",
        "lesson": "小型向量模型本地跑完全可行，不需要云端API，privacy友好",
        "domain": "向量/记忆",
        "tags": ["embedding", "sentence-transformers", "中文", "向量", "CPU"],
        "confidence": 0.92
    },
]

def seed_experiences() -> int:
    """写入种子经验（首次建库时调用）"""
    saved = 0
    for exp in SEED_EXPERIENCES:
        eid = add_experience(
            exp_type=exp["type"],
            title=exp["title"],
            description=exp.get("description",""),
            outcome=exp.get("outcome",""),
            lesson=exp.get("lesson",""),
            domain=exp.get("domain",""),
            tags=exp.get("tags",[]),
            confidence=exp.get("confidence",0.8),
            source="seed"
        )
        if eid:
            saved += 1
    return saved

# ─── CLI 入口 ──────────────────────────────────────────────────────

def cmd_init():
    """初始化数据库 + 种子数据 + 导入失败日志"""
    print("初始化经验记忆层...")
    init_db()
    # 种子
    s = seed_experiences()
    print(f"  种子经验：{s} 条")
    # 从失败日志导入
    f = import_from_failure_log()
    print(f"  失败日志导入：{f} 条")
    # 从近7天日记提取
    d = import_from_diary(days_back=7)
    print(f"  日记自动提取：{d} 条")
    st = stats()
    print(f"\n经验库就位：")
    print(f"  成功经验 {st[TYPE_SUCCESS]} 条")
    print(f"  失败教训 {st[TYPE_LESSON]} 条")
    print(f"  注意事项 {st[TYPE_CAUTION]} 条")
    print(f"  合计 {st['total']} 条 -> {EXP_DB}")

def cmd_list(exp_type=None, limit=20):
    """列出经验"""
    entries = get_all(exp_type, limit)
    if not entries:
        print("经验库为空")
        return
    for e in entries:
        emoji = EMOJI.get(e["type"], "?")
        print(f"\n{emoji} [{e['type']}] {e['title']}")
        if e.get("lesson"):
            print(f"   教训: {e['lesson'][:80]}")
        if e.get("domain"):
            print(f"   领域: {e['domain']}  时间: {e['created_at'][:10]}")

def cmd_search(keyword):
    """搜索经验"""
    results = search_experience(keyword)
    print(f"\n搜索 '{keyword}' -> {len(results)} 条\n")
    for r in results:
        emoji = EMOJI.get(r["type"], "?")
        print(f"{emoji} {r['title']}")
        if r.get("lesson"):
            print(f"   {r['lesson'][:80]}")

def cmd_add(exp_type, title, lesson="", domain=""):
    """手动添加一条经验"""
    eid = add_experience(exp_type, title, lesson=lesson, domain=domain, source="manual")
    if eid:
        print(f"已添加：[{exp_type}] {title}")
    else:
        print("已存在相同标题，跳过")

def cmd_stats():
    """显示统计"""
    st = stats()
    print(f"\n经验记忆库统计：")
    print(f"  总计: {st['total']} 条")
    print(f"  成功经验: {st[TYPE_SUCCESS]} 条")
    print(f"  失败教训: {st[TYPE_LESSON]} 条")
    print(f"  注意事项: {st[TYPE_CAUTION]} 条")

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "init":
        cmd_init()
    elif cmd == "list":
        t = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_list(t)
    elif cmd == "search":
        kw = sys.argv[2] if len(sys.argv) > 2 else ""
        cmd_search(kw)
    elif cmd in ("add-success", "add-lesson", "add-caution"):
        type_map = {"add-success": TYPE_SUCCESS, "add-lesson": TYPE_LESSON, "add-caution": TYPE_CAUTION}
        title = sys.argv[2] if len(sys.argv) > 2 else "无标题"
        lesson = sys.argv[3] if len(sys.argv) > 3 else ""
        cmd_add(type_map[cmd], title, lesson)
    elif cmd == "stats":
        cmd_stats()
    else:
        print("用法：")
        print("  python lan_experience.py init            # 初始化 + 种子数据")
        print("  python lan_experience.py list [type]     # 列出经验（SUCCESS/LESSON/CAUTION）")
        print("  python lan_experience.py search <关键词> # 搜索")
        print("  python lan_experience.py add-success <标题> [教训]  # 手动添加成功经验")
        print("  python lan_experience.py add-lesson <标题> [教训]   # 手动添加失败教训")
        print("  python lan_experience.py add-caution <标题> [教训]  # 手动添加注意事项")
        print("  python lan_experience.py stats           # 统计")
