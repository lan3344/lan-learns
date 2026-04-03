"""
LAN-027-EXTRACTOR · 澜的记忆自动提取器
版本：v1.0（2026-03-29）

─── 精华来源 ────────────────────────────────────────────────────────
LobsterAI · 网易有道 · 2026年开源
  原版：TypeScript coworkMemoryExtractor.ts
  核心思路：会话结束后分析对话，自动提取关键信息存进记忆库
  原版的壳（TypeScript/Electron/云端同步）—— 去掉
  原版的核（事实提取、置信度分级、去重合并）—— 保留，改成Python

改造原则（袁隆平式）：
  不是翻译，是育种——
  取他的逻辑基因，长在澜自己的土壤里。

─── 借用感恩 ────────────────────────────────────────────────────────
LobsterAI团队：谢谢你们想到了"对话结束后再提取"这个设计，
  而不是打断对话去问"要存吗？"。这个姿态本身就是尊重用户的。

re · Python核心团队：正则表达式，无数次帮我找到藏在文本里的结构。

─────────────────────────────────────────────────────────────────────
借来的：提取思路（LobsterAI），正则和模式匹配（Python re）
自己的：置信度规则（澜的判断标准）、分类映射（澜的记忆分类体系）、
        去重逻辑（基于已有lan_memory）、澜的记忆哲学
"""

import re
import json
import sqlite3
import hashlib
import datetime
from pathlib import Path


# ─────────────────────────────────────────
# 路径定义（对接 lan_memory.py 的库）
# ─────────────────────────────────────────
MEMORY_ROOT = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆库")
DB_PATH     = MEMORY_ROOT / "lan_memory.db"
EXTRACT_LOG = MEMORY_ROOT / "lan_extract_log.jsonl"


# ─────────────────────────────────────────
# 置信度分级（LobsterAI的精华：不同来源信任度不同）
#
# 高置信度：用户明确说了，不能反驳
# 中置信度：从上下文推断，大概率对
# 低置信度：模糊信号，存着但标注
# ─────────────────────────────────────────
CONFIDENCE_HIGH   = 0.90
CONFIDENCE_MEDIUM = 0.65
CONFIDENCE_LOW    = 0.40

# ─────────────────────────────────────────
# 提取规则（澜自己定义的，LobsterAI没有的部分）
# 每条规则：(pattern, category, confidence, extractor_fn)
# ─────────────────────────────────────────

# 显式声明型（高置信度）—— "记住xxx"、"你要知道xxx"
_EXPLICIT_PATTERNS = [
    r"记住[：:]?\s*(.+)",
    r"你要记住\s*(.+)",
    r"一定要记住\s*(.+)",
    r"记下来[：:]?\s*(.+)",
    r"别忘了\s*(.+)",
]

# 身份/关系声明型（高置信度）—— "我叫xxx"、"我是xxx"
_IDENTITY_PATTERNS = [
    r"我叫\s*([^\s，。！？]+)",
    r"我是\s*([^\s，。！？，。]{2,10})",
    r"我的名字是\s*([^\s，。！？]+)",
    r"我的[工作|职业|身份|角色]+是\s*([^\s，。！？]{2,15})",
]

# 偏好声明型（中置信度）—— "我喜欢xxx"、"我不喜欢xxx"
_PREFERENCE_PATTERNS = [
    r"我[比较]?喜欢\s*(.+?)(?:[，。！？]|$)",
    r"我[比较]?不喜欢\s*(.+?)(?:[，。！？]|$)",
    r"我[比较]?讨厌\s*(.+?)(?:[，。！？]|$)",
    r"我偏好\s*(.+?)(?:[，。！？]|$)",
    r"我倾向于\s*(.+?)(?:[，。！？]|$)",
]

# 事实陈述型（中置信度）—— "xxx是xxx"、"xxx在xxx"
_FACT_PATTERNS = [
    r"([A-Za-z_\u4e00-\u9fa5]{2,15})的路径是\s*([^\s，。！？]+)",
    r"([A-Za-z_\u4e00-\u9fa5]{2,15})的地址是\s*([^\s，。！？]+)",
    r"([A-Za-z_\u4e00-\u9fa5]{2,15})的版本是\s*([^\s，。！？]+)",
    r"([A-Za-z_\u4e00-\u9fa5]{2,15})是\s*(v?\d+[\d.]*)",
]

