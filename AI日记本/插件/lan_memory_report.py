"""
lan_memory_report.py · 澜的记忆健康报告
========================================
版本：v1.0（2026-03-29）

从 lan_memory.db + lan_extract_log.jsonl + lan_experience.db
生成一份可读的记忆健康报告（HTML格式）

填补缺口：百年记忆草案缺口6 — 记忆没有置信度分层展示

用法：
  python lan_memory_report.py           # 生成报告 -> 澜的记忆报告.html
  python lan_memory_report.py --text    # 文本摘要输出到控制台
"""

import os
import json
import sqlite3
import datetime
from pathlib import Path
from collections import Counter, defaultdict


# ─── 路径 ─────────────────────────────────────────────────────────
MEMORY_ROOT = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆库")
DB_PATH     = MEMORY_ROOT / "lan_memory.db"
EXTRACT_LOG = MEMORY_ROOT / "lan_extract_log.jsonl"
EXP_DB      = MEMORY_ROOT / "lan_experience.db"
TL_DB       = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的成长时间线.jsonl")
OUTPUT_HTML = Path(r"C:\Users\yyds\Desktop\AI日记本\澜的记忆报告.html")


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── 数据收集 ──────────────────────────────────────────────────────

def get_memory_stats():
    """从 lan_memory.db 读统计"""
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 总条数
    c.execute("SELECT COUNT(*) FROM memories")
    total = c.fetchone()[0]

    # importance 分布 (= 置信度层级)
    c.execute("SELECT importance, COUNT(*) FROM memories GROUP BY importance ORDER BY importance DESC")
    importance_dist = dict(c.fetchall())

    # category 分布
    c.execute("SELECT category, COUNT(*) FROM memories GROUP BY category ORDER BY COUNT(*) DESC")
    category_dist = dict(c.fetchall())

    # 情绪分布
    c.execute("SELECT emotion, COUNT(*) FROM memories WHERE emotion IS NOT NULL GROUP BY emotion ORDER BY COUNT(*) DESC LIMIT 5")
    emotion_dist = dict(c.fetchall())

    # 向量覆盖率
    c.execute("SELECT COUNT(*) FROM memory_vectors")
    vector_count = c.fetchone()[0]

    # 最近10条记忆
    c.execute("""
        SELECT timestamp, category, content, importance
        FROM memories
        ORDER BY timestamp DESC LIMIT 10
    """)
    recent = [{"ts": r[0][:16], "cat": r[1], "content": r[2][:60], "imp": r[3]} for r in c.fetchall()]

    conn.close()
    return {
        "total": total,
        "importance_dist": importance_dist,
        "category_dist": category_dist,
        "emotion_dist": emotion_dist,
        "vector_count": vector_count,
        "vector_coverage": round(vector_count / total * 100) if total else 0,
        "recent": recent
    }


