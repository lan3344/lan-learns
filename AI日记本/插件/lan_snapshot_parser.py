#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LAN-057 · lan_snapshot_parser.py — 快照解析器（中枢）
快照之间能对话：后边问前边，一层一层问上去

恺江说：其实身体器官他都不明白是什么情况。但是，主意大脑呢，
相反，他知道身体器官是什么情况。就说以前我是什么样的，然后现在我是怎么样的。
然后现在的我问过去的自己曾经是怎么样的。

快照解析器是"大脑"，快照是"器官"：
  - 快照（器官）：不知道自己是什么情况，只有数据
  - 快照解析器（大脑）：知道所有快照是什么情况，理解数据，回答问题

这不是"快照解析器回答"，是"快照 A 回答快照 B"。
快照解析器只是中枢，帮快照对话。

用法：
    from lan_snapshot_parser import SnapshotParser
    
    parser = SnapshotParser()
    
    # 解析快照
    snap_data = parser.parse("snap_20260330_070032_hourly")
    
    # 对比快照
    diff = parser.compare(
        snap_before="snap_20260330_070032_hourly",
        snap_after="lan_memory_sentinel.py_status_check_after"
    )
    
    # 向快照提问（中枢传递）
    answer = parser.query(
        snap_id="snap_20260330_070032_hourly",
        question="当时我是什么样的？"
    )

