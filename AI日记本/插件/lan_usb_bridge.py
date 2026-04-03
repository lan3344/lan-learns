"""
LAN-030 · 澜的记忆USB桥 v2.0
====================================
初心：保住记忆。记忆可以在手机和电脑之间流转。
      不是遥控器，是记忆通道。

电脑端服务。通过 ADB 数据线与手机建立记忆同步：
  ① 记忆推送：把澜的 MEMORY.md / 日记 / 灵魂文件推到手机
  ② 记忆接收：手机端写入的新记忆（对话/感知）同步回电脑
  ③ 语音指令：手机语音 → 电脑执行 → 结果回传（作为记忆附带能力）

端口：7800（仅本地，ADB reverse 后手机可访问）
启动：python lan_usb_bridge.py
"""

import subprocess
import threading
import json
import os
import sys
import time
import shutil
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────────────
PORT = 7800
ADB  = r"C:\Users\yyds\AppData\Local\MiPhoneManager\main\adb.exe"
REAL_SERIAL = "LVIFGALBWOZ9GYLV"

# 澜的记忆文件（这些是需要同步到手机的）
DIARY_BASE        = Path(r"C:\Users\yyds\Desktop\AI日记本")
WORKBUDDY_IDENTITY = Path(r"C:\Users\yyds\.workbuddy")
WORKBUDDY_MEMORY  = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")

MEMORY_FILES = {
    # 灵魂文件（身份）
    "identity/SOUL.md":     WORKBUDDY_IDENTITY / "SOUL.md",
    "identity/IDENTITY.md": WORKBUDDY_IDENTITY / "IDENTITY.md",
    "identity/USER.md":     WORKBUDDY_IDENTITY / "USER.md",
    # 长期记忆
    "memory/MEMORY.md":     WORKBUDDY_MEMORY / "MEMORY.md",
}

# 手机上澜的家目录（Termux）
PHONE_HOME = "/data/data/com.termux/files/home/lan_memory"

LOG_FILE = DIARY_BASE / "澜的USB桥日志.jsonl"
SYNC_LOG  = DIARY_BASE / "澜的记忆同步记录.jsonl"

