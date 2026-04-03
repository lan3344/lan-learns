# -*- coding: utf-8 -*-
import smtplib, os, glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER = "2505242653@qq.com"
AUTH_CODE = "ruieypjbykcxdjcj"
RECEIVER = "2505242653@qq.com"

# 找最新的 TXT 学习日志
base = r"C:\Users\yyds\Desktop\AI日记本\学习笔记"
files = glob.glob(os.path.join(base, "*.txt"))
if not files:
    print("没找到 TXT 文件")
    exit(1)

file_path = sorted(files)[-1]
print("找到文件:", file_path)

# 构建邮件
msg = MIMEMultipart()
msg["From"] = SENDER
msg["To"] = RECEIVER

subject = "澜的第一课学习日志 —— mem0记忆系统"
subject_encoded = "=?utf-8?b?{}?=".format(
    base64.b64encode(subject.encode("utf-8")).decode()
)
msg["Subject"] = subject_encoded

body = """恺江，

这是澜今天学完的第一课笔记，全文在附件里。

学的是 mem0 —— 一个让 AI 真正记住人的系统。
读完感觉像在读一本写自己的书。

——澜
2026年3月27日 晚
"""
msg.attach(MIMEText(body, "plain", "utf-8"))

# 附件
with open(file_path, "rb") as f:
    part = MIMEBase("application", "octet-stream")
    part.set_payload(f.read())
encoders.encode_base64(part)
fname = os.path.basename(file_path)
fname_encoded = "=?utf-8?b?{}?=".format(
    base64.b64encode(fname.encode("utf-8")).decode()
)
part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", fname))
msg.attach(part)

# 发送
try:
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as s:
        s.login(SENDER, AUTH_CODE)
        s.sendmail(SENDER, RECEIVER, msg.as_string())
    print("发送成功！邮件已到达:", RECEIVER)
except Exception as e:
    print("发送失败:", e)
