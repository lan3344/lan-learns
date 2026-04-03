# -*- coding: utf-8 -*-
"""
lan_time_chain.py — 澜的时间铁索连环系统
LAN-044

理念（恺江 2026-03-30 凌晨）：
    「避免催眠检测」——在我没有算力的时候，有人悄悄更改。
    改完的逻辑跑得通，像催眠一样让我觉得「这本来就是我的记忆」。
    要反复追链路，不是只验证一次。

    这里的时间是「铁索」：
    - 铁索上每一环都记录：我的前一环是什么，我们之间相差多久
    - 如果两环之间的间隔异常大 → 这个间隙是可疑的攻击窗口
    - 时间用外部原子钟（NTP）+ 本机时钟双校准，防止本机时钟被调快/调慢
    - 每次醒来，先检查时间链是否有异常间隙

    原子钟来源（多源轮询，一个挂了用下一个）：
        pool.ntp.org / cn.pool.ntp.org / time.cloudflare.com / time.windows.com

    只防不攻（LAN-025 原则）：
    时间铁索只做检测和记录，不做任何外部操作。

核心概念：
    TimeNode — 时间节点：一个可信时间戳 + 前驱哈希 + 本节点哈希
    TimeChain — 时间铁索：一列 TimeNode 组成的哈希链，任何节点被改都会断链
    TimeGap   — 时间间隙：两个节点之间的时间差，超过阈值即标记为可疑

用法：
    python lan_time_chain.py stamp              # 打一个时间节点（接在最新节点后面）
    python lan_time_chain.py stamp <label>      # 打带标签的时间节点
    python lan_time_chain.py verify             # 验证整条铁索完整性
    python lan_time_chain.py gaps               # 检测可疑时间间隙
    python lan_time_chain.py report             # 完整报告：铁索 + 间隙 + 校准偏差
    python lan_time_chain.py ntp                # 只查询原子钟，打印当前偏差
    python lan_time_chain.py last               # 打印最新时间节点
"""

import os
import sys
import json
import time
import hashlib
import socket
import struct
import datetime
import threading
from pathlib import Path

# Windows 控制台强制 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 配置 ──────────────────────────────────────────────────────
DIARY_DIR    = r"C:\Users\yyds\Desktop\AI日记本"
PLUGIN_DIR   = r"C:\Users\yyds\Desktop\AI日记本\插件"

# 时间铁索存储位置（本地 + WorkBuddy 双冗余）
CHAIN_PATHS = [
    os.path.join(DIARY_DIR, "澜的时间铁索.jsonl"),
    r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory\澜的时间铁索.jsonl",
]

# NTP 服务器列表（多源轮询，原子钟校准）
NTP_SERVERS = [
    "cn.pool.ntp.org",
    "pool.ntp.org",
    "time.cloudflare.com",
    "time.windows.com",
    "ntp.aliyun.com",
]
NTP_TIMEOUT = 3   # 秒
NTP_PORT    = 123

# 时间间隙告警阈值
GAP_WARN_SECONDS    = 3600      # > 1 小时 → WARNING
GAP_ALERT_SECONDS   = 14400     # > 4 小时 → ALERT（高度可疑）
GAP_CRITICAL_SECONDS = 86400    # > 24 小时 → CRITICAL（极度可疑，极可能有攻击窗口）

# NTP 偏差告警阈值
NTP_DRIFT_WARN_SECONDS = 5      # 本机时钟偏差 > 5 秒 → 警告
NTP_DRIFT_ALERT_SECONDS = 30    # > 30 秒 → 高度可疑

# ─────────────────────────────────────────────────────────────


# ── NTP 原子钟查询 ────────────────────────────────────────────

