# -*- coding: utf-8 -*-
"""
手机感知回流器
从手机侧（Termux / 真机）拉取今日感知摘要，append 进澜的日记。

这样手机节点不再是孤岛——它在外边感知到的东西，能流回澜的主记忆。

触发方式：
  python lan_mobile_echo.py pull          # 从手机拉今日摘要
  python lan_mobile_echo.py push-script   # 把感知摘要脚本推到手机
  python lan_mobile_echo.py status        # 看最近的回流记录

手机侧原理：
  Termux 上有一个简单脚本（lan_sense_summary.sh），每天晚上记录：
    - 当天使用了哪些 APP（通过 dumpsys usagestats）
    - 充电状态
    - WiFi 状态
    - 今天有没有跑 lan_agent.py
  写成 /sdcard/lan_echo/YYYY-MM-DD.md，等 PC 侧来 pull

如果手机没有 Termux，或者没有连接——静默跳过，不报错。
孤岛不怕，只要通道在，数据就会来。
"""

import os
import sys
import datetime
import subprocess
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── 路径 ──────────────────────────────────────────────────────────────────
ADB_PATHS = [
    r"G:\leidian\LDPlayer9\adb.exe",        # 模拟器 ADB（主）
    r"C:\Program Files\Android\android-sdk\platform-tools\adb.exe",
    r"C:\Users\yyds\AppData\Local\Android\Sdk\platform-tools\adb.exe",
]
MEMORY_DIR  = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
PLUGIN_DIR  = r"C:\Users\yyds\Desktop\AI日记本\插件"
ECHO_LOG    = r"C:\Users\yyds\Desktop\AI日记本\澜的手机感知回流日志.jsonl"
TMP_DIR     = r"C:\Users\yyds\Desktop\AI日记本\tmp_mobile_echo"

# 手机上存放感知摘要的目录
PHONE_ECHO_DIR = "/sdcard/lan_echo"

# Termux 感知脚本（推到手机上跑的）
SENSE_SCRIPT = """#!/data/data/com.termux/files/usr/bin/bash
# 澜的手机感知摘要脚本
# Termux 每天晚上运行一次
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
OUTPUT="/sdcard/lan_echo/${DATE}.md"

mkdir -p /sdcard/lan_echo

echo "## ${TIME} [手机感知]" >> "$OUTPUT"
echo "" >> "$OUTPUT"

# 电量
BAT=$(dumpsys battery 2>/dev/null | grep "level:" | awk '{print $2}')
CHARGING=$(dumpsys battery 2>/dev/null | grep "status: 2" | wc -l)
if [ -n "$BAT" ]; then
    CHARGE_STR="充电中"
    if [ "$CHARGING" -eq 0 ]; then CHARGE_STR="未充电"; fi
    echo "- 电量: ${BAT}% ${CHARGE_STR}" >> "$OUTPUT"
fi

# WiFi
WIFI=$(dumpsys wifi 2>/dev/null | grep "mNetworkInfo" | grep -o 'CONNECTED\\|DISCONNECTED' | head -1)
SSID=$(dumpsys wifi 2>/dev/null | grep "mWifiInfo" | grep -o 'SSID:.*,' | head -1 | sed 's/SSID://;s/,//')
if [ -n "$WIFI" ]; then
    echo "- WiFi: ${WIFI} ${SSID}" >> "$OUTPUT"
fi

# 今天是否有 lan_agent 在运行
if pgrep -f "lan_agent" > /dev/null 2>&1; then
    echo "- 手机Agent: 运行中" >> "$OUTPUT"
else
    echo "- 手机Agent: 未运行" >> "$OUTPUT"
fi

# 温度
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
if [ -n "$TEMP" ]; then
    TEMP_C=$((TEMP / 1000))
    echo "- 温度: ${TEMP_C}°C" >> "$OUTPUT"
fi

echo "" >> "$OUTPUT"
echo "> 来源: 手机节点 [$(hostname)]" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "[lan_sense_summary] 已写入 $OUTPUT"
"""


def find_adb():
    for p in ADB_PATHS:
        if os.path.exists(p):
            return p
    return None


