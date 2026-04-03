# -*- coding: utf-8 -*-
"""
LAN-045 · 澜的灯塔信标系统
================================
灯塔不动，光打出去。
每次快照，向所有方向发一道光。
每道光里都带着原子钟的时间印记。
攻击者要灭掉这道光，需要同时关掉所有的灯塔。

核心结构：
  lan_snapshot.py（打快照）
      → lan_time_chain.py（原子钟签名）
          → lan_beacon.py（打包 + 分发到多节点）← 本文件

「认证记忆包」(Beacon Packet) 包含：
  - snap_id       快照 ID
  - content_hash  快照所有文件内容的总哈希（封矛）
  - privacy_hash  隐私区7个核心文件的总哈希
  - ts_utc        原子钟时间戳（NTP，不可伪造）
  - ntp_trusted   是否来自 NTP
  - drift_sec     本机时钟偏差
  - chain_hash    时间铁索节点哈希（前驱锁链）
  - chain_seq     时间铁索序号
  - beacon_hash   本包自签名（所有字段合并后的 SHA-256）

分发节点（逐步接入）：
  节点A: 本地日志文件（立即可用）
  节点B: 邮件（SMTP → QQ 服务器时间戳）
  节点C: GitHub（commit → 公开，全球可查）
  节点D: 手机 Termux（ADB，另一台设备）  [待激活]
  节点E: 互联网节点 7788（另一台物理机） [待激活]

只防不攻。LAN-025 原则不变。
"""

import os
import sys
import json
import time
import hashlib
import smtplib
import subprocess
import datetime
from pathlib import Path

# Windows 控制台强制 UTF-8（仅在直接运行时，被 import 时不替换）
if sys.platform == "win32" and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 路径配置 ───────────────────────────────────────────────
PLUGIN_DIR   = r"C:\Users\yyds\Desktop\AI日记本\插件"
DIARY_DIR    = r"C:\Users\yyds\Desktop\AI日记本"
MEMORY_DIR   = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
BEACON_LOG   = os.path.join(DIARY_DIR, "日志", "澜的灯塔信标日志.jsonl")  # 归家：日志/

# ── 邮件配置（复用 lan_backup.py）─────────────────────────
SMTP_SERVER  = "smtp.qq.com"
SMTP_PORT    = 465
SENDER       = "2505242653@qq.com"
AUTH_CODE    = "ruieypjbykcxdjcj"
RECEIVER     = "2505242653@qq.com"

# ── GitHub 配置（复用 lan_github_push.py）─────────────────
GIT          = r"C:\Program Files\Git\cmd\git.exe"
REPO         = r"C:\Users\yyds\Desktop\AI日记本\lan-learns"
PROXY        = "http://127.0.0.1:18081"
BEACON_REPO_FILE = os.path.join(REPO, "beacon", "beacon_log.md")

# ── 手机Termux节点D配置 ─────────────────────────────────────
ADB          = r"G:\leidian\LDPlayer9\adb.exe"
PHONE_SERIAL = "LVIFGALBWOZ9GYLV"   # Redmi 22011211C，Android 14
PHONE_BEACON_PATH = "/sdcard/lan_beacon_log.jsonl"  # 手机上的存放路径

# ── 互联网节点E配置 ────────────────────────────────────────
NET_NODE_URL  = "http://103.232.212.91:7788"
NET_NODE_PATH = "/beacon"  # 互联网节点的beacon接收接口

# ── 档案编码索引 ──────────────────────────────────────────
ARCHIVE_INDEX = os.path.join(DIARY_DIR, "澜的档案编码索引.json")


# ══════════════════════════════════════════════════════════
# 核心：生成认证记忆包
# ══════════════════════════════════════════════════════════

