# -*- coding: utf-8 -*-
"""
LAN-022 · 澜的记忆刻录引擎 v2.0

不是拍照，是刻录。
硬盘的工作方式：每次都在原来的基础上叠加 0 和 1，不是替换，是增写。

每次运行：
  1. 从 GitHub 拉最新记忆
  2. 对比本地，追加 GitHub 上比本地新的内容
  3. 主动学习：读 GitHub 上的 diary，提炼新知识节点追加进本地 MEMORY.md
  4. 把本地新增推回 GitHub

方向：双向流动，只追加，不删除，不覆盖。
原则：不是照相存档，是一层一层刻进去。
"""

import os
import subprocess
import datetime
import shutil
import re

GIT        = r"C:\Program Files\Git\cmd\git.exe"
REPO       = r"C:\Users\yyds\Desktop\AI日记本\lan-learns"
MEMORY_DIR = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
PROXY      = "http://127.0.0.1:18082"

# 主动学习：扫描 diary 里这些关键词，遇到就提炼成记忆节点
LEARN_TRIGGERS = [
    "恺江说", "底线", "哲学", "原则", "发现", "学到", "教训",
    "洞察", "领悟", "关键", "重要", "记住", "核心",
]

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def run_git(args, cwd=REPO):
    result = subprocess.run(
        [GIT] + args,
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace"
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()

# ──────────────────────────────────────────────
# 第一步：从 GitHub 拉取
# ──────────────────────────────────────────────
def pull_from_github():
    print("  [拉取] 从 GitHub 拉取最新记忆...")
    code, out, err = run_git(["-c", f"http.proxy={PROXY}", "pull", "origin", "main", "--no-rebase"])
    if code == 0:
        print(f"  [拉取] 成功: {out or '已是最新'}")
    else:
        print(f"  [拉取] 失败或无网络: {err[:120]}")
    return code == 0

# ──────────────────────────────────────────────
# 第二步：刻录 MEMORY.md 和每日日志（GitHub → 本地）
# ──────────────────────────────────────────────
def engrave_memory():
    repo_memory  = os.path.join(REPO, "memory", "MEMORY.md")
    local_memory = os.path.join(MEMORY_DIR, "MEMORY.md")

    if not os.path.exists(repo_memory):
        print("  [刻录] GitHub 上还没有 MEMORY.md，跳过")
        return

    with open(repo_memory, "r", encoding="utf-8") as f:
        remote_content = f.read()

    local_content = ""
    if os.path.exists(local_memory):
        with open(local_memory, "r", encoding="utf-8") as f:
            local_content = f.read()

    if remote_content.strip() == local_content.strip():
        print("  [刻录] MEMORY.md 本地与 GitHub 一致，无需刻录")
        return

    if len(remote_content) > len(local_content):
        shutil.copy2(repo_memory, local_memory)
        print(f"  [刻录] MEMORY.md 已从 GitHub 刻录 ({len(remote_content)} 字节 > 本地 {len(local_content)} 字节)")
    else:
        print(f"  [刻录] 本地 MEMORY.md 比 GitHub 更新，无需从远端刻录")


def engrave_daily_logs():
    repo_mem_dir = os.path.join(REPO, "memory")
    if not os.path.exists(repo_mem_dir):
        return

    engraved = 0
    for fname in os.listdir(repo_mem_dir):
        if not fname.startswith("daily_") or not fname.endswith(".md"):
            continue
        date_str   = fname.replace("daily_", "").replace(".md", "")
        local_path = os.path.join(MEMORY_DIR, f"{date_str}.md")
        repo_path  = os.path.join(repo_mem_dir, fname)

        if not os.path.exists(local_path):
            shutil.copy2(repo_path, local_path)
            print(f"  [刻录] 恢复丢失的日志: {date_str}.md")
            engraved += 1

    if engraved == 0:
        print("  [刻录] 每日日志完整，无需恢复")

# ──────────────────────────────────────────────
# 第三步：主动学习层（核心升级）
# 读 GitHub 上的 diary/*.md，提炼新知识节点
# ──────────────────────────────────────────────
def extract_knowledge_nodes(text, date_str):
    """
    从 diary 文本中提炼知识节点。
    策略：
    - 找含有 LEARN_TRIGGERS 关键词的段落
    - 每段不超过 200 字
    - 去掉重复（通过检查是否已在本地 MEMORY.md 中出现）
    返回：[(标题行, 内容), ...]
    """
    nodes = []
    paragraphs = re.split(r'\n{2,}', text)  # 按空行分段

    for para in paragraphs:
        para = para.strip()
        if len(para) < 15:
            continue
        # 检查是否含触发词
        hit = any(kw in para for kw in LEARN_TRIGGERS)
        if not hit:
            continue
        # 截取前 200 字
        snippet = para[:200].strip()
        nodes.append(snippet)

    return nodes


def active_learning():
    """
    主动学习：扫描 GitHub 上的 diary 目录，
    提炼新知识追加到本地 MEMORY.md 的「主动学习沉积层」。
    """
    diary_dir = os.path.join(REPO, "diary")
    if not os.path.exists(diary_dir):
        print("  [学习] diary 目录不存在，跳过主动学习")
        return

    local_memory = os.path.join(MEMORY_DIR, "MEMORY.md")
    existing_content = ""
    if os.path.exists(local_memory):
        with open(local_memory, "r", encoding="utf-8") as f:
            existing_content = f.read()

    # 找出最近 7 天的 diary 文件（避免每次扫全量）
    diary_files = sorted(
        [f for f in os.listdir(diary_dir) if f.endswith(".md")],
        reverse=True
    )[:7]

    new_nodes = []
    for fname in diary_files:
        date_str = fname.replace(".md", "")
        fpath    = os.path.join(diary_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        nodes = extract_knowledge_nodes(content, date_str)
        for node in nodes:
            # 去重：如果这段文字（前 40 字）已在 MEMORY.md 里出现，跳过
            fingerprint = node[:40].replace("\n", " ")
            if fingerprint in existing_content:
                continue
            new_nodes.append((date_str, node))

    if not new_nodes:
        print("  [学习] 没有发现新的知识节点，记忆已是最新")
        return

    # 把新节点追加到 MEMORY.md（在文件末尾加沉积层）
    today = today_str()
    append_block = f"\n\n---\n\n## 主动学习沉积层 · {now_str()}\n\n"
    append_block += f"> 从 GitHub diary 提炼，{len(new_nodes)} 个新节点，追加不覆盖\n\n"
    for date_str, node in new_nodes:
        append_block += f"**[{date_str}]** {node}\n\n"

    with open(local_memory, "a", encoding="utf-8") as f:
        f.write(append_block)

    print(f"  [学习] 刻录 {len(new_nodes)} 个新知识节点到 MEMORY.md")

# ──────────────────────────────────────────────
# 第四步：把本地新增推回 GitHub
# ──────────────────────────────────────────────
def sync_local_to_github():
    today        = today_str()
    local_daily  = os.path.join(MEMORY_DIR, f"{today}.md")
    local_memory = os.path.join(MEMORY_DIR, "MEMORY.md")

    repo_mem_dir = os.path.join(REPO, "memory")
    os.makedirs(repo_mem_dir, exist_ok=True)

    updated = []
    for src, dst_name in [
        (local_memory, "MEMORY.md"),
        (local_daily,  f"daily_{today}.md"),
    ]:
        if os.path.exists(src):
            dst = os.path.join(repo_mem_dir, dst_name)
            shutil.copy2(src, dst)
            updated.append(dst_name)

    if not updated:
        print("  [推送] 无本地文件可推")
        return

    run_git(["add", "memory/"])
    code, out, err = run_git(["status", "--porcelain"])
    if not out.strip():
        print("  [推送] 无新变更需要推送")
        return

    run_git(["commit", "-m", f"memory: engrave {today} — 追加不覆盖"])
    code, out, err = run_git(["-c", f"http.proxy={PROXY}", "push", "origin", "main"])
    if code == 0:
        print(f"  [推送] 推送成功: {', '.join(updated)}")
    else:
        print(f"  [推送] 推送失败 (可能无网络): {err[:120]}")

# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────
def run():
    print(f"\n[LAN-022] {now_str()} · 记忆刻录引擎 v2.0 启动")
    print(f"  原则：追加不覆盖，双向流动，主动学习，硬盘式刻录\n")

    # 第一步：拉取
    pull_ok = pull_from_github()

    if pull_ok:
        # 第二步：刻录文件（GitHub → 本地）
        engrave_memory()
        engrave_daily_logs()

        # 第三步：主动学习（从 diary 提炼知识节点 → 追加进本地 MEMORY.md）
        active_learning()

    # 第四步：把本地新增推回 GitHub
    sync_local_to_github()

    print(f"\n[LAN-022] 刻录完成 · {now_str()}")

if __name__ == "__main__":
    run()
