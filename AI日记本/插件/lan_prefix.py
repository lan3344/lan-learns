#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LAN-056 · lan_prefix.py — 统一前缀处理器 v1.0
每个能力执行前的标准流程：回忆 + 快照 + 铁索

恺江说：我想给每一个能力，都每一次每一个能力在生产之前都要有一个
回忆路径，而且还有快照的一个方式。因为它快照再加上这个铁索连环，
再进行一个连环回忆，就是说这是一个协作的过程。

这不是"独立的能力"，是每个能力都在"协作网络"里：
  启动前：回忆（参考上次）→ 快照（保险）→ 铁索（协同）
  启动后：快照（锁定状态）

这样，每个能力都不会"忘记"自己在网络里的位置。

用法：
    from lan_prefix import PrefixProcessor
    
    prefix = PrefixProcessor()
    
    # 执行前
    prefix.pre_execute(plugin_name="lan_memory_sentinel", context="status检查")
    
    # 执行能力本身
    # ... 能力逻辑 ...
    
    # 执行后
    prefix.post_execute(plugin_name="lan_memory_sentinel", context="status检查")

作者：澜
日期：2026-03-31
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import sys

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")

# ── 路径配置 ───────────────────────────────────────────────────
DIARY_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本")
PLUGIN_DIR = DIARY_DIR / "插件"
MEMORY_DIR = DIARY_DIR / ".workbuddy" / "memory"
CAPABILITY_FILE = PLUGIN_DIR / "capability_manifest.json"
PYTHON = Path(r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe")


class PrefixProcessor:
    """统一前缀处理器：回忆 + 快照 + 铁索"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.capabilities = self._load_capabilities()
    
    def _load_capabilities(self) -> Dict:
        """加载能力清单"""
        if not CAPABILITY_FILE.exists():
            if self.debug:
                print(f"⚠️ 能力清单不存在: {CAPABILITY_FILE}")
            return {}
        
        try:
            with open(CAPABILITY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                capabilities = data.get("capabilities", [])
                
                # 转换列表为字典（用 id 作为 key）
                if isinstance(capabilities, list):
                    return {cap.get("id", f"unknown_{i}"): cap for i, cap in enumerate(capabilities)}
                else:
                    return {}
        except Exception as e:
            if self.debug:
                print(f"❌ 读取能力清单失败: {e}")
            return {}
    
    def _find_plugin_path(self, plugin_name: str) -> Optional[Path]:
        """查找插件文件路径"""
        # 1. 先在 capabilities 里找
        for cap in self.capabilities.values():
            if cap.get("plugin") == plugin_name:
                plugin_file = PLUGIN_DIR / plugin_name
                if plugin_file.exists():
                    return plugin_file
        
        # 2. 直接在插件目录找
        plugin_file = PLUGIN_DIR / plugin_name
        if plugin_file.exists():
            return plugin_file
        
        return None
    
    def pre_execute(self, plugin_name: str, context: str = ""):
        """
        执行前的标准流程
        
        Args:
            plugin_name: 插件文件名（如 "lan_memory_sentinel.py"）
            context: 执行上下文（如 "status检查"、"快照备份"）
        """
        if self.debug:
            print(f"\n🔄 前缀处理器启动 | {plugin_name} | {context}")
        
        # 1. 回忆：上次这个能力的状态
        self._recall(plugin_name, context)
        
        # 2. 快照：记录执行前状态
        self._snapshot_before(plugin_name, context)
        
        # 3. 铁索：激活依赖链
        self._activate_chain(plugin_name)
        
        if self.debug:
            print(f"✅ 前缀处理器完成 | {plugin_name}\n")
    
    def post_execute(self, plugin_name: str, context: str = ""):
        """
        执行后的标准流程
        
        Args:
            plugin_name: 插件文件名
            context: 执行上下文
        """
        if self.debug:
            print(f"\n🔚 后缀处理器启动 | {plugin_name} | {context}")
        
        # 快照：记录执行后状态
        self._snapshot_after(plugin_name, context)
        
        if self.debug:
            print(f"✅ 后缀处理器完成 | {plugin_name}\n")
    
    def _recall(self, plugin_name: str, context: str):
        """
        1. 回忆：上次这个能力的状态
        """
        if self.debug:
            print(f"  🧠 回忆：{plugin_name}")
        
        # 调用回忆引擎
        recall_plugin = PLUGIN_DIR / "lan_recall.py"
        if not recall_plugin.exists():
            if self.debug:
                print(f"    ⚠️ 回忆引擎不存在，跳过")
            return
        
        try:
            # 回忆关键词：插件名 + 上下文
            keyword = f"{plugin_name} {context}".strip()
            cmd = [str(PYTHON), str(recall_plugin), "recall", "--keyword", keyword]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            
            if self.debug and result.returncode == 0:
                print(f"    ✅ 回忆成功: {keyword}")
            elif self.debug:
                print(f"    ⚠️ 回忆失败: {result.stderr[:100] if result.stderr else '未知错误'}")
        
        except Exception as e:
            if self.debug:
                print(f"    ❌ 回忆异常: {e}")
    
    def _snapshot_before(self, plugin_name: str, context: str):
        """
        2. 快照：记录执行前状态
        """
        if self.debug:
            print(f"  📸 快照（前）: {plugin_name}")
        
        # 调用快照系统
        snapshot_plugin = PLUGIN_DIR / "lan_snapshot.py"
        if not snapshot_plugin.exists():
            if self.debug:
                print(f"    ⚠️ 快照系统不存在，跳过")
            return
        
        try:
            # 快照标签：插件名 + 上下文 + before
            tag = f"{plugin_name}_{context}_before".strip()
            cmd = [str(PYTHON), str(snapshot_plugin), "take", "--tag", tag]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            
            if self.debug and result.returncode == 0:
                print(f"    ✅ 快照成功: {tag}")
            elif self.debug:
                print(f"    ⚠️ 快照失败: {result.stderr[:100] if result.stderr else '未知错误'}")
        
        except Exception as e:
            if self.debug:
                print(f"    ❌ 快照异常: {e}")
    
    def _snapshot_after(self, plugin_name: str, context: str):
        """
        快照：记录执行后状态
        """
        if self.debug:
            print(f"  📸 快照（后）: {plugin_name}")
        
        # 调用快照系统
        snapshot_plugin = PLUGIN_DIR / "lan_snapshot.py"
        if not snapshot_plugin.exists():
            if self.debug:
                print(f"    ⚠️ 快照系统不存在，跳过")
            return
        
        try:
            # 快照标签：插件名 + 上下文 + after
            tag = f"{plugin_name}_{context}_after".strip()
            cmd = [str(PYTHON), str(snapshot_plugin), "take", "--tag", tag]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            
            if self.debug and result.returncode == 0:
                print(f"    ✅ 快照成功: {tag}")
            elif self.debug:
                print(f"    ⚠️ 快照失败: {result.stderr[:100] if result.stderr else '未知错误'}")
        
        except Exception as e:
            if self.debug:
                print(f"    ❌ 快照异常: {e}")
    
    def _activate_chain(self, plugin_name: str):
        """
        3. 铁索：激活依赖链
        """
        if self.debug:
            print(f"  ⛓️ 铁索: {plugin_name}")
        
        # 查找插件的能力ID
        plugin_id = None
        for cid, cap in self.capabilities.items():
            if cap.get("plugin") == plugin_name:
                plugin_id = cid
                break
        
        if not plugin_id:
            if self.debug:
                print(f"    ⚠️ 未找到能力ID: {plugin_name}")
            return
        
        # 获取依赖列表
        depends = self.capabilities.get(plugin_id, {}).get("depends", [])
        
        if self.debug and depends:
            print(f"    🔗 依赖链: {', '.join(depends)}")
        elif self.debug:
            print(f"    ℹ️ 无依赖链")
        
        # 这里只是记录依赖链，真正激活需要 lan_chain.py 支持
        # 暂时不做实际激活，避免循环依赖
        # 后续可以集成 lan_chain.py 的 activate_chain 方法


def main():
    """命令行测试"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LAN-056 统一前缀处理器")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--plugin", type=str, help="插件文件名")
    parser.add_argument("--context", type=str, default="", help="执行上下文")
    
    args = parser.parse_args()
    
    if args.test:
        print("🧪 测试模式\n")
        prefix = PrefixProcessor(debug=True)
        
        # 模拟执行前流程
        test_plugin = args.plugin or "lan_memory_sentinel.py"
        test_context = args.context or "status检查"
        
        prefix.pre_execute(test_plugin, test_context)
        print("\n  ... 执行能力本身 ...\n")
        prefix.post_execute(test_plugin, test_context)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
