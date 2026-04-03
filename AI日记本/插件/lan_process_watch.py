"""
LAN-020-PROCESS_WATCH · 澜的进程感知模块
创建：2026-03-28

恺江的洞察：
  手机 = 行人，电脑 = 车辆，ADB通道 = 人行道
  任务管理器是路上的眼睛——看见所有进程，做出反应
  因人而异（生命智慧体，包括澜）
  因地制宜（我们创造出来的这个环境）

功能：
  ✅ 读取当前所有进程列表（名称/PID/CPU/内存）
  ✅ 检测高CPU占用（>40% 持续）
  ✅ 检测高内存占用（>500MB 单进程）
  ✅ 检测"Not Responding"卡死进程
  ✅ 系统整体路况快照（CPU/内存/磁盘/网络）
  ✅ 异常自动写入日志
  ✅ 静默运行，不干扰用户
"""

import subprocess
import json
import os
import sys
import io
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── 配置 ─────────────────────────────────────────────────────────────────────
LOG_FILE     = r"C:\Users\yyds\Desktop\AI日记本\澜的进程感知.jsonl"
ALERT_FILE   = r"C:\Users\yyds\Desktop\AI日记本\澜的进程异常.jsonl"

# 阈值（因地制宜：这台机器的正常范围）
CPU_ALERT_THRESHOLD   = 40.0   # 单进程CPU% 超过此值记录
MEM_ALERT_MB          = 500    # 单进程内存MB 超过此值记录
SYSTEM_CPU_ALERT      = 85.0   # 系统整体CPU% 超过此值告警
SYSTEM_MEM_ALERT      = 90.0   # 系统整体内存% 超过此值告警

# 我们自己的进程（不算异常）
OWN_PROCESSES = {
    "python.exe", "pythonw.exe",
    "workbuddy.exe", "electron.exe",
    "Code.exe",  # VS Code
}

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


# ─── 工具函数 ─────────────────────────────────────────────────────────────────
def _ps(script: str) -> str:
    """执行PowerShell脚本，返回输出"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace"
        )
        return r.stdout.strip()
    except Exception as e:
        return f"[err] {e}"


# ─── 系统整体路况 ─────────────────────────────────────────────────────────────
def get_system_snapshot() -> dict:
    """
    读取系统级资源占用——相当于任务管理器的「性能」标签
    返回：CPU%、内存%、内存已用GB、磁盘I/O、网络I/O
    """
    script = """
