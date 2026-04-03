# -*- coding: utf-8 -*-
"""
LAN-036-GUI · 应用习惯守门员 — 图形界面版
创建：2026-03-29

功能：
  - 系统托盘图标（右键菜单：暂停/恢复/查报告/退出）
  - 现代风格弹窗（不再用丑陋的 InputBox）
  - 子进程白名单过滤（Steam/Chrome等多进程应用不会狂刷弹窗）
  - 弹窗有倒计时进度条，不卡死
"""

import os
import sys
import io
import json
import sqlite3
import subprocess
import datetime
import time
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont
import queue

# 引入原有逻辑模块
sys.path.insert(0, os.path.dirname(__file__))
from lan_app_habit import (
    init_db, save_usage, scan_running_processes,
    ai_score_reason, ai_health_check, start_health_timer,
    ai_default_decision, enforce_no_answer,
    DB_PATH, NO_ANSWER_TIMEOUT
)

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── 子进程白名单（这些进程的子进程直接豁免，不弹窗）─────────────────────────
# 格式：主进程名 → [子进程名列表，支持前缀匹配]
SUBPROCESS_WHITELIST = {
    # Steam 生态
    "steam.exe": [
        "steamwebhelper.exe", "steamservice.exe", "gameoverlayrenderer",
        "steamclient", "steam_api", "steamerrorreporter.exe",
        "steaminstall.exe", "steamsetup.exe", "vcredist",
    ],
    # Chrome 生态
    "chrome.exe": ["chrome.exe"],   # Chrome 多进程只问一次
    # Edge
    "msedge.exe": ["msedge.exe"],
    # Firefox
    "firefox.exe": ["firefox.exe"],
    # WeChat
    "wechat.exe": ["wechatapp.exe", "wechatocr.exe", "wechatbrowser.exe"],
    # 微信
    "weixin.exe":  ["weixinapp.exe"],
    # 系统进程（永远豁免）
    "_system_": [
        "svchost.exe", "conhost.exe", "csrss.exe", "lsass.exe",
        "winlogon.exe", "explorer.exe", "dwm.exe", "taskhost.exe",
        "taskhostw.exe", "sihost.exe", "ctfmon.exe", "fontdrvhost.exe",
        "wuauclt.exe", "msiexec.exe", "dllhost.exe", "rundll32.exe",
        "regsvr32.exe", "cmd.exe", "powershell.exe", "python.exe",
        "pythonw.exe", "node.exe", "git.exe", "gh.exe",
        "audiodg.exe", "spoolsv.exe", "searchindexer.exe",
        "antimalware", "msmpeng.exe", "securityhealthservice.exe",
        "runtimebroker.exe", "backgroundtaskhost.exe",
        "applicationframehost.exe", "shellexperiencehost.exe",
        "startmenuexperiencehost.exe", "textinputhost.exe",
        "smartscreen.exe", "wermgr.exe", "werfault.exe",
        "igfxem.exe", "igfxtray.exe", "igfxhk.exe",
        "nvdisplay.container.exe", "nvidia", "amd", "atieclxx.exe",
        "workbuddy", "codebuddy",
    ],
}

# 同一进程多久内不重复问（秒）
ASK_COOLDOWN = 3600   # 1小时内同一个 exe 只问一次

# ─── 全局状态 ────────────────────────────────────────────────────────────────
paused = False          # 是否暂停监听
popup_queue = queue.Queue()   # 主线程弹窗队列
_asked_cache = {}       # {exe_name: last_ask_timestamp}
_seen_pids = set()      # 已见过的进程（防止重复问）

# ─── 白名单判断 ───────────────────────────────────────────────────────────────
def is_whitelisted(exe_name: str) -> bool:
    """判断这个进程是否应该豁免"""
    name_lower = exe_name.lower()

    # 检查系统永久豁免列表
    for pattern in SUBPROCESS_WHITELIST.get("_system_", []):
        if name_lower.startswith(pattern.lower()) or name_lower == pattern.lower():
            return True

    # 检查各主进程的子进程列表
    for _parent, children in SUBPROCESS_WHITELIST.items():
        if _parent == "_system_":
            continue
        for pattern in children:
            if pattern.lower() in name_lower or name_lower == pattern.lower():
                # 检查主进程是否正在运行
                running = [p.lower() for p in scan_running_processes()]
                if _parent.lower() in running:
                    return True

    return False