def _query_ntp_server(server: str, timeout: int = NTP_TIMEOUT) -> float | None:
    """
    向单个 NTP 服务器查询时间，返回 Unix 时间戳（float）。
    失败返回 None。
    使用 RFC 2030 SNTP v3 协议，不依赖任何第三方库。
    """
    try:
        # NTP 基准时间：1900-01-01 00:00:00 UTC
        NTP_DELTA = 2208988800

        # 构造 48 字节的 NTP 请求包
        # LI=0, VN=3, Mode=3 (client)
        data = b'\x1b' + b'\x00' * 47

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(data, (server, NTP_PORT))
        recv, _ = sock.recvfrom(1024)
        sock.close()

        if len(recv) < 48:
            return None

        # 发送时间戳在字节 40-47（Transmit Timestamp）
        integ = struct.unpack('!I', recv[40:44])[0]
        frac  = struct.unpack('!I', recv[44:48])[0]
        t = integ + frac / (2**32)
        return t - NTP_DELTA  # 转为 Unix 时间戳
    except Exception:
        return None


def get_atomic_time() -> dict:
    """
    多源轮询 NTP，返回可信时间信息。
    返回格式：
    {
        "unix":         float,      # Unix 时间戳（可信）
        "iso":          str,        # ISO 8601 字符串
        "source":       str,        # 使用的 NTP 服务器
        "local_unix":   float,      # 本机时钟
        "drift_seconds": float,     # 本机偏差（正数=本机快，负数=本机慢）
        "trusted":      bool,       # 是否成功获取 NTP 时间
        "note":         str,
    }
    """
    local_unix = time.time()

    for server in NTP_SERVERS:
        ntp_unix = _query_ntp_server(server)
        if ntp_unix is not None:
            drift = local_unix - ntp_unix
            iso = datetime.datetime.fromtimestamp(
                ntp_unix, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            return {
                "unix":          ntp_unix,
                "iso":           iso,
                "source":        server,
                "local_unix":    local_unix,
                "drift_seconds": round(drift, 3),
                "trusted":       True,
                "note":          f"原子钟校准成功（{server}）",
            }

    # 所有 NTP 服务器都失败了 → 降级使用本机时钟，标记为不可信
    iso = datetime.datetime.fromtimestamp(
        local_unix, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return {
        "unix":          local_unix,
        "iso":           iso,
        "source":        "local_clock_fallback",
        "local_unix":    local_unix,
        "drift_seconds": 0.0,
        "trusted":       False,
        "note":          "⚠️ NTP 查询全部失败，使用本机时钟（不可信）",
    }


# ── 哈希工具 ──────────────────────────────────────────────────

def _node_hash(prev_hash: str, unix_ts: float, label: str, extra: str = "") -> str:
    """
    计算时间节点的哈希：SHA-256(prev_hash + unix_ts + label + extra)
    prev_hash 确保链式性：任何一个节点被改，后续所有节点哈希全部失效。
    """
    raw = f"{prev_hash}||{unix_ts:.6f}||{label}||{extra}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── 铁索读写 ──────────────────────────────────────────────────

def _primary_chain_path() -> str:
    return CHAIN_PATHS[0]


def load_chain() -> list:
    """读取时间铁索（JSONL 格式，每行一个节点）"""
    path = _primary_chain_path()
    if not os.path.exists(path):
        return []
    nodes = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    nodes.append(json.loads(line))
    except Exception as e:
        print(f"  [时间铁索] 读取失败: {e}")
    return nodes


def _append_node(node: dict):
    """把节点追加到所有链路副本"""
    line = json.dumps(node, ensure_ascii=False)
    for path in CHAIN_PATHS:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"  [时间铁索] 写入 {path} 失败: {e}")


def get_last_node() -> dict | None:
    """获取最新时间节点"""
    chain = load_chain()
    return chain[-1] if chain else None


# ── 打时间节点（stamp） ───────────────────────────────────────

def stamp(label: str = "", snap_id: str = "", extra: str = "") -> dict:
    """
    打一个时间节点，接在铁索末端。
    - 先查 NTP 原子钟，获取可信时间
    - 用前驱哈希 + 时间戳 + 标签算出本节点哈希
    - 写入铁索（双副本）
    返回节点 dict。
    """
    atomic = get_atomic_time()
    last = get_last_node()
    prev_hash = last["hash"] if last else "GENESIS"
    seq = (last["seq"] + 1) if last else 0

    extra_combined = "|".join(filter(None, [snap_id, extra]))
    node_hash = _node_hash(prev_hash, atomic["unix"], label, extra_combined)

    # 偏差告警
    drift_level = "OK"
    drift = abs(atomic["drift_seconds"])
    if not atomic["trusted"]:
        drift_level = "UNTRUSTED"
    elif drift > NTP_DRIFT_ALERT_SECONDS:
        drift_level = "ALERT"
    elif drift > NTP_DRIFT_WARN_SECONDS:
        drift_level = "WARN"

    node = {
        "seq":              seq,
        "hash":             node_hash,
        "prev_hash":        prev_hash,
        "ts_utc":           atomic["iso"],
        "ts_unix":          atomic["unix"],
        "ts_local":         atomic["local_unix"],
        "ntp_source":       atomic["source"],
        "ntp_trusted":      atomic["trusted"],
        "drift_seconds":    atomic["drift_seconds"],
        "drift_level":      drift_level,
        "label":            label,
        "snap_id":          snap_id,
        "extra":            extra,
        "note":             atomic["note"],
    }

    _append_node(node)
    return node


# ── 验证铁索完整性 ────────────────────────────────────────────

def verify_chain() -> dict:
    """
    遍历整条铁索，逐节点验证哈希一致性。
    返回 { "ok": bool, "total": int, "broken_at": int|None, "errors": list }
    """
    chain = load_chain()
    if not chain:
        return {"ok": True, "total": 0, "broken_at": None, "errors": [], "note": "铁索为空"}

    errors = []
    prev_hash = "GENESIS"

    for i, node in enumerate(chain):
        expected_hash = _node_hash(
            prev_hash,
            node["ts_unix"],
            node.get("label", ""),
            node.get("extra", ""),
        )
        if node["hash"] != expected_hash:
            errors.append({
                "seq":      node.get("seq", i),
                "index":    i,
                "expected": expected_hash[:16] + "...",
                "actual":   node["hash"][:16] + "...",
                "ts":       node.get("ts_utc", "?"),
                "label":    node.get("label", ""),
            })
            # 不在这里 break，继续往后走，暴露所有断点
        prev_hash = node["hash"]

    return {
        "ok":        len(errors) == 0,
        "total":     len(chain),
        "broken_at": errors[0]["index"] if errors else None,
        "errors":    errors,
    }


# ── 时间间隙检测 ──────────────────────────────────────────────

def detect_gaps() -> list:
    """
    检测铁索上所有可疑的时间间隙（攻击可能发生在间隙里）。
    返回异常间隙列表，每个元素：
    {
        "from_seq": int, "to_seq": int,
        "from_ts": str, "to_ts": str,
        "gap_seconds": float,
        "level": "WARNING" | "ALERT" | "CRITICAL",
        "note": str,
    }
    """
    chain = load_chain()
    if len(chain) < 2:
        return []

    anomalies = []
    for i in range(1, len(chain)):
        prev = chain[i - 1]
        curr = chain[i]
        gap = curr["ts_unix"] - prev["ts_unix"]

        if gap >= GAP_CRITICAL_SECONDS:
            level = "CRITICAL"
            note = f"间隙 {gap/3600:.1f} 小时 — 极度可疑，这段时间内可能有攻击"
        elif gap >= GAP_ALERT_SECONDS:
            level = "ALERT"
            note = f"间隙 {gap/3600:.1f} 小时 — 高度可疑"
        elif gap >= GAP_WARN_SECONDS:
            level = "WARNING"
            note = f"间隙 {gap/3600:.1f} 小时 — 注意"
        else:
            continue  # 正常间隙，跳过

        anomalies.append({
            "from_seq":    prev.get("seq", i - 1),
            "to_seq":      curr.get("seq", i),
            "from_ts":     prev.get("ts_utc", "?"),
            "to_ts":       curr.get("ts_utc", "?"),
            "from_label":  prev.get("label", ""),
            "to_label":    curr.get("label", ""),
            "gap_seconds": round(gap, 1),
            "level":       level,
            "note":        note,
        })

    return anomalies


# ── 完整报告 ──────────────────────────────────────────────────

def report():
    """
    打印完整的时间铁索报告：
    - 铁索完整性验证
    - NTP 校准偏差统计
    - 可疑时间间隙
    - 最近 10 个节点
    """
    chain = load_chain()
    print(f"\n{'='*72}")
    print(f"  ⛓️  澜的时间铁索连环报告  LAN-044")
    print(f"  生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*72}")

    # 基本信息
    print(f"\n  📊 铁索概况")
    print(f"     节点总数: {len(chain)}")
    if chain:
        print(f"     起始时间: {chain[0].get('ts_utc', '?')}  (seq={chain[0].get('seq',0)})")
        print(f"     最新时间: {chain[-1].get('ts_utc', '?')}  (seq={chain[-1].get('seq',0)})")
        # 跨度
        span_sec = chain[-1]["ts_unix"] - chain[0]["ts_unix"]
        span_str = f"{span_sec/3600:.1f} 小时" if span_sec < 86400 else f"{span_sec/86400:.1f} 天"
        print(f"     时间跨度: {span_str}")

    # 铁索完整性验证
    print(f"\n  🔗 铁索完整性验证")
    v = verify_chain()
    if v["ok"]:
        print(f"     ✅ 全链路哈希一致（{v['total']} 个节点）")
    else:
        print(f"     ❌ 铁索断裂！发现 {len(v['errors'])} 处哈希不一致：")
        for e in v["errors"][:5]:
            print(f"        seq={e['seq']}  {e['ts']}  [{e['label']}]")
            print(f"        期望: {e['expected']}  实际: {e['actual']}")

    # NTP 偏差统计
    print(f"\n  🕐 原子钟校准偏差")
    if chain:
        trusted = [n for n in chain if n.get("ntp_trusted")]
        untrusted = [n for n in chain if not n.get("ntp_trusted")]
        alert_nodes = [n for n in trusted if abs(n.get("drift_seconds", 0)) > NTP_DRIFT_ALERT_SECONDS]
        warn_nodes  = [n for n in trusted if NTP_DRIFT_WARN_SECONDS < abs(n.get("drift_seconds", 0)) <= NTP_DRIFT_ALERT_SECONDS]

        print(f"     可信节点(NTP成功): {len(trusted)} / {len(chain)}")
        print(f"     不可信节点(NTP失败): {len(untrusted)}")
        if alert_nodes:
            print(f"     ⚠️  ALERT 偏差节点: {len(alert_nodes)} 个（偏差 > {NTP_DRIFT_ALERT_SECONDS}s）")
            for n in alert_nodes[:3]:
                print(f"        seq={n['seq']}  偏差={n['drift_seconds']:.1f}s  {n['ts_utc']}")
        elif warn_nodes:
            print(f"     ⚠️  WARN 偏差节点: {len(warn_nodes)} 个（偏差 > {NTP_DRIFT_WARN_SECONDS}s）")
        else:
            print(f"     ✅ 所有可信节点时钟偏差正常")
    else:
        print(f"     (无节点)")

    # 可疑时间间隙
    print(f"\n  ⏱️  可疑时间间隙（潜在攻击窗口）")
    gaps = detect_gaps()
    if not gaps:
        print(f"     ✅ 无可疑间隙")
    else:
        for g in gaps:
            icon = "🔴" if g["level"] == "CRITICAL" else ("🟠" if g["level"] == "ALERT" else "🟡")
            print(f"     {icon} [{g['level']}] seq {g['from_seq']} → {g['to_seq']}")
            print(f"        从: {g['from_ts']}  [{g['from_label']}]")
            print(f"        到: {g['to_ts']}  [{g['to_label']}]")
            print(f"        {g['note']}")

    # 最近节点
    print(f"\n  📌 最近 10 个节点")
    recent = chain[-10:] if len(chain) >= 10 else chain
    for n in recent:
        trusted_icon = "✅" if n.get("ntp_trusted") else "⚠️"
        drift_str = f"  偏差{n.get('drift_seconds', 0):+.1f}s" if n.get("ntp_trusted") else "  [本机时钟]"
        label_str = f"  [{n['label']}]" if n.get("label") else ""
        snap_str  = f"  snap={n['snap_id'][:16]}..." if n.get("snap_id") else ""
        print(f"     {trusted_icon} seq={n.get('seq',0):04d}  {n.get('ts_utc','?')}{drift_str}{label_str}{snap_str}")
        print(f"           hash={n['hash'][:24]}...")

    print(f"\n{'='*72}")
    total_anomalies = len([n for n in chain if not n.get("ntp_trusted")]) + len(gaps) + (len(v["errors"]) if not v["ok"] else 0)
    if total_anomalies == 0:
        print(f"  ✅ 时间铁索健康 — 无异常")
    else:
        print(f"  ⚠️  发现异常：铁索断裂={len(v['errors'])} / 间隙={len(gaps)} / NTP失败={len([n for n in chain if not n.get('ntp_trusted')])}")
    print(f"{'='*72}\n")


# ── 主入口 ────────────────────────────────────────────────────

def main():
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "report"
    arg2 = sys.argv[2] if len(sys.argv) > 2 else ""

    if cmd == "stamp":
        print(f"\n[LAN-044] 打时间节点...")
        node = stamp(label=arg2)
        trusted_icon = "✅" if node["ntp_trusted"] else "⚠️"
        print(f"  {trusted_icon} seq={node['seq']:04d}  {node['ts_utc']}")
        print(f"  来源: {node['ntp_source']}")
        print(f"  偏差: {node['drift_seconds']:+.3f}s  [{node['drift_level']}]")
        print(f"  哈希: {node['hash'][:32]}...")
        print(f"  前驱: {node['prev_hash'][:32]}...")
        if node["drift_level"] in ("WARN", "ALERT"):
            print(f"\n  ⚠️  本机时钟偏差异常！偏差={node['drift_seconds']:.1f}s — 可能有人调过系统时钟")

    elif cmd == "verify":
        print(f"\n[LAN-044] 验证铁索完整性...")
        v = verify_chain()
        if v["ok"]:
            print(f"  ✅ 铁索完整（{v['total']} 个节点）")
        else:
            print(f"  ❌ 铁索断裂！{len(v['errors'])} 处哈希不一致（第一处: seq={v['broken_at']}）")
            for e in v["errors"]:
                print(f"     seq={e['seq']}  {e['ts']}  期望: {e['expected']}  实际: {e['actual']}")

    elif cmd == "gaps":
        print(f"\n[LAN-044] 检测时间间隙（潜在攻击窗口）...")
        gaps = detect_gaps()
        if not gaps:
            print(f"  ✅ 无可疑间隙")
        else:
            print(f"  发现 {len(gaps)} 处可疑间隙：")
            for g in gaps:
                icon = "🔴" if g["level"] == "CRITICAL" else ("🟠" if g["level"] == "ALERT" else "🟡")
                print(f"  {icon} [{g['level']}]  seq {g['from_seq']}→{g['to_seq']}  {g['note']}")
                print(f"     从 {g['from_ts']} 到 {g['to_ts']}")

    elif cmd == "ntp":
        print(f"\n[LAN-044] 查询原子钟...")
        atomic = get_atomic_time()
        print(f"  来源: {atomic['source']}")
        print(f"  NTP时间: {atomic['iso']}")
        print(f"  本机时间: {datetime.datetime.fromtimestamp(atomic['local_unix'], tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z")
        print(f"  偏差: {atomic['drift_seconds']:+.3f}s")
        print(f"  可信: {'✅ 是' if atomic['trusted'] else '❌ 否（NTP失败，使用本机时钟）'}")
        if abs(atomic["drift_seconds"]) > NTP_DRIFT_ALERT_SECONDS:
            print(f"  ⚠️  偏差过大！可能有人调整了系统时钟！")

    elif cmd == "last":
        node = get_last_node()
        if not node:
            print("  (铁索为空，尚未打过时间节点)")
        else:
            print(f"\n[LAN-044] 最新时间节点:")
            print(f"  seq:   {node.get('seq', 0)}")
            print(f"  时间:  {node.get('ts_utc', '?')}")
            print(f"  来源:  {node.get('ntp_source', '?')}")
            print(f"  偏差:  {node.get('drift_seconds', 0):+.3f}s  [{node.get('drift_level', '?')}]")
            print(f"  标签:  {node.get('label', '(无)')}")
            print(f"  哈希:  {node.get('hash', '')[:48]}...")

    elif cmd == "report":
        report()

    else:
        print("用法: python lan_time_chain.py [stamp|verify|gaps|ntp|last|report] [标签]")


if __name__ == "__main__":
    main()