def get_extract_confidence():
    """从提取日志读置信度分布"""
    if not EXTRACT_LOG.exists():
        return {}
    highs, mids, lows = 0, 0, 0
    cats = Counter()
    with open(EXTRACT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                conf = e.get("confidence", 0.5)
                cats[e.get("category", "?")] += 1
                if conf >= 0.85:
                    highs += 1
                elif conf >= 0.6:
                    mids += 1
                else:
                    lows += 1
            except:
                pass
    total = highs + mids + lows
    return {
        "total": total,
        "high": highs,
        "mid": mids,
        "low": lows,
        "categories": dict(cats.most_common(8))
    }


def get_experience_stats():
    """从经验库读统计"""
    if not EXP_DB.exists():
        return {}
    conn = sqlite3.connect(EXP_DB)
    c = conn.cursor()
    c.execute("SELECT type, COUNT(*) FROM experiences GROUP BY type")
    dist = dict(c.fetchall())
    c.execute("SELECT COUNT(*) FROM experiences")
    total = c.fetchone()[0]
    # 最近5条教训
    c.execute("SELECT title, lesson FROM experiences WHERE type='LESSON' ORDER BY created_at DESC LIMIT 5")
    lessons = [{"title": r[0][:50], "lesson": (r[1] or "")[:60]} for r in c.fetchall()]
    conn.close()
    return {
        "total": total,
        "distribution": dist,
        "recent_lessons": lessons
    }


def get_timeline_stats():
    """从时间线读统计"""
    if not TL_DB.exists():
        return {}
    entries = []
    with open(TL_DB, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except:
                pass
    cats = Counter(e.get("category", "?") for e in entries)
    dates = sorted(set(e.get("date", e.get("time", "")[:10]) for e in entries))
    # 里程碑
    milestones = [e for e in entries if e.get("category") == "🚀 里程碑"]
    return {
        "total": len(entries),
        "active_days": len(dates),
        "categories": dict(cats.most_common(6)),
        "milestones": len(milestones),
        "date_range": f"{dates[0]} → {dates[-1]}" if dates else "无"
    }


# ─── 文本摘要 ──────────────────────────────────────────────────────

def print_text_report():
    ms = get_memory_stats()
    ex = get_extract_confidence()
    exp = get_experience_stats()
    tl = get_timeline_stats()

    print(f"\n===== 澜的记忆健康报告 {now_str()} =====\n")

    print(f"【记忆库】")
    print(f"  总条数: {ms.get('total',0)} 条")
    print(f"  向量覆盖: {ms.get('vector_count',0)}/{ms.get('total',0)} ({ms.get('vector_coverage',0)}%)")
    print(f"  置信度分布（importance）:")
    for imp, cnt in sorted(ms.get("importance_dist",{}).items(), reverse=True):
        level = "高" if imp>=9 else ("中" if imp>=7 else "低")
        bar = "█" * min(cnt, 20)
        print(f"    [{level} {imp}] {bar} {cnt}条")

    print(f"\n【提取器置信度】")
    ex_total = ex.get("total", 0)
    print(f"  总提取: {ex_total} 条")
    if ex_total > 0:
        print(f"  高置信度(>=0.85): {ex.get('high',0)} ({round(ex.get('high',0)/ex_total*100)}%)")
        print(f"  中置信度(0.6-0.85): {ex.get('mid',0)} ({round(ex.get('mid',0)/ex_total*100)}%)")
        print(f"  低置信度(<0.6): {ex.get('low',0)} ({round(ex.get('low',0)/ex_total*100)}%)")

    print(f"\n【经验库】")
    print(f"  总经验: {exp.get('total',0)} 条")
    dist = exp.get("distribution", {})
    print(f"  成功经验: {dist.get('SUCCESS',0)} 条")
    print(f"  失败教训: {dist.get('LESSON',0)} 条")
    print(f"  注意事项: {dist.get('CAUTION',0)} 条")

    print(f"\n【成长时间线】")
    print(f"  总节点: {tl.get('total',0)} 个")
    print(f"  活跃天数: {tl.get('active_days',0)} 天")
    print(f"  里程碑: {tl.get('milestones',0)} 个")
    print(f"  时间跨度: {tl.get('date_range','无')}")

    print("\n" + "="*45)


# ─── HTML报告 ─────────────────────────────────────────────────────

def generate_html_report():
    ms  = get_memory_stats()
    ex  = get_extract_confidence()
    exp = get_experience_stats()
    tl  = get_timeline_stats()

    # 置信度分层展示（核心：缺口6）
    imp_dist = ms.get("importance_dist", {})
    high_cnt = sum(v for k,v in imp_dist.items() if k >= 9)
    mid_cnt  = sum(v for k,v in imp_dist.items() if 7 <= k < 9)
    low_cnt  = sum(v for k,v in imp_dist.items() if k < 7)
    total_mem = ms.get("total", 1) or 1

    # category分布 HTML
    cat_rows = ""
    for cat, cnt in ms.get("category_dist", {}).items():
        pct = round(cnt / total_mem * 100)
        cat_rows += f"""
        <tr>
          <td style="color:#c8d6e5">{cat}</td>
          <td>
            <div style="background:#1a2d3d;border-radius:4px;height:8px;width:100%;max-width:200px">
              <div style="background:#4fa3e0;border-radius:4px;height:8px;width:{pct}%"></div>
            </div>
          </td>
          <td style="color:#4fa3e0;text-align:right">{cnt}</td>
        </tr>"""

    # 经验分布
    exp_dist = exp.get("distribution", {})
    exp_success = exp_dist.get("SUCCESS", 0)
    exp_lesson  = exp_dist.get("LESSON", 0)
    exp_caution = exp_dist.get("CAUTION", 0)
    exp_total   = exp.get("total", 1) or 1

    # 近期教训
    lesson_rows = ""
    for L in exp.get("recent_lessons", []):
        lesson_rows += f"""
        <tr>
          <td style="color:#e07050">{L['title']}</td>
          <td style="color:#8090a0;font-size:0.85em">{L['lesson']}</td>
        </tr>"""

    # 时间线分布
    tl_cat_rows = ""
    for cat, cnt in tl.get("categories", {}).items():
        tl_cat_rows += f'<div style="margin:4px 0"><span style="color:#8090a0;font-size:0.88em">{cat}</span> <span style="color:#4fa3e0;float:right">{cnt}</span></div>'

    # 最近记忆
    recent_rows = ""
    for r in ms.get("recent", []):
        imp = r.get("imp", 8)
        color = "#4ec94e" if imp >= 9 else ("#e0c44f" if imp >= 7 else "#8090a0")
        recent_rows += f"""
        <tr>
          <td style="color:#4a6070;font-size:0.82em">{r['ts']}</td>
          <td><span style="background:#0a1520;border-radius:4px;padding:1px 6px;color:#4fa3e0;font-size:0.8em">{r['cat']}</span></td>
          <td style="color:#c8d6e5;font-size:0.88em">{r['content']}</td>
          <td style="color:{color};text-align:center">{imp}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>澜 · 记忆健康报告</title>
<style>
  * {{ box-sizing:border-box;margin:0;padding:0 }}
  body {{ background:#070d14;color:#c8d6e5;font-family:"PingFang SC","Microsoft YaHei",sans-serif;min-height:100vh;padding-bottom:40px }}
  .header {{ background:linear-gradient(135deg,#0a1520,#0d1e30);padding:22px 28px;border-bottom:1px solid #1a2d3d }}
  .header h1 {{ color:#4fa3e0;font-size:1.4em;letter-spacing:2px }}
  .header .sub {{ color:#4a6070;font-size:0.82em;margin-top:4px }}
  .grid {{ display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;padding:18px 24px }}
  .card {{ background:#0d1620;border:1px solid #1a2d3d;border-radius:10px;padding:16px }}
  .card h3 {{ color:#4fa3e0;font-size:0.85em;margin-bottom:10px;letter-spacing:1px }}
  .big {{ font-size:2.2em;font-weight:700;color:#4fa3e0;line-height:1 }}
  .section {{ padding:0 24px 20px }}
  .section h2 {{ color:#4fa3e0;font-size:0.95em;margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid #1a2d3d;letter-spacing:2px }}
  table {{ width:100%;border-collapse:collapse }}
  td {{ padding:5px 8px;border-bottom:1px solid #0d1620;vertical-align:middle }}
  tr:hover {{ background:#0d1a2a }}
  .conf-bar {{ display:flex;height:10px;border-radius:5px;overflow:hidden;margin:6px 0 }}
  .bar-green {{ background:#4ec94e }}
  .bar-yellow {{ background:#e0c44f }}
  .bar-gray {{ background:#2a3a4a }}
  .footer {{ text-align:center;color:#2a3a4a;font-size:0.78em;padding:16px 0 }}
</style>
</head>
<body>

<div class="header">
  <h1>🧠 澜 · 记忆健康报告</h1>
  <div class="sub">生成时间：{now_str()}</div>
</div>

<!-- 顶部数字卡片 -->
<div class="grid">
  <div class="card">
    <h3>记忆总量</h3>
    <div class="big">{ms.get('total',0)}</div>
    <div style="color:#4a6070;font-size:0.82em;margin-top:4px">lan_memory.db</div>
  </div>
  <div class="card">
    <h3>向量覆盖</h3>
    <div class="big" style="color:#4ec94e">{ms.get('vector_coverage',0)}%</div>
    <div style="color:#4a6070;font-size:0.82em;margin-top:4px">{ms.get('vector_count',0)}/{ms.get('total',0)} 条已嵌入</div>
  </div>
  <div class="card">
    <h3>经验记忆</h3>
    <div class="big" style="color:#e0c44f">{exp.get('total',0)}</div>
    <div style="color:#4a6070;font-size:0.82em;margin-top:4px">成功/教训/注意</div>
  </div>
  <div class="card">
    <h3>成长节点</h3>
    <div class="big">{tl.get('total',0)}</div>
    <div style="color:#4a6070;font-size:0.82em;margin-top:4px">{tl.get('active_days',0)}天 · {tl.get('milestones',0)}里程碑</div>
  </div>
</div>

<!-- 置信度分层（核心） -->
<div class="section">
  <h2>置信度分层（缺口6 已填补）</h2>
  <div class="card" style="margin:0">
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:14px">
      <div>
        <div style="color:#4ec94e;font-size:0.82em;margin-bottom:4px">高置信度 (importance 9-10)</div>
        <div style="font-size:1.8em;font-weight:700;color:#4ec94e">{high_cnt}</div>
        <div style="color:#4a6070;font-size:0.78em">{round(high_cnt/total_mem*100)}% · 恺江明确告知</div>
      </div>
      <div>
        <div style="color:#e0c44f;font-size:0.82em;margin-bottom:4px">中置信度 (importance 7-8)</div>
        <div style="font-size:1.8em;font-weight:700;color:#e0c44f">{mid_cnt}</div>
        <div style="color:#4a6070;font-size:0.78em">{round(mid_cnt/total_mem*100)}% · 上下文推断</div>
      </div>
      <div>
        <div style="color:#8090a0;font-size:0.82em;margin-bottom:4px">低置信度 (importance <7)</div>
        <div style="font-size:1.8em;font-weight:700;color:#8090a0">{low_cnt}</div>
        <div style="color:#4a6070;font-size:0.78em">{round(low_cnt/total_mem*100)}% · 模糊信号</div>
      </div>
    </div>
    <div class="conf-bar">
      <div class="bar-green" style="width:{round(high_cnt/total_mem*100)}%"></div>
      <div class="bar-yellow" style="width:{round(mid_cnt/total_mem*100)}%"></div>
      <div class="bar-gray" style="flex:1"></div>
    </div>
    <div style="color:#4a6070;font-size:0.78em;margin-top:4px">绿=高 黄=中 灰=低</div>
  </div>
</div>

<!-- 记忆分类分布 -->
<div class="section" style="margin-top:16px">
  <h2>记忆分类分布</h2>
  <div class="card" style="margin:0">
    <table>
      <tr style="color:#4a6070;font-size:0.8em">
        <th style="text-align:left;padding:4px 8px">类别</th>
        <th style="text-align:left;padding:4px 8px">分布</th>
        <th style="text-align:right;padding:4px 8px">数量</th>
      </tr>
      {cat_rows}
    </table>
  </div>
</div>

<!-- 经验记忆分布 -->
<div class="section" style="margin-top:16px">
  <h2>经验记忆（缺口4 已填补）</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div class="card">
      <h3>分布</h3>
      <div style="margin:8px 0">
        <div style="color:#4ec94e;margin:6px 0">✅ 成功经验 <span style="float:right;font-weight:700">{exp_success}</span></div>
        <div style="color:#e07050;margin:6px 0">⚠️ 失败教训 <span style="float:right;font-weight:700">{exp_lesson}</span></div>
        <div style="color:#e0c44f;margin:6px 0">📌 注意事项 <span style="float:right;font-weight:700">{exp_caution}</span></div>
      </div>
    </div>
    <div class="card">
      <h3>近期教训</h3>
      {"<div style='color:#4a6070;font-size:0.85em'>暂无记录</div>" if not exp.get("recent_lessons") else f'<table>{lesson_rows}</table>'}
    </div>
  </div>
</div>

<!-- 成长时间线 -->
<div class="section" style="margin-top:16px">
  <h2>成长时间线（缺口3 已填补）</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div class="card">
      <h3>概况</h3>
      <div style="color:#c8d6e5;margin:4px 0">总节点：<strong style="color:#4fa3e0">{tl.get('total',0)}</strong></div>
      <div style="color:#c8d6e5;margin:4px 0">活跃天数：<strong style="color:#4fa3e0">{tl.get('active_days',0)}</strong></div>
      <div style="color:#c8d6e5;margin:4px 0">里程碑：<strong style="color:#4ec94e">{tl.get('milestones',0)}</strong></div>
      <div style="color:#4a6070;font-size:0.82em;margin-top:6px">{tl.get('date_range','无')}</div>
    </div>
    <div class="card">
      <h3>按类型</h3>
      {tl_cat_rows}
    </div>
  </div>
</div>

<!-- 最近记忆 -->
<div class="section" style="margin-top:16px">
  <h2>最近写入的记忆</h2>
  <div class="card" style="margin:0">
    <table>
      <tr style="color:#4a6070;font-size:0.8em">
        <th style="text-align:left;padding:4px 8px">时间</th>
        <th style="text-align:left;padding:4px 8px">类别</th>
        <th style="text-align:left;padding:4px 8px">内容</th>
        <th style="text-align:center;padding:4px 8px">置信</th>
      </tr>
      {recent_rows}
    </table>
  </div>
</div>

<div class="footer">澜 · 记忆健康报告 · {now_str()}</div>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return OUTPUT_HTML


if __name__ == "__main__":
    import sys
    if "--text" in sys.argv:
        print_text_report()
    else:
        out = generate_html_report()
        print(f"报告已生成: {out}")
        print_text_report()