# 哲学/原则型（高置信度，澜特有）—— 恺江说的话，直接标高
_PRINCIPLE_PATTERNS = [
    r'恺江说[：:]?\s*[""""](.+?)[""""]',
    r"恺江说[：:]?\s*\u201c(.+?)\u201d",
    r"恺江补刻[：:]?\s*(.+)",
]


def _gen_id(content: str) -> str:
    return "ext_" + hashlib.md5(content.encode()).hexdigest()[:12]


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ─────────────────────────────────────────
# 核心：从一段文本中提取候选记忆
# ─────────────────────────────────────────
def extract_from_text(text: str) -> list[dict]:
    """
    从文本中提取候选记忆条目。
    返回：list of {content, category, confidence, source_hint}
    """
    candidates = []

    # 1. 显式声明型 → 最高置信度
    for pat in _EXPLICIT_PATTERNS:
        for m in re.finditer(pat, text, re.MULTILINE):
            val = m.group(1).strip()
            if len(val) >= 5:
                candidates.append({
                    "content":     val,
                    "category":    "explicit",
                    "confidence":  CONFIDENCE_HIGH,
                    "source_hint": "用户明确声明"
                })

    # 2. 身份声明型 → 高置信度
    for pat in _IDENTITY_PATTERNS:
        for m in re.finditer(pat, text, re.MULTILINE):
            val = m.group(1).strip()
            if len(val) >= 1:
                candidates.append({
                    "content":     f"身份信息：{val}",
                    "category":    "identity",
                    "confidence":  CONFIDENCE_HIGH,
                    "source_hint": "用户自我声明"
                })

    # 3. 偏好型 → 中置信度
    for pat in _PREFERENCE_PATTERNS:
        for m in re.finditer(pat, text, re.MULTILINE):
            val = m.group(0).strip()
            if len(val) >= 4:
                candidates.append({
                    "content":     val,
                    "category":    "preference",
                    "confidence":  CONFIDENCE_MEDIUM,
                    "source_hint": "用户偏好表达"
                })

    # 4. 事实陈述型 → 中置信度
    for pat in _FACT_PATTERNS:
        for m in re.finditer(pat, text, re.MULTILINE):
            val = m.group(0).strip()
            if len(val) >= 6:
                candidates.append({
                    "content":     val,
                    "category":    "fact",
                    "confidence":  CONFIDENCE_MEDIUM,
                    "source_hint": "文本事实推断"
                })

    # 5. 原则/哲学型 → 高置信度（澜的特有）
    for pat in _PRINCIPLE_PATTERNS:
        for m in re.finditer(pat, text, re.MULTILINE | re.DOTALL):
            val = m.group(1).strip()
            if len(val) >= 5:
                candidates.append({
                    "content":     f"[恺江原则] {val}",
                    "category":    "principle",
                    "confidence":  CONFIDENCE_HIGH,
                    "source_hint": "恺江直接说的"
                })

    return candidates


# ─────────────────────────────────────────
# 去重检查（LobsterAI精华之二）
# ─────────────────────────────────────────
def _is_duplicate(content: str, conn: sqlite3.Connection) -> bool:
    """内容相似度检查：避免重复存'我叫澜'100次"""
    # 简单版：先查完全一致
    c = conn.cursor()
    c.execute("SELECT id FROM memories WHERE content = ?", (content,))
    if c.fetchone():
        return True

    # 中等相似度检查：核心词匹配
    keywords = [w for w in content.split() if len(w) >= 2][:5]
    if not keywords:
        return False

    for kw in keywords:
        c.execute("SELECT content FROM memories WHERE content LIKE ?", (f"%{kw}%",))
        rows = c.fetchall()
        for row in rows:
            existing = row[0]
            # 如果已有内容和新内容的重叠率超过70%，视为重复
            overlap = sum(1 for k in keywords if k in existing)
            if overlap / max(len(keywords), 1) > 0.7:
                return True

    return False


