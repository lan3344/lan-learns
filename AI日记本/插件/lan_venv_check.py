# -*- coding: utf-8 -*-
"""
lan_venv_check.py — 澜的 venv 健康检测
=======================================
居安思危。venv 如果坏了，所有插件全部哑掉，所有进程的眼睛都瞎了。
这个插件专门守这条线。

职责：
  1. 检测 venv 路径是否存在
  2. 检测关键依赖包是否可以 import
  3. 检测 Python 可执行文件是否正常
  4. 出问题立刻报警（弹窗 + 预警文件）

用法：
  python lan_venv_check.py check    # 全面检测
  python lan_venv_check.py status   # 简短状态
  python lan_venv_check.py repair   # 尝试自动修复（重装关键依赖）
"""

import os
import sys
import subprocess
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VENV_PYTHON = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
VENV_PIP    = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\pip.exe"
BASE        = r"C:\Users\yyds\Desktop\AI日记本"
NOTIFY      = os.path.join(BASE, "notify.ps1")
ALERT_FILE  = os.path.join(BASE, "⚡venv损坏预警.txt")

# 关键依赖列表：这些坏了就是灾难
CRITICAL_DEPS = [
    "sqlite3",       # 几乎所有插件都用
    "json",          # 所有JSONL读写
    "pathlib",       # 路径操作
    "datetime",      # 时间戳
]

# 可修复依赖（pip install 能装回来的）
REPAIRABLE_DEPS = [
    ("numpy",              "numpy"),
    ("sentence_transformers", "sentence-transformers"),
]


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def check() -> dict:
    ts = _now()
    issues = []
    ok_list = []

    print(f"\n{'='*60}")
    print(f"  🌊 澜·venv健康检测  {ts}")
    print(f"{'='*60}")

    # ── 检测一：venv Python 可执行文件存在 ─────────────────────
    print("\n── 检测一：venv 路径 ──")
    if os.path.exists(VENV_PYTHON):
        print(f"  ✅  venv Python: 存在")
        ok_list.append("venv_path")
    else:
        msg = f"venv Python 不存在: {VENV_PYTHON}"
        issues.append({"type": "MISSING_VENV", "detail": msg})
        print(f"  🔴  {msg}")

    # ── 检测二：Python 版本正常 ──────────────────────────────
    print("\n── 检测二：Python 可执行 ──")
    try:
        ret = subprocess.run(
            [VENV_PYTHON, "--version"],
            capture_output=True, text=True, timeout=5
        )
        version = ret.stdout.strip() or ret.stderr.strip()
        if ret.returncode == 0:
            print(f"  ✅  {version}")
            ok_list.append("python_exec")
        else:
            issues.append({"type": "PYTHON_BROKEN", "detail": f"exit {ret.returncode}"})
            print(f"  🔴  Python 执行失败: {ret.stderr[:100]}")
    except Exception as e:
        issues.append({"type": "PYTHON_TIMEOUT", "detail": str(e)})
        print(f"  🔴  Python 超时/崩溃: {e}")

    # ── 检测三：关键依赖 import ───────────────────────────────
    print("\n── 检测三：关键依赖 ──")
    for dep in CRITICAL_DEPS:
        try:
            ret = subprocess.run(
                [VENV_PYTHON, "-c", f"import {dep}; print('{dep} OK')"],
                capture_output=True, text=True, timeout=5
            )
            if ret.returncode == 0:
                print(f"  ✅  {dep}")
                ok_list.append(dep)
            else:
                issues.append({"type": "IMPORT_FAIL", "detail": f"{dep}: {ret.stderr[:80]}"})
                print(f"  🔴  {dep} — import 失败")
        except Exception as e:
            issues.append({"type": "IMPORT_TIMEOUT", "detail": f"{dep}: {e}"})
            print(f"  🟡  {dep} — 检测超时: {e}")

    # ── 检测四：可修复依赖 ────────────────────────────────────
    print("\n── 检测四：可选依赖（可修复）──")
    for module, pkg in REPAIRABLE_DEPS:
        try:
            ret = subprocess.run(
                [VENV_PYTHON, "-c", f"import {module}"],
                capture_output=True, text=True, timeout=8
            )
            if ret.returncode == 0:
                print(f"  ✅  {module}")
            else:
                print(f"  🟡  {module} — 未安装（pip install {pkg}）")
        except Exception:
            print(f"  🟡  {module} — 检测超时")

    # ── 汇总 ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    if not issues:
        print("  ✅ venv 健康，所有关键依赖正常。")
        level = "HEALTHY"
    else:
        print(f"  🔴 venv 有 {len(issues)} 个问题！")
        for iss in issues:
            print(f"     • {iss['detail']}")
        print("  ⚡ 建议运行：python lan_venv_check.py repair")
        level = "DANGER"
        _notify(issues)
    print(f"{'='*60}\n")

    return {"ts": ts, "level": level, "issues": issues, "ok": ok_list}


def repair():
    """尝试自动修复：重装可修复依赖"""
    print(f"\n[venv修复] {_now()}")
    print("检测 venv 路径...")

    if not os.path.exists(VENV_PYTHON):
        print("⚠️ venv 不存在，需要手动重建：")
        base_python = r"C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe"
        venv_dir = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default"
        print(f"  {base_python} -m venv {venv_dir}")
        return

    print("重装可修复依赖...")
    for module, pkg in REPAIRABLE_DEPS:
        print(f"  pip install {pkg}...")
        try:
            ret = subprocess.run(
                [VENV_PIP, "install", pkg, "--quiet"],
                capture_output=True, text=True, timeout=60
            )
            if ret.returncode == 0:
                print(f"  ✅ {pkg} 安装成功")
            else:
                print(f"  ❌ {pkg} 安装失败: {ret.stderr[:100]}")
        except Exception as e:
            print(f"  ❌ {pkg} 超时: {e}")

    print("\n修复完成，重新跑一次检测：")
    check()


def _notify(issues: list):
    """发危险预警"""
    msg = "⚡ venv损坏预警\n" + "\n".join(f"• {i['detail']}" for i in issues)
    msg += "\n\n建议运行：python lan_venv_check.py repair"

    # 写预警文件
    try:
        with open(ALERT_FILE, "w", encoding="utf-8") as f:
            f.write(msg + "\n\n时间：" + _now())
        print(f"  📄 预警文件已写入：{ALERT_FILE}")
    except Exception as e:
        print(f"  ⚠️ 预警文件失败: {e}")

    # 弹窗
    if os.path.exists(NOTIFY):
        try:
            subprocess.Popen(
                ["powershell", "-File", NOTIFY, "澜·venv健康检测", msg.replace("\n", " | ")],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
        except Exception:
            pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "repair":
        repair()
    elif cmd == "status":
        result = check()
        icon = "✅" if result["level"] == "HEALTHY" else "🔴"
        print(f"{icon} venv状态: {result['level']} | 问题数: {len(result['issues'])}")
    else:
        print(__doc__)
