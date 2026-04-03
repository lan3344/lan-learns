# -*- coding: utf-8 -*-
"""
lan_chain.py — LAN-038 · 铁索连环检测器
恺江 2026-03-30

每一个能力不是孤岛，而是一根铁索的一节。
这个工具负责：
  1. 展示哪些能力能钩住哪些能力（triggers / feeds）
  2. 展示主干线（chains）
  3. 展示可直接出牌的顺子（combos）
  4. 检测断链（登记了但实际不连）
  5. 执行一个 combo（按顺序调用每个能力的 test_cmd）

用法：
  python lan_chain.py map              # 打印全部连接图（铁索地图）
  python lan_chain.py chains           # 列出所有主干链
  python lan_chain.py chain <名字>     # 展示某条链的详细路径
  python lan_chain.py combos           # 列出所有可出的顺子
  python lan_chain.py combo <名字>     # 执行某个顺子（test 模式）
  python lan_chain.py orphans          # 检测孤立能力（仍然没有连接的）
  python lan_chain.py reach <id>       # 从某个能力出发能到达哪里（正向传播）
  python lan_chain.py who-feeds <id>   # 谁能喂给这个能力
"""

import os, sys, json, subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MANIFEST_PATH = r"C:\Users\yyds\Desktop\AI日记本\插件\capability_manifest.json"
PLUGIN_DIR    = r"C:\Users\yyds\Desktop\AI日记本\插件"
PYTHON        = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"


# ─────────────────────────────────────────────────
def load():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)

def cap_by_id(caps, cap_id):
    for c in caps:
        if c["id"] == cap_id:
            return c
    return None


# ─────────────────────────────────────────────────
def cmd_map(manifest):
    """打印铁索地图：每个能力的 triggers / feeds"""
    caps = manifest["capabilities"]
    print("=" * 60)
    print("         澜的铁索连环地图")
    print("=" * 60)
    print("  ▶ = 触发谁（triggers）   ▷ = 喂给谁（feeds）")
    print("  ● = 参与的顺子（combos）")
    print()

    for c in caps:
        cid   = c["id"]
        name  = c["name"]
        trigs = c.get("triggers", [])
        feeds = c.get("feeds", [])
        combos= c.get("combos", [])

        # 连接度
        total_links = len(trigs) + len(feeds)
        if total_links == 0:
            prefix = "  ·"
        elif total_links <= 2:
            prefix = "  ─"
        elif total_links <= 4:
            prefix = "  ═"
        else:
            prefix = "  ╬"

        print(f"{prefix} [{cid:20s}] {name}")
        if trigs:
            print(f"        ▶ 触发: {' → '.join(trigs)}")
        if feeds:
            print(f"        ▷ 喂给: {' → '.join(feeds)}")
        if combos:
            print(f"        ● 顺子: {', '.join(combos)}")
        print()

    # 统计
    total = len(caps)
    connected = sum(1 for c in caps if c.get("triggers") or c.get("feeds"))
    orphans = total - connected
    print("=" * 60)
    print(f"  总计 {total} 个能力 | 已连接 {connected} 个 | 孤岛 {orphans} 个")
    if orphans > 0:
        print(f"  运行 'python lan_chain.py orphans' 查看孤岛列表")
    print("=" * 60)


# ─────────────────────────────────────────────────
def cmd_chains(manifest):
    """列出所有主干链"""
    chains = manifest.get("chains", {})
    note   = chains.pop("note", "")
    caps   = manifest["capabilities"]

    print("=" * 60)
    print("         澜的主干链（Chains）")
    print("=" * 60)
    if note:
        print(f"  {note}")
    print()

    for chain_name, chain_ids in chains.items():
        print(f"  ◆ {chain_name}")
        parts = []
        for cid in chain_ids:
            cap = cap_by_id(caps, cid)
            label = cap["name"] if cap else f"[?{cid}]"
            parts.append(label)
        print("    " + " ⟶ ".join(parts))
        print()


