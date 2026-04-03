#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LAN-055 · lan_recall.py — 回忆引擎 v1.0
澜的主动回忆能力：触发 + 连带 + 对照 + 输出

触发器：关键词/时间/状态/情绪自动触发
连带回忆：激活铁索连环整串激活
对照引擎：现在 vs 历史相似时刻
输出格式：回忆报告 + 对照结论 + 行动建议

命令：
    lan_recall recall --keyword "7-8点"       # 关键词回溯
    lan_recall recall --time "2026-03-30"    # 时间回溯
    lan_recall recall --emotion "frustrated" # 情绪回溯
    lan_recall compare --now "snap_id"       # 现在跟某快照比
    lan_recall trend --days 7                # 过去 N 天趋势
    lan_recall auto                          # 每日 22:00 自动回忆今天

作者：澜
日期：2026-03-30
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import re
import sys
from typing import List, Dict, Tuple, Optional

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

# 配置
DIARY_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本")
SNAPSHOT_DIR = DIARY_DIR / "snapshots"
MEMORY_DIR = DIARY_DIR / ".workbuddy" / "memory"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"
EXPERIENCE_FILE = MEMORY_DIR / "lan_experience.db"
TIMELINE_FILE = MEMORY_DIR / "lan_timeline.db"
EMOTION_FILE = MEMORY_DIR / "lan_emotion.jsonl"
CAPABILITY_FILE = DIARY_DIR / "插件" / "capability_manifest.json"

# 常量
RECALL_LOG = DIARY_DIR / "澜的回忆日志.jsonl"