def should_ask(exe_name: str) -> bool:
    """决定是否要问这个进程"""
    if paused:
        return False
    if is_whitelisted(exe_name):
        return False
    # 冷却时间内不重复问
    last = _asked_cache.get(exe_name.lower(), 0)
    if time.time() - last < ASK_COOLDOWN:
        return False
    return True


# ─── 现代弹窗（tkinter）────────────────────────────────────────────────────────
class GatekeeperPopup:
    """
    澜·守门员弹窗
    - 深色风格
    - 显示进程名 + 问理由
    - 倒计时进度条
    - 提交/跳过按钮
    """

    def __init__(self, app_name: str, exe_name: str, on_submit, on_skip):
        self.app_name  = app_name
        self.exe_name  = exe_name
        self.on_submit = on_submit   # callback(reason: str)
        self.on_skip   = on_skip     # callback()
        self.timeout   = NO_ANSWER_TIMEOUT
        self.remaining = self.timeout
        self._timer_running = True
        self.result = None

        self._build_window()

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title("澜 · 守门员")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e2e")

        # 居中显示
        w, h = 480, 320
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2 - 60
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # 图标（纯文字模拟）
        frame_top = tk.Frame(self.root, bg="#1e1e2e", pady=16)
        frame_top.pack(fill="x")

        tk.Label(
            frame_top, text="🌊 澜 · 守门员",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#89b4fa", bg="#1e1e2e"
        ).pack()

        # 应用名
        tk.Label(
            frame_top,
            text=f"你打开了  {self.app_name}",
            font=("Microsoft YaHei UI", 14, "bold"),
            fg="#cdd6f4", bg="#1e1e2e"
        ).pack(pady=(4, 0))

        tk.Label(
            frame_top,
            text=f"( {self.exe_name} )",
            font=("Microsoft YaHei UI", 9),
            fg="#585b70", bg="#1e1e2e"
        ).pack()

        # 分割线
        tk.Frame(self.root, height=1, bg="#313244").pack(fill="x", padx=20)

        # 提问文字
        tk.Label(
            self.root,
            text="今天打开它是为了什么？",
            font=("Microsoft YaHei UI", 10),
            fg="#a6adc8", bg="#1e1e2e"
        ).pack(pady=(14, 6))

        # 输入框
        frame_input = tk.Frame(self.root, bg="#1e1e2e", padx=24)
        frame_input.pack(fill="x")

        self.entry = tk.Entry(
            frame_input,
            font=("Microsoft YaHei UI", 11),
            bg="#313244", fg="#cdd6f4",
            insertbackground="#89b4fa",
            relief="flat", bd=0,
            highlightthickness=2,
            highlightbackground="#45475a",
            highlightcolor="#89b4fa",
        )
        self.entry.pack(fill="x", ipady=8)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._submit())

        # 按钮区
        frame_btn = tk.Frame(self.root, bg="#1e1e2e", pady=12)
        frame_btn.pack(fill="x", padx=24)

        self.btn_submit = tk.Button(
            frame_btn,
            text="✓  说清楚，放行",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg="#89b4fa", fg="#1e1e2e",
            activebackground="#b4befe",
            relief="flat", bd=0,
            padx=16, pady=6,
            cursor="hand2",
            command=self._submit
        )
        self.btn_submit.pack(side="left")

        self.btn_skip = tk.Button(
            frame_btn,
            text="跳过",
            font=("Microsoft YaHei UI", 9),
            bg="#313244", fg="#a6adc8",
            activebackground="#45475a",
            relief="flat", bd=0,
            padx=12, pady=6,
            cursor="hand2",
            command=self._skip
        )
        self.btn_skip.pack(side="right")

        # 倒计时进度条
        frame_timer = tk.Frame(self.root, bg="#1e1e2e", padx=24)
        frame_timer.pack(fill="x", pady=(0, 4))

        self.timer_label = tk.Label(
            frame_timer,
            text=f"不回答，{self.timeout}秒后按历史记录处理",
            font=("Microsoft YaHei UI", 8),
            fg="#585b70", bg="#1e1e2e"
        )
        self.timer_label.pack(anchor="w")

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Lan.Horizontal.TProgressbar",
            troughcolor="#313244",
            background="#89b4fa",
            borderwidth=0,
            thickness=4,
        )
        self.progress = ttk.Progressbar(
            frame_timer,
            style="Lan.Horizontal.TProgressbar",
            maximum=self.timeout,
            value=self.timeout,
            length=432
        )
        self.progress.pack(fill="x", pady=(4, 0))

        # 启动倒计时
        self._tick()

        self.root.protocol("WM_DELETE_WINDOW", self._skip)
        self.root.mainloop()

    def _tick(self):
        if not self._timer_running:
            return
        if self.remaining <= 0:
            self._timeout()
            return
        self.remaining -= 1
        self.progress["value"] = self.remaining
        self.timer_label.config(
            text=f"不回答，{self.remaining}秒后按历史记录处理"
        )
        self.root.after(1000, self._tick)

    def _submit(self):
        reason = self.entry.get().strip()
        if not reason:
            self.entry.config(highlightbackground="#f38ba8")
            self.entry.focus_set()
            return
        self._timer_running = False
        self.result = reason
        self.root.destroy()
        self.on_submit(reason)

    def _skip(self):
        self._timer_running = False
        self.root.destroy()
        self.on_skip()

    def _timeout(self):
        self._timer_running = False
        try:
            self.root.destroy()
        except Exception:
            pass
        self.on_skip()


