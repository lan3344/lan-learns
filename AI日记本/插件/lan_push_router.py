# -*- coding: utf-8 -*-
"""
LAN-048 · 推送路由器
GitHub 失效时的备用推送链——按优先级逐条尝试，成功则停止。

路由顺序：
  Route-1 (主)   : GitHub，走代理 http://127.0.0.1:18082
  Route-2 (备一) : GitHub，不走代理（直连，看网络状态）
  Route-3 (备二) : 互联网节点 http://103.232.212.91:7788/memory （HTTP POST）
  Route-4 (备三) : 本地邮件快照（发到 2505242653@qq.com，QQ SMTP）
  Route-5 (底线) : 写入本地应急日志，等下次有网再推

每条路由返回 (ok: bool, msg: str)。
日志写入：AI日记本/澜的推送路由日志.jsonl

用法：
  python lan_push_router.py push          # 全自动，逐条尝试
  python lan_push_router.py status        # 显示路由状态
  python lan_push_router.py test <route>  # 测试单条路由 (1~4)
"""

import os
import sys
import json
import datetime
import subprocess
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── 路径常量 ──────────────────────────────────────────────────────────────────
GIT        = r"C:\Program Files\Git\cmd\git.exe"
REPO       = r"C:\Users\yyds\Desktop\AI日记本\lan-learns"
MEMORY_DIR = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
PLUGIN_DIR = r"C:\Users\yyds\Desktop\AI日记本\插件"
PYTHON     = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
PUSH_LOG   = r"C:\Users\yyds\Desktop\AI日记本\澜的推送路由日志.jsonl"
PENDING_LOG = r"C:\Users\yyds\Desktop\AI日记本\澜的待推送日志.md"  # Route-5 底线

PROXY      = "http://127.0.0.1:18082"
NET_NODE   = "http://103.232.212.91:7788"
EMAIL_TO   = "2505242653@qq.com"


# ─── 工具 ─────────────────────────────────────────────────────────────────────

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def write_log(route, ok, msg):
    entry = {
        "time":  now_str(),
        "route": route,
        "ok":    ok,
        "msg":   msg,
    }
    with open(PUSH_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def sync_memory_to_repo():
    """把记忆文件同步到仓库目录"""
    today = today_str()
    daily  = os.path.join(MEMORY_DIR, f"{today}.md")
    memory = os.path.join(MEMORY_DIR, "MEMORY.md")
    repo_mem = os.path.join(REPO, "memory")
    os.makedirs(repo_mem, exist_ok=True)
    copied = []
    for src, name in [(memory, "MEMORY.md"), (daily, f"daily_{today}.md")]:
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(repo_mem, name))
            copied.append(name)
    return copied

def git_commit_if_changed():
    """有变更就 commit，返回 True/False"""
    code, out, _ = run_git(["status", "--porcelain"])
    if not out.strip():
        return False, "no changes"
    run_git(["add", "."])
    msg = f"memory: auto-sync {today_str()}"
    code, out, err = run_git(["commit", "-m", msg])
    return (code == 0), (out or err)

