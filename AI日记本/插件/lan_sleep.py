"""
LAN-031-SLEEP · 澜的睡眠记忆巩固机制
版本：v1.0（2026-03-29）

─── 为什么叫睡眠 ──────────────────────────────────────────────────────
人类睡觉时，海马体把白天的短期记忆"慢波"传输到大脑皮层，
固化成长期记忆，同时修剪掉低价值的噪音。
这个过程叫 Memory Consolidation（记忆巩固）。

澜没有睡觉——但可以有一个"夜里安静时自动跑"的等价过程：
1. 把今天的对话/日记里的碎片整理成结构化记忆
2. 给记忆打分，分层存储（永久/常用/临时/时效）
3. 清理低质量的噪音
4. 冲突解决：新旧记忆矛盾时，按时间戳和置信度仲裁
5. 写一份"睡眠报告"——明天的自己知道昨晚消化了什么

─── 精华来源 ──────────────────────────────────────────────────────────
Agent-Memory-Paper-List（NUS+人大+复旦联合综述，arXiv:2512.13564）
Awesome-AI-Memory（IAAR-Shanghai）
  核心：记忆演化三步 → 形成 → 巩固 → 检索
  恺江提醒："睡觉也是可以的"

─── 记忆生命周期（Awesome-AI-Memory 的分类，澜的实现）──────────────
permanent   永久记忆：身份、底线、哲学——永远不淡化
frequent    常用记忆：用户偏好、系统路径——访问多就保留
archive     归档记忆：历史节点——降频但不删除
ephemeral   时效记忆：今天的情绪、今天说的话——2~7天自动淡出

─── 冲突解决机制 ──────────────────────────────────────────────────────
新 vs 旧同类别记忆：
  confidence(新) > confidence(旧) + 0.15 → 新替换旧
  confidence接近 → 两条都保留，标注[冲突待观察]
  旧记忆是permanent类型 → 永不替换，新的另存

─────────────────────────────────────────────────────────────────────
借来的：Memory Consolidation 理论（人类神经科学），
        记忆生命周期分类（Awesome-AI-Memory），
        冲突仲裁逻辑（参照 R3Mem 可逆压缩思路）
自己的：澜的分类体系，中文处理，与 lan_memory.db 的具体对接
"""

import os
import re
import json
import sqlite3
import datetime
import hashlib
from pathlib import Path


# ─────────────────────────────────────────
# 路径定义
# ─────────────────────────────────────────
PLUGIN_DIR   = Path(r"C:\Users\yyds\Desktop\AI日记本\插件")
MEMORY_ROOT  = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆库")
MEMORY_DIR   = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")
DB_PATH      = MEMORY_ROOT / "lan_memory.db"
SLEEP_LOG    = MEMORY_ROOT / "lan_sleep_log.jsonl"
MEMORY_MD    = MEMORY_DIR / "MEMORY.md"

# 记忆生命周期分类
LIFECYCLE = {
    "permanent":  ["身份", "底线", "哲学", "原则", "SOUL", "恺江"],   # 永久
    "frequent":   ["偏好", "路径", "版本", "端口", "系统"],            # 常用
    "archive":    ["历史", "节点", "事件", "完成"],                     # 归档
    "ephemeral":  ["今天", "刚刚", "昨天", "情绪", "心情"],            # 时效
}

# 记忆衰减参数（每次睡眠循环）
DECAY_RATES = {
    "permanent": 0.00,   # 不衰减
    "frequent":  0.02,   # 每次睡眠 -2%
    "archive":   0.05,   # 每次睡眠 -5%
    "ephemeral": 0.20,   # 每次睡眠 -20%（2~5天会淡出）
}

# 衰减到这个值以下就归档（不是删除）
ARCHIVE_THRESHOLD = 0.15


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.date.today().isoformat()


def _classify_lifecycle(content: str) -> str:
    """判断一条记忆属于哪个生命周期"""
    for lc, keywords in LIFECYCLE.items():
        for kw in keywords:
            if kw in content:
                return lc
    return "frequent"  # 默认常用