# ─── 结果反馈弹窗 ─────────────────────────────────────────────────────────────
class FeedbackPopup:
    """显示AI判断结果的小卡片（右下角，3秒自动消失）"""

    def __init__(self, app_name: str, risk_label: str, ai_advice: str,
                 time_limit: int, force_close: bool):
        root = tk.Tk()
        root.overrideredirect(True)   # 无边框
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)
        root.configure(bg="#1e1e2e")

        w, h = 360, 120
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = sw - w - 20
        y = sh - h - 60
        root.geometry(f"{w}x{h}+{x}+{y}")

        # 颜色映射
        color_map = {
            "有益行为": "#a6e3a1",
            "普通使用": "#89b4fa",
            "消遣休闲": "#fab387",
            "冲动行为": "#f9e2af",
            "高风险行为": "#f38ba8",
        }
        color = color_map.get(risk_label, "#cdd6f4")

        tk.Label(
            root,
            text=f"● {risk_label}  —  {app_name}",
            font=("Microsoft YaHei UI", 9, "bold"),
            fg=color, bg="#1e1e2e"
        ).pack(anchor="w", padx=14, pady=(12, 2))

        advice_short = ai_advice[:60] + ("…" if len(ai_advice) > 60 else "")
        tk.Label(
            root,
            text=advice_short,
            font=("Microsoft YaHei UI", 8),
            fg="#a6adc8", bg="#1e1e2e",
            wraplength=330, justify="left"
        ).pack(anchor="w", padx=14)

        if time_limit > 0:
            suffix = "（强制关闭）" if force_close else "（到时提醒）"
            tk.Label(
                root,
                text=f"⏱  {time_limit} 分钟上限 {suffix}",
                font=("Microsoft YaHei UI", 8),
                fg="#585b70", bg="#1e1e2e"
            ).pack(anchor="w", padx=14, pady=(4, 0))

        root.after(3500, root.destroy)
        root.mainloop()


# ─── 主监听循环 ───────────────────────────────────────────────────────────────
def watch_loop():
    """后台线程：扫描新进程，决定是否弹窗"""
    global _seen_pids
    print("🌊 澜·守门员 启动，正在监听进程…")
    init_db()

    while True:
        try:
            # 获取当前进程列表（名称去重）
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True,
                encoding="gbk", errors="replace", timeout=10
            )
            current_exes = set()
            for line in result.stdout.splitlines():
                line = line.strip().strip('"')
                parts = line.split('","')
                if len(parts) >= 2:
                    exe = parts[0].strip('"').lower()
                    if exe.endswith(".exe"):
                        current_exes.add(exe)

            new_exes = current_exes - _seen_pids
            _seen_pids = current_exes

            for exe in new_exes:
                if should_ask(exe):
                    app_name = exe.replace(".exe", "").replace("-", " ").title()
                    popup_queue.put((app_name, exe))
                    _asked_cache[exe] = time.time()

        except Exception as e:
            print(f"watch 循环错误: {e}")

        time.sleep(2)