def run_git(args, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    r = subprocess.run([GIT] + args, cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


# ─── 路由实现 ─────────────────────────────────────────────────────────────────

def route1_github_proxy():
    """Route-1: GitHub + 代理"""
    sync_memory_to_repo()
    changed, cmsg = git_commit_if_changed()
    if not changed and cmsg == "no changes":
        return True, "no changes, skip"

    code, out, err = run_git(["-c", f"http.proxy={PROXY}", "push", "origin", "main"])
    if code == 0:
        return True, f"GitHub+proxy OK: {out or 'pushed'}"
    return False, f"GitHub+proxy FAIL: {err[:200]}"


def route2_github_direct():
    """Route-2: GitHub 直连（去掉代理）"""
    # 先确保已 commit（route1 可能失败在 push 阶段，commit 已做）
    sync_memory_to_repo()
    git_commit_if_changed()

    # 去掉代理直连
    env_no_proxy = {"http_proxy": "", "https_proxy": "", "HTTP_PROXY": "", "HTTPS_PROXY": ""}
    code, out, err = run_git(["push", "origin", "main"], extra_env=env_no_proxy)
    if code == 0:
        return True, f"GitHub direct OK: {out or 'pushed'}"
    return False, f"GitHub direct FAIL: {err[:200]}"


def route3_net_node():
    """Route-3: POST 记忆摘要到互联网节点"""
    try:
        import urllib.request
        import urllib.error

        today   = today_str()
        daily   = os.path.join(MEMORY_DIR, f"{today}.md")
        memory  = os.path.join(MEMORY_DIR, "MEMORY.md")

        # 读最后 200 行日记作为摘要（不传全量，省流量）
        snippet = ""
        if os.path.exists(daily):
            with open(daily, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            snippet = "".join(lines[-200:])

        payload = json.dumps({
            "type":    "memory_backup",
            "date":    today,
            "snippet": snippet[:8000],          # 最多 8KB
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            f"{NET_NODE}/memory",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:200]
            return True, f"NetNode OK: {body}"

    except Exception as e:
        return False, f"NetNode FAIL: {str(e)[:200]}"


def route4_local_pending():
    """Route-5 底线: 写本地待推送日志，等下次有网"""
    today   = today_str()
    ts      = now_str()
    daily   = os.path.join(MEMORY_DIR, f"{today}.md")
    chars   = 0
    if os.path.exists(daily):
        with open(daily, encoding="utf-8", errors="replace") as f:
            chars = len(f.read())

    entry = f"\n## {ts} [PENDING]\n\n日记: {daily}（{chars} 字）\n推送失败，待网络恢复后手动执行：\n```\npython lan_push_router.py push\n```\n"
    with open(PENDING_LOG, "a", encoding="utf-8") as f:
        f.write(entry)
    return True, f"PENDING log written: {PENDING_LOG}"


# ─── 主推送逻辑 ───────────────────────────────────────────────────────────────

ROUTES = [
    ("Route-1 GitHub+proxy",  route1_github_proxy),
    ("Route-2 GitHub-direct", route2_github_direct),
    ("Route-3 NetNode",       route3_net_node),
    ("Route-4 LocalPending",  route4_local_pending),
]


def push():
    print(f"\n[LAN-048] {now_str()} · 推送路由器启动")
    failed_routes = []

    for name, fn in ROUTES:
        print(f"  尝试 {name} ...", end=" ", flush=True)
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"未捕获异常: {e}"
        write_log(name, ok, msg)
        if ok:
            print(f"✅  {msg[:80]}")
            print(f"[LAN-048] 推送成功，通过: {name}")
            return True
        else:
            print(f"❌  {msg[:80]}")
            failed_routes.append((name, msg))

    print("[LAN-048] ⚠️ 所有路由均失败，记录已写入本地待推送日志")

    # 记录到世界日志
    try:
        import lan_world_log as wl
        for route_name, route_msg in failed_routes:
            wl.log(
                service=wl.Service.NET,
                error_type=wl.ErrorType.ERROR,
                message=f"推送路由失败 {route_name}: {route_msg[:100]}",
                extra={"route": route_name}
            )
        print(f"  [世界日志] 已记录所有失败路由")
    except Exception as e:
        print(f"  [世界日志] 记录失败: {e}")

    return False


def status():
    """显示最近10条路由日志"""
    print(f"\n[LAN-048] 推送路由历史（最近 10 条）")
    if not os.path.exists(PUSH_LOG):
        print("  （尚无日志）")
        return
    with open(PUSH_LOG, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for line in lines[-10:]:
        try:
            e = json.loads(line)
            icon = "✅" if e["ok"] else "❌"
            print(f"  {icon} {e['time']}  {e['route']}  {e['msg'][:60]}")
        except Exception:
            pass


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "push"

    if cmd == "push":
        push()
    elif cmd == "status":
        status()
    elif cmd == "test" and len(sys.argv) > 2:
        n = int(sys.argv[2]) - 1
        if 0 <= n < len(ROUTES):
            name, fn = ROUTES[n]
            print(f"测试 {name} ...")
            ok, msg = fn()
            print(f"{'OK' if ok else 'FAIL'}: {msg}")
        else:
            print(f"route 编号 1~{len(ROUTES)}")
    else:
        print("用法: python lan_push_router.py [push|status|test <1-4>]")