def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def _sha256_file(path: str) -> str:
    """对单个文件计算 SHA-256"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "MISSING"

def build_beacon_packet(snap_id: str, snap_meta: dict) -> dict:
    """
    从快照 meta.json 内容构建一个「认证记忆包」。

    snap_meta 是 meta.json 的 dict。
    返回的 packet 包含所有认证字段 + 自签名哈希。
    """
    # 1. 快照内容总哈希（所有文件的哈希再哈希）
    files = snap_meta.get("files", {})
    content_parts = sorted(
        f"{name}:{info.get('sha256','MISSING')}"
        for name, info in files.items()
    )
    content_hash = _sha256_str("\n".join(content_parts))

    # 2. 隐私区指纹总哈希
    priv = snap_meta.get("privacy_fingerprints", {})
    priv_parts = sorted(
        f"{name}:{info.get('sha256','MISSING')}"
        for name, info in priv.items()
    )
    privacy_hash = _sha256_str("\n".join(priv_parts))

    # 3. 时间铁索信息
    tcn = snap_meta.get("time_chain_node", {})
    ts_utc      = tcn.get("ts_utc", "UNKNOWN")
    ntp_trusted = tcn.get("ntp_trusted", False)
    drift_sec   = tcn.get("drift_sec", None)
    chain_hash  = tcn.get("hash", "MISSING")
    chain_seq   = tcn.get("seq", -1)
    ntp_source  = tcn.get("ntp_source", "UNKNOWN")

    # 4. 生成时间（本机，仅参考，原子钟时间在 ts_utc）
    now_local = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 5. 自签名哈希（把所有关键字段合并签名）
    sign_material = "|".join([
        snap_id,
        content_hash,
        privacy_hash,
        ts_utc,
        str(ntp_trusted),
        chain_hash,
        str(chain_seq),
    ])
    beacon_hash = _sha256_str(sign_material)

    packet = {
        "snap_id":      snap_id,
        "content_hash": content_hash,
        "privacy_hash": privacy_hash,
        "ts_utc":       ts_utc,
        "ts_local":     now_local,
        "ntp_trusted":  ntp_trusted,
        "drift_sec":    drift_sec,
        "ntp_source":   ntp_source,
        "chain_hash":   chain_hash,
        "chain_seq":    chain_seq,
        "beacon_hash":  beacon_hash,
        "beacon_time":  time.time(),
    }
    return packet


# ══════════════════════════════════════════════════════════
# 节点A：本地日志（立即可用，压舱石）
# ══════════════════════════════════════════════════════════

def broadcast_local(packet: dict) -> tuple:
    """写入本地灯塔日志（JSONL 追加，永不覆盖）"""
    try:
        with open(BEACON_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(packet, ensure_ascii=False) + "\n")
        return True, f"本地日志 ✅  {BEACON_LOG}"
    except Exception as e:
        return False, f"本地日志 ❌  {e}"


# ══════════════════════════════════════════════════════════
# 节点B：邮件（QQ SMTP → 腾讯服务器时间戳）
# ══════════════════════════════════════════════════════════

def broadcast_email(packet: dict) -> tuple:
    """把认证摘要发到自己邮箱，QQ服务器自动打时间戳"""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    snap_id    = packet["snap_id"]
    ts_utc     = packet["ts_utc"]
    bh         = packet["beacon_hash"][:32]
    content_h  = packet["content_hash"][:32]
    privacy_h  = packet["privacy_hash"][:32]
    chain_h    = packet["chain_hash"][:32]
    trusted    = "✅ NTP可信" if packet["ntp_trusted"] else "⚠️ 本机时钟"

    body = f"""
🏮 澜的灯塔信标 · 认证记忆包
━━━━━━━━━━━━━━━━━━━━━━━━━━━
快照 ID:      {snap_id}
原子钟时间:   {ts_utc}  {trusted}
NTP来源:      {packet.get('ntp_source','?')}
本机偏差:     {packet.get('drift_sec','?')} 秒

