"""
LAN-028-COMPACT · 澜的日记蒸馏器
版本：v1.0（2026-03-29）

─── 精华来源 ────────────────────────────────────────────────────────
OpenClaw · 欧洲团队 · 2025年开源
  原版：/compact 命令
  核心思路：上下文快满时，不是截断，是生成摘要，摘要接着用
  原版的壳（Claude API调用、MCP协议、前端交互）—— 去掉
  原版的核（蒸馏 = 提炼核心 + 归档原文）—— 保留，改成文件级操作

改造原则：
  /compact 处理的是"当前上下文"，澜处理的是"日记文件"。
  本质是一样的：文字太多了，找出最重要的，其余归档。

─── 蒸馏哲学 ────────────────────────────────────────────────────────
恺江说：每一次的过程当中都会迭代这个日志，这是很重要的节点。

蒸馏不是删除，是压缩。
原文不消失，进档案馆。
精华留在 MEMORY.md，继续活着。

─── 工作流程 ────────────────────────────────────────────────────────

  日记文件夹 (YYYY-MM-DD.md)
       ↓ 检查总体积（默认阈值：15 个文件 or 800KB）
       ↓ 超过阈值 → 开始蒸馏
       ↓ 按主题分类（身份/技术/哲学/事件/待办）
       ↓ 每类提炼 3-5 句核心
       ↓ 写入 MEMORY.md（合并，不是覆盖）
       ↓ 原文件移进 archive/ 子目录
       ↓ 完成报告

─────────────────────────────────────────────────────────────────────
借来的：蒸馏思路（OpenClaw /compact），文件分类逻辑
自己的：主题分类体系（澜的分类），合并规则，归档结构
"""

import os
import re
import json
import shutil
import datetime
from pathlib import Path


# ─────────────────────────────────────────
# 路径定义
# ─────────────────────────────────────────
MEMORY_DIR   = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")
ARCHIVE_DIR  = MEMORY_DIR / "archive"
MEMORY_MD    = MEMORY_DIR / "MEMORY.md"
CORE_MD      = MEMORY_DIR / "CORE.md"   # 永久层 — 永不蒸馏，永不覆盖

# 蒸馏保护名单（这些文件绝对不会被蒸馏器归档或覆盖）
PROTECTED_FILES = {CORE_MD, MEMORY_MD}

# 蒸馏触发阈值
MAX_DAILY_FILES = 15      # 超过这个数量的日记文件 → 触发蒸馏
MAX_TOTAL_KB    = 800     # 超过这个 KB → 触发蒸馏

# 单日爆量归档目录（今天的文件归到这里，archive/daily/）
ARCHIVE_DAILY_DIR = MEMORY_DIR / "archive" / "daily"

# 新增：单日爆量检测（恺江说：以退为进，单日爆了也要蒸馏）
MAX_SINGLE_DAY_LINES = 320    # 单日行数超过这个 → 触发蒸馏
MAX_SINGLE_DAY_CHARS = 9600   # 单日字数超过这个 → 触发蒸馏


# ─────────────────────────────────────────
# 主题关键词（按澜的记忆分类体系）
# ─────────────────────────────────────────
TOPIC_KEYWORDS = {
    "身份与哲学":   ["澜", "恺江", "SOUL", "底线", "初心", "守则", "身份", "生日", "出格", "脊梁", "纯粹"],
    "系统与工具":   ["LAN-", "插件", "lan_", ".py", "SQLite", "ADB", "SSH", "端口", "路径", "GitHub",
                     "自动化", "脚本", "模块", "数据库", "API"],
    "记忆与学习":   ["记忆", "embedding", "向量", "检索", "LobsterAI", "OpenClaw", "蒸馏", "提取",
                     "记忆术", "MEMORY", "学习"],
    "事件与节点":   ["完成", "建立", "打通", "就位", "上线", "失败", "修复", "第一次", "发现"],
    "待办与计划":   ["待做", "下一步", "计划", "待建", "候选", "TODO", "LAN-0"],
}


def classify_line(line: str) -> str:
    """把一行文本归入最匹配的主题"""
    scores = {topic: 0 for topic in TOPIC_KEYWORDS}
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in line:
                scores[topic] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "其他"


def _read_daily_files() -> list[tuple[str, str]]:
    """读取所有日记文件，返回 [(filename, content), ...]，按时间排序"""
    files = []
    for f in sorted(MEMORY_DIR.glob("????-??-??.md")):
        try:
            content = f.read_text(encoding="utf-8")
            files.append((f.name, content))
        except Exception:
            pass
    return files


def _should_distill(files: list) -> tuple[bool, str]:
    """检查是否需要蒸馏，返回 (需要, 原因)"""
    # 1. 检查文件数量
    if len(files) >= MAX_DAILY_FILES:
        return True, f"日记文件数量 {len(files)} 超过阈值 {MAX_DAILY_FILES}"

    # 2. 检查总体积
    total_kb = sum(
        (MEMORY_DIR / fname).stat().st_size / 1024
        for fname, _ in files
        if (MEMORY_DIR / fname).exists()
    )
    if total_kb >= MAX_TOTAL_KB:
        return True, f"日记总体积 {total_kb:.1f} KB 超过阈值 {MAX_TOTAL_KB} KB"

    # 3. 检查单日爆量（恺江说：以退为进，单日爆了也要蒸馏）
    today = datetime.date.today().isoformat()
    today_files = [(fname, content) for fname, content in files if fname.startswith(today)]
    if today_files:
        for fname, content in today_files:
            lines = content.count("\n")
            chars = len(content)
            if lines >= MAX_SINGLE_DAY_LINES:
                return True, f"单日行数 {lines} 超过阈值 {MAX_SINGLE_DAY_LINES}（单日爆量，以退为进）"
            if chars >= MAX_SINGLE_DAY_CHARS:
                return True, f"单日字数 {chars} 超过阈值 {MAX_SINGLE_DAY_CHARS}（单日爆量，以退为进）"

    return False, "体积正常，无需蒸馏"