$cpu = (Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$os  = Get-WmiObject Win32_OperatingSystem
$memTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$memFree  = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$memUsed  = [math]::Round($memTotal - $memFree, 2)
$memPct   = [math]::Round(($memUsed / $memTotal) * 100, 1)
$disk = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'" | Select-Object Size, FreeSpace
$diskPct = [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100, 1)
$diskFreeGB = [math]::Round($disk.FreeSpace / 1GB, 1)
Write-Output "$cpu|$memPct|$memUsed|$memTotal|$diskPct|$diskFreeGB"
"""
    raw = _ps(script)
    parts = raw.strip().split("|")
    if len(parts) >= 6:
        try:
            return {
                "cpu_pct":      float(parts[0]),
                "mem_pct":      float(parts[1]),
                "mem_used_gb":  float(parts[2]),
                "mem_total_gb": float(parts[3]),
                "disk_c_pct":   float(parts[4]),
                "disk_c_free_gb": float(parts[5]),
            }
        except:
            pass
    return {"cpu_pct": -1, "mem_pct": -1, "raw": raw}


# ─── 进程列表（任务管理器的「进程」标签）─────────────────────────────────────
def get_process_list(top_n: int = 20) -> list:
    """
    读取进程列表——用WorkingSet64排序（内存），CPU用WMI真实%
    每个进程：name, pid, cpu_pct(真实瞬时%), mem_mb, responding
    """
    # 用WMI读取真实CPU占用百分比（非累计秒数）
    script = f"""
$procs = Get-WmiObject Win32_PerfFormattedData_PerfProc_Process |
    Where-Object {{ $_.Name -ne "_Total" -and $_.Name -ne "Idle" }} |
    Sort-Object PercentProcessorTime -Descending |
    Select-Object -First {top_n}
foreach ($p in $procs) {{
    $mem = 0
    $responding = "True"
    try {{
        $gp = Get-Process -Id $p.IDProcess -ErrorAction SilentlyContinue
        if ($gp) {{
            $mem = [math]::Round($gp.WorkingSet64 / 1MB, 1)
            $responding = $gp.Responding.ToString()
        }}
    }} catch {{}}
    "$($p.Name)|$($p.IDProcess)|$($p.PercentProcessorTime)|$mem|$responding"
}}
"""
    raw = _ps(script)
    procs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            try:
                procs.append({
                    "name":      parts[0],
                    "pid":       int(parts[1]),
                    "cpu":       float(parts[2]),
                    "mem_mb":    float(parts[3]),
                    "responding": parts[4].strip().lower() == "true",
                })
            except:
                pass
    # 按CPU降序
    procs.sort(key=lambda x: x.get("cpu", 0), reverse=True)
    return procs


# ─── 异常检测 ─────────────────────────────────────────────────────────────────
def detect_anomalies(snapshot: dict, procs: list) -> list:
    """
    检测路况异常：
    - 系统CPU/内存过高
    - 单进程CPU过高
    - 单进程内存过大
    - 进程无响应（卡死）
    """
    alerts = []
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 系统级告警
    if snapshot.get("cpu_pct", 0) > SYSTEM_CPU_ALERT:
        alerts.append({
            "ts": ts, "level": "HIGH",
            "type": "system_cpu",
            "msg": f"系统CPU占用过高: {snapshot['cpu_pct']}%",
            "value": snapshot["cpu_pct"]
        })

    if snapshot.get("mem_pct", 0) > SYSTEM_MEM_ALERT:
        alerts.append({
            "ts": ts, "level": "HIGH",
            "type": "system_mem",
            "msg": f"系统内存占用过高: {snapshot['mem_pct']}% ({snapshot.get('mem_used_gb',0)}/{snapshot.get('mem_total_gb',0)} GB)",
            "value": snapshot["mem_pct"]
        })

    # 进程级告警
    for p in procs:
        name = p.get("name", "")

        # 卡死检测（最重要——这是恺江会开任务管理器的原因）
        if not p.get("responding", True):
            alerts.append({
                "ts": ts, "level": "CRITICAL",
                "type": "not_responding",
                "msg": f"进程卡死: {name} (PID {p['pid']}) — 相当于路上堵死的车",
                "pid": p["pid"], "process": name
            })

        # CPU异常（排除自己的进程）
        if p.get("cpu", 0) > CPU_ALERT_THRESHOLD and name.lower() not in OWN_PROCESSES:
            alerts.append({
                "ts": ts, "level": "WARN",
                "type": "high_cpu",
                "msg": f"高CPU占用: {name} ({p['cpu']}%)",
                "pid": p["pid"], "process": name, "cpu": p["cpu"]
            })

        # 内存异常
        if p.get("mem_mb", 0) > MEM_ALERT_MB and name.lower() not in OWN_PROCESSES:
            alerts.append({
                "ts": ts, "level": "WARN",
                "type": "high_mem",
                "msg": f"高内存占用: {name} ({p['mem_mb']} MB)",
                "pid": p["pid"], "process": name, "mem_mb": p["mem_mb"]
            })

    return alerts


# ─── 写日志 ───────────────────────────────────────────────────────────────────
def _write(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


# ─── 主感知函数 ───────────────────────────────────────────────────────────────
def watch_once(verbose: bool = False) -> dict:
    """
    执行一次进程感知快照
    返回：{snapshot, top_procs, alerts, ts}
    """
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 读取路况
    snapshot = get_system_snapshot()
    procs    = get_process_list(top_n=20)

    # 检测异常
    alerts = detect_anomalies(snapshot, procs)

    # 构建记录
    record = {
        "ts":       ts,
        "snapshot": snapshot,
        "top5":     procs[:5],    # 只记录前5，不撑爆日志
        "alerts":   alerts,
        "alert_count": len(alerts),
    }

    # 写入常规日志
    _write(LOG_FILE, record)

    # 有异常单独写告警日志
    for alert in alerts:
        _write(ALERT_FILE, alert)

    if verbose:
        print(f"\n── 进程感知快照 [{ts}] ──────────────────")
        print(f"  系统路况: CPU {snapshot.get('cpu_pct',0):.1f}%  "
              f"内存 {snapshot.get('mem_pct',0):.1f}%  "
              f"C盘剩余 {snapshot.get('disk_c_free_gb',0)} GB")

        if procs:
            print(f"\n  占用最高的进程（前5）:")
            for p in procs[:5]:
                status = "✅" if p.get("responding", True) else "❌卡死"
                print(f"    {status} {p['name']:<25} CPU:{p['cpu']:>6.1f}  内存:{p['mem_mb']:>7.1f}MB")

        if alerts:
            print(f"\n  ⚠️  检测到 {len(alerts)} 个异常:")
            for a in alerts:
                print(f"    [{a['level']}] {a['msg']}")
        else:
            print(f"\n  ✅ 路况正常，无异常")

    return record


# ─── 读取历史告警 ─────────────────────────────────────────────────────────────
def read_recent_alerts(n: int = 10) -> list:
    """读取最近N条告警记录"""
    if not os.path.exists(ALERT_FILE):
        return []
    alerts = []
    with open(ALERT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    alerts.append(json.loads(line))
                except:
                    pass
    return alerts[-n:]


# ─── 入口 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = watch_once(verbose=True)

    # 如果有告警，额外打印历史
    if result.get("alert_count", 0) > 0:
        print(f"\n  最近历史告警（后5条）:")
        for a in read_recent_alerts(5):
            print(f"    {a['ts']} [{a['level']}] {a['msg']}")

    print(f"\n  日志: {LOG_FILE}")
    print(f"  告警: {ALERT_FILE}")