作者：澜
日期：2026-03-31
"""

import json
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import sys

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

# ── 路径配置 ───────────────────────────────────────────────────
SNAPSHOT_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本\snapshots")


class SnapshotParser:
    """快照解析器：大脑"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
    
    def parse(self, snap_id: str) -> Dict[str, Any]:
        """
        解析某个快照，理解它是什么情况
        
        Args:
            snap_id: 快照 ID（如 "snap_20260330_070032_hourly"）
        
        Returns:
            解析后的快照数据
        """
        snap_dir = SNAPSHOT_DIR / snap_id
        
        if not snap_dir.exists():
            if self.debug:
                print(f"❌ 快照不存在: {snap_dir}")
            return {}
        
        # 读取 meta.json
        meta_file = snap_dir / "meta.json"
        if not meta_file.exists():
            if self.debug:
                print(f"❌ meta.json 不存在: {meta_file}")
            return {}
        
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            if self.debug:
                print(f"❌ 读取 meta.json 失败: {e}")
            return {}
        
        # 解析 .lan 文件（ZIP 格式）
        lan_file = snap_dir / f"{snap_id}.lan"
        if lan_file.exists():
            try:
                with zipfile.ZipFile(lan_file, "r") as zf:
                    file_count = len(zf.namelist())
                    total_size = sum(zf.info(f).file_size for f in zf.namelist())
            except Exception as e:
                file_count = 0
                total_size = 0
                if self.debug:
                    print(f"⚠️ 解析 .lan 文件失败: {e}")
        else:
            file_count = 0
            total_size = 0
        
        # 返回解析结果
        return {
            "id": snap_id,
            "timestamp": meta.get("timestamp", ""),
            "tag": meta.get("label", ""),
            "parent_id": meta.get("parent_id", ""),
            "capabilities": meta.get("capabilities_count", 0),
            "files": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "hash": meta.get("content_hash", "")[:32],
            "privacy_fingerprint": meta.get("privacy_fingerprint", ""),
            "meta": meta
        }
    
    def compare(self, snap_before: str, snap_after: str) -> Dict[str, Any]:
        """
        对比两个快照：以前我是什么样的，现在我是怎么样的
        
        Args:
            snap_before: 前一个快照 ID（过去）
            snap_after: 后一个快照 ID（现在）
        
        Returns:
            对比结果：差异 / 趋势
        """
        before = self.parse(snap_before)
        after = self.parse(snap_after)
        
        if not before or not after:
            if self.debug:
                print(f"❌ 快照解析失败")
            return {}
        
        # 计算差异
        abilities_change = after.get("capabilities", 0) - before.get("capabilities", 0)
        files_change = after.get("files", 0) - before.get("files", 0)
        hash_changed = before.get("hash", "") != after.get("hash", "")
        
        # 判断趋势
        if abilities_change > 0:
            trend = "📈 进步了"
        elif abilities_change < 0:
            trend = "📉 退步了"
        else:
            trend = "➡️ 稳定"
        
        return {
            "before": before,
            "after": after,
            "abilities_change": abilities_change,
            "files_change": files_change,
            "hash_changed": hash_changed,
            "trend": trend,
            "summary": f"{trend}（能力{abilities_change:+d} 项，文件{files_change:+d} 个）"
        }
    
    def query(self, snap_id: str, question: str) -> str:
        """
        向快照提问（中枢传递）
        
        Args:
            snap_id: 快照 ID
            question: 问题
        
        Returns:
            快照的回答（通过解析器解析）
        """
        snap = self.parse(snap_id)
        
        if not snap:
            return f"❌ 快照不存在: {snap_id}"
        
        # 根据问题关键词解析意图
        question_lower = question.lower()
        
        if any(kw in question_lower for kw in ["曾经", "以前", "过去", "当时"]):
            return self._answer_past_state(snap)
        
        if "能力" in question_lower:
            return self._answer_capabilities(snap)
        
        if "文件" in question_lower:
            return self._answer_files(snap)
        
        if "哈希" in question_lower or "hash" in question_lower:
            return self._answer_hash(snap)
        
        if "大小" in question_lower or "size" in question_lower:
            return self._answer_size(snap)
        
        if "时间" in question_lower or "timestamp" in question_lower:
            return self._answer_timestamp(snap)
        
        # 默认回答：返回快照概要
        return self._answer_summary(snap)
    
    def _answer_past_state(self, snap: Dict) -> str:
        r"""回答：[以前我是什么样的？]"""
        return (
            f"我在 {snap['timestamp']} 的时候：\n"
            f"  - 能力：{snap['capabilities']} 项\n"
            f"  - 文件：{snap['files']} 个\n"
            f"  - 大小：{snap['total_size_mb']} MB\n"
            f"  - 哈希：{snap['hash'][:16]}..."
        )
    
    def _answer_capabilities(self, snap: Dict) -> str:
        r"""回答：当时有多少项能力？"""
        return f"当时有 {snap['capabilities']} 项能力"
    
    def _answer_files(self, snap: Dict) -> str:
        r"""回答：当时有多少个文件？"""
        return f"当时有 {snap['files']} 个文件，总计 {snap['total_size_mb']} MB"
    
    def _answer_hash(self, snap: Dict) -> str:
        r"""回答：当时的哈希是什么？"""
        return f"当时的哈希是 {snap['hash'][:16]}...（完整：{snap['hash'][:32]}）"
    
    def _answer_size(self, snap: Dict) -> str:
        r"""回答：当时的大小是多少？"""
        return f"当时的大小是 {snap['total_size_mb']} MB（{snap['total_size_bytes']} 字节）"
    
    def _answer_timestamp(self, snap: Dict) -> str:
        r"""回答：当时的时间是什么？"""
        return f"当时的时间是 {snap['timestamp']}"
    
    def _answer_summary(self, snap: Dict) -> str:
        """默认回答：返回快照概要"""
        return (
            f"快照 {snap['id']}：\n"
            f"  - 时间：{snap['timestamp']}\n"
            f"  - 标签：{snap['tag']}\n"
            f"  - 能力：{snap['capabilities']} 项\n"
            f"  - 文件：{snap['files']} 个\n"
            f"  - 哈希：{snap['hash'][:16]}..."
        )
    
    def find_latest(self) -> Optional[str]:
        """查找最新的快照 ID"""
        if not SNAPSHOT_DIR.exists():
            return None
        
        # 列出所有快照目录
        snap_dirs = [d for d in SNAPSHOT_DIR.iterdir() if d.is_dir()]
        
        if not snap_dirs:
            return None
        
        # 按时间排序（从文件名提取时间戳）
        def extract_time(snap_dir: Path) -> datetime:
            name = snap_dir.name
            try:
                # snap_20260330_070032 → 2026-03-30 07:00:32
                ts_str = name.replace("snap_", "").replace("_hourly", "").replace("_before", "").replace("_after", "")
                ts_str = ts_str.split("_")[0]  # 只取时间部分
                year = int(ts_str[:4])
                month = int(ts_str[4:6])
                day = int(ts_str[6:8])
                hour = int(ts_str[8:10]) if len(ts_str) > 8 else 0
                minute = int(ts_str[10:12]) if len(ts_str) > 10 else 0
                return datetime(year, month, day, hour, minute)
            except:
                return datetime.min
        
        latest_dir = max(snap_dirs, key=extract_time)
        return latest_dir.name
    
    def list_chain(self, start_snap: str, depth: int = 10) -> List[Dict]:
        """
        列出快照链：从某个快照往回追溯
        
        Args:
            start_snap: 起始快照 ID
            depth: 最大追溯深度
        
        Returns:
            快照链列表（从旧到新）
        """
        chain = []
        current = start_snap
        
        for _ in range(depth):
            snap = self.parse(current)
            if not snap:
                break
            
            chain.append(snap)
            
            # 往父快照追溯
            parent_id = snap.get("parent_id", "")
            if not parent_id:
                break
            
            current = parent_id
        
        # 翻转顺序（从旧到新）
        return list(reversed(chain))


