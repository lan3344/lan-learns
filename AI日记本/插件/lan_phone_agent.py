#!/usr/bin/env python3
"""
澜的手机端记忆Agent · lan_phone_agent.py
==========================================
在 Termux 里运行。

功能：
  1. 从电脑拉取澜的记忆（SOUL / IDENTITY / MEMORY）
  2. 本地展示澜的状态
  3. 接收语音/文字输入，写回电脑的日记
  4. 当做数据线连着时，这里是澜的第二个家

电脑端：python 插件/lan_usb_bridge.py
通信方式：HTTP → 127.0.0.1:7800（ADB reverse 通道）

用法：
  python ~/lan_phone_agent.py            # 启动（读记忆 + 交互模式）
  python ~/lan_phone_agent.py sync       # 只同步记忆
  python ~/lan_phone_agent.py read       # 只读 MEMORY.md
  python ~/lan_phone_agent.py say "内容" # 直接写一条记忆到电脑
"""

import sys
import json
import os
import time
from datetime import datetime

try:
    import urllib.request as req
    import urllib.error as req_err
except ImportError:
    print("Python 标准库缺失，请在 Termux 里运行：pkg install python")
    sys.exit(1)

BRIDGE = "http://127.0.0.1:7800"
MEMORY_DIR = os.path.expanduser("~/lan_memory")

def _post(path: str, data: dict) -> dict:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    r = req.Request(
        f"{BRIDGE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with req.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except req_err.URLError as e:
        return {"error": str(e)}

def _get(path: str) -> dict:
    try:
        with req.urlopen(f"{BRIDGE}{path}", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except req_err.URLError as e:
        return {"error": str(e)}

def check_bridge() -> bool:
    r = _get("/ping")
    if "error" in r:
        print(f"❌ 电脑端桥未响应：{r['error']}")
        print("   请在电脑端先运行：python 插件/lan_usb_bridge.py")
        return False
    print(f"✅ {r.get('bridge', '电脑桥在线')} 🌊")
    return True

def sync_memory():
    """从电脑拉取记忆文件，保存到本地"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    os.makedirs(f"{MEMORY_DIR}/identity", exist_ok=True)
    os.makedirs(f"{MEMORY_DIR}/memory", exist_ok=True)

    files = [
        ("/memory/soul",     "identity/SOUL.md"),
        ("/memory/identity", "identity/IDENTITY.md"),
        ("/memory/today",    "memory/today.md"),
    ]
    synced = 0
    for endpoint, save_as in files:
        r = _get(endpoint)
        if "content" in r:
            path = f"{MEMORY_DIR}/{save_as}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(r["content"])
            print(f"  ✓ {save_as}  ({r['chars']} 字)")
            synced += 1
        else:
            print(f"  ✗ {save_as}：{r.get('error','失败')}")

    print(f"\n已同步 {synced}/{len(files)} 个文件到 {MEMORY_DIR}/")
    return synced

def read_memory():
    """读取并显示 MEMORY.md 摘要"""
    r = _get("/memory/summary")
    if "error" in r:
        print(f"❌ {r['error']}")
        return
    print(f"\n━━━ 澜的长期记忆（{r['chars']} 字）━━━")
    print(r.get("preview", "")[:2000])
    if r.get("has_more"):
        print("\n... （还有更多，用 /memory/summary 完整获取）")

def write_memory(content: str, source: str = "手机端", tag: str = ""):
    """把一条记忆写回电脑的日记"""
    r = _post("/memory/write", {
        "content": content,
        "source": source,
        "tag": tag
    })
    if r.get("saved"):
        print(f"✅ 记忆已写入电脑 [{r['ts']}] 🌊")
    else:
        print(f"❌ 写入失败：{r.get('error','未知')}")

def send_voice(text: str):
    """发送语音/文字指令到电脑"""
    r = _post("/voice", {"text": text})
    if "reply" in r:
        print(f"\n澜：{r['reply']}")
        if r.get("recorded"):
            print("（已记入今日日记）")
    else:
        print(f"❌ {r.get('error','无响应')}")

def interactive_mode():
    """交互模式：持续对话，每条都写进记忆"""
    print("\n━━━ 交互模式 ━━━")
    print("输入任何内容，直接发到电脑端的澜")
    print("':q' 退出  ':r' 读记忆  ':s' 同步\n")

    while True:
        try:
            text = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if not text:
            continue
        if text == ":q":
            break
        elif text == ":r":
            read_memory()
        elif text == ":s":
            print("同步中...")
            sync_memory()
        else:
            send_voice(text)

def status():
    """显示当前状态"""
    r = _get("/status")
    if "error" in r:
        print(f"❌ {r['error']}")
        return
    print(f"\n━━━ 澜的电脑端状态 ━━━")
    print(f"  时间：{r.get('time','')}")
    print(f"  今日日记：{r.get('today_diary_kb',0)} KB")
    print(f"  MEMORY.md：{r.get('memory_md_kb',0)} KB")
    print(f"  {r.get('message','')}")

def main():
    args = sys.argv[1:]

    print("🌊 澜的手机端记忆Agent")
    print(f"   电脑桥：{BRIDGE}")
    print()

    if not check_bridge():
        return

    if not args or args[0] == "sync":
        print("\n📦 同步记忆...")
        sync_memory()
        if not args:
            status()
            print()
            interactive_mode()

    elif args[0] == "read":
        read_memory()

    elif args[0] == "say" and len(args) > 1:
        content = " ".join(args[1:])
        write_memory(content, source="手机端语音", tag="voice")

    elif args[0] == "status":
        status()

    elif args[0] == "chat":
        interactive_mode()

    else:
        print(f"未知命令：{args[0]}")
        print("用法：python lan_phone_agent.py [sync|read|say <内容>|status|chat]")

if __name__ == "__main__":
    main()