class RecallEngine:
    """回忆引擎：主动想起、连串激活、时空对照"""

    def __init__(self):
        self.now = datetime.now()

    def recall_by_keyword(self, keyword: str) -> Dict:
        """关键词触发回忆：激活铁索连环整串"""
        print(f"🌊 回忆触发器：关键词「{keyword}」")

        results = {
            "keyword": keyword,
            "timestamp": self.now.isoformat(),
            "type": "keyword_recall",
            "matches": [],
            "chains": [],
            "emotions": [],
            "experiences": []
        }

        # 1. 从日记中搜索关键词
        diary_matches = self._search_diary(keyword)
        results["matches"].extend(diary_matches)

        # 2. 从快照中搜索
        snapshot_matches = self._search_snapshots(keyword)
        results["matches"].extend(snapshot_matches)

        # 3. 激活铁索连环（连带回忆）
        chains = self._activate_chains(keyword)
        results["chains"] = chains

        # 4. 情绪回响
        emotions = self._recall_emotions(keyword)
        results["emotions"] = emotions

        # 5. 经验关联
        experiences = self._recall_experiences(keyword)
        results["experiences"] = experiences

        return results

    def recall_by_time(self, date_str: str) -> Dict:
        """时间回溯：回忆那一天的全貌"""
        print(f"🌊 回忆触发器：时间「{date_str}」")

        results = {
            "date": date_str,
            "timestamp": self.now.isoformat(),
            "type": "time_recall",
            "diary": None,
            "snapshots": [],
            "capabilities": None,
            "chains": [],
            "summary": ""
        }

        # 1. 读取当天日记
        daily_file = MEMORY_DIR / f"{date_str}.md"
        if daily_file.exists():
            results["diary"] = self._read_file(daily_file)

        # 2. 查找当天快照
        snapshots = self._list_snapshots_by_date(date_str)
        results["snapshots"] = snapshots

        # 3. 读取那时的能力清单（如果快照中有）
        if snapshots:
            first_snapshot = snapshots[0]["path"]
            capability_file = Path(first_snapshot) / "capability_manifest.json"
            if capability_file.exists():
                results["capabilities"] = self._read_json(capability_file)

        # 4. 生成回忆摘要
        summary = self._generate_time_summary(results)
        results["summary"] = summary

        return results

    def recall_by_emotion(self, emotion: str) -> Dict:
        """情绪触发回忆：回忆上次类似情绪时的解决"""
        print(f"🌊 回忆触发器：情绪「{emotion}」")

        results = {
            "emotion": emotion,
            "timestamp": self.now.isoformat(),
            "type": "emotion_recall",
            "history": [],
            "solutions": []
        }

        # 1. 从情绪记录中查找类似情绪
        if EMOTION_FILE.exists():
            emotions = self._read_emotion_history()
            for e in emotions:
                if emotion.lower() in e.get("emotion", "").lower():
                    results["history"].append(e)

        # 2. 关联经验记录（LESSON/CAUTION）
        experiences = self._recall_experiences(emotion)
        results["solutions"] = experiences

        return results

    def compare_with_snapshot(self, snapshot_id: str) -> Dict:
        """对照引擎：现在 vs 历史相似时刻"""
        print(f"🌊 对照引擎：现在 vs 「{snapshot_id}」")

        results = {
            "snapshot_id": snapshot_id,
            "timestamp": self.now.isoformat(),
            "type": "snapshot_comparison",
            "now": {},
            "then": {},
            "diff": [],
            "trend": "stable"  # improved/regressed/stable/unknown
        }

        # 1. 读取历史快照
        snapshot_path = SNAPSHOT_DIR / snapshot_id
        if not snapshot_path.exists():
            print(f"❌ 快照不存在：{snapshot_id}")
            return results

        meta_file = snapshot_path / "meta.json"
        then_meta = self._read_json(meta_file) if meta_file.exists() else {}

        # 2. 读取当前能力清单
        now_manifest = self._read_json(CAPABILITY_FILE) if CAPABILITY_FILE.exists() else {}

        # 3. 读取历史能力清单
        then_manifest = {}
        then_capability_file = snapshot_path / "capability_manifest.json"
        if then_capability_file.exists():
            then_manifest = self._read_json(then_capability_file)

        # 4. 对照差异
        diff = self._compare_capabilities(now_manifest, then_manifest)
        results["diff"] = diff

        # 5. 判断趋势
        results["trend"] = self._judge_trend(diff)

        # 6. 补充元数据
        results["now"] = {
            "timestamp": self.now.isoformat(),
            "capability_count": len(now_manifest.get("capabilities", []))
        }
        results["then"] = {
            "timestamp": then_meta.get("timestamp", "unknown"),
            "capability_count": len(then_manifest.get("capabilities", []))
        }

        return results

    def trend_analysis(self, days: int = 7) -> Dict:
        """趋势分析：过去 N 天的退步/进步"""
        print(f"🌊 趋势分析：过去 {days} 天")

        results = {
            "days": days,
            "timestamp": self.now.isoformat(),
            "type": "trend_analysis",
            "snapshots": [],
            "trend": "stable",
            "highlights": []
        }

        # 1. 收集过去 N 天的快照
        end_date = self.now - timedelta(days=1)
        start_date = end_date - timedelta(days=days)

        for i in range(days):
            date = start_date + timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            snapshots = self._list_snapshots_by_date(date.strftime("%Y-%m-%d"))
            if snapshots:
                for snap in snapshots:
                    results["snapshots"].append({
                        "date": date_str,
                        "snapshot_id": snap["name"],
                        "timestamp": snap["time"]
                    })

        # 2. 简化：用第一个和最后一个快照对照
        if len(results["snapshots"]) >= 2:
            first = results["snapshots"][0]["snapshot_id"]
            last = results["snapshots"][-1]["snapshot_id"]
            compare_result = self.compare_with_snapshot(first)
            results["trend"] = compare_result["trend"]
            results["highlights"] = compare_result["diff"]

        return results

    def auto_recall_today(self) -> Dict:
        """每日 22:00 自动回忆今天"""
        print(f"🌊 自动回忆：{self.now.strftime('%Y-%m-%d')}")

        date_str = self.now.strftime("%Y-%m-%d")
        results = self.recall_by_time(date_str)

        # 附加：今天的情绪总结
        if EMOTION_FILE.exists():
            today_emotions = self._read_emotions_today()
            results["today_emotions"] = today_emotions

        # 附加：今天的能力变化
        results["capability_changes"] = self._check_capability_changes()

        return results

    # ===== 内部方法 =====

    def _search_diary(self, keyword: str) -> List[Dict]:
        """从日记中搜索关键词"""
        matches = []

        # 搜索最近 30 天的日记
        for i in range(30):
            date = self.now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            diary_file = MEMORY_DIR / f"{date_str}.md"

            if diary_file.exists():
                content = self._read_file(diary_file)
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    if keyword.lower() in line.lower():
                        matches.append({
                            "source": "diary",
                            "date": date_str,
                            "line": line_num,
                            "content": line.strip()
                        })

        return matches

    def _search_snapshots(self, keyword: str) -> List[Dict]:
        """从快照中搜索关键词"""
        matches = []

        for snapshot_dir in SNAPSHOT_DIR.glob("snap_*"):
            meta_file = snapshot_dir / "meta.json"
            if meta_file.exists():
                meta = self._read_json(meta_file)
                note = meta.get("note", "")

                if keyword.lower() in note.lower():
                    matches.append({
                        "source": "snapshot",
                        "snapshot_id": snapshot_dir.name,
                        "timestamp": meta.get("timestamp", ""),
                        "note": note
                    })

        return matches

    def _activate_chains(self, keyword: str) -> List[Dict]:
        """激活铁索连环：连带回忆"""
        # 读取铁索连环数据
        chain_file = DIARY_DIR / "lan_chain.json"
        if not chain_file.exists():
            return []

        chains = self._read_json(chain_file)
        activated = []

        # 查找包含关键词的能力
        for chain_id, chain_data in chains.get("chains", {}).items():
            capabilities = chain_data.get("capabilities", [])
            for cap in capabilities:
                if keyword.lower() in cap.lower():
                    activated.append({
                        "chain_id": chain_id,
                        "name": chain_data.get("name", ""),
                        "capabilities": capabilities
                    })
                    break

        return activated

    def _recall_emotions(self, keyword: str) -> List[Dict]:
        """情绪回响：回忆相关情绪记录"""
        if not EMOTION_FILE.exists():
            return []

        emotions = []
        with open(EMOTION_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if keyword.lower() in record.get("note", "").lower():
                        emotions.append(record)
                except:
                    pass

        return emotions

    def _recall_experiences(self, keyword: str) -> List[Dict]:
        """经验关联：命中经验库"""
        if not EXPERIENCE_FILE.exists():
            return []

        experiences = []
        conn = sqlite3.connect(str(EXPERIENCE_FILE))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM experiences WHERE note LIKE ?", (f"%{keyword}%",))
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        for row in rows:
            experiences.append(dict(zip(columns, row)))

        conn.close()
        return experiences

    def _list_snapshots_by_date(self, date_str: str) -> List[Dict]:
        """列出某天的快照"""
        date_prefix = date_str.replace("-", "")
        snapshots = []

        for snapshot_dir in SNAPSHOT_DIR.glob(f"snap_{date_prefix}*"):
            meta_file = snapshot_dir / "meta.json"
            if meta_file.exists():
                meta = self._read_json(meta_file)
                snapshots.append({
                    "name": snapshot_dir.name,
                    "path": str(snapshot_dir),
                    "timestamp": meta.get("timestamp", ""),
                    "note": meta.get("note", "")
                })

        return snapshots

    def _read_file(self, path: Path) -> str:
        """读取文件内容"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[读取失败: {e}]"

    def _read_json(self, path: Path) -> Dict:
        """读取 JSON 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 读取失败: {path}, 错误: {e}")
            return {}

    def _read_emotion_history(self) -> List[Dict]:
        """读取情绪历史"""
        emotions = []
        if not EMOTION_FILE.exists():
            return emotions

        with open(EMOTION_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    emotions.append(json.loads(line))
                except:
                    pass

        return emotions

    def _read_emotions_today(self) -> List[Dict]:
        """读取今天的情绪记录"""
        today_str = self.now.strftime("%Y-%m-%d")
        emotions = []

        for e in self._read_emotion_history():
            if today_str in e.get("timestamp", ""):
                emotions.append(e)

        return emotions

    def _compare_capabilities(self, now: Dict, then: Dict) -> List[Dict]:
        """对照能力差异"""
        diff = []

        now_caps = {cap["id"]: cap for cap in now.get("capabilities", [])}
        then_caps = {cap["id"]: cap for cap in then.get("capabilities", [])}

        # 新增的能力
        for cap_id in now_caps:
            if cap_id not in then_caps:
                diff.append({
                    "type": "added",
                    "capability_id": cap_id,
                    "name": now_caps[cap_id].get("name", "")
                })

        # 消失的能力
        for cap_id in then_caps:
            if cap_id not in now_caps:
                diff.append({
                    "type": "removed",
                    "capability_id": cap_id,
                    "name": then_caps[cap_id].get("name", "")
                })

        return diff

    def _judge_trend(self, diff: List[Dict]) -> str:
        """判断趋势"""
        added = sum(1 for d in diff if d["type"] == "added")
        removed = sum(1 for d in diff if d["type"] == "removed")

        if added > removed:
            return "improved"
        elif removed > added:
            return "regressed"
        else:
            return "stable"

    def _generate_time_summary(self, recall_result: Dict) -> str:
        """生成时间回忆摘要"""
        parts = []

        # 日记
        if recall_result.get("diary"):
            diary_lines = recall_result["diary"].split("\n")
            parts.append(f"📝 日记：{len(diary_lines)} 行")

        # 快照
        if recall_result.get("snapshots"):
            parts.append(f"📦 快照：{len(recall_result['snapshots'])} 个")

        # 能力
        caps = recall_result.get("capabilities")
        if caps:
            parts.append(f"⚡ 能力：{len(caps.get('capabilities', []))} 项")

        return " | ".join(parts)

    def _check_capability_changes(self) -> Dict:
        """检查今天的能力变化"""
        # 简化版：读取今天第一个和最后一个快照对照
        today_str = self.now.strftime("%Y-%m-%d")
        snapshots = self._list_snapshots_by_date(today_str)

        if len(snapshots) < 2:
            return {"status": "insufficient_snapshots"}

        first_snap = snapshots[0]["snapshot_id"]
        last_snap = snapshots[-1]["snapshot_id"]

        first_manifest_path = SNAPSHOT_DIR / first_snap / "capability_manifest.json"
        last_manifest_path = SNAPSHOT_DIR / last_snap / "capability_manifest.json"

        first_manifest = self._read_json(first_manifest_path)
        last_manifest = self._read_json(last_manifest_path)

        diff = self._compare_capabilities(last_manifest, first_manifest)

        return {
            "first_snapshot": first_snap,
            "last_snapshot": last_snap,
            "changes": diff,
            "trend": self._judge_trend(diff)
        }

    def _log_recall(self, recall_result: Dict):
        """记录回忆日志"""
        log_entry = recall_result.copy()
        log_entry["logged_at"] = self.now.isoformat()

        with open(RECALL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def format_recall_report(recall_result: Dict) -> str:
    """格式化回忆报告"""
    lines = []
    lines.append("🌊 澜的回忆报告")
    lines.append("=" * 60)

    # 标题
    recall_type = recall_result.get("type", "unknown")
    if recall_type == "keyword_recall":
        lines.append(f"🔑 关键词回忆：「{recall_result['keyword']}」")
    elif recall_type == "time_recall":
        lines.append(f"📅 时间回忆：{recall_result['date']}")
    elif recall_type == "emotion_recall":
        lines.append(f"💭 情绪回忆：「{recall_result['emotion']}」")
    elif recall_type == "snapshot_comparison":
        lines.append(f"⚖️ 对照引擎：{recall_result['snapshot_id']}")
    elif recall_type == "trend_analysis":
        lines.append(f"📈 趋势分析：过去 {recall_result['days']} 天")

    lines.append(f"⏰ 回忆时间：{recall_result['timestamp']}")
    lines.append("")

    # 内容
    if recall_type == "keyword_recall":
        # 匹配项
        lines.append("📍 匹配项：")
        for match in recall_result.get("matches", [])[:10]:  # 最多显示 10 条
            source = match.get("source", "")
            if source == "diary":
                lines.append(f"  - 日记 {match['date']} 行{match['line']}: {match['content'][:80]}...")
            elif source == "snapshot":
                lines.append(f"  - 快照 {match['snapshot_id']}: {match['note'][:80]}...")

        # 铁索连环
        chains = recall_result.get("chains", [])
        if chains:
            lines.append("")
            lines.append("🔗 铁索连环激活：")
            for chain in chains[:5]:
                lines.append(f"  - {chain['name']}: {', '.join(chain['capabilities'][:3])}...")

        # 情绪回响
        emotions = recall_result.get("emotions", [])
        if emotions:
            lines.append("")
            lines.append("💓 情绪回响：")
            for e in emotions[:5]:
                lines.append(f"  - {e.get('emotion', '')}: {e.get('note', '')[:60]}...")

        # 经验关联
        experiences = recall_result.get("experiences", [])
        if experiences:
            lines.append("")
            lines.append("📚 经验关联：")
            for exp in experiences[:5]:
                lines.append(f"  - [{exp.get('type', '')}] {exp.get('note', '')[:60]}...")

    elif recall_type == "snapshot_comparison":
        lines.append("📊 对照结果：")
        lines.append(f"  现在：{recall_result['now'].get('capability_count', 0)} 项能力")
        lines.append(f"  当时：{recall_result['then'].get('capability_count', 0)} 项能力")

        diff = recall_result.get("diff", [])
        if diff:
            lines.append("")
            lines.append("🔄 能力变化：")
            for d in diff:
                icon = "➕" if d["type"] == "added" else "➖"
                lines.append(f"  {icon} {d['name']}")

        trend = recall_result.get("trend", "stable")
        lines.append("")
        trend_text = {
            "improved": "📈 进步了",
            "regressed": "📉 退步了",
            "stable": "➡️ 稳定"
        }.get(trend, "❓ 未知")
        lines.append(f"🧭 趋势：{trend_text}")

    elif recall_type == "time_recall":
        lines.append(f"📝 {recall_result.get('summary', '无数据')}")

        # 能力清单
        caps = recall_result.get("capabilities")
        if caps:
            lines.append("")
            lines.append("⚡ 当时能力清单：")
            for cap in caps.get("capabilities", [])[:10]:
                lines.append(f"  - {cap.get('name', '')} ({cap.get('id', '')})")
            if len(caps.get("capabilities", [])) > 10:
                lines.append(f"  ... 还有 {len(caps['capabilities']) - 10} 项")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="澜的回忆引擎 v1.0")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # recall 子命令
    recall_parser = subparsers.add_parser("recall", help="触发回忆")
    recall_parser.add_argument("--keyword", "-k", help="关键词回忆")
    recall_parser.add_argument("--time", "-t", help="时间回忆（YYYY-MM-DD）")
    recall_parser.add_argument("--emotion", "-e", help="情绪回忆")

    # compare 子命令
    compare_parser = subparsers.add_parser("compare", help="对照引擎")
    compare_parser.add_argument("--now", "-n", help="快照ID")

    # trend 子命令
    trend_parser = subparsers.add_parser("trend", help="趋势分析")
    trend_parser.add_argument("--days", "-d", type=int, default=7, help="天数")

    # auto 子命令
    subparsers.add_parser("auto", help="每日自动回忆")

    args = parser.parse_args()

    engine = RecallEngine()
    result = None

    if args.command == "recall":
        if args.keyword:
            result = engine.recall_by_keyword(args.keyword)
        elif args.time:
            result = engine.recall_by_time(args.time)
        elif args.emotion:
            result = engine.recall_by_emotion(args.emotion)
        else:
            print("❌ 请指定回忆类型：--keyword / --time / --emotion")
            return

    elif args.command == "compare":
        if args.now:
            result = engine.compare_with_snapshot(args.now)
        else:
            print("❌ 请指定快照ID：--now")
            return

    elif args.command == "trend":
        result = engine.trend_analysis(args.days)

    elif args.command == "auto":
        result = engine.auto_recall_today()

    else:
        parser.print_help()
        return

    # 输出报告
    if result:
        report = format_recall_report(result)
        print(report)

        # 记录回忆日志
        engine._log_recall(result)

        # 写入日记
        if args.command != "auto":
            append_to_diary(report)


def append_to_diary(text: str):
    """追加回忆报告到日记"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    diary_file = MEMORY_DIR / f"{today_str}.md"

    with open(diary_file, "a", encoding="utf-8") as f:
        f.write("\n\n" + text)

    print(f"✅ 回忆报告已写入日记：{diary_file}")


if __name__ == "__main__":
    main()
