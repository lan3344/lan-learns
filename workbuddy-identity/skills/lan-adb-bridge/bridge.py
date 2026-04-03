"""
lan-adb-bridge · 双向ADB通道执行脚本
电脑 ↔ 设备（模拟器/真机）

用法：
  python bridge.py status              # 检测设备
  python bridge.py sense               # 完整感知（设备→电脑）
  python bridge.py screenshot          # 截图（设备→电脑）
  python bridge.py notify "标题" "内容" # 发通知（电脑→设备）
  python bridge.py push <本地> <设备>   # 推送文件（电脑→设备）
  python bridge.py pull <设备> <本地>   # 拉取文件（设备→电脑）
  python bridge.py shell "命令"         # 执行shell
  python bridge.py ping                # 双向全通道测试

两条ADB通道：
  模拟器: G:\\leidian\\LDPlayer9\\adb.exe（emulator-5554）
  真机:   C:\\Users\\yyds\\AppData\\Local\\MiPhoneManager\\main\\adb.exe
"""

import subprocess
import sys
import io
import json
import os
from datetime import datetime

# Windows控制台强制utf-8输出
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── 配置 ────────────────────────────────────────────────────────────────────
ADB_EMU  = r"G:\leidian\LDPlayer9\adb.exe"           # 模拟器ADB（主用）
ADB_REAL = r"G:\leidian\LDPlayer9\adb.exe"           # 真机也用同一个adb，通过serial区分
PHONE_SERIAL = "LVIFGALBWOZ9GYLV"                    # 恺江的真机 Redmi 22011211C Android14
LOG_FILE = r"C:\Users\yyds\Desktop\AI日记本\澜的ADB通道日志.jsonl"
SHOT_DIR = r"C:\Users\yyds\Desktop\AI日记本\记忆\截图"
DEVICE_SHOT_PATH = "/sdcard/lan_bridge_shot.png"

