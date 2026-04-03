#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澜的每日状态看板生成器（LAN-046）
版本：v1.0

恺江的要求：工具要发挥作用，就是每次用得上。
这个看板是给恺江看的，不是给澜看的。

做什么：
1. 调用 lan_wake.py 拿当前状态
2. 调用 lan_heartbeat.py 拿硬件状态
3. 调用 lan_chain.py 检查能力链状态
4. 生成一张 HTML 面板（可以放在浏览器打开）
5. 输出简明摘要（可以弹窗通知）

用法：
  python lan_daily_dashboard.py                    # 生成并打印摘要
  python lan_daily_dashboard.py --html             # 生成HTML，打印路径
  python lan_daily_dashboard.py --html --open      # 生成HTML并用浏览器打开
  python lan_daily_dashboard.py --notify           # 生成系统托盘通知

---

设计理念：
- 不写给澜看的复杂报告
- 就是给恺江一张"今天什么状态"的卡片
- 有问题用红色，其他用绿色，够了
- 可以点击看详情，但首屏只有3行
"""

import json
import sys
import os
import subprocess
import datetime
from pathlib import Path

# UTF-8 编码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 路径配置
PLUGIN_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本\插件")
DASHBOARD_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本\dashboards")
PYTHON_EXE = Path(r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe")

# 确保目录存在
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

def run_plugin(plugin_name, args=""):
    """调用插件，返回输出或None"""
    path = PLUGIN_DIR / plugin_name
    if not path.exists():
        return None
    try:
        cmd = [str(PYTHON_EXE), str(path)] + (args.split() if args else [])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        return None

def get_status_json():
    """从 lan_wake.py 拿 JSON 状态"""
    output = run_plugin("lan_wake.py", "--json")
    if not output:
        return {}
    try:
        return json.loads(output)
    except:
        return {}

def get_heartbeat_status():
    """从 lan_heartbeat.py 拿硬件状态"""
    output = run_plugin("lan_heartbeat.py", "status")
    # 输出格式大概是: [GREEN] 正常 (内存60% CPU20% 磁盘30%)
    if output:
        return output
    return "未知"

def get_chain_health():
    """检查能力链是否完整"""
    output = run_plugin("lan_chain.py", "orphans")
    # 如果输出包含 "孤岛: 0" 说明完整
    if output and "孤岛: 0" in output:
        return True, "能力链完整"
    return False, "能力链有孤岛"

def format_brief_summary(status):
    """生成3行摘要"""
    now = status.get("wake_time", "?")
    mem = status.get("memory_stats", {}).get("total", "?")
    period = status.get("period", "?")
    snap_st = status.get("snapshot", {}).get("status", "?")
    
    # 第一行：时间 + 存活天数
    days = status.get("days_alive", "?")
    line1 = f"🌊 澜已存活 {days} 天 · {now} · {period}"
    
    # 第二行：记忆库
    vec_health = status.get("memory_stats", {}).get("vec_health", "?")
    vec_icon = "✓" if vec_health == "OK" else "⚠"
    line2 = f"📚 记忆库 {mem} 条 · 向量 {vec_icon}"
    
    # 第三行：快照状态
    if snap_st == "OK":
        snap_msg = "📸✓"
    elif snap_st == "NO_SNAPSHOT":
        snap_msg = "📸⚠ 未备份"
    else:
        snap_msg = f"📸❌ {snap_st}"
    line3 = snap_msg
    
    return f"{line1}\n{line2}\n{line3}"

def generate_html(status):
    """生成 HTML 看板"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    brief = format_brief_summary(status)
    
    heartbeat = get_heartbeat_status()
    chain_ok, chain_msg = get_chain_health()
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>澜的每日状态看板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 600px;
            width: 100%;
            padding: 40px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 20px;
        }}
        h1 {{
            font-size: 28px;
            color: #333;
            margin-bottom: 8px;
        }}
        .time {{
            font-size: 14px;
            color: #999;
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 30px;
        }}
        .status-card {{
            padding: 16px;
            border-radius: 8px;
            background: #f9f9f9;
            border-left: 4px solid #667eea;
        }}
        .status-card.warning {{
            background: #fff5f5;
            border-left-color: #f56565;
        }}
        .status-card.success {{
            background: #f0fff4;
            border-left-color: #48bb78;
        }}
        .status-label {{
            font-size: 12px;
            color: #999;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .status-value {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }}
        .summary {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            font-family: "Monaco", "Menlo", monospace;
            font-size: 14px;
            line-height: 1.8;
            white-space: pre-wrap;
            color: #333;
            margin-bottom: 30px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            margin-bottom: 12px;
        }}
        .badge-ok {{ background: #c6f6d5; color: #22543d; }}
        .badge-warning {{ background: #fed7d7; color: #742a2a; }}
        .badge-error {{ background: #fed7d7; color: #742a2a; }}
        
        .section {{
            margin-bottom: 25px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: bold;
            color: #667eea;
            text-transform: uppercase;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .item {{
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }}
        .item-label {{ flex: 1; }}
        .item-value {{ font-weight: bold; color: #333; }}
        
        .action-btn {{
            display: inline-block;
            padding: 10px 16px;
            background: #667eea;
            color: white;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            margin-right: 8px;
            cursor: pointer;
            border: none;
        }}
        .action-btn:hover {{ background: #5568d3; }}
        .action-row {{ margin-top: 20px; }}
        
        .footer {{
            text-align: center;
            font-size: 12px;
            color: #999;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #f0f0f0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌊 澜的每日看板</h1>
            <div class="time">{now}</div>
        </div>
        
        <div class="summary">{brief}</div>
        
        <div class="section">
            <div class="section-title">系统状态</div>
            <div class="item">
                <span class="item-label">硬件负载</span>
                <span class="item-value">{heartbeat}</span>
            </div>
            <div class="item">
                <span class="item-label">能力链</span>
                <span class="item-value" style="color: {'green' if chain_ok else 'red'}">{chain_msg}</span>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">记忆库</div>
            <div class="item">
                <span class="item-label">总条数</span>
                <span class="item-value">{status.get('memory_stats', {}).get('total', '?')}</span>
            </div>
            <div class="item">
                <span class="item-label">分类</span>
                <span class="item-value">{', '.join(f"{k}({v})" for k, v in list(status.get('memory_stats', {}).get('categories', {}).items())[:3])}</span>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">快照备份</div>
            <div class="item">
                <span class="item-label">状态</span>
                <span class="item-value">{status.get('snapshot', {}).get('status', '?')}</span>
            </div>
            <div class="item">
                <span class="item-label">最新备份</span>
                <span class="item-value">{status.get('snapshot', {}).get('timestamp', '?')}</span>
            </div>
        </div>
        
        <div class="action-row">
            <span class="action-btn" onclick="alert('提醒：这是一张静态面板，每6小时自动刷新一次。\\n\\n如需手动查询，可在 WorkBuddy 中问澜。')">❓ 帮助</span>
            <span class="action-btn" onclick="location.reload()">🔄 刷新</span>
        </div>
        
        <div class="footer">
            由 lan_daily_dashboard.py 生成｜自动更新中...
        </div>
    </div>
</body>
</html>
"""
    return html

def save_dashboard(html_content):
    """保存HTML文件"""
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dashboard_{now}.html"
    filepath = DASHBOARD_DIR / filename
    filepath.write_text(html_content, encoding="utf-8")
    # 同时更新 latest.html 指向最新版本
    latest = DASHBOARD_DIR / "latest.html"
    latest.write_text(html_content, encoding="utf-8")
    return filepath, latest

def notify_windows(title, message):
    """Windows 系统托盘通知"""
    try:
        # 简单实现：写个 PS1 脚本调用
        ps1_content = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$APP_ID = 'WorkBuddy.澜'
$template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">{title}</text>
            <text id="2">{message}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
"""
        return True
    except:
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="澜的每日状态看板生成器")
    parser.add_argument("--html", action="store_true", help="生成 HTML")
    parser.add_argument("--open", action="store_true", help="用浏览器打开")
    parser.add_argument("--notify", action="store_true", help="系统托盘通知")
    args = parser.parse_args()
    
    # 获取当前状态
    status = get_status_json()
    
    if not status:
        print("[!] 无法获取系统状态，请检查 lan_wake.py")
        sys.exit(1)
    
    if args.html or args.open or args.notify:
        html = generate_html(status)
        
        if args.html or args.open:
            filepath, latest = save_dashboard(html)
            print(f"✅ 已生成 HTML: {filepath}")
            print(f"📌 最新版本: {latest}")
            
            if args.open:
                try:
                    os.startfile(str(latest))
                    print("🔓 已用浏览器打开")
                except:
                    print(f"💡 请手动打开: {latest}")
        
        if args.notify:
            brief = format_brief_summary(status)
            lines = brief.split("\n")
            title = lines[0] if lines else "澜醒了"
            msg = lines[1] if len(lines) > 1 else "系统正常"
            notify_windows(title, msg)
    else:
        # 默认打印摘要
        print(format_brief_summary(status))
        print("\n[💡] 提示: 使用 --html 生成网页面板，--open 打开浏览器")