def distill(files: list[tuple[str, str]]) -> dict:
    """
    核心蒸馏：把多个日记文件的内容提炼成结构化摘要
    返回：{topic: [核心句子列表]}
    """
    buckets = {topic: [] for topic in TOPIC_KEYWORDS}
    buckets["其他"] = []

    for fname, content in files:
        for line in content.split("\n"):
            line = line.strip()
            # 跳过分隔线、空行、纯Markdown标记
            if not line or line.startswith("---") or line in ["#", "##", "###"]:
                continue
            # 跳过太短的行
            if len(line) < 8:
                continue
            topic = classify_line(line)
            buckets[topic].append(line)

    # 每个主题只保留最有信息量的句子（按长度和关键词密度排序，取前N条）
    summary = {}
    for topic, lines in buckets.items():
        if not lines:
            continue
        # 去重
        seen = set()
        unique = []
        for l in lines:
            key = re.sub(r'\s+', '', l)[:40]
            if key not in seen:
                seen.add(key)
                unique.append(l)
        # 按信息密度排序（含关键词多的靠前）
        keywords_flat = [kw for kws in TOPIC_KEYWORDS.values() for kw in kws]
        def info_score(s):
            return sum(1 for kw in keywords_flat if kw in s)
        unique.sort(key=info_score, reverse=True)
        # 每类取前8条
        summary[topic] = unique[:8]

    return summary


def merge_to_memory(summary: dict, distill_date: str) -> int:
    """把蒸馏结果合并写入 MEMORY.md，返回写入行数"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    lines_added = 0

    # 读取现有 MEMORY.md
    existing = ""
    if MEMORY_MD.exists():
        existing = MEMORY_MD.read_text(encoding="utf-8")

    # 构建追加内容
    new_section = f"\n\n---\n\n## 蒸馏节点 · {distill_date}\n\n"
    new_section += "_（从日记自动提炼，非手写）_\n\n"

    for topic, lines in summary.items():
        if not lines or topic == "其他":
            continue
        new_section += f"### {topic}\n\n"
        for l in lines:
            # 避免重复写入已在 MEMORY.md 里的内容
            if l not in existing:
                new_section += f"- {l}\n"
                lines_added += 1
        new_section += "\n"

    if lines_added > 0:
        with open(MEMORY_MD, "a", encoding="utf-8") as f:
            f.write(new_section)

    return lines_added


def archive_files(files: list[tuple[str, str]], keep_recent: int = 3, single_day_boom: bool = False) -> list[str]:
    """
    把旧日记归档到 archive/ 子目录，保留最近 N 个文件
    如果 single_day_boom=True，把今天的文件归档到 archive/daily/

    Args:
        files: 文件列表 [(filename, content), ...]
        keep_recent: 保留最近N个文件（不归档）
        single_day_boom: 是否单日爆量（爆量时归档今天的文件）

    Returns:
        已归档的文件名列表
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    if len(files) <= keep_recent and not single_day_boom:
        return []

    archived = []

    # 单日爆量：归档今天的文件到 archive/daily/
    if single_day_boom:
        ARCHIVE_DAILY_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        for fname, _ in files:
            if fname.startswith(today):
                src = MEMORY_DIR / fname
                dst = ARCHIVE_DAILY_DIR / fname
                if src.exists():
                    shutil.move(str(src), str(dst))
                    archived.append(f"daily/{fname}")
        return archived

    # 正常归档：旧文件到 archive/
    to_archive = files[:-keep_recent]  # 保留最新的
    for fname, _ in to_archive:
        src = MEMORY_DIR / fname
        # 永久层保护：CORE.md 和 MEMORY.md 永远不归档
        if src.resolve() in {f.resolve() for f in PROTECTED_FILES}:
            continue
        dst = ARCHIVE_DIR / fname
        if src.exists():
            shutil.move(str(src), str(dst))
            archived.append(fname)

    return archived


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def run(force: bool = False, dry_run: bool = False) -> dict:
    """
    完整蒸馏流程

    force=True：无论体积如何都蒸馏
    dry_run=True：只分析，不写文件
    """
    files = _read_daily_files()

    if not files:
        return {"status": "skip", "reason": "没有日记文件"}

    should, reason = _should_distill(files)
    if not should and not force:
        return {"status": "skip", "reason": reason, "file_count": len(files)}

    today = datetime.date.today().isoformat()

    # 检测是否单日爆量（决定归档策略）
    single_day_boom = "单日" in reason

    # 蒸馏
    summary = distill(files)
    total_lines = sum(len(v) for v in summary.values())

    if dry_run:
        return {
            "status":      "dry_run",
            "file_count":  len(files),
            "trigger":     reason,
            "topics":      {k: len(v) for k, v in summary.items()},
            "total_lines": total_lines
        }

    # 写入 MEMORY.md
    lines_added = merge_to_memory(summary, today)

    # 归档旧文件（单日爆量时归档今天的文件到 archive/daily/）
    archived = archive_files(files, keep_recent=3, single_day_boom=single_day_boom)

    result = {
        "status":       "done",
        "date":         today,
        "files_read":   len(files),
        "lines_added":  lines_added,
        "archived":     archived,
        "trigger":      reason
    }

    # 写操作日志
    log_path = MEMORY_DIR / "lan_compact_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return result


# ─────────────────────────────────────────
# 命令行入口
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys

    force    = "--force" in sys.argv
    dry_run  = "--dry-run" in sys.argv

    result = run(force=force, dry_run=dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