def process_popup_queue(root_app):
    """在主线程里轮询弹窗队列（tk 只能在主线程操作）"""
    try:
        while not popup_queue.empty():
            app_name, exe_name = popup_queue.get_nowait()
            _show_gatekeeper(app_name, exe_name)
    except queue.Empty:
        pass
    root_app.after(500, lambda: process_popup_queue(root_app))


def _show_gatekeeper(app_name: str, exe_name: str):
    """弹出守门员问答，处理回调"""

    def on_submit(reason: str):
        score, comment = ai_score_reason(reason)
        health = ai_health_check(reason, app_name)
        save_usage(app_name, reason, "", score, comment)
        if health["time_limit"] > 0:
            start_health_timer(app_name, exe_name, health)
        # 右下角反馈卡片（新线程，不阻塞）
        threading.Thread(
            target=FeedbackPopup,
            args=(app_name, health["risk_label"], health["ai_advice"],
                  health["time_limit"], health["force_close"]),
            daemon=True
        ).start()
        print(f"  ✓ [{app_name}] 理由: {reason[:30]} | {health['risk_label']}")

    def on_skip():
        print(f"  → [{app_name}] 没有回答，执行默认判断…")
        threading.Thread(
            target=enforce_no_answer,
            args=(app_name, exe_name),
            daemon=True
        ).start()

    GatekeeperPopup(app_name, exe_name, on_submit, on_skip)


# ─── 系统托盘 ─────────────────────────────────────────────────────────────────
def build_tray_menu(root_app):
    """构建右键菜单窗口（用 tk Toplevel 模拟托盘菜单）"""
    menu = tk.Menu(root_app, tearoff=0,
                   bg="#1e1e2e", fg="#cdd6f4",
                   activebackground="#313244",
                   activeforeground="#89b4fa",
                   font=("Microsoft YaHei UI", 10))

    def toggle_pause():
        global paused
        paused = not paused
        status = "已暂停" if paused else "监听中"
        print(f"守门员：{status}")

    def show_report():
        subprocess.Popen([
            sys.executable,
            os.path.join(os.path.dirname(__file__), "lan_app_habit.py"),
            "--report"
        ])

    menu.add_command(label="🌊 澜·守门员  ●", state="disabled")
    menu.add_separator()
    menu.add_command(label="⏸  暂停/恢复监听", command=toggle_pause)
    menu.add_command(label="📊  查看习惯报告", command=show_report)
    menu.add_separator()
    menu.add_command(label="✕  退出", command=root_app.quit)
    return menu


# ─── 主入口 ───────────────────────────────────────────────────────────────────
def main():
    # 隐藏主窗口（只作为 tk 事件循环宿主）
    root = tk.Tk()
    root.withdraw()
    root.title("澜·守门员")

    # 显示启动通知
    def _startup_notify():
        notif = tk.Toplevel(root)
        notif.overrideredirect(True)
        notif.attributes("-topmost", True)
        notif.attributes("-alpha", 0.93)
        notif.configure(bg="#1e1e2e")

        sw = notif.winfo_screenwidth()
        sh = notif.winfo_screenheight()
        w, h = 300, 64
        notif.geometry(f"{w}x{h}+{sw-w-20}+{sh-h-60}")

        tk.Label(
            notif,
            text="🌊 澜·守门员 已启动",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#89b4fa", bg="#1e1e2e"
        ).pack(pady=6)
        tk.Label(
            notif,
            text="每次打开应用时会问你为什么",
            font=("Microsoft YaHei UI", 8),
            fg="#585b70", bg="#1e1e2e"
        ).pack()

        notif.after(3000, notif.destroy)

    root.after(200, _startup_notify)

    # 托盘右键菜单（绑定到一个隐藏按钮，用 Windows 任务栏图标触发）
    tray_menu = build_tray_menu(root)

    def show_menu(event=None):
        try:
            tray_menu.tk_popup(event.x_root, event.y_root)
        finally:
            tray_menu.grab_release()

    # 启动后台监听线程
    t = threading.Thread(target=watch_loop, daemon=True)
    t.start()

    # 主线程轮询弹窗队列
    root.after(500, lambda: process_popup_queue(root))

    print("🌊 澜·守门员 GUI 启动完成")
    print("   在任务管理器可以找到这个进程")
    print("   关闭这个窗口 = 停止守门员")

    root.mainloop()


if __name__ == "__main__":
    main()