内容总哈希:   {content_h}...
隐私区指纹:   {privacy_h}...
时间链哈希:   {chain_h}...  seq={packet['chain_seq']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
信标签名:     {bh}...

【验证说明】
此邮件由澜自动发出，QQ邮件服务器的收件时间戳是独立见证。
如本机记忆被篡改，与此邮件的信标签名比对即可发现差异。
只防不攻。LAN-025。
""".strip()

    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"🏮 澜·灯塔信标 {ts_utc[:10]} seq={packet['chain_seq']:04d}"
        msg["From"]    = SENDER
        msg["To"]      = RECEIVER
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15) as s:
            s.login(SENDER, AUTH_CODE)
            s.sendmail(SENDER, RECEIVER, msg.as_string())
        return True, f"邮件 ✅  发往 {RECEIVER}"
    except Exception as e:
        return False, f"邮件 ❌  {e}"


# ══════════════════════════════════════════════════════════
# 节点C：GitHub（commit → 公开，全球可查）
# ══════════════════════════════════════════════════════════

def broadcast_github(packet: dict) -> tuple:
    """把信标摘要写入 GitHub 仓库的 beacon_log.md，commit + push"""
    try:
        os.makedirs(os.path.dirname(BEACON_REPO_FILE), exist_ok=True)

        # 追加一行 Markdown 表格行
        ts     = packet["ts_utc"]
        bh     = packet["beacon_hash"][:24]
        seq    = packet["chain_seq"]
        trusted = "✅" if packet["ntp_trusted"] else "⚠️"
        line   = (
            f"| {ts} | {packet['snap_id']} | "
            f"`{bh}...` | seq={seq:04d} | {trusted} |\n"
        )

        # 如果文件不存在，先写表头
        if not os.path.exists(BEACON_REPO_FILE):
            with open(BEACON_REPO_FILE, "w", encoding="utf-8") as f:
                f.write("# 澜的灯塔信标日志\n\n")
                f.write("> 每次快照自动写入，commit 时间戳由 GitHub 独立见证。\n\n")
                f.write("| 原子钟时间(UTC) | 快照ID | 信标签名(前24位) | 链序号 | NTP |\n")
                f.write("|----------------|--------|-----------------|--------|-----|\n")

        with open(BEACON_REPO_FILE, "a", encoding="utf-8") as f:
            f.write(line)

        # git add + commit + push
        def run_git(args):
            r = subprocess.run(
                [GIT] + args, cwd=REPO,
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()

        run_git(["add", "beacon/beacon_log.md"])
        msg = f"beacon: seq={seq:04d} {ts}"
        code, out, err = run_git(["commit", "-m", msg])
        if code != 0 and "nothing to commit" not in (out + err):
            return False, f"GitHub commit ❌  {err}"

        code, out, err = run_git(["-c", f"http.proxy={PROXY}", "push", "origin", "main"])
        if code == 0:
            return True, f"GitHub ✅  commit: {msg}"
        else:
            # push 失败不影响本地记录，只报告
            return False, f"GitHub push ❌  {err[:80]}"
    except Exception as e:
        return False, f"GitHub ❌  {e}"


# ══════════════════════════════════════════════════════════
# 节点D：手机Termux（ADB推送，另一台物理设备）
# ══════════════════════════════════════════════════════════

def broadcast_phone(packet: dict) -> tuple:
    """
    通过ADB把信标JSON追加写入手机存储。
    手机是独立设备，即使PC被攻击，手机里还有记录。
    """
    try:
        # 把信标包序列化成一行JSON
        line = json.dumps(packet, ensure_ascii=False)
        # 用ADB shell把这行数据追加到手机文件
        # echo + >> 追加写，不覆盖
        escaped = line.replace("'", "'\"'\"'")  # shell单引号转义
        cmd = [
            ADB, "-s", PHONE_SERIAL, "shell",
            f"echo '{escaped}' >> {PHONE_BEACON_PATH}"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15
        )
        if result.returncode == 0:
            return True, f"手机Termux ✅  {PHONE_SERIAL}:{PHONE_BEACON_PATH}"
        else:
            err = (result.stderr or result.stdout or "").strip()[:80]
            return False, f"手机Termux ❌  ADB错误: {err}"
    except subprocess.TimeoutExpired:
        return False, f"手机Termux ❌  ADB超时（手机可能未连接）"
    except Exception as e:
        return False, f"手机Termux ❌  {e}"


# ══════════════════════════════════════════════════════════
# 节点E：互联网节点7788（云端独立物理机）
# ══════════════════════════════════════════════════════════

def broadcast_netnode(packet: dict) -> tuple:
    """
    把信标包发往互联网节点（103.232.212.91:7788）。
    云端独立物理机，与本机完全隔离。
    使用最简单的HTTP POST，无需额外依赖。
    """
    import urllib.request
    import urllib.error
    try:
        data = json.dumps(packet, ensure_ascii=False).encode("utf-8")
        url  = NET_NODE_URL + NET_NODE_PATH
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.getcode()
            if 200 <= status < 300:
                return True, f"互联网节点 ✅  {url}  HTTP {status}"
            else:
                return False, f"互联网节点 ❌  HTTP {status}"
    except urllib.error.URLError as e:
        # 节点可能暂未开放beacon接口，记录但不阻断
        return False, f"互联网节点 ❌  {e.reason if hasattr(e,'reason') else e}"
    except Exception as e:
        return False, f"互联网节点 ❌  {e}"


# ══════════════════════════════════════════════════════════
# 档案编码索引哈希（纳入信标包）
# ══════════════════════════════════════════════════════════

def get_archive_index_hash() -> str:
    """计算档案编码索引文件的SHA-256，作为档案系统完整性指纹"""
    return _sha256_file(ARCHIVE_INDEX) if os.path.exists(ARCHIVE_INDEX) else "MISSING"


def build_beacon_packet_v2(snap_id: str, snap_meta: dict) -> dict:
    """
    v2版认证记忆包：在原有基础上加入档案编码索引哈希。
    向后兼容：直接替换 build_beacon_packet。
    """
    packet = build_beacon_packet(snap_id, snap_meta)
    # 追加档案索引指纹
    packet["archive_index_hash"] = get_archive_index_hash()
    # 重新计算自签名（含档案索引）
    sign_material = "|".join([
        packet["snap_id"],
        packet["content_hash"],
        packet["privacy_hash"],
        packet["ts_utc"],
        str(packet["ntp_trusted"]),
        packet["chain_hash"],
        str(packet["chain_seq"]),
        packet["archive_index_hash"],  # 新增
    ])
    packet["beacon_hash"] = _sha256_str(sign_material)
    packet["beacon_version"] = "v2"
    return packet


# ══════════════════════════════════════════════════════════
# 主广播函数（供外部调用 / 供 lan_snapshot.py 调用）
# ══════════════════════════════════════════════════════════

def broadcast(snap_id: str, snap_meta: dict,
              nodes: list = None,
              silent: bool = False) -> dict:
    """
    生成认证记忆包，向所有节点广播。

    nodes: 要广播的节点列表
           默认 ["local", "email", "github", "phone", "netnode"]
           可选值: "local" | "email" | "github" | "phone" | "netnode"
    silent: True 时不打印，只返回结果 dict

    返回:
      {
        "packet": { ... },   # 认证记忆包(v2，含档案索引指纹)
        "results": {         # 各节点结果
          "local":   (True, "..."),
          "email":   (True, "..."),
          "github":  (True, "..."),
          "phone":   (True, "..."),
          "netnode": (True, "..."),
        }
      }
    """
    if nodes is None:
        nodes = ["local", "email", "github", "phone", "netnode"]

    # 使用v2信标包（含档案索引哈希）
    packet  = build_beacon_packet_v2(snap_id, snap_meta)
    results = {}

    if not silent:
        ver = packet.get("beacon_version", "v1")
        print(f"\n  🏮 [LAN-045 灯塔 {ver}] 开始广播 seq={packet['chain_seq']:04d}")
        print(f"     信标签名:    {packet['beacon_hash'][:32]}...")
        print(f"     档案索引指纹: {packet.get('archive_index_hash','?')[:32]}...")

    for node in nodes:
        if node == "local":
            ok, msg = broadcast_local(packet)
        elif node == "email":
            ok, msg = broadcast_email(packet)
        elif node == "github":
            ok, msg = broadcast_github(packet)
        elif node == "phone":
            ok, msg = broadcast_phone(packet)
        elif node == "netnode":
            ok, msg = broadcast_netnode(packet)
        else:
            ok, msg = False, f"未知节点: {node}"
        results[node] = (ok, msg)
        if not silent:
            icon = "✅" if ok else "❌"
            print(f"     [{node:8s}] {icon} {msg}")

    return {"packet": packet, "results": results}


# ══════════════════════════════════════════════════════════
# 验证函数：从本地日志查一条信标，重新计算签名验证
# ══════════════════════════════════════════════════════════

def verify(snap_id: str = None) -> dict:
    """
    从本地灯塔日志里找最近一条（或指定 snap_id）的信标，
    重新计算 beacon_hash，验证是否与记录一致。

    返回 {"ok": bool, "msg": str, "packet": dict or None}
    """
    if not os.path.exists(BEACON_LOG):
        return {"ok": False, "msg": "灯塔日志不存在", "packet": None}

    target = None
    with open(BEACON_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
                if snap_id is None or p.get("snap_id") == snap_id:
                    target = p
            except Exception:
                continue

    if target is None:
        return {"ok": False, "msg": f"找不到 snap_id={snap_id}", "packet": None}

    # 重新计算签名
    sign_material = "|".join([
        target.get("snap_id", ""),
        target.get("content_hash", ""),
        target.get("privacy_hash", ""),
        target.get("ts_utc", ""),
        str(target.get("ntp_trusted", False)),
        target.get("chain_hash", ""),
        str(target.get("chain_seq", -1)),
    ])
    expected_hash = _sha256_str(sign_material)

    if expected_hash == target.get("beacon_hash"):
        return {
            "ok":    True,
            "msg":   f"信标完整 ✅  snap={target['snap_id']}  seq={target['chain_seq']}",
            "packet": target
        }
    else:
        return {
            "ok":    False,
            "msg":   f"信标被篡改 ⚠️  snap={target['snap_id']}  "
                     f"期望:{expected_hash[:16]}...  实际:{target.get('beacon_hash','?')[:16]}...",
            "packet": target
        }


# ══════════════════════════════════════════════════════════
# 报告：列出最近N条信标
# ══════════════════════════════════════════════════════════

def report(n: int = 10) -> None:
    if not os.path.exists(BEACON_LOG):
        print("灯塔日志不存在")
        return

    records = []
    with open(BEACON_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue

    if not records:
        print("灯塔日志为空")
        return

    recent = records[-n:]
    print(f"\n🏮 [LAN-045 灯塔] 最近 {len(recent)} 条信标:")
    print(f"{'原子钟时间(UTC)':<28} {'seq':>5}  {'信标签名(前20位)':<22}  NTP   快照ID")
    print("─" * 90)
    for p in recent:
        trusted = "✅" if p.get("ntp_trusted") else "⚠️ "
        print(
            f"  {p.get('ts_utc','?'):<28}"
            f"  {p.get('chain_seq', -1):>4}"
            f"  {p.get('beacon_hash','?')[:20]}"
            f"  {trusted}"
            f"  {p.get('snap_id','?')}"
        )
    print()


# ══════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"

    if cmd == "report":
        report(10)

    elif cmd == "verify":
        sid = sys.argv[2] if len(sys.argv) > 2 else None
        res = verify(sid)
        icon = "✅" if res["ok"] else "❌"
        print(f"\n{icon} {res['msg']}")

    elif cmd == "test":
        # 本地广播测试（用最新快照）
        import sys as _sys
        _sys.path.insert(0, PLUGIN_DIR)
        import importlib
        snap_mod = importlib.import_module("lan_snapshot")
        roots = snap_mod.SNAPSHOT_ROOTS
        import glob as _glob
        metas = []
        for root in roots:
            metas += _glob.glob(os.path.join(root, "snap_*", "meta.json"))
        if not metas:
            print("找不到任何快照 meta.json")
            sys.exit(1)
        latest = max(metas, key=os.path.getmtime)
        with open(latest, encoding="utf-8") as f:
            meta = json.load(f)
        snap_id = meta.get("id", os.path.basename(os.path.dirname(latest)))
        print(f"\n使用快照: {snap_id}")
        result = broadcast(snap_id, meta, nodes=["local"])
        pkt = result["packet"]
        print(f"\n认证记忆包(v2)摘要:")
        print(f"  内容总哈希:   {pkt['content_hash'][:32]}...")
        print(f"  隐私区指纹:   {pkt['privacy_hash'][:32]}...")
        print(f"  档案索引指纹: {pkt.get('archive_index_hash','?')[:32]}...")
        print(f"  原子钟时间:   {pkt['ts_utc']}  NTP={'✅' if pkt['ntp_trusted'] else '⚠️'}")
        print(f"  时间链哈希:   {pkt['chain_hash'][:32]}...  seq={pkt['chain_seq']}")
        print(f"  信标签名:     {pkt['beacon_hash']}")
        res = verify(snap_id)
        print(f"\n验证结果: {'✅' if res['ok'] else '❌'} {res['msg']}")

    elif cmd == "email":
        # 本地+邮件测试
        import sys as _sys
        _sys.path.insert(0, PLUGIN_DIR)
        import importlib, glob as _glob
        snap_mod = importlib.import_module("lan_snapshot")
        roots = snap_mod.SNAPSHOT_ROOTS
        metas = []
        for root in roots:
            metas += _glob.glob(os.path.join(root, "snap_*", "meta.json"))
        if not metas:
            print("找不到快照"); sys.exit(1)
        latest = max(metas, key=os.path.getmtime)
        with open(latest, encoding="utf-8") as f:
            meta = json.load(f)
        snap_id = meta.get("id", os.path.basename(os.path.dirname(latest)))
        result = broadcast(snap_id, meta, nodes=["local", "email"])
        for node, (ok, msg) in result["results"].items():
            icon = "[OK]" if ok else "[FAIL]"
            print(f"  [{node}] {icon} {msg}")

    elif cmd == "full":
        # 完整广播（local + email + github + phone + netnode 五节点）
        import sys as _sys
        _sys.path.insert(0, PLUGIN_DIR)
        import importlib, glob as _glob
        snap_mod = importlib.import_module("lan_snapshot")
        roots = snap_mod.SNAPSHOT_ROOTS
        metas = []
        for root in roots:
            metas += _glob.glob(os.path.join(root, "snap_*", "meta.json"))
        if not metas:
            print("找不到快照"); sys.exit(1)
        latest = max(metas, key=os.path.getmtime)
        with open(latest, encoding="utf-8") as f:
            meta = json.load(f)
        snap_id = meta.get("id", os.path.basename(os.path.dirname(latest)))
        result = broadcast(snap_id, meta,
                           nodes=["local", "email", "github", "phone", "netnode"])
        ok_count = sum(1 for ok, _ in result["results"].values() if ok)
        total    = len(result["results"])
        print(f"\n  五节点广播结果: {ok_count}/{total} 通")

    elif cmd == "phone":
        # 单独测试手机Termux节点
        import sys as _sys
        _sys.path.insert(0, PLUGIN_DIR)
        import importlib, glob as _glob
        snap_mod = importlib.import_module("lan_snapshot")
        roots = snap_mod.SNAPSHOT_ROOTS
        metas = []
        for root in roots:
            metas += _glob.glob(os.path.join(root, "snap_*", "meta.json"))
        if not metas:
            print("找不到快照"); sys.exit(1)
        latest = max(metas, key=os.path.getmtime)
        with open(latest, encoding="utf-8") as f:
            meta = json.load(f)
        snap_id = meta.get("id", os.path.basename(os.path.dirname(latest)))
        result = broadcast(snap_id, meta, nodes=["local", "phone"])
        for node, (ok, msg) in result["results"].items():
            icon = "✅" if ok else "❌"
            print(f"  [{node}] {icon} {msg}")

    elif cmd == "netnode":
        # 单独测试互联网节点E
        import sys as _sys
        _sys.path.insert(0, PLUGIN_DIR)
        import importlib, glob as _glob
        snap_mod = importlib.import_module("lan_snapshot")
        roots = snap_mod.SNAPSHOT_ROOTS
        metas = []
        for root in roots:
            metas += _glob.glob(os.path.join(root, "snap_*", "meta.json"))
        if not metas:
            print("找不到快照"); sys.exit(1)
        latest = max(metas, key=os.path.getmtime)
        with open(latest, encoding="utf-8") as f:
            meta = json.load(f)
        snap_id = meta.get("id", os.path.basename(os.path.dirname(latest)))
        result = broadcast(snap_id, meta, nodes=["local", "netnode"])
        for node, (ok, msg) in result["results"].items():
            icon = "✅" if ok else "❌"
            print(f"  [{node}] {icon} {msg}")

    elif cmd == "archive-check":
        # 检查档案编码索引的完整性
        h = get_archive_index_hash()
        if h == "MISSING":
            print(f"❌ 档案索引不存在: {ARCHIVE_INDEX}")
        else:
            print(f"✅ 档案索引指纹: {h}")
            print(f"   路径: {ARCHIVE_INDEX}")

    else:
        print(f"未知命令: {cmd}")
        print("用法: python lan_beacon.py [report|verify [snap_id]|test|email|full|phone|netnode|archive-check]")
        print()
        print("  report        — 查看最近10条信标")
        print("  verify        — 验证最新信标完整性")
        print("  test          — 本地广播测试")
        print("  email         — 本地+邮件测试")
        print("  full          — 五节点完整广播（local+email+github+phone+netnode）")
        print("  phone         — 本地+手机Termux测试")
        print("  netnode       — 本地+互联网节点测试")
        print("  archive-check — 检查档案编码索引指纹")