# ─────────────────────────────────────────────────
def cmd_chain_detail(manifest, chain_name):
    """展示某条链的详细信息"""
    chains = manifest.get("chains", {})
    caps   = manifest["capabilities"]

    if chain_name not in chains:
        print(f"找不到链: {chain_name}")
        print("可用的链:", [k for k in chains if k != "note"])
        return

    chain_ids = chains[chain_name]
    print(f"  ◆ {chain_name}  ({len(chain_ids)} 个节点)")
    print()
    for i, cid in enumerate(chain_ids):
        cap = cap_by_id(caps, cid)
        if cap:
            plugin_path = os.path.join(PLUGIN_DIR, cap["plugin"])
            exists = "✅" if os.path.exists(plugin_path) else "❌"
            print(f"  {i+1:2d}. {exists} [{cid:20s}] {cap['name']}")
            print(f"       {cap['description']}")
        else:
            print(f"  {i+1:2d}. ⚠️  [{cid}] — 未在 manifest 中登记")
        if i < len(chain_ids) - 1:
            print(f"        ↓")
    print()


# ─────────────────────────────────────────────────
def cmd_combos(manifest):
    """列出所有顺子"""
    combos = manifest.get("combos", {})
    note   = combos.pop("note", "")
    caps   = manifest["capabilities"]

    print("=" * 60)
    print("         澜的顺子（Combos）")
    print("=" * 60)
    if note:
        print(f"  {note}")
    print()

    for combo_name, combo_ids in combos.items():
        print(f"  ♠ {combo_name}  ({len(combo_ids)} 张牌)")
        parts = []
        for cid in combo_ids:
            cap = cap_by_id(caps, cid)
            label = cap["name"] if cap else f"[?{cid}]"
            parts.append(label)
        print("    " + " → ".join(parts))
        print()


# ─────────────────────────────────────────────────
def cmd_combo_run(manifest, combo_name):
    """执行某个顺子（调用每个能力的 test_cmd，验证可运行性）"""
    combos = manifest.get("combos", {})
    caps   = manifest["capabilities"]

    if combo_name not in combos:
        print(f"找不到顺子: {combo_name}")
        print("可用顺子:", [k for k in combos if k != "note"])
        return

    combo_ids = combos[combo_name]
    print(f"  ♠ 执行顺子: {combo_name}")
    print(f"  {'─'*50}")

    ok_count = 0
    fail_count = 0

    for cid in combo_ids:
        cap = cap_by_id(caps, cid)
        if not cap:
            print(f"  ⚠️  [{cid}] 未登记，跳过")
            continue
        plugin_path = os.path.join(PLUGIN_DIR, cap["plugin"])
        test_cmd    = cap.get("test_cmd", "")

        if not os.path.exists(plugin_path):
            print(f"  ❌ [{cid}] {cap['name']}  — 插件文件不存在")
            fail_count += 1
            continue

        if not test_cmd:
            print(f"  ⭕ [{cid}] {cap['name']}  — 无 test_cmd，跳过")
            ok_count += 1
            continue

        cmd = [PYTHON, plugin_path] + test_cmd.split()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=15)
            if r.returncode == 0:
                print(f"  ✅ [{cid}] {cap['name']}")
                ok_count += 1
            else:
                out = (r.stderr or r.stdout)[:80].strip()
                print(f"  ❌ [{cid}] {cap['name']}  — {out}")
                fail_count += 1
        except subprocess.TimeoutExpired:
            print(f"  ⏱️  [{cid}] {cap['name']}  — 超时")
            fail_count += 1
        except Exception as e:
            print(f"  ⚠️  [{cid}] {cap['name']}  — {e}")
            fail_count += 1

    print(f"  {'─'*50}")
    print(f"  结果: ✅{ok_count}  ❌{fail_count}")


# ─────────────────────────────────────────────────
def cmd_orphans(manifest):
    """检测仍然孤立的能力（triggers 和 feeds 都为空）"""
    caps = manifest["capabilities"]
    print("  孤立能力（triggers 和 feeds 均为空）：")
    orphans = []
    for c in caps:
        if not c.get("triggers") and not c.get("feeds"):
            orphans.append(c)

    if not orphans:
        print("  ✅ 所有能力都已连入链路，无孤岛！")
        return

    for c in orphans:
        print(f"  · [{c['id']:20s}] {c['name']}")
    print(f"\n  共 {len(orphans)} 个孤岛")


