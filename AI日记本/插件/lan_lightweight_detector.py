# -*- coding: utf-8 -*-
"""
LAN-054 · 轻量模式检测器
检测澜当前运行状态，报告哪些模块在跑，哪些停了
"""

import psutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def find_processes(keyword):
    """找到包含关键词的Python进程"""
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if keyword.lower() in cmdline.lower():
                procs.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return procs

def main():
    print("\n" + "=" * 60)
    print("  澜的运行状态检测")
    print("=" * 60)

    # 检测各个模块
    modules = [
        ("lan_net_server.py", "互联网节点 (LAN-015)", "重算力"),
        ("lan_self_loop.py", "自循环引擎", "中算力"),
        ("lan_embed.py", "向量检索 (LAN-026)", "重算力"),
        ("lan_extractor.py", "对话提取器 (LAN-027)", "轻量"),
        ("lan_compact.py", "蒸馏器 (LAN-028)", "轻量"),
        ("lan_world_log.py", "世界日志 (LAN-054)", "轻量"),
    ]

    heavy_count = 0
    for script, name, level in modules:
        procs = find_processes(script)
        status = "🟢 运行中" if procs else "⚪ 已停止"
        if procs:
            print(f"\n  {status}  {name}")
            print(f"      算力等级: {level}")
            if level == "重算力":
                heavy_count += 1
                print(f"      PID: {procs[0]['pid']}")
        else:
            print(f"\n  {status}  {name}")

    # 总结
    print("\n" + "-" * 60)
    if heavy_count == 0:
        print("  当前状态: ✅ 轻量模式（适合游戏）")
    elif heavy_count <= 2:
        print(f"  当前状态: ⚠️ 混合模式（{heavy_count} 个重算力模块运行）")
    else:
        print(f"  当前状态: ⚠️ 完整模式（{heavy_count} 个重算力模块运行）")

    print("-" * 60 + "\n")

if __name__ == "__main__":
    main()