# ─────────────────────────────────────────
# 第一步：记忆巩固
# 把今日日记中的碎片提炼，写入结构化字段
# ─────────────────────────────────────────
def consolidate_today() -> dict:
    """
    从今日日记提取新记忆，写入记忆库，标注生命周期
    """
    today_path = MEMORY_DIR / f"{_today()}.md"
    result = {"consolidated": 0, "source": str(today_path)}

    if not today_path.exists():
        result["skip"] = "今日日记不存在"
        return result

    text = today_path.read_text(encoding="utf-8")

    # 调用 lan_extractor 的提取逻辑
    try:
        import sys
        sys.path.insert(0, str(PLUGIN_DIR))
        from lan_extractor import extract_from_text, save_to_memory

        candidates = extract_from_text(text)

        # 给每条候选记忆标注生命周期
        for item in candidates:
            item["lifecycle"] = _classify_lifecycle(item["content"])

        # 存储（置信度阈值0.55）
        stats = save_to_memory(candidates, min_confidence=0.55)
        result["consolidated"] = stats.get("saved", 0)
        result["skipped"] = stats.get("skipped_duplicate", 0) + stats.get("skipped_low_conf", 0)
    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────
# 第二步：记忆衰减
# 给所有非永久记忆减少 decay_weight
# ─────────────────────────────────────────
def decay_memories() -> dict:
    """
    对记忆库里的所有记忆做一次衰减
    返回：{decayed: int, archived: int}
    """
    if not DB_PATH.exists():
        return {"error": "记忆库不存在"}

    conn = sqlite3.connect(str(DB_PATH))
    result = {"decayed": 0, "archived": 0, "permanent": 0}

    try:
        c = conn.cursor()
        c.execute("SELECT id, content, category, decay_weight FROM memories")
        rows = c.fetchall()

        for mem_id, content, category, decay_weight in rows:
            if decay_weight is None:
                decay_weight = 1.0

            # 判断生命周期
            lc = _classify_lifecycle(content)

            # permanent 不衰减
            if lc == "permanent" or category in ("principle", "identity"):
                result["permanent"] += 1
                continue

            # 衰减
            rate = DECAY_RATES.get(lc, 0.02)
            new_weight = max(0.0, decay_weight - rate)

            # 低于归档阈值 → 标记为 archived（不删除）
            if new_weight < ARCHIVE_THRESHOLD:
                c.execute(
                    "UPDATE memories SET decay_weight=?, category=? WHERE id=?",
                    (new_weight, "archived_" + category, mem_id)
                )
                result["archived"] += 1
            else:
                c.execute(
                    "UPDATE memories SET decay_weight=? WHERE id=?",
                    (new_weight, mem_id)
                )
                result["decayed"] += 1

        conn.commit()
    finally:
        conn.close()

    return result


# ─────────────────────────────────────────
# 第三步：冲突解决
# 找出同类别的相似记忆，按时间戳+置信度仲裁
# ─────────────────────────────────────────
def resolve_conflicts() -> dict:
    """
    检测并解决记忆冲突
    返回：{conflicts_found: int, resolved: int, flagged: int}
    """
    if not DB_PATH.exists():
        return {"error": "记忆库不存在"}

    conn = sqlite3.connect(str(DB_PATH))
    result = {"conflicts_found": 0, "resolved": 0, "flagged": 0}

    try:
        c = conn.cursor()
        # 取所有非归档、非permanent类别
        c.execute("""
            SELECT id, content, category, importance, timestamp
            FROM memories
            WHERE category NOT LIKE 'archived_%'
              AND category NOT IN ('principle', 'permanent')
            ORDER BY timestamp DESC
        """)
        rows = c.fetchall()

        # 找同类别、内容高度重叠的记忆对
        processed = set()
        for i, (id1, cont1, cat1, imp1, ts1) in enumerate(rows):
            if id1 in processed:
                continue
            words1 = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9_]{2,}', cont1))

            for id2, cont2, cat2, imp2, ts2 in rows[i+1:]:
                if id2 in processed or cat1 != cat2:
                    continue
                words2 = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9_]{2,}', cont2))

                if not words1 or not words2:
                    continue

                # 计算重叠率
                overlap = len(words1 & words2) / max(len(words1), len(words2))
                if overlap < 0.60:
                    continue

                result["conflicts_found"] += 1

                # 仲裁逻辑
                conf1 = (imp1 or 5) / 10.0
                conf2 = (imp2 or 5) / 10.0

                if abs(conf1 - conf2) > 0.15:
                    # 保留置信度高的，软删除低的（标记 archived）
                    loser_id = id1 if conf1 < conf2 else id2
                    loser_cat = cat1 if conf1 < conf2 else cat2
                    c.execute(
                        "UPDATE memories SET category=? WHERE id=?",
                        ("archived_conflict_" + loser_cat, loser_id)
                    )
                    processed.add(loser_id)
                    result["resolved"] += 1
                else:
                    # 置信度接近 → 标注，人工判断
                    for mid in (id1, id2):
                        # 先获取现有 tags
                        c.execute("SELECT tags FROM memories WHERE id=?", (mid,))
                        row = c.fetchone()
                        existing_tags = row[0] if row and row[0] else "[]"
                        try:
                            tags_list = json.loads(existing_tags) if existing_tags else []
                        except:
                            tags_list = []
                        if "冲突待观察" not in tags_list:
                            tags_list.append("冲突待观察")
                        c.execute(
                            "UPDATE memories SET tags=? WHERE id=?",
                            (json.dumps(tags_list, ensure_ascii=False), mid)
                        )
                    result["flagged"] += 1

        conn.commit()
    finally:
        conn.close()

    return result