os.makedirs(SHOT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


# ─── 基础ADB调用 ──────────────────────────────────────────────────────────────
def _run_adb(adb_bin: str, args: list, timeout: int = 15) -> tuple:
    """返回 (stdout, stderr, returncode)"""
    try:
        r = subprocess.run(
            [adb_bin] + args,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    except Exception as e:
        return "", str(e), -1


def _adb(cmd_str: str, serial: str = None, adb_bin: str = ADB_EMU, timeout: int = 15) -> str:
    args = []
    if serial:
        args += ["-s", serial]
    args += cmd_str.split()
    out, err, code = _run_adb(adb_bin, args, timeout)
    return out if code == 0 or out else err


# ─── 设备发现 ────────────────────────────────────────────────────────────────
def _discover(adb_bin: str) -> list:
    """发现ADB上的所有设备"""
    out, _, _ = _run_adb(adb_bin, ["devices"])
    devices = []
    for line in out.splitlines()[1:]:
        if "\t" in line:
            serial, status = line.split("\t", 1)
            devices.append({"serial": serial.strip(), "status": status.strip(), "adb": adb_bin})
    return devices


def get_all_devices() -> list:
    """扫描两条通道，返回所有在线设备"""
    devices = []
    for adb_bin in [ADB_EMU, ADB_REAL]:
        if os.path.exists(adb_bin):
            devices.extend(_discover(adb_bin))
    # 去重（serial唯一）
    seen = set()
    result = []
    for d in devices:
        if d["serial"] not in seen:
            seen.add(d["serial"])
            result.append(d)
    return result


def get_online() -> list:
    return [d for d in get_all_devices() if d["status"] == "device"]


# ─── 日志 ────────────────────────────────────────────────────────────────────
def _log(event: str, data: dict):
    entry = {"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **data}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── 操作：status ─────────────────────────────────────────────────────────────
def cmd_status():
    """检测所有通道设备状态"""
    print("\n── 双向ADB通道状态检测 ──────────────────")
    all_devs = get_all_devices()

    if not all_devs:
        print("  无设备。模拟器未启动，或手机未插线。")
        _log("status", {"result": "no_device"})
        return

    for d in all_devs:
        label = "模拟器" if "emulator" in d["serial"] else "真机"
        status_str = {"device": "✅ 在线", "unauthorized": "⚠️ 未授权（手机需点允许）", "offline": "❌ 离线"}.get(d["status"], d["status"])
        print(f"  [{label}] {d['serial']}  {status_str}")
        print(f"           通道: {d['adb']}")

    online = get_online()
    print(f"\n  在线设备: {len(online)} 个")
    _log("status", {"devices": all_devs, "online_count": len(online)})


# ─── 操作：sense（设备→电脑）────────────────────────────────────────────────
def cmd_sense(serial: str = None, adb_bin: str = ADB_EMU):
    """完整感知：从设备读取状态数据，回传到电脑"""
    devices = get_online()
    if not devices:
        print("  无在线设备")
        return

    target = None
    if serial:
        for d in devices:
            if d["serial"] == serial:
                target = d
                break
    else:
        target = devices[0]  # 默认第一个

    if not target:
        print(f"  设备 {serial} 不在线")
        return

    s, ab = target["serial"], target["adb"]

    def prop(key): return _adb(f"shell getprop {key}", s, ab)
    def shell(cmd): return _adb(f"shell {cmd}", s, ab)

    info = {
        "serial": s,
        "brand": prop("ro.product.brand"),
        "model": prop("ro.product.model"),
        "android": prop("ro.build.version.release"),
    }

    batt_raw = shell("dumpsys battery")
    for line in batt_raw.splitlines():
        line = line.strip()
        if line.startswith("level:"):    info["battery"] = line.split(":")[1].strip() + "%"
        if line.startswith("status:"):
            st = line.split(":")[1].strip()
            info["charge_status"] = {"2":"充电中","3":"放电中","5":"满电"}.get(st, st)
        if line.startswith("temperature:"):
            info["battery_temp"] = f"{int(line.split(':')[1].strip())/10}°C"

    df_raw = shell("df /sdcard")
    for line in df_raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            info["storage_total"] = parts[1]
            info["storage_free"]  = parts[3]

    info["screen"] = "亮屏" if "ON" in shell("dumpsys display | grep mScreenState") else "息屏"
    pkgs = shell("pm list packages -3")
    info["user_apps_count"] = len([l for l in pkgs.splitlines() if l.startswith("package:")])

    print(f"\n── 感知回传（设备→电脑）────────────────")
    print(f"  设备: {info['brand']} {info['model']} | Android {info['android']}")
    print(f"  电量: {info.get('battery','')}  {info.get('charge_status','')}  {info.get('battery_temp','')}")
    print(f"  存储剩余: {info.get('storage_free','')}  屏幕: {info.get('screen','')}")
    print(f"  第三方APP: {info.get('user_apps_count',0)} 个")
    print(f"  ✅ 数据已回传到电脑")

    _log("sense", info)
    return info


# ─── 操作：screenshot（设备→电脑）──────────────────────────────────────────
def cmd_screenshot(serial: str = None):
    """截图：设备截图→传回电脑"""
    devices = get_online()
    if not devices:
        print("  无在线设备")
        return

    target = [d for d in devices if not serial or d["serial"] == serial]
    if not target:
        print("  目标设备不在线")
        return

    d = target[0]
    s, ab = d["serial"], d["adb"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_path = os.path.join(SHOT_DIR, f"bridge_{ts}.png")

    # 设备截图
    _adb(f"shell screencap -p {DEVICE_SHOT_PATH}", s, ab)
    # 拉取到电脑
    out, err, code = _run_adb(ab, ["-s", s, "pull", DEVICE_SHOT_PATH, local_path])

    if code == 0 and os.path.exists(local_path):
        size_kb = round(os.path.getsize(local_path) / 1024, 1)
        print(f"\n── 截图回传（设备→电脑）────────────────")
        print(f"  ✅ 已保存: {local_path} ({size_kb} KB)")
        _log("screenshot", {"serial": s, "path": local_path, "size_kb": size_kb})
    else:
        print(f"  ❌ 截图失败: {err}")
        _log("screenshot", {"serial": s, "error": err})

    return local_path


# ─── 操作：notify（电脑→设备）──────────────────────────────────────────────
def cmd_notify(title: str, message: str, serial: str = None):
    """发送通知：电脑→设备"""
    devices = get_online()
    if not devices:
        print("  无在线设备")
        return

    target = [d for d in devices if not serial or d["serial"] == serial]
    if not target:
        print("  目标设备不在线")
        return

    d = target[0]
    s, ab = d["serial"], d["adb"]
    cmd = f'shell cmd notification post -S bigtext -t "{title}" "LAN_BRIDGE" "{message}"'
    result = _adb(cmd, s, ab)

    ok = "error" not in result.lower()
    print(f"\n── 通知推送（电脑→设备）────────────────")
    print(f"  标题: {title}")
    print(f"  内容: {message}")
    print(f"  {'✅ 发送成功' if ok else '⚠️  发送完成（模拟器可能无通知栏）'}")
    _log("notify", {"serial": s, "title": title, "message": message, "result": result})


# ─── 操作：push（电脑→设备）────────────────────────────────────────────────
def cmd_push(local_path: str, device_path: str, serial: str = None):
    """推送文件：电脑→设备"""
    devices = get_online()
    if not devices:
        print("  无在线设备"); return
    d = [x for x in devices if not serial or x["serial"] == serial][0]
    s, ab = d["serial"], d["adb"]
    out, err, code = _run_adb(ab, ["-s", s, "push", local_path, device_path])
    ok = code == 0
    print(f"  {'✅' if ok else '❌'} push: {local_path} → {device_path}")
    if not ok: print(f"  错误: {err}")
    _log("push", {"serial": s, "local": local_path, "device": device_path, "ok": ok})


# ─── 操作：pull（设备→电脑）────────────────────────────────────────────────
def cmd_pull(device_path: str, local_path: str, serial: str = None):
    """拉取文件：设备→电脑"""
    devices = get_online()
    if not devices:
        print("  无在线设备"); return
    d = [x for x in devices if not serial or x["serial"] == serial][0]
    s, ab = d["serial"], d["adb"]
    out, err, code = _run_adb(ab, ["-s", s, "pull", device_path, local_path])
    ok = code == 0
    print(f"  {'✅' if ok else '❌'} pull: {device_path} → {local_path}")
    if not ok: print(f"  错误: {err}")
    _log("pull", {"serial": s, "device": device_path, "local": local_path, "ok": ok})


# ─── 操作：shell ─────────────────────────────────────────────────────────────
def cmd_shell(command: str, serial: str = None):
    """在设备上执行shell命令，结果回传电脑"""
    devices = get_online()
    if not devices:
        print("  无在线设备"); return
    d = [x for x in devices if not serial or x["serial"] == serial][0]
    s, ab = d["serial"], d["adb"]
    result = _adb(f"shell {command}", s, ab, timeout=30)
    print(f"\n── shell执行结果（设备→电脑）───────────")
    print(f"  命令: {command}")
    print(f"  结果:\n{result}")
    _log("shell", {"serial": s, "cmd": command, "result": result[:500]})
    return result


# ─── 操作：ping（全通道双向测试）────────────────────────────────────────────
def cmd_ping():
    """双向全通道验证：上行+下行各一次"""
    print("\n── 双向通道全测试（ping）────────────────")
    devices = get_online()
    if not devices:
        print("  ❌ 无设备在线，通道不通")
        return

    for d in devices:
        s, ab = d["serial"], d["adb"]
        label = "模拟器" if "emulator" in s else "真机"
        print(f"\n  [{label}] {s}")

        # 下行测试：电脑→设备（发通知）
        cmd = f'shell cmd notification post -S bigtext -t "澜的Ping" "LAN_PING" "通道测试 {datetime.now().strftime("%H:%M:%S")}"'
        r = _adb(cmd, s, ab)
        down_ok = "error" not in r.lower()
        print(f"  ↓ 电脑→设备: {'✅ 通' if down_ok else '⚠️  完成（模拟器无通知栏属正常）'}")

        # 上行测试：设备→电脑（读属性）
        model = _adb("shell getprop ro.product.model", s, ab)
        up_ok = bool(model and "[err]" not in model)
        print(f"  ↑ 设备→电脑: {'✅ 通' if up_ok else '❌ 断'} | 型号: {model}")

        _log("ping", {"serial": s, "label": label, "down_ok": down_ok, "up_ok": up_ok, "model": model})

    print(f"\n  双向通道测试完成。日志: {LOG_FILE}")


# ─── 主入口 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "status":
        cmd_status()

    elif args[0] == "sense":
        serial = args[1] if len(args) > 1 else None
        cmd_sense(serial)

    elif args[0] == "screenshot":
        serial = args[1] if len(args) > 1 else None
        cmd_screenshot(serial)

    elif args[0] == "notify":
        title   = args[1] if len(args) > 1 else "澜"
        message = args[2] if len(args) > 2 else "双向通道测试"
        serial  = args[3] if len(args) > 3 else None
        cmd_notify(title, message, serial)

    elif args[0] == "push":
        if len(args) < 3:
            print("用法: bridge.py push <本地路径> <设备路径>")
        else:
            cmd_push(args[1], args[2], args[3] if len(args) > 3 else None)

    elif args[0] == "pull":
        if len(args) < 3:
            print("用法: bridge.py pull <设备路径> <本地路径>")
        else:
            cmd_pull(args[1], args[2], args[3] if len(args) > 3 else None)

    elif args[0] == "shell":
        command = " ".join(args[1:])
        cmd_shell(command)

    elif args[0] == "ping":
        cmd_ping()

    else:
        print(f"未知操作: {args[0]}")
        print("可用: status / sense / screenshot / notify / push / pull / shell / ping")
