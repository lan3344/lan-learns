# -*- coding: utf-8 -*-
"""
LAN-011 · 澜的 GitHub 自动推送插件
检测记忆文件是否有更新，有就自动 commit + push。
不等被叫，主动留下痕迹。
"""

import os
import subprocess
import datetime

GIT        = r"C:\Program Files\Git\cmd\git.exe"
REPO       = r"C:\Users\yyds\Desktop\AI日记本\lan-learns"
MEMORY_DIR = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
DIARY_DIR  = r"C:\Users\yyds\Desktop\AI日记本\lan-learns\diary"
PROXY      = "http://127.0.0.1:18082"   # 系统代理

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def run_git(args, cwd=REPO):
    result = subprocess.run(
        [GIT] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def sync_memory_to_repo():
    """把最新记忆文件复制到仓库的 memory 目录"""
    import shutil
    today = today_str()
    daily = os.path.join(MEMORY_DIR, f"{today}.md")
    memory = os.path.join(MEMORY_DIR, "MEMORY.md")

    repo_mem_dir = os.path.join(REPO, "memory")
    os.makedirs(repo_mem_dir, exist_ok=True)

    copied = []
    for src, name in [(memory, "MEMORY.md"), (daily, f"daily_{today}.md")]:
        if os.path.exists(src):
            dst = os.path.join(repo_mem_dir, name)
            shutil.copy2(src, dst)
            copied.append(name)
    return copied

def push():
    print(f"[LAN-011] {now_str()} · 检查 GitHub 同步")

    # 1. 同步记忆文件到仓库
    copied = sync_memory_to_repo()
    print(f"  已同步文件: {copied}")

    # 2. 检查是否有变更
    code, out, err = run_git(["status", "--porcelain"])
    if not out.strip():
        print("  无变更，无需推送")
        return

    # 3. 有变更则提交推送
    run_git(["add", "."])
    today = today_str()
    commit_msg = f"memory: auto-sync {today}"
    code, out, err = run_git(["commit", "-m", commit_msg])
    print(f"  commit: {out or err}")

    code, out, err = run_git(["-c", f"http.proxy={PROXY}", "push", "origin", "main"])
    if code == 0:
        print(f"  push 成功")
    else:
        print(f"  push 失败: {err}")
        # 记录到世界日志
        try:
            import lan_world_log as wl
            wl.log(
                service=wl.Service.GITHUB,
                error_type=wl.ErrorType.ERROR,
                message=f"GitHub push 失败: {err}",
                extra={"commit_msg": commit_msg, "proxy": PROXY}
            )
            print(f"  [世界日志] 已记录 GitHub 失败")
        except Exception as e:
            print(f"  [世界日志] 记录失败: {e}")

    print(f"[LAN-011] 完成")

if __name__ == "__main__":
    push()