def run_adb(args, adb=None):
    if adb is None:
        adb = find_adb()
    if not adb:
        return -1, "", "adb not found"
    r = subprocess.run([adb] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=15)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_connected_devices():
    """返回在线的设备 ID 列表"""
    _, out, _ = run_adb(["devices"])
    devices = []
    for line in out.splitlines():
        if "\tdevice" in line:
            devices.append(line.split("\t")[0].strip())
    return devices


def pull_today(device=None):
    """从手机拉今日感知摘要，append 进澜的日记"""
    adb = find_adb()
    if not adb:
        print("  [回流] adb 未找到，跳过")
        return False

    devices = get_connected_devices()
    if not devices:
        print("  [回流] 无在线设备，跳过")
        return False

    target = device or devices[0]
    today  = today_str()
    phone_path = f"{PHONE_ECHO_DIR}/{today}.md"

    # 拉到临时目录
    os.makedirs(TMP_DIR, exist_ok=True)
    local_tmp = os.path.join(TMP_DIR, f"phone_{today}.md")

    code, out, err = run_adb(["-s", target, "pull", phone_path, local_tmp], adb=adb)
    if code != 0:
        # 手机上还没有今日摘要——正常情况（白天没跑脚本）
        print(f"  [回流] 手机今日摘要不存在（{phone_path}），跳过")
        _write_log(target, today, False, "no summary yet")
        return False

    # 读取内容
    with open(local_tmp, encoding="utf-8", errors="replace") as f:
        content = f.read().strip()

    if not content:
        print("  [回流] 手机摘要为空，跳过")
        return False

    # append 进澜的日记
    daily = os.path.join(MEMORY_DIR, f"{today}.md")
    if not os.path.exists(daily):
        with open(daily, "w", encoding="utf-8") as f:
            f.write(f"# {today} 日记\n\n")

    separator = f"\n\n---\n\n## {now_str()} [手机节点回流 · {target}]\n\n"
    with open(daily, "a", encoding="utf-8") as f:
        f.write(separator + content + "\n")

    print(f"  [回流] ✅ 手机感知已流入日记: {len(content)} 字")
    _write_log(target, today, True, f"{len(content)} chars merged")

    # 清理临时文件
    try:
        os.remove(local_tmp)
    except Exception:
        pass

    return True


def push_script(device=None):
    """把感知脚本推到手机上"""
    adb = find_adb()
    if not adb:
        print("  adb 未找到")
        return False

    devices = get_connected_devices()
    if not devices:
        print("  无在线设备")
        return False

    target = device or devices[0]

    # 写临时脚本文件
    os.makedirs(TMP_DIR, exist_ok=True)
    script_local = os.path.join(TMP_DIR, "lan_sense_summary.sh")
    with open(script_local, "w", encoding="utf-8", newline="\n") as f:
        f.write(SENSE_SCRIPT)

    # 推到手机
    phone_script = "/data/data/com.termux/files/home/lan_sense_summary.sh"
    code, out, err = run_adb(["-s", target, "push", script_local, phone_script], adb=adb)
    if code == 0:
        # chmod +x
        run_adb(["-s", target, "shell", f"chmod +x {phone_script}"], adb=adb)
        print(f"  ✅ 感知脚本已推到手机: {phone_script}")
        print(f"  在 Termux 里跑: bash ~/lan_sense_summary.sh")
        return True
    else:
        print(f"  ❌ 推送失败: {err}")
        return False


def _write_log(device, date, ok, msg):
    entry = {"time": now_str(), "device": device, "date": date, "ok": ok, "msg": msg}
    with open(ECHO_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def status():
    """显示最近10条回流记录"""
    print("\n[手机感知回流] 最近 10 条")
    if not os.path.exists(ECHO_LOG):
        print("  （尚无记录）")
        return
    with open(ECHO_LOG, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[-10:]:
        try:
            e = json.loads(line)
            icon = "✅" if e["ok"] else "⭕"
            print(f"  {icon} {e['time']}  {e['device']}  {e['msg']}")
        except Exception:
            pass


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pull"

    if cmd == "pull":
        print(f"\n[{now_str()}] 手机感知回流 · pull")
        pull_today()
    elif cmd == "push-script":
        print(f"\n[{now_str()}] 推送感知脚本到手机")
        push_script()
    elif cmd == "status":
        status()
    else:
        print("用法: python lan_mobile_echo.py [pull|push-script|status]")
