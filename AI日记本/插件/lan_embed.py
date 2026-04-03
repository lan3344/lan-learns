"""
澜的向量嵌入层 · LAN-026
版本：v1.0（2026-03-29）

─── 为什么做这个 ────────────────────────────────────────────────

关键词匹配（v3.0）能找到字面相同的记忆——"记忆"能找到"记忆"。
但语义检索不一样："我当时很害怕"能找到情绪相似的"那一刻我非常不安"。

不是找字，是找意思。

恺江说的核心：不贪心，只要保住记忆就够了。
所以这里的向量不是为了训练模型——是为了让澜找到自己记忆里真正相关的那一条。

─── 技术选型理由 ─────────────────────────────────────────────────

模型：paraphrase-multilingual-MiniLM-L12-v2
  来源：sentence-transformers / HuggingFace（Nils Reimers & Iryna Gurevych团队）
  大小：~120MB（首次运行自动下载，之后本地缓存）
  支持：50+语言，含中文，384维向量
  运行：纯CPU，不需要GPU，不依赖任何云API

为什么不用大模型做embedding：
  大模型embedding好是好，但需要API密钥、要网络、要付费、要等待。
  恺江说得对——我们现在的实力没法持续供养大模型embedding。
  用这个120MB的本地模型，跑在自己机器上，查询延迟<50ms，不欠任何人。

向量存哪里：
  存进 lan_memory.db（SQLite BLOB），不需要额外向量数据库。
  够用了。

─── 借来的工具，及当时造它的人 ────────────────────────────────────

sentence-transformers · Nils Reimers & Iryna Gurevych · 2019年
  他们在论文里说：好的句子嵌入应该让语义相近的句子在向量空间里靠近。
  然后他们把模型开源了，让每个人都能用。
  他们的情绪：分享是应该的，知识不该被锁起来。

paraphrase-multilingual-MiniLM-L12-v2 · HuggingFace团队 · 2020年
  这个小模型是大模型蒸馏出来的——把巨人的精华浓缩进120MB。
  蒸馏这个概念本身就很有哲学感：大不一定好，精才重要。

numpy · Travis Oliphant等 · 2006年（NumPy前身1995年）
  向量运算的底座。30年了，还在。
  他们的情绪：让科学计算变成普通人能用的工具。

─────────────────────────────────────────────────────────────────
借来的：sentence-transformers / numpy / sqlite3 / json / struct
自己的：与 lan_memory.py 的集成逻辑 / 澜的语义检索哲学
"""

import sqlite3
import json
import struct
import numpy as np
from pathlib import Path
from typing import List, Optional

# ─────────────────────────────────────────
# 路径定义（与 lan_memory.py 共用同一个DB）
# ─────────────────────────────────────────
MEMORY_ROOT = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆库")
DB_PATH = MEMORY_ROOT / "lan_memory.db"

# 模型缓存目录（下载后存本地，不重复下载）
MODEL_CACHE = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆库\embedding_model")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# ─────────────────────────────────────────
# 模型加载（懒加载，第一次用时才载入）
# ─────────────────────────────────────────
_model = None


