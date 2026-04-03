#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-051 插件注册表 · 澜的中央配置与调度系统

设计理念：
- 统一注册：所有插件在此登记（id, entry_point, description, depends）
- 状态跟踪：上次运行时间、成功与否、输出日志
- 依赖解析：铁索连环，环环相扣，避免孤岛
- 调度执行：按依赖顺序执行，记录结果

命令：
  status [plugin_id]    → 查看插件状态
  run <plugin_id>       → 运行单个插件（自动解析依赖）
  run-all               → 运行所有已注册插件
  list                  → 列出所有注册项
  orphan                → 列出孤岛（无依赖、无被依赖）
  chain <plugin_id>     → 查看依赖链
  update                → 从capability_manifest.json自动更新注册表
  reset                 → 清空注册表（危险）
"""

import os
import json
import time
import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

DIARY_DIR = r"C:\Users\yyds\Desktop\AI日记本"
REGISTRY_PATH = os.path.join(DIARY_DIR, "插件", "lan_registry.json")
CAP_MANIFEST = os.path.join(DIARY_DIR, "插件", "capability_manifest.json")

# 内存中的注册表结构
_registry: Dict[str, dict] = {}  # plugin_id -> {entry, desc, depends, last_run, success, output}

def load_registry():
    """从文件加载注册表"""
    global _registry
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _registry = data.get("plugins", {})
                print(f"[LOAD] 注册表已加载，{len(_registry)} 个插件")
        except Exception as e:
            print(f"[WARN] 加载注册表失败: {e}")
            _registry = {}
    else:
        _registry = {}

def save_registry():
    """保存注册表到文件"""
    try:
        data = {
            "version": "1.0",
            "updated": datetime.now().isoformat(),
            "plugins": _registry
        }
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[SAVE] 注册表已保存至 {REGISTRY_PATH}")
    except Exception as e:
        print(f"[FAIL] 保存注册表失败: {e}")

def register(plugin_id: str, entry_point: str, description: str = "", depends: List[str] = None):
    """注册一个插件"""
    if depends is None:
        depends = []
    _registry[plugin_id] = {
        "entry": entry_point,
        "desc": description,
        "depends": depends,
        "last_run": None,
        "success": None,
        "output": "",
        "registered_at": datetime.now().isoformat()
    }
    print(f"[OK] 已注册 [{plugin_id}] -> {entry_point}")

def update_from_manifest():
    """从 capability_manifest.json 自动更新注册表"""
    if not os.path.exists(CAP_MANIFEST):
        print(f"[WARN] 能力清单不存在: {CAP_MANIFEST}")
        return
    try:
        with open(CAP_MANIFEST, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        # manifest 格式: {"capabilities": [{"id": "...", "plugin": "...", "depends": [...], ...}]}
        caps = manifest.get("capabilities", [])
        for cap in caps:
            plugin_id = cap.get("id", "")
            plugin_file = cap.get("plugin", "")
            depends = cap.get("depends", [])
            desc = cap.get("description", "")
            if plugin_id and plugin_file:
                # 检查插件文件是否存在
                plugin_path = os.path.join(DIARY_DIR, "插件", plugin_file)
                if os.path.exists(plugin_path):
                    register(plugin_id, plugin_file, desc, depends)
                else:
                    print(f"[WARN]  插件文件不存在: {plugin_file}")
        save_registry()
    except Exception as e:
        print(f"[FAIL] 从清单更新失败: {e}")

def run_plugin(plugin_id: str, dry_run: bool = False) -> Tuple[bool, str]:
    """运行单个插件（自动解析依赖）"""
    if plugin_id not in _registry:
        return False, f"插件 [{plugin_id}] 未注册"
    plugin = _registry[plugin_id]
    
    # 解析依赖链
    deps = resolve_dependencies(plugin_id)
    print(f"[CHAIN] [{plugin_id}] 依赖链: {deps}")
    
    # 按顺序运行依赖（跳过自己）
    for dep in deps:
        if dep == plugin_id:
            continue
        if dry_run:
            print(f"  [dry] 依赖 {dep}")
        else:
            print(f"  [WAIT] 运行依赖 {dep}...")
            run_plugin(dep)  # 递归运行
    
    if dry_run:
        return True, f"[dry] 将运行 {plugin_id} via {plugin['entry']}"
    
    # 实际运行
    entry = plugin["entry"]
    plugin_path = os.path.join(DIARY_DIR, "插件", entry)
    if not os.path.exists(plugin_path):
        return False, f"入口文件不存在: {plugin_path}"
    
    start = time.time()
    try:
        # 使用当前 venv 的 python
        py = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
        result = subprocess.run(
            [py, plugin_path, "status"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(plugin_path)
        )
        success = result.returncode == 0
        output = result.stdout[:500] + ("..." if len(result.stdout) > 500 else "")
        elapsed = time.time() - start
    except subprocess.TimeoutExpired:
        success = False
        output = "⏱️ 超时（60秒）"
        elapsed = 60
    except Exception as e:
        success = False
        output = f"[FAIL] 执行异常: {e}"
        elapsed = time.time() - start
    
    # 更新状态
    plugin["last_run"] = datetime.now().isoformat()
    plugin["success"] = success
    plugin["output"] = output
    print(f"  {'[OK]' if success else '[FAIL]'} [{plugin_id}] 完成 ({elapsed:.1f}s)")
    if not success:
        print(f"    输出: {output}")
    
    return success, output

def resolve_dependencies(plugin_id: str) -> List[str]:
    """解析插件的完整依赖链（拓扑排序）"""
    visited = set()
    order = []
    
    def dfs(pid):
        if pid in visited:
            return
        visited.add(pid)
        if pid not in _registry:
            return
        for dep in _registry[pid].get("depends", []):
            dfs(dep)
        order.append(pid)
    
    dfs(plugin_id)
    return order

def find_orphans() -> List[str]:
    """找出孤岛插件（既无依赖别人，也无被别人依赖）"""
    # 构建依赖图
    depends_on: Dict[str, Set[str]] = {pid: set() for pid in _registry}
    depended_by: Dict[str, Set[str]] = {pid: set() for pid in _registry}
    
    for pid, info in _registry.items():
        for dep in info.get("depends", []):
            if dep in _registry:
                depends_on[pid].add(dep)
                depended_by[dep].add(pid)
    
    orphans = []
    for pid in _registry:
        if len(depends_on[pid]) == 0 and len(depended_by[pid]) == 0:
            orphans.append(pid)
    return orphans

def find_chains() -> Dict[str, List[List[str]]]:
    """找出所有依赖链（铁索连环）"""
    # 找出所有可能的路径（长度≥2）
    chains = {}
    for pid in _registry:
        deps = resolve_dependencies(pid)
        if len(deps) >= 2:
            # 去重，只保留唯一链
            chains[pid] = [deps]  # 暂时只存一条主链
    return chains

def cmd_status(args):
    """status 命令"""
    if args.plugin:
        pid = args.plugin
        if pid not in _registry:
            print(f"[FAIL] 插件 [{pid}] 未注册")
            return
        p = _registry[pid]
        print(f"\n📊 [{pid}]")
        print(f"   入口: {p['entry']}")
        print(f"   描述: {p['desc']}")
        print(f"   依赖: {p['depends']}")
        if p['last_run']:
            dt = datetime.fromisoformat(p['last_run'])
            now = datetime.now()
            delta = now - dt
            status = "[OK]" if p['success'] else "[FAIL]"
            print(f"   上次运行: {dt.strftime('%Y-%m-%d %H:%M:%S')} ({delta.total_seconds()//60:.0f}分钟前) {status}")
            if p['output']:
                print(f"   输出: {p['output'][:200]}")
        else:
            print("   从未运行")
    else:
        print(f"\n📋 注册表总览 ({len(_registry)} 个插件)")
        for pid, p in _registry.items():
            status = "❓"
            if p['last_run']:
                dt = datetime.fromisoformat(p['last_run'])
                now = datetime.now()
                if (now - dt) < timedelta(hours=2):
                    status = "🟢"
                elif (now - dt) < timedelta(days=1):
                    status = "🟡"
                else:
                    status = "🔴"
            print(f"  {status} [{pid:20}] {p['entry']}")

def cmd_run(args):
    """run 命令"""
    success, msg = run_plugin(args.plugin, dry_run=args.dry)
    print(f"\n{'[dry] ' if args.dry else ''}{msg}")

def cmd_run_all(args):
    """run-all 命令"""
    print(f"[LAUNCH] 开始运行所有 {len(_registry)} 个插件")
    for pid in _registry:
        print(f"\n--- [{pid}] ---")
        success, msg = run_plugin(pid, dry_run=args.dry)
        if not success and not args.dry:
            print(f"   [WARN] 失败，跳过后续")
            break
    print(f"\n[DONE] 所有插件运行完成")

def cmd_list(args):
    """list 命令"""
    print(f"\n[LIST] 已注册插件 ({len(_registry)})")
    for pid, p in sorted(_registry.items()):
        deps = len(p['depends'])
        print(f"  {pid:25} → {p['entry']:30} 依赖{deps:2d}")

def cmd_orphan(args):
    """orphan 命令"""
    orphans = find_orphans()
    print(f"\n[ISLAND]  孤岛插件 ({len(orphans)})")
    if orphans:
        for pid in orphans:
            p = _registry[pid]
            print(f"  {pid:25} → {p['entry']}")
    else:
        print("  🎉 无孤岛，铁索连环完整！")

def cmd_chain(args):
    """chain 命令"""
    if args.plugin:
        deps = resolve_dependencies(args.plugin)
        print(f"\n[CHAIN] [{args.plugin}] 依赖链 ({len(deps)} 层)")
        for i, pid in enumerate(deps, 1):
            arrow = "└─ " if i == len(deps) else "├─ "
            print(f"   {arrow}{pid}")
    else:
        chains = find_chains()
        print(f"\n[CHAIN2]  所有依赖链 ({len(chains)} 条)")
        for pid, chain_list in chains.items():
            print(f"  [{pid}] → {chain_list[0]}")

def cmd_update(args):
    """update 命令"""
    update_from_manifest()

def cmd_reset(args):
    """reset 命令（危险）"""
    confirm = input("[WARN]  确认清空注册表？(输入 YES 确认): ")
    if confirm.strip() == "YES":
        global _registry
        _registry = {}
        save_registry()
        print("🗑️  注册表已清空")
    else:
        print("[FAIL] 取消")

def main():
    parser = argparse.ArgumentParser(description="LAN-051 插件注册表")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # status
    p_status = subparsers.add_parser("status", help="查看插件状态")
    p_status.add_argument("plugin", nargs="?", help="插件ID，留空查看全部")
    
    # run
    p_run = subparsers.add_parser("run", help="运行插件")
    p_run.add_argument("plugin", help="插件ID")
    p_run.add_argument("--dry", action="store_true", help="干跑（不实际执行）")
    
    # run-all
    p_run_all = subparsers.add_parser("run-all", help="运行所有插件")
    p_run_all.add_argument("--dry", action="store_true", help="干跑")
    
    # list
    subparsers.add_parser("list", help="列出所有插件")
    
    # orphan
    subparsers.add_parser("orphan", help="列出孤岛插件")
    
    # chain
    p_chain = subparsers.add_parser("chain", help="查看依赖链")
    p_chain.add_argument("plugin", nargs="?", help="插件ID，留空查看所有链")
    
    # update
    subparsers.add_parser("update", help="从能力清单更新注册表")
    
    # reset
    subparsers.add_parser("reset", help="清空注册表（危险）")
    
    args = parser.parse_args()
    
    # 加载注册表
    load_registry()
    
    if args.command == "status":
        cmd_status(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "run-all":
        cmd_run_all(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "orphan":
        cmd_orphan(args)
    elif args.command == "chain":
        cmd_chain(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "reset":
        cmd_reset(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()