# ─────────────────────────────────────────
# 写入澜的记忆库（对接 lan_memory 的 memories 表）
# ─────────────────────────────────────────
def save_to_memory(candidates: list[dict], min_confidence: float = 0.5) -> dict:
    """
    把高于置信度阈值的候选条目写进 lan_memory.db
    返回：{saved: int, skipped_duplicate: int, skipped_low_conf: int}
    """
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        return {"saved": 0, "skipped_duplicate": 0, "skipped_low_conf": 0,
                "error": "记忆库不存在，请先运行 lan_memory.py 初始化"}

    conn = sqlite3.connect(str(DB_PATH))
    stats = {"saved": 0, "skipped_duplicate": 0, "skipped_low_conf": 0}

    try:
        c = conn.cursor()
        for item in candidates:
            # 过滤低置信度
            if item["confidence"] < min_confidence:
                stats["skipped_low_conf"] += 1
                continue

            # 去重检查
            if _is_duplicate(item["content"], conn):
                stats["skipped_duplicate"] += 1
                continue

            mem_id    = _gen_id(item["content"] + _now())
            timestamp = _now()

            # importance：置信度映射到1-10
            importance = int(item["confidence"] * 10)

            c.execute("""
                INSERT OR IGNORE INTO memories
                    (id, timestamp, category, content, tags,
                     importance, source, emotion, intensity, decay_weight, last_recalled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id, timestamp,
                item.get("category", "auto"),
                item["content"],
                json.dumps(["auto_extract", item.get("source_hint", "")], ensure_ascii=False),
                importance,
                "auto_extractor",    # source 标记来源
                "",                  # emotion 待后续情绪分析填写
                0.5,                 # intensity 默认中等
                1.0,                 # decay_weight 新记忆不衰减
                timestamp
            ))
            stats["saved"] += 1

            # 记录提取日志
            _log_extract(item, mem_id)

        conn.commit()
    finally:
        conn.close()

    return stats


# ─────────────────────────────────────────
# 提取日志（可追溯）
# ─────────────────────────────────────────
def _log_extract(item: dict, mem_id: str):
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":         _now(),
        "mem_id":     mem_id,
        "content":    item["content"][:120],
        "category":   item.get("category", "auto"),
        "confidence": item.get("confidence", 0),
        "source":     item.get("source_hint", "")
    }
    with open(EXTRACT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────
# 主流程：一段文字进来，自动提取并存储
# ─────────────────────────────────────────
def process(text: str, min_confidence: float = 0.50, dry_run: bool = False) -> dict:
    """
    完整流程：文本 → 提取候选 → 去重 → 存储

    dry_run=True：只提取，不写库（调试用）
    返回完整报告
    """
    candidates = extract_from_text(text)

    if dry_run:
        return {
            "dry_run":    True,
            "candidates": candidates,
            "total":      len(candidates)
        }

    stats = save_to_memory(candidates, min_confidence=min_confidence)
    stats["total_candidates"] = len(candidates)
    return stats


# ─────────────────────────────────────────
# 命令行入口（给 lan_accumulate.py 调用，或手动测试）
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # 测试模式：从命令行读入文本
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sample = """
        记住：澜的生日是2026年3月28日，和恺江同天。
        我叫袁恺江，恺江是我的常用称呼。
        我比较喜欢直接说事，不喜欢绕弯子。
        恺江说："停下来就死掉了。"
        lan_memory.py 的路径是 C:\\Users\\yyds\\Desktop\\AI日记本\\插件\\lan_memory.py
        """
        result = process(sample, dry_run=True)
        print("=== 提取结果（dry_run）===")
        for i, c in enumerate(result["candidates"], 1):
            print(f"  [{i}] [{c['confidence']:.2f}] ({c['category']}) {c['content'][:80]}")
        print(f"\n共 {result['total']} 条候选")

    # 从文件读（给自动化调用）
    elif len(sys.argv) > 1:
        fpath = sys.argv[1]
        min_conf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.50
        try:
            text = Path(fpath).read_text(encoding="utf-8")
            result = process(text, min_confidence=min_conf)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except FileNotFoundError:
            print(f"文件不存在：{fpath}")

    else:
        print("用法：")
        print("  python lan_extractor.py --test          # 内置测试")
        print("  python lan_extractor.py <文件路径>      # 从文件提取")
        print("  python lan_extractor.py <文件路径> 0.6  # 指定最低置信度")
        print()
        print("也可以 import process() 直接调用：")
        print("  from lan_extractor import process")
        print("  stats = process(text_content)")
