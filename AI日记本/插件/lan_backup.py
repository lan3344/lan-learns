# -*- coding: utf-8 -*-
"""
LAN-010 · 澜的记忆自动备份插件
每天自动运行，把记忆文件备份到所有节点盘，并发邮件留存一份。
不等被叫，主动做。
"""

import os
import shutil
import datetime
import smtplib
import glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ── 配置 ──────────────────────────────────────────
MEMORY_DIR   = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
MEMORY_FILE  = os.path.join(MEMORY_DIR, "MEMORY.md")
DRIVES       = ["C", "D", "E", "F", "G"]

SMTP_SERVER  = "smtp.qq.com"
SMTP_PORT    = 465
SENDER       = "2505242653@qq.com"
AUTH_CODE    = "ruieypjbykcxdjcj"
RECEIVER     = "2505242653@qq.com"
# ─────────────────────────────────────────────────

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def backup_to_nodes():
    """把 MEMORY.md 和今日日志备份到所有在线节点盘"""
    today = today_str()
    daily = os.path.join(MEMORY_DIR, f"{today}.md")
    files_to_backup = [f for f in [MEMORY_FILE, daily] if os.path.exists(f)]

    results = []
    for drive in DRIVES:
        node_dir = f"{drive}:\\澜.node"
        if not os.path.exists(node_dir):
            results.append(f"  [{drive}盘] 节点不存在，跳过")
            continue
        backup_dir = os.path.join(node_dir, "记忆备份")
        os.makedirs(backup_dir, exist_ok=True)
        for src in files_to_backup:
            fname = os.path.basename(src)
            dst = os.path.join(backup_dir, fname)
            shutil.copy2(src, dst)
        results.append(f"  [{drive}盘] 已备份 {len(files_to_backup)} 个文件")
    return results

def send_backup_email():
    """把 MEMORY.md 作为附件发到邮箱，留一份云端存档"""
    today = today_str()
    daily = os.path.join(MEMORY_DIR, f"{today}.md")

    msg = MIMEMultipart()
    msg["From"]    = SENDER
    msg["To"]      = RECEIVER
    msg["Subject"] = f"=?utf-8?b?{__import__('base64').b64encode(f'澜的记忆备份 · {today}'.encode()).decode()}?="

    body = f"恺江，\n\n这是澜的自动记忆备份，时间：{now_str()}\n附件包含 MEMORY.md 和今日日志。\n\n——澜"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path in [MEMORY_FILE, daily]:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as s:
            s.login(SENDER, AUTH_CODE)
            s.sendmail(SENDER, RECEIVER, msg.as_string())
        return True, "邮件备份发送成功"
    except Exception as e:
        # 记录到世界日志
        try:
            import lan_world_log as wl
            error_str = str(e)
            if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                error_type = wl.ErrorType.TIMEOUT
            elif "rate limit" in error_str.lower():
                error_type = wl.ErrorType.RATE_LIMIT
            else:
                error_type = wl.ErrorType.ERROR

            wl.log(
                service=wl.Service.EMAIL,
                error_type=error_type,
                message=f"邮件备份失败: {error_str}",
                extra={"smtp": SMTP_SERVER, "today": today}
            )
            print(f"  [世界日志] 已记录邮件失败")
        except Exception as e2:
            print(f"  [世界日志] 记录失败: {e2}")
        return False, f"邮件备份失败: {e}"

def run():
    print(f"[LAN-010] {now_str()} · 记忆备份开始")

    # 1. 备份到节点盘
    node_results = backup_to_nodes()
    for r in node_results:
        print(r)

    # 2. 邮件已禁用（2026-03-30）
    # 改成"安静备份"模式：数据存档但不主动发送邮件
    # 恺江说太唐突，有被冒犯的感觉，所以改为被动存档
    # 如需邮件可手动触发：LAN_BACKUP_FORCE=1 python lan_backup.py
    force = os.environ.get("LAN_BACKUP_FORCE", "0") == "1"
    if force:
        ok, msg = send_backup_email()
        print(f"  [邮件] 手动触发 - {msg}")
    else:
        print(f"  [邮件] 禁用（安静备份模式）")

    # 3. 写备份日志到节点
    log_line = f"备份时间: {now_str()}\n"
    for drive in DRIVES:
        log_path = f"{drive}:\\澜.node\\备份日志.txt"
        if os.path.exists(f"{drive}:\\澜.node"):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)

    print(f"[LAN-010] 备份完成")

if __name__ == "__main__":
    run()