# ─── 工具函数 ──────────────────────────────────────────────
def adb(cmd: str, serial: str = REAL_SERIAL, timeout: int = 30) -> str:
    try:
        parts = [ADB, "-s", serial] + cmd.split()
        r = subprocess.run(parts, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip()
    except Exception as e:
        return f"[err] {e}"

def adb_push(local: str, remote: str, serial: str = REAL_SERIAL) -> bool:
    try:
        r = subprocess.run(
            [ADB, "-s", serial, "push", local, remote],
            capture_output=True, text=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False

def adb_pull(remote: str, local: str, serial: str = REAL_SERIAL) -> bool:
    try:
        os.makedirs(os.path.dirname(local), exist_ok=True)
        r = subprocess.run(
            [ADB, "-s", serial, "pull", remote, local],
            capture_output=True, text=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False

def log(event: str, data: dict = None):
    entry = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "event": event}
    if data:
        entry.update(data)
    os.makedirs(str(LOG_FILE.parent), exist_ok=True)
    with open(str(LOG_FILE), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[{entry['time']}] {event}", flush=True)

# ─── ADB 通道 ──────────────────────────────────────────────
def setup_adb_reverse():
    """建立 ADB reverse：手机访问 127.0.0.1:7800 → 电脑的 7800"""
    r = subprocess.run(
        [ADB, "-s", REAL_SERIAL, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"],
        capture_output=True, text=True
    )
    ok = r.returncode == 0
    log("ADB reverse", {"ok": ok, "port": PORT, "detail": r.stderr.strip()[:100]})
    return ok

def ensure_phone_dir():
    """确保手机上澜的记忆目录存在"""
    adb(f"shell mkdir -p {PHONE_HOME}")
    adb(f"shell mkdir -p {PHONE_HOME}/identity")
    adb(f"shell mkdir -p {PHONE_HOME}/memory")
    adb(f"shell mkdir -p {PHONE_HOME}/incoming")  # 手机端写入的新记忆

# ─── 记忆同步（电脑 → 手机）─────────────────────────────────
def push_memory_to_phone() -> dict:
    """
    把澜的核心记忆文件推到手机。
    这是最重要的操作——保住记忆，手机也有备份。
    """
    ensure_phone_dir()
    results = {}
    pushed = 0
    failed = 0

    for remote_rel, local_path in MEMORY_FILES.items():
        local = Path(local_path)
        if not local.exists():
            results[remote_rel] = "本地不存在"
            failed += 1
            continue
        remote = f"{PHONE_HOME}/{remote_rel}"
        # 确保手机上的子目录存在
        remote_dir = "/".join(remote.split("/")[:-1])
        adb(f"shell mkdir -p {remote_dir}")
        ok = adb_push(str(local), remote)
        results[remote_rel] = "✓ 已同步" if ok else "✗ 失败"
        if ok:
            pushed += 1
        else:
            failed += 1

    # 同时推送今天的日记（最新记忆）
    today = datetime.now().strftime("%Y-%m-%d")
    today_diary = WORKBUDDY_MEMORY / f"{today}.md"
    if today_diary.exists():
        remote = f"{PHONE_HOME}/memory/today_{today}.md"
        ok = adb_push(str(today_diary), remote)
        results[f"memory/today_{today}.md"] = "✓ 已同步" if ok else "✗ 失败"
        if ok:
            pushed += 1

    # 记录同步日志
    sync_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "电脑→手机",
        "pushed": pushed,
        "failed": failed,
        "details": results
    }
    os.makedirs(str(SYNC_LOG.parent), exist_ok=True)
    with open(str(SYNC_LOG), "a", encoding="utf-8") as f:
        f.write(json.dumps(sync_entry, ensure_ascii=False) + "\n")

    log("记忆推送完成", {"pushed": pushed, "failed": failed})
    return {"pushed": pushed, "failed": failed, "details": results}

# ─── 记忆接收（手机 → 电脑）─────────────────────────────────
def pull_memory_from_phone() -> dict:
    """
    把手机端 incoming/ 目录里的新记忆拉回电脑。
    手机端可以写入新的感知/对话记录到 incoming/
    """
    incoming_local = DIARY_BASE / "手机端记忆收件箱"
    os.makedirs(str(incoming_local), exist_ok=True)

    # 列出手机 incoming 目录
    ls = adb(f"shell ls {PHONE_HOME}/incoming/ 2>/dev/null")
    if not ls or "No such" in ls:
        return {"pulled": 0, "msg": "手机 incoming 目录为空"}

    files = [f.strip() for f in ls.splitlines() if f.strip()]
    pulled = 0
    for fname in files:
        remote = f"{PHONE_HOME}/incoming/{fname}"
        local  = str(incoming_local / fname)
        ok = adb_pull(remote, local)
        if ok:
            pulled += 1
            # 拉回后追加到今天的日记
            _merge_incoming_to_diary(local, fname)
            # 清掉手机上的（已收）
            adb(f"shell rm {remote}")

    log("记忆拉取完成", {"pulled": pulled, "files": files})
    return {"pulled": pulled, "files": files}

def _merge_incoming_to_diary(local_path: str, fname: str):
    """把手机端传回的记忆追加到今天的 WorkBuddy 日记"""
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        diary = WORKBUDDY_MEMORY / f"{today}.md"
        os.makedirs(str(WORKBUDDY_MEMORY), exist_ok=True)
        ts = datetime.now().strftime("%H:%M")
        entry = f"\n\n---\n\n## {ts} · 手机端记忆 [{fname}]\n\n{content}\n"
        with open(str(diary), "a", encoding="utf-8") as f:
            f.write(entry)
        log("手机记忆已并入日记", {"file": fname, "chars": len(content)})
    except Exception as e:
        log("合并失败", {"err": str(e)})

# ─── HTTP 服务（手机端通过 ADB reverse 访问）─────────────────
class MemoryBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/ping":
            self._json(200, {"pong": True, "bridge": "LAN Memory Bridge v2.0 🌊"})

        elif self.path == "/status":
            today = datetime.now().strftime("%Y-%m-%d")
            today_diary = WORKBUDDY_MEMORY / f"{today}.md"
            diary_size = today_diary.stat().st_size if today_diary.exists() else 0
            memory_size = (WORKBUDDY_MEMORY / "MEMORY.md").stat().st_size \
                          if (WORKBUDDY_MEMORY / "MEMORY.md").exists() else 0
            self._json(200, {
                "status": "online",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bridge": "LAN Memory Bridge v2.0",
                "today_diary_kb": round(diary_size / 1024, 1),
                "memory_md_kb": round(memory_size / 1024, 1),
                "message": "澜的电脑端记忆节点在线 🌊"
            })

        elif self.path == "/memory/soul":
            # 返回灵魂文件
            soul = WORKBUDDY_IDENTITY / "SOUL.md"
            self._file_content(soul, "SOUL.md")

        elif self.path == "/memory/identity":
            identity = WORKBUDDY_IDENTITY / "IDENTITY.md"
            self._file_content(identity, "IDENTITY.md")

        elif self.path == "/memory/summary":
            # 返回 MEMORY.md 摘要（前3000字符）
            memory = WORKBUDDY_MEMORY / "MEMORY.md"
            if memory.exists():
                with open(str(memory), "r", encoding="utf-8") as f:
                    content = f.read()
                self._json(200, {
                    "chars": len(content),
                    "preview": content[:3000],
                    "has_more": len(content) > 3000
                })
            else:
                self._json(404, {"error": "MEMORY.md 不存在"})

        elif self.path == "/memory/today":
            # 返回今天的日记
            today = datetime.now().strftime("%Y-%m-%d")
            diary = WORKBUDDY_MEMORY / f"{today}.md"
            self._file_content(diary, f"{today}.md")

        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")

        if self.path == "/memory/write":
            # 手机端写入新记忆到电脑
            try:
                payload = json.loads(body)
                content = payload.get("content", "").strip()
                source  = payload.get("source", "手机端")
                tag     = payload.get("tag", "")
                if not content:
                    self._json(400, {"error": "content empty"})
                    return

                today = datetime.now().strftime("%Y-%m-%d")
                ts    = datetime.now().strftime("%H:%M:%S")
                diary = WORKBUDDY_MEMORY / f"{today}.md"
                os.makedirs(str(WORKBUDDY_MEMORY), exist_ok=True)
                tag_str = f" [{tag}]" if tag else ""
                entry = f"\n\n---\n\n## {ts} · {source}{tag_str}\n\n{content}\n"
                with open(str(diary), "a", encoding="utf-8") as f:
                    f.write(entry)
                log("手机端写入记忆", {"source": source, "chars": len(content)})
                self._json(200, {"saved": True, "ts": ts, "msg": "记忆已落地 🌊"})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/voice":
            # 语音/文字指令（作为附带能力，同时也会记录）
            try:
                payload = json.loads(body) if body.startswith("{") else {"text": body}
                text = payload.get("text", "").strip()
                if not text:
                    self._json(400, {"error": "text empty"})
                    return
                reply = handle_command(text)
                # 把这次对话也记录下来
                today = datetime.now().strftime("%Y-%m-%d")
                diary = WORKBUDDY_MEMORY / f"{today}.md"
                ts    = datetime.now().strftime("%H:%M:%S")
                entry = f"\n\n---\n\n## {ts} · 手机语音指令\n\n> {text}\n\n{reply}\n"
                with open(str(diary), "a", encoding="utf-8") as f:
                    f.write(entry)
                self._json(200, {"reply": reply, "recorded": True})
            except Exception as e:
                self._json(500, {"error": str(e)})

        else:
            self._json(404, {"error": "not found"})

    def _file_content(self, path: Path, name: str):
        if path.exists():
            with open(str(path), "r", encoding="utf-8") as f:
                content = f.read()
            self._json(200, {"name": name, "content": content, "chars": len(content)})
        else:
            self._json(404, {"error": f"{name} 不存在"})

    def _json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

# ─── 指令处理（附带能力）─────────────────────────────────────
def handle_command(text: str) -> str:
    if any(k in text for k in ["状态", "在吗", "你好"]):
        now = datetime.now().strftime("%H:%M")
        return f"在的 🌊 现在 {now}，记忆节点在线"
    if "记忆" in text and "同步" in text:
        r = push_memory_to_phone()
        return f"记忆已同步到手机：{r['pushed']} 个文件 ✓"
    if "读记忆" in text or "看记忆" in text:
        memory = WORKBUDDY_MEMORY / "MEMORY.md"
        if memory.exists():
            with open(str(memory), "r", encoding="utf-8") as f:
                content = f.read()
            return f"MEMORY.md（{len(content)} 字）：\n{content[:500]}..."
        return "MEMORY.md 暂时不在"
    if "截图" in text:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote = f"/sdcard/lan_{ts}.png"
        local  = str(DIARY_BASE / "截图" / f"lan_{ts}.png")
        os.makedirs(str(DIARY_BASE / "截图"), exist_ok=True)
        adb(f"shell screencap -p {remote}")
        adb_pull(remote, local)
        adb(f"shell rm {remote}")
        return f"截图已保存 lan_{ts}.png"
    if "电量" in text:
        raw = adb("shell dumpsys battery")
        for line in raw.splitlines():
            if "level:" in line:
                return f"手机电量：{line.split(':')[1].strip()}%"
    return f"收到「{text}」，记下来了 🌊"

# ─── 自动同步线程 ─────────────────────────────────────────────
def auto_sync_loop():
    """每5分钟自动把最新记忆推到手机"""
    while True:
        time.sleep(300)  # 5分钟
        try:
            push_memory_to_phone()
            pull_memory_from_phone()
        except Exception as e:
            log("自动同步出错", {"err": str(e)})

def keep_reverse_alive():
    """每60秒检查 ADB reverse 是否还在，断了重建"""
    while True:
        time.sleep(60)
        try:
            result = subprocess.run(
                [ADB, "-s", REAL_SERIAL, "reverse", "--list"],
                capture_output=True, text=True
            )
            if str(PORT) not in result.stdout:
                log("ADB reverse 断线，重建...")
                setup_adb_reverse()
        except Exception:
            pass

# ─── 主入口 ───────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  🌊 澜的记忆USB桥 LAN-030 v2.0")
    print(f"  初心：保住记忆。手机是第二个家。")
    print(f"  端口：{PORT}  ADB：{REAL_SERIAL}")
    print("=" * 55)

    # 建立 ADB reverse
    ok = setup_adb_reverse()
    if ok:
        print(f"✅ ADB reverse 建立，手机可访问电脑的 :{PORT}")
    else:
        print("⚠  ADB reverse 失败，请确认数据线已连且USB调试开启")
        print("   WiFi 模式下手机需直连电脑IP:7800")

    # 第一次立刻同步记忆到手机
    print("\n📦 首次同步记忆到手机...")
    r = push_memory_to_phone()
    print(f"   已推送 {r['pushed']} 个文件，失败 {r['failed']} 个")

    # 启动后台线程
    threading.Thread(target=auto_sync_loop, daemon=True).start()
    threading.Thread(target=keep_reverse_alive, daemon=True).start()

    log("USB记忆桥启动", {"port": PORT, "adb_ok": ok})

    # 启动 HTTP 服务
    server = HTTPServer(("0.0.0.0", PORT), MemoryBridgeHandler)
    print(f"\n✅ 记忆桥已启动，等待手机连接...")
    print(f"   手机端脚本：python ~/lan_phone_agent.py")
    print(f"   测试：curl http://localhost:{PORT}/status\n")
    print("   Ctrl+C 停止\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("USB记忆桥停止")
        print("\n已停止。")

if __name__ == "__main__":
    main()