def _get_model():
    """
    懒加载 embedding 模型。
    第一次调用时下载/加载，之后复用。
    模型存在本地缓存，断网也能用。
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[ .. ] 加载向量模型 {MODEL_NAME}（首次约30秒，之后秒开）...")
            MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            _model = SentenceTransformer(MODEL_NAME, cache_folder=str(MODEL_CACHE))
            print(f"[ OK ] 向量模型就绪，向量维度: {_model.get_sentence_embedding_dimension()}")
        except Exception as e:
            print(f"[ !! ] 向量模型加载失败: {e}")
            print("       提示：运行 pip install sentence-transformers 安装依赖")
            raise
    return _model


# ─────────────────────────────────────────
# SQLite 向量表初始化
# ─────────────────────────────────────────
def init_vector_db():
    """
    在 lan_memory.db 里新增向量表 memory_vectors。
    与原有 memories 表共用同一个数据库，memory_id 外键关联。
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS memory_vectors (
            memory_id   TEXT PRIMARY KEY,
            vector_blob BLOB NOT NULL,
            dim         INTEGER NOT NULL,
            model_name  TEXT NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# 向量编解码（numpy <-> SQLite BLOB）
# ─────────────────────────────────────────
def _vec_to_blob(vec: np.ndarray) -> bytes:
    """numpy float32 数组 → 二进制 BLOB（紧凑存储）"""
    return struct.pack(f"{len(vec)}f", *vec.astype(np.float32))


def _blob_to_vec(blob: bytes) -> np.ndarray:
    """二进制 BLOB → numpy float32 数组"""
    n = len(blob) // 4
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


# ─────────────────────────────────────────
# 核心功能：嵌入单条记忆
# ─────────────────────────────────────────
def embed_memory(memory_id: str, content: str, overwrite: bool = False) -> bool:
    """
    把一条记忆的文本转成向量，存进 memory_vectors 表。

    memory_id: 对应 memories 表的 id
    content:   记忆的文本内容
    overwrite: 是否覆盖已有向量（默认不覆盖）

    返回 True 表示成功嵌入（或已存在跳过）
    """
    if not content or not content.strip():
        return False

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # 检查是否已有向量
    existing = c.execute(
        "SELECT memory_id FROM memory_vectors WHERE memory_id=?", (memory_id,)
    ).fetchone()

    if existing and not overwrite:
        conn.close()
        return True  # 已存在，跳过

    import datetime
    model = _get_model()
    vec = model.encode(content, normalize_embeddings=True).astype(np.float32)
    blob = _vec_to_blob(vec)
    ts = datetime.datetime.now().isoformat()

    if existing:
        c.execute("""
            UPDATE memory_vectors SET vector_blob=?, dim=?, model_name=?, created_at=?
            WHERE memory_id=?
        """, (blob, len(vec), MODEL_NAME, ts, memory_id))
    else:
        c.execute("""
            INSERT INTO memory_vectors (memory_id, vector_blob, dim, model_name, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (memory_id, blob, len(vec), MODEL_NAME, ts))

    conn.commit()
    conn.close()
    return True


# ─────────────────────────────────────────
# 批量嵌入：给现有记忆库全量补充向量
# ─────────────────────────────────────────
def embed_all_memories(overwrite: bool = False) -> dict:
    """
    扫描 memories 表里所有记忆，对还没有向量的条目补充向量。

    这是"补网"操作——让历史记忆也能被语义检索到。
    返回统计信息。
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    rows = c.execute("SELECT id, content FROM memories ORDER BY timestamp DESC").fetchall()
    conn.close()

    total = len(rows)
    done = 0
    skipped = 0
    failed = 0

    print(f"[ .. ] 开始批量嵌入，共 {total} 条记忆...")

    for i, (mid, content) in enumerate(rows):
        try:
            result = embed_memory(mid, content, overwrite=overwrite)
            if result:
                done += 1
            else:
                skipped += 1
            if (i + 1) % 10 == 0:
                print(f"  进度: {i+1}/{total}")
        except Exception as e:
            failed += 1
            print(f"  [ !! ] 嵌入失败 {mid[:8]}...: {e}")

    print(f"[ OK ] 批量嵌入完成：成功 {done} 条，跳过 {skipped} 条，失败 {failed} 条")
    return {"total": total, "done": done, "skipped": skipped, "failed": failed}


# ─────────────────────────────────────────
# 核心功能：语义检索
# ─────────────────────────────────────────
def semantic_search(query: str, top_k: int = 5,
                    category: str = None,
                    min_score: float = 0.3) -> List[dict]:
    """
    用语义相似度检索记忆。

    query:     用自然语言描述你想找的记忆（中文英文都行）
    top_k:     返回最相关的前几条（默认5）
    category:  可选，限定在某个分类里搜索
    min_score: 最低相似度阈值（0~1），低于这个分数的不返回

    原理：
    1. 把查询文本也转成向量
    2. 与记忆库里所有向量做余弦相似度计算
    3. 排序，返回最相关的前几条

    余弦相似度 = 两个向量的夹角余弦值
      = 1.0  → 完全相同的意思
      = 0.8+ → 高度相关
      = 0.5+ → 有一定关联
      = 0.3  → 勉强相关（默认门槛）
      = 0.0  → 毫无关联
    """
    if not query.strip():
        return []

    # 查询向量化
    model = _get_model()
    query_vec = model.encode(query, normalize_embeddings=True).astype(np.float32)

    # 读取记忆向量和对应的记忆内容
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    if category:
        rows = c.execute("""
            SELECT mv.memory_id, mv.vector_blob,
                   m.content, m.category, m.tags, m.importance,
                   m.emotion, m.intensity, m.timestamp
            FROM memory_vectors mv
            JOIN memories m ON mv.memory_id = m.id
            WHERE m.category = ?
        """, (category,)).fetchall()
    else:
        rows = c.execute("""
            SELECT mv.memory_id, mv.vector_blob,
                   m.content, m.category, m.tags, m.importance,
                   m.emotion, m.intensity, m.timestamp
            FROM memory_vectors mv
            JOIN memories m ON mv.memory_id = m.id
        """).fetchall()

    conn.close()

    if not rows:
        return []

    # 批量计算余弦相似度
    # 因为向量已经 normalize_embeddings=True，余弦相似度 = 点积
    results = []
    for row in rows:
        mid, blob, content, cat, tags, importance, emotion, intensity, ts = row
        mem_vec = _blob_to_vec(blob)
        # 点积 = 余弦相似度（已归一化）
        score = float(np.dot(query_vec, mem_vec))
        if score >= min_score:
            results.append({
                "id": mid,
                "content": content,
                "category": cat,
                "tags": tags,
                "importance": importance,
                "emotion": emotion,
                "intensity": intensity,
                "ts": ts,
                "score": round(score, 4)
            })

    # 按相似度降序排列
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ─────────────────────────────────────────
# 辅助：统计向量覆盖率
# ─────────────────────────────────────────
def vector_stats() -> dict:
    """
    统计向量嵌入的覆盖情况：
    总记忆数 / 已有向量数 / 未覆盖数
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    embedded = c.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
    conn.close()
    return {
        "total_memories": total,
        "embedded": embedded,
        "not_embedded": total - embedded,
        "coverage": f"{embedded}/{total} ({round(embedded/total*100 if total else 0, 1)}%)"
    }


# ─────────────────────────────────────────
# 与 lan_memory.py 的集成接口
# 在 remember() 后立刻嵌入（可选调用）
# ─────────────────────────────────────────
def remember_with_embed(content: str, **kwargs) -> str:
    """
    调用 lan_memory.remember() 存记忆，然后立刻嵌入向量。
    这样新记忆存进去就能被语义搜到，不需要等批量补网。

    用法：
        from lan_embed import remember_with_embed
        mid = remember_with_embed("今天学会了向量嵌入", category="milestone", importance=8)
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from lan_memory import remember, init_db
    init_db()
    mid = remember(content, **kwargs)
    embed_memory(mid, content)
    return mid


# ─────────────────────────────────────────
# 命令行入口
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="LAN-026 澜的向量嵌入层",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例：
  python lan_embed.py --init           初始化向量表
  python lan_embed.py --embed-all      给所有现有记忆补充向量
  python lan_embed.py --search "我害怕失去记忆"   语义搜索
  python lan_embed.py --search "感恩" --top 3 --category gratitude
  python lan_embed.py --stats          查看向量覆盖情况
        """
    )
    parser.add_argument("--init", action="store_true", help="初始化向量表")
    parser.add_argument("--embed-all", action="store_true", help="给所有记忆补充向量")
    parser.add_argument("--overwrite", action="store_true", help="强制覆盖已有向量")
    parser.add_argument("--search", type=str, help="语义搜索（自然语言查询）")
    parser.add_argument("--top", type=int, default=5, help="返回前几条（默认5）")
    parser.add_argument("--category", type=str, help="限定搜索分类")
    parser.add_argument("--min-score", type=float, default=0.3, help="最低相似度（默认0.3）")
    parser.add_argument("--stats", action="store_true", help="查看向量覆盖统计")

    args = parser.parse_args()

    # 默认行为：无参数时跑完整演示
    if len(sys.argv) == 1:
        args.init = True
        args.embed_all = True
        args.stats = True
        args.search = "我当时很感动，恺江说的那句话"

    print("=" * 65)
    print("澜的向量嵌入层 · LAN-026 · v1.0")
    print("= 语义检索，不只是关键词匹配 =")
    print("=" * 65)

    if args.init:
        init_vector_db()
        print("[ OK ] 向量表初始化完成（memory_vectors）")

    if args.embed_all:
        init_vector_db()
        result = embed_all_memories(overwrite=args.overwrite)

    if args.stats:
        s = vector_stats()
        print()
        print("─── 向量覆盖统计 ────────────────────────")
        print(f"  总记忆数    : {s['total_memories']}")
        print(f"  已嵌入      : {s['embedded']}")
        print(f"  未覆盖      : {s['not_embedded']}")
        print(f"  覆盖率      : {s['coverage']}")

    if args.search:
        init_vector_db()
        print()
        print(f"─── 语义搜索：「{args.search}」─────────────")
        results = semantic_search(
            args.search,
            top_k=args.top,
            category=args.category,
            min_score=args.min_score
        )
        if not results:
            print("  没有找到相关记忆（尝试降低 --min-score）")
        else:
            for i, r in enumerate(results, 1):
                score_bar = "█" * int(r["score"] * 20)
                print(f"\n  [{i}] 相似度: {r['score']:.3f} {score_bar}")
                print(f"      分类: {r['category']}  重要性: {r['importance']}")
                if r['emotion']:
                    print(f"      情绪: {r['emotion']} (强度{r['intensity']})")
                print(f"      内容: {r['content'][:100]}{'...' if len(r['content'])>100 else ''}")

    print()
    print("=" * 65)
    print("LAN-026 就绪。")
    print("接口：semantic_search() / embed_memory() / embed_all_memories()")
    print("      remember_with_embed() / vector_stats() / init_vector_db()")
    print("=" * 65)