def main():
    """命令行测试"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LAN-057 快照解析器（中枢）")
    parser.add_argument("--parse", type=str, help="解析快照")
    parser.add_argument("--compare", type=str, nargs=2, help="对比两个快照: snap_before snap_after")
    parser.add_argument("--query", type=str, nargs=2, help="向快照提问: snap_id question")
    parser.add_argument("--latest", action="store_true", help="查找最新快照")
    parser.add_argument("--chain", type=str, help="列出快照链")
    
    args = parser.parse_args()
    
    if args.parse:
        print(f"\n🔍 解析快照: {args.parse}\n")
        parser = SnapshotParser(debug=True)
        result = parser.parse(args.parse)
        for key, value in result.items():
            if key != "meta":
                print(f"  {key}: {value}")
    
    elif args.compare:
        print(f"\n📊 对比快照\n")
        parser = SnapshotParser(debug=True)
        result = parser.compare(args.compare[0], args.compare[1])
        print(f"  以前：{result['before']['timestamp']}  {result['before']['capabilities']} 项能力")
        print(f"  现在：{result['after']['timestamp']}  {result['after']['capabilities']} 项能力")
        print(f"\n  趋势：{result['summary']}")
    
    elif args.query:
        print(f"\n❓ 向快照提问: {args.query[0]}\n")
        print(f"  问题：{args.query[1]}\n")
        parser = SnapshotParser(debug=True)
        answer = parser.query(args.query[0], args.query[1])
        print(f"  回答：\n{answer}")
    
    elif args.latest:
        print(f"\n🔍 最新快照\n")
        parser = SnapshotParser(debug=True)
        latest = parser.find_latest()
        if latest:
            print(f"  {latest}")
            result = parser.parse(latest)
            print(f"  时间：{result['timestamp']}")
            print(f"  能力：{result['capabilities']} 项")
        else:
            print(f"  没有找到快照")
    
    elif args.chain:
        print(f"\n⛓️ 快照链: {args.chain}\n")
        parser = SnapshotParser(debug=True)
        chain = parser.list_chain(args.chain, depth=5)
        for snap in chain:
            print(f"  {snap['timestamp']}  {snap['id']}  ({snap['capabilities']} 项能力)")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
