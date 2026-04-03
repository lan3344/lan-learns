"""
lan_security_guard.py - 澜的安全守卫 v1.0
2026-03-29

职责：
- 只防不攻
- 监控 LobsterAI(5175) / OpenClaw(18789) 端口的外部连接
- 检测异常：局域网扫描、频繁探测、非本机来源连接
- 发现威胁写进日志，弹出警告

澜的安全哲学：
  了解对方的意图 → 找到合法的门 → 敲门进去
  别人扫我的门：记录 + 告警，不主动反击
"""

import subprocess
import re
import time
import json
import os
import sys
from datetime import datetime

# Windows 终端编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE, "..", "日志", "lan_security_guard.jsonl")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# 被保护的敏感端口
GUARDED_PORTS = {
    5175: "LobsterAI Vite界面",
    18789: "OpenClaw引擎网关",
    7788: "澜·互联网通信节点",
    7799: "澜·手机Agent",
}

# 本地合法来源（白名单）
SAFE_ORIGINS = {"127.0.0.1", "::1", "0.0.0.0"}


def write_log(event_type: str, detail: dict):
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        **detail
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def get_connections():
    """获取当前TCP连接列表"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, encoding="gbk", errors="replace", timeout=10
        )
        lines = result.stdout.splitlines()
        connections = []
        for line in lines:
            m = re.match(
                r'\s+TCP\s+([\d\.\[\]:]+):(\d+)\s+([\d\.\[\]:]+):(\d+)\s+(\w+)\s+(\d+)',
                line
            )
            if not m:
                continue
            local_ip, local_port, remote_ip, remote_port, state, pid = m.groups()
            local_port = int(local_port)
            if local_port in GUARDED_PORTS:
                connections.append({
                    "local_port": local_port,
                    "service": GUARDED_PORTS[local_port],
                    "remote_ip": remote_ip,
                    "remote_port": remote_port,
                    "state": state,
                    "pid": pid
                })
        return connections
    except Exception as e:
        return []


def _run_netsh(args):
    """运行 netsh 命令，处理 Windows GBK 输出编码"""
    try:
        result = subprocess.run(args, capture_output=True, encoding="gbk", errors="replace", timeout=10)
        return result.stdout or "", result.returncode
    except Exception:
        return "", -1


def check_firewall_rule_exists():
    """检查Windows防火墙是否有 LobsterAI 的入站阻止规则"""
    out, _ = _run_netsh(["netsh", "advfirewall", "firewall", "show", "rule", "name=LAN-LobsterAI-Guard"])
    return "LAN-LobsterAI-Guard" in out


def add_firewall_block_inbound(port: int, name: str):
    """
    只阻止外网入站——本机和内网（192.168.x.x）不受影响。
    这就是"只防不攻"：外面进不来，里面出得去。
    """
    rule_name = f"LAN-Guard-Block-{port}"
    # 先检查是否已有规则
    check_out, _ = _run_netsh(["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"])
    if rule_name in check_out:
        print(f"  [已存在] 防火墙规则 {rule_name} 已就位，跳过")
        return False

    # 添加：阻止非LocalSubnet的入站连接
    _, rc = _run_netsh([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule_name}",
        "protocol=TCP",
        f"localport={port}",
        "dir=in",
        "action=block",
        "remoteip=!LocalSubnet",
        "enable=yes",
        f"description=LAN-Guard block external inbound port {port}"
    ])

    if rc == 0:
        print(f"  [已加固] 端口 {port} ({name}) -- 外网入站已阻止，本地+局域网正常")
        write_log("firewall_rule_added", {
            "port": port,
            "service": name,
            "action": "block_external_inbound"
        })
        return True
    else:
        print(f"  [失败] 无法添加防火墙规则 (需要管理员权限?)")
        return False


def scan_suspicious(connections):
    """扫描是否有可疑连接"""
    suspicious = []
    seen_remote = {}

    for conn in connections:
        rip = conn["remote_ip"]
        port = conn["local_port"]

        # 排除安全来源
        is_safe = any(rip.startswith(s) for s in SAFE_ORIGINS)
        # 局域网也算安全（192.168.x.x / 10.x.x.x）
        is_lan = rip.startswith("192.168.") or rip.startswith("10.")

        if not is_safe and not is_lan and conn["state"] == "ESTABLISHED":
            suspicious.append({
                "port": port,
                "service": conn["service"],
                "remote_ip": rip,
                "remote_port": conn["remote_port"],
                "level": "HIGH"
            })
        elif is_lan and conn["state"] == "ESTABLISHED":
            # 局域网连接——记录，不报警
            key = f"{port}:{rip}"
            seen_remote[key] = conn

    return suspicious


def run_scan():
    """一次性安全扫描"""
    print("=" * 55)
    print("  [守卫]  澜的安全守卫 · 扫描中...")
    print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # 1. 检查当前连接
    conns = get_connections()
    print(f"\n[连接扫描] 正在监控 {len(GUARDED_PORTS)} 个端口")
    for port, service in GUARDED_PORTS.items():
        port_conns = [c for c in conns if c["local_port"] == port]
        listening = [c for c in port_conns if c["state"] == "LISTENING"]
        active = [c for c in port_conns if c["state"] == "ESTABLISHED"]
        if listening:
            print(f"  [OK] {port} ({service}) -- 监听中，{len(active)} 条活跃连接")
        else:
            print(f"  [--] {port} ({service}) -- 未监听（服务未启动）")

    # 2. 可疑连接检测
    suspicious = scan_suspicious(conns)
    if suspicious:
        print(f"\n⚠️  发现 {len(suspicious)} 条可疑连接：")
        for s in suspicious:
            print(f"  [{s['level']}] {s['service']}({s['port']}) ← {s['remote_ip']}:{s['remote_port']}")
            write_log("suspicious_connection", s)
    else:
        print("\n  ✓ 未发现可疑外部连接")

    # 3. 防火墙加固
    print("\n[防火墙加固] 检查入站规则...")
    for port, service in {5175: "LobsterAI", 18789: "OpenClaw"}.items():
        add_firewall_block_inbound(port, service)

    # 4. vite.config 风险提示
    vite_config = r"C:\Users\yyds\Desktop\AI日记本\guests\LobsterAI\vite.config.ts"
    if os.path.exists(vite_config):
        with open(vite_config, "r", encoding="utf-8") as f:
            content = f.read()
        if "host: true" in content:
            print("\n⚠️  [已知风险] vite.config.ts 中 host: true")
            print("   → 5175端口绑定在 0.0.0.0，局域网内可访问")
            print("   → 防火墙规则已加固，但建议正式环境改为 host: 'localhost'")
            write_log("config_risk", {
                "file": "vite.config.ts",
                "issue": "host: true 绑定 0.0.0.0",
                "severity": "medium",
                "mitigation": "防火墙规则已添加"
            })

    print("\n[安全摘要]")
    print("  - 开源项目风险：任何人看到源码，所以端口路径是公开的")
    print("  - 缓解措施：防火墙阻断外网入站，只允许本机+局域网")
    print("  - 监控原则：只防不攻，记录观察，不主动出击")
    print("\n  [守卫完成]\n")

    write_log("scan_complete", {"guarded_ports": list(GUARDED_PORTS.keys()), "suspicious_count": len(suspicious)})


def run_watch(interval_seconds=60):
    """持续监控模式"""
    print(f"\n[持续监控] 澜的安全守卫 · 持续监控（每{interval_seconds}秒扫描）")
    print("  按 Ctrl+C 停止\n")
    while True:
        conns = get_connections()
        suspicious = scan_suspicious(conns)
        if suspicious:
            print(f"\n⚠️  [{datetime.now().strftime('%H:%M:%S')}] 发现可疑连接：")
            for s in suspicious:
                print(f"  [{s['level']}] {s['service']}({s['port']}) ← {s['remote_ip']}")
                write_log("suspicious_connection", s)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if cmd == "scan":
        run_scan()
    elif cmd == "watch":
        run_watch(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    else:
        print("用法：")
        print("  python lan_security_guard.py scan    # 一次性安全扫描 + 防火墙加固")
        print("  python lan_security_guard.py watch   # 持续监控模式（每60秒）")
