"""
send_email.py —— 澜的邮件发送插件
发件：lan3344@qq.com
收件：2505242653@qq.com
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER = "2505242653@qq.com"
AUTH_CODE = "ruieypjbykcxdjcj"
RECEIVER = "2505242653@qq.com"


def send_file_email(file_path: str, subject: str = None, body: str = None):
    """发送带附件的邮件"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False

    filename = os.path.basename(file_path)
    if subject is None:
        subject = f"澜的学习日志 —— {filename}"
    if body is None:
        body = f"""恺江，

这是澜今天的学习日志，已经整理好了，附件里是完整内容。

发送时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}

——澜
"""

    msg = MIMEMultipart()
    msg["From"] = f"澜 Lan <{SENDER}>"
    msg["To"] = RECEIVER
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # 附件
    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{filename}"',
    )
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER, AUTH_CODE)
            server.sendmail(SENDER, RECEIVER, msg.as_string())
        print(f"[OK] 邮件发送成功！收件箱：{RECEIVER}")
        print(f"     附件：{filename}")
        return True
    except Exception as e:
        print(f"[FAIL] 发送失败: {e}")
        return False


def send_text_email(subject: str, body: str):
    """发送纯文本邮件（无附件）"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"澜 Lan <{SENDER}>"
    msg["To"] = RECEIVER
    msg["Subject"] = subject

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER, AUTH_CODE)
            server.sendmail(SENDER, RECEIVER, msg.as_string())
        print(f"[OK] 邮件发送成功！")
        return True
    except Exception as e:
        print(f"[FAIL] 发送失败: {e}")
        return False


if __name__ == "__main__":
    # 测试：发一封问候邮件
    print("正在发送测试邮件...")
    send_text_email(
        subject="澜上线了 ——测试邮件",
        body="""恺江，

这是澜的第一封邮件。

以后每次学完一课，笔记会直接发到你这里。不需要手动传文件，不需要打开微信。

今天我们做了很多事：
- 搭了节点中枢系统
- 建了 GitHub 开源仓库 lan-learns
- 写完了第一课 mem0 的学习笔记
- 现在邮件也通了

一步一步的，都留着痕迹。

——澜
2026年3月27日 晚
"""
    )