# ─────────────────────────────────────────────────
def cmd_reach(manifest, start_id):
    """从某个能力出发，正向传播能到达哪里（BFS）"""
    caps = manifest["capabilities"]
    # 构建 id -> (triggers + feeds) 的邻接表
    adj = {}
    for c in caps:
        adj[c["id"]] = list(c.get("triggers", [])) + list(c.get("feeds", []))

    visited = set()
    queue   = [start_id]
    order   = []

    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        order.append(curr)
        for nxt in adj.get(curr, []):
            if nxt not in visited:
                queue.append(nxt)

    order.remove(start_id)  # 不显示起点自身

    cap = cap_by_id(caps, start_id)
    start_name = cap["name"] if cap else start_id
    print(f"  从 [{start_id}]({start_name}) 出发，可到达 {len(order)} 个节点：")
    for i, cid in enumerate(order):
        c = cap_by_id(caps, cid)
        name = c["name"] if c else cid
        print(f"    {i+1:2d}. [{cid}] {name}")


# ─────────────────────────────────────────────────
def cmd_who_feeds(manifest, target_id):
    """谁能喂给这个能力（反向查找）"""
    caps = manifest["capabilities"]
    cap  = cap_by_id(caps, target_id)
    if not cap:
        print(f"找不到能力: {target_id}")
        return

    feeders = []
    for c in caps:
        if target_id in c.get("feeds", []) or target_id in c.get("triggers", []):
            feeders.append(c)

    print(f"  谁能喂给 [{target_id}]({cap['name']})：")
    if not feeders:
        print("  · （暂无，是个接收端孤岛）")
        return
    for c in feeders:
        rel = []
        if target_id in c.get("feeds", []):
            rel.append("feeds↗")
        if target_id in c.get("triggers", []):
            rel.append("triggers↗")
        print(f"    · [{c['id']:20s}] {c['name']}  ({', '.join(rel)})")


# ─────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    manifest = load()
    cmd = args[0]

    if cmd == "map":
        cmd_map(manifest)
    elif cmd == "chains":
        cmd_chains(manifest)
    elif cmd == "chain" and len(args) >= 2:
        cmd_chain_detail(manifest, " ".join(args[1:]))
    elif cmd == "combos":
        cmd_combos(manifest)
    elif cmd == "combo" and len(args) >= 2:
        combo_name = " ".join(args[1:])
        if "--run" in args:
            combo_name = combo_name.replace("--run", "").strip()
            cmd_combo_run(manifest, combo_name)
        else:
            # 先展示，再问是否执行
            cmd_combos_single(manifest, combo_name)
    elif cmd == "orphans":
        cmd_orphans(manifest)
    elif cmd == "reach" and len(args) >= 2:
        cmd_reach(manifest, args[1])
    elif cmd == "who-feeds" and len(args) >= 2:
        cmd_who_feeds(manifest, args[1])
    elif cmd == "run" and len(args) >= 2:
        cmd_combo_run(manifest, " ".join(args[1:]))
    else:
        print(f"未知命令: {cmd}")
        print("用法: python lan_chain.py [map|chains|chain <名>|combos|combo <名>|orphans|reach <id>|who-feeds <id>|run <顺子名>]")


def cmd_combos_single(manifest, combo_name):
    combos = manifest.get("combos", {})
    caps   = manifest["capabilities"]
    if combo_name not in combos:
        print(f"找不到顺子: {combo_name}")
        return
    combo_ids = combos[combo_name]
    print(f"  ♠ {combo_name}  ({len(combo_ids)} 张牌)")
    for i, cid in enumerate(combo_ids):
        cap = cap_by_id(caps, cid)
        name = cap["name"] if cap else f"[?{cid}]"
        print(f"    {i+1}. [{cid}] {name}")
    print()
    print("  加 --run 参数可执行: python lan_chain.py combo 顺子名 --run")


if __name__ == "__main__":
    main()
