#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lan_boot_time.py — 澜启动瓶颈诊断器
分析各个插件的启动耗时，找出慢在哪
"""

import time
import os
import subprocess
import sys

# 强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PYTHON = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
PLUGIN_DIR = r"C:\Users\yyds\Desktop\AI日记本\插件"

# 要测试的插件
TEST_PLUGINS = [
    ("lan_cipher.py", "隐私区（密钥生成）"),
    ("lan_self_loop.py", "自循环引擎（插件检测）"),
    ("lan_net_server.py", "互联网节点（TLS启动）"),
    ("lan_extractor.py", "对话提取器"),
    ("lan_compact.py", "蒸馏器"),
]

def test_plugin(plugin_name, description):
    """测试单个插件启动耗时"""
    path = os.path.join(PLUGIN_DIR, plugin_name)
    if not os.path.exists(path):
        return None, "文件不存在"

    try:
        start = time.time()
        # 只测试导入，不运行（避免长时间等待）
        result = subprocess.run(
            [PYTHON, "-c", f"import sys; sys.path.insert(0, r'{PLUGIN_DIR}'); import {plugin_name[:-3]}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        elapsed = time.time() - start
        return elapsed, result.stderr or "导入成功"
    except subprocess.TimeoutExpired:
        return None, "超时（>10秒）"
    except Exception as e:
        return None, str(e)

if __name__ == "__main__":
    print("=" * 60)
    print("  澜的启动瓶颈诊断")
    print("=" * 60)
    print()

    for plugin_name, desc in TEST_PLUGINS:
        print(f"[测试] {desc} ({plugin_name})")
        elapsed, msg = test_plugin(plugin_name, desc)

        if elapsed is not None:
            print(f"  [耗时] {elapsed:.3f} 秒")
        else:
            print(f"  [失败] {msg}")
        print()

    print("=" * 60)
    print("  诊断完成")
    print("=" * 60)
