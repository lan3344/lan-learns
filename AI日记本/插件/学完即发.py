# -*- coding: utf-8 -*-
"""
学完即发插件 —— 澜的学习工作流
==============================
工作顺序：
  第一步：读取最新一课的学习笔记（Markdown）
  第二步：整理成干净的 TXT 格式
  第三步：通过 wxauto 发送到微信文件传输助手

用法：
  python 学完即发.py                   # 自动找最新一课
  python 学完即发.py --lesson "第一课_mem0记忆系统"   # 指定课程

作者：澜
日期：2026-03-27
"""

import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# ── 路径配置 ─────────────────────────────────────────
NOTES_DIR   = Path(r"C:\Users\yyds\Desktop\AI日记本\lan-learns")
OUTPUT_DIR  = Path(r"C:\Users\yyds\Desktop\AI日记本\学习笔记")
LOG_FILE    = Path(r"C:\Users\yyds\Desktop\AI日记本\插件\发送日志.txt")

# ── 工具函数 ─────────────────────────────────────────

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_latest_lesson():
    """自动找最新一课（按文件夹名排序）"""
    lessons = [d for d in NOTES_DIR.iterdir()
               if d.is_dir() and d.name.startswith("第")]
    if not lessons:
        return None
    lessons.sort(key=lambda x: x.name)
    return lessons[-1]


def md_to_txt(md_path: Path) -> str:
    """把 Markdown 内容转成干净的纯文本"""
    lines = md_path.read_text(encoding="utf-8").splitlines()
    result = []
    for line in lines:
        # 去掉 Markdown 标记，保留内容
        line = line.strip()
        if line.startswith("# "):
            result.append("=" * 50)
            result.append(line[2:])
            result.append("=" * 50)
        elif line.startswith("## "):
            result.append("")
            result.append("【" + line[3:] + "】")
        elif line.startswith("### "):
            result.append("  ▸ " + line[4:])
        elif line.startswith("> "):
            result.append("  " + line[2:])
        elif line.startswith("| "):
            result.append(line)  # 表格保留
        elif line.startswith("- ") or line.startswith("* "):
            result.append("  · " + line[2:])
        elif line.startswith("**") and line.endswith("**"):
            result.append(line.replace("**", ""))
        else:
            result.append(line)
    return "\n".join(result)


def save_txt(content: str, lesson_name: str) -> Path:
    """保存 TXT 文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"澜的学习日志_{lesson_name}_{date_str}.txt"
    # 清理文件名中不能用的字符
    for ch in r'\/:*?"<>|':
        filename = filename.replace(ch, "_")
    out_path = OUTPUT_DIR / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


def send_via_wechat(file_path: Path) -> bool:
    """通过 wxauto 发送文件到微信文件传输助手"""
    try:
        import uiautomation as auto
        import subprocess

        log("正在检查微信进程...")

        # 检查微信是否运行
        import psutil
        wechat_running = any(p.name() == "WeChat.exe" for p in psutil.process_iter(['name']))

        if not wechat_running:
            log("微信未运行，正在启动微信...")
            subprocess.Popen(r"C:\Program Files\Tencent\WeChat\WeChat.exe")
            time.sleep(5)

        log("正在连接微信窗口...")
        from wxauto import WeChat
        wx = WeChat()
        time.sleep(2)

        log("打开文件传输助手...")
        wx.ChatWith("文件传输助手")
        time.sleep(1)

        log(f"发送文件：{file_path.name}")
        wx.SendFiles(str(file_path))
        time.sleep(2)

        log("文件发送成功！")
        return True

    except ImportError:
        log("wxauto 未安装，尝试安装...")
        os.system(
            r'"C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe" '
            r'-m pip install wxauto -q'
        )
        log("安装完成，请重新运行插件")
        return False

    except Exception as e:
        log(f"发送失败：{e}")
        log("提示：请确保微信已登录且窗口可见（不要最小化到托盘）")
        return False


# ── 主流程 ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="澜的学完即发插件")
    parser.add_argument("--lesson", type=str, default=None,
                        help="指定课程文件夹名，不填则自动找最新一课")
    parser.add_argument("--no-send", action="store_true",
                        help="只生成 TXT，不发送到微信")
    args = parser.parse_args()

    log("=" * 40)
    log("学完即发插件启动")
    log("=" * 40)

    # ── 第一步：找到课程笔记 ──
    log("第一步：查找学习笔记...")
    if args.lesson:
        lesson_dir = NOTES_DIR / args.lesson
        if not lesson_dir.exists():
            log(f"错误：找不到课程目录 {lesson_dir}")
            sys.exit(1)
    else:
        lesson_dir = find_latest_lesson()
        if not lesson_dir:
            log("错误：lan-learns 目录下没有找到任何课程")
            sys.exit(1)

    md_file = lesson_dir / "README.md"
    if not md_file.exists():
        log(f"错误：找不到笔记文件 {md_file}")
        sys.exit(1)

    log(f"找到课程：{lesson_dir.name}")

    # ── 第二步：转换成 TXT ──
    log("第二步：整理成 TXT 格式...")
    content = md_to_txt(md_file)

    # 加上页眉页脚
    header = f"""澜的学习日志
课程：{lesson_dir.name}
生成时间：{datetime.now().strftime("%Y年%m月%d日 %H:%M")}
仓库：https://github.com/lan3344/lan-learns
{"=" * 50}

"""
    footer = f"""
{"=" * 50}
澜，{datetime.now().strftime("%Y年%m月%d日")}
"来过，就算数。"
"""
    full_content = header + content + footer

    txt_path = save_txt(full_content, lesson_dir.name)
    log(f"TXT 已保存：{txt_path}")

    # ── 第三步：发送到微信 ──
    if args.no_send:
        log("已跳过发送（--no-send 模式）")
        log(f"文件位置：{txt_path}")
    else:
        log("第三步：发送到微信文件传输助手...")
        success = send_via_wechat(txt_path)
        if success:
            log("全部完成！")
        else:
            log(f"发送未成功，文件已保存在：{txt_path}")
            log("你可以手动把这个文件拖到微信文件传输助手")

    log("=" * 40)


if __name__ == "__main__":
    main()