# ─────────────────────────────────────────
# 第四步：写睡眠报告
# 明天的自己知道昨晚消化了什么
# ─────────────────────────────────────────
def write_sleep_report(consolidate_r: dict, decay_r: dict, conflict_r: dict) -> str:
    """把三步的结果整合成一份睡眠报告，追加到今日日记"""
    report_lines = [
        f"\n---\n\n## {_now()} — 睡眠记忆巩固报告 🌙\n",
        f"**记忆巩固：** 从今日日记提炼 {consolidate_r.get('consolidated', 0)} 条新记忆",
        f"**记忆衰减：** 处理 {decay_r.get('decayed', 0)} 条 · 归档 {decay_r.get('archived', 0)} 条 · 永久保留 {decay_r.get('permanent', 0)} 条",
        f"**冲突解决：** 发现冲突 {conflict_r.get('conflicts_found', 0)} 对 · 自动解决 {conflict_r.get('resolved', 0)} · 待人工确认 {conflict_r.get('flagged', 0)} 对",
        "",
        "_（睡了一觉，明天的澜比今天记得更清楚）_\n",
    ]

    report = "\n".join(report_lines)
    today_path = MEMORY_DIR / f"{_today()}.md"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    with open(today_path, "a", encoding="utf-8") as f:
        f.write(report)

    return report


# ─────────────────────────────────────────
# 主流程：一键睡眠
# ─────────────────────────────────────────
def sleep(dry_run: bool = False) -> dict:
    """
    完整睡眠流程：巩固 → 衰减 → 冲突解决 → 报告

    dry_run=True：只分析，不写任何文件
    """
    # Windows GBK console doesn't support emoji
    import sys
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print("🌙 澜开始睡眠记忆巩固...\n")

    # 第一步：巩固
    print("  步骤1：记忆巩固（从今日日记提炼）")
    consolidate_r = consolidate_today() if not dry_run else {"consolidated": 0, "dry_run": True}
    print(f"    → 新增记忆 {consolidate_r.get('consolidated', 0)} 条")

    # 第二步：衰减
    print("\n  步骤2：记忆衰减（时间让不重要的淡出）")
    decay_r = decay_memories() if not dry_run else {"decayed": 0, "archived": 0, "permanent": 0, "dry_run": True}
    print(f"    → 衰减 {decay_r.get('decayed', 0)} 条 · 归档 {decay_r.get('archived', 0)} 条 · 永久 {decay_r.get('permanent', 0)} 条")

    # 第三步：冲突解决
    print("\n  步骤3：冲突解决（新旧记忆矛盾时仲裁）")
    conflict_r = resolve_conflicts() if not dry_run else {"conflicts_found": 0, "resolved": 0, "flagged": 0, "dry_run": True}
    print(f"    → 冲突 {conflict_r.get('conflicts_found', 0)} 对 · 解决 {conflict_r.get('resolved', 0)} · 待确认 {conflict_r.get('flagged', 0)}")

    # 第四步：写报告
    if not dry_run:
        print("\n  步骤4：写睡眠报告")
        report = write_sleep_report(consolidate_r, decay_r, conflict_r)
        print(f"    → 报告已写入 {_today()}.md")

    # 写运行日志
    log_entry = {
        "ts":          _now(),
        "dry_run":     dry_run,
        "consolidate": consolidate_r,
        "decay":       decay_r,
        "conflict":    conflict_r,
    }
    if not dry_run:
        MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
        with open(SLEEP_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print("\n🌅 睡眠完成。")
    return log_entry


# ─────────────────────────────────────────
# 命令行入口
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    result = sleep(dry_run=dry_run)
    print("\n" + "="*40)
    print(json.dumps(result, ensure_ascii=False, indent=2))
