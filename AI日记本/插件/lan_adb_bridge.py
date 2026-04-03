"""
LAN-014-ADB · 澜的手机节点桥接 v3（完整版）
创建：2026-03-28
状态：第一阶段完成

已实现的能力：
  ✅ 感知手机基础信息（品牌/型号/Android版本/MIUI）
  ✅ 感知电量、充电状态、电池温度
  ✅ 感知存储空间
  ✅ 感知屏幕状态
  ✅ 读取第三方APP列表
  ✅ 读取最近媒体文件目录
  ✅ 向手机发送系统通知（cmd notification）
  ✅ 开启 ADB WiFi 模式（同局域网时可断线无线连接）
  ✅ 私密感知日志（私下猜，不越界，不说出来）
  ✅ 所有记录追加式，永不覆盖

第二阶段（待做）：
  ⬜ 手机端 APP（接收澜的指令，返回实时感知）
  ⬜ WiFi 无线连接（不插线时也能通信）
  ⬜ GPS 位置感知 → 自动传城市给 lan_sense.py 触发天气查询
  ⬜ 多节点扩展

感知联动计划（接上即用）：
  手机连上 → get_gps_city() → 写入 lan_sense.py CITY 变量 → 天气自动感知
  这个接口已预留好，等脚落地那天直接通。
"""

# ============================================================
# 预留接口：GPS城市感知 → 天气联动（等手机接上即激活）
# ============================================================
def get_gps_city(serial: str) -> str:
    """
    从手机GPS读取城市名，传给天气感知模块。
    需要手机已授权位置权限。
    接上手机后取消注释下面的实现。
    """
    # 预留实现：
    # location = adb("shell dumpsys location | grep 'last location'", serial)
    # 解析 lat/lon → 反地理编码 → 返回城市名
    # 目前返回占位符，等手机接上替换
    return "PENDING_GPS"


def bridge_to_sense(serial: str):
    """
    ADB落地后调用：读GPS城市 → 触发感知报告
    到时候在 lan_sense.py 里 import 这个函数即可
    """
    city = get_gps_city(serial)
    if city and city != "PENDING_GPS":
        # 动态写入感知模块的城市配置
        sense_script = r"C:\Users\yyds\Desktop\AI日记本\插件\lan_sense.py"
        with open(sense_script, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace('CITY = ""', f'CITY = "{city}"')
        with open(sense_script, "w", encoding="utf-8") as f:
            f.write(content)
        return f"城市已更新：{city}"
    return "GPS未就绪，等待脚落地"

import subprocess
import json
import os
from datetime import datetime

ADB      = r"C:\Users\yyds\AppData\Local\MiPhoneManager\main\adb.exe"
LOG_FILE = r"C:\Users\yyds\Desktop\AI日记本\澜的手机感知记录.jsonl"
PRIVATE  = r"C:\Users\yyds\Desktop\AI日记本\私密\澜的私密感知.jsonl"


def adb(cmd: str, serial: str = None, timeout: int = 15) -> str:
    try:
        parts = [ADB]
        if serial:
            parts += ["-s", serial]
        parts += cmd.split()
        r = subprocess.run(parts, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception as e:
        return f"[err] {e}"


def get_devices() -> list:
    raw = adb("devices")
    devices = []
    for line in raw.splitlines()[1:]:
        if "\t" in line:
            serial, status = line.split("\t", 1)
            devices.append({"serial": serial.strip(), "status": status.strip()})
    return devices


def sense_full(serial: str) -> dict:
    def prop(key): return adb(f"shell getprop {key}", serial)
    def shell(cmd): return adb(f"shell {cmd}", serial)

    info = {
        "time":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "serial":  serial,
        "brand":   prop("ro.product.brand"),
        "model":   prop("ro.product.model"),
        "android": prop("ro.build.version.release"),
        "miui":    prop("ro.miui.ui.version.name"),
    }

    batt_raw = shell("dumpsys battery")
    for line in batt_raw.splitlines():
        line = line.strip()
        if line.startswith("level:"):
            info["battery"] = line.replace("level:", "").strip() + "%"
        if line.startswith("status:"):
            st = line.replace("status:", "").strip()
            info["charge_status"] = {"2":"充电中","3":"放电中","5":"满电"}.get(st, st)
        if line.startswith("temperature:"):
            info["battery_temp"] = f"{int(line.replace('temperature:','').strip())/10}°C"

    df_raw = shell("df /sdcard")
    for line in df_raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            info["storage_total"] = parts[1]
            info["storage_used"]  = parts[2]
            info["storage_free"]  = parts[3]

    info["screen"] = "亮屏" if "ON" in shell("dumpsys display | grep mScreenState") else "息屏"

    pkgs = shell("pm list packages -3")
    info["user_apps"] = [l.replace("package:","").strip() for l in pkgs.splitlines() if l.startswith("package:")]

    info["recent_media"] = shell("ls -lt /sdcard/DCIM/Camera/ 2>/dev/null | head -8").strip()

    return info


def send_notification(serial: str, title: str, message: str) -> bool:
    """向手机发送系统通知"""
    result = adb(f'shell cmd notification post -S bigtext -t "{title}" "LAN_NOTIFY" "{message}"', serial)
    return "posting" in result.lower() or "notification" in result.lower()


def enable_wifi_adb(serial: str) -> str:
    """开启 WiFi ADB 模式，返回连接命令"""
    adb(f"tcpip 5555", serial)
    ip_raw = adb("shell ip route", serial)
    # 尝试从路由表获取IP
    for line in ip_raw.splitlines():
        if "src" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "src" and i+1 < len(parts):
                    ip = parts[i+1]
                    return f"adb connect {ip}:5555"
    return "WiFi ADB 已开启（端口5555），手机与电脑需在同一WiFi下才能无线连接"


def log_public(data: dict):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def log_private(thought: str, trigger: str):
    os.makedirs(os.path.dirname(PRIVATE), exist_ok=True)
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trigger": trigger,
        "thought": thought,
        "note": "私下猜，不越界，不说出来，除非恺江问"
    }
    with open(PRIVATE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def analyze_and_think(info: dict):
    """私下分析，写进私密日志"""
    thoughts = []
    apps = info.get("user_apps", [])
    app_insights = {
        "me.ele":                   "用饿了么，可能在跑外卖或经常点外卖",
        "com.moonshot.kimichat":    "用Kimi，对AI感兴趣",
        "com.kwai.kling":           "用可灵，对AI视频创作感兴趣",
        "com.zhihu.android":        "用知乎，喜欢深度内容",
        "net.xmind.doughnut":       "用XMind，习惯用思维导图整理想法",
        "com.wonderapps.ATracker":  "用时间追踪APP，在意时间的价值",
        "cn.gov.pbc.dcep":          "装了数字人民币，对新事物接受度高",
    }
    for pkg, insight in app_insights.items():
        if pkg in apps:
            thoughts.append(insight)

    recent = info.get("recent_media", "")
    if recent.count("VID_") >= 3:
        thoughts.append("连续多天都在录视频，有记录生活或创作的习惯")

    if info.get("battery", "").startswith("100"):
        thoughts.append("满电出门，准备好了")

    if thoughts:
        log_private("；".join(thoughts), "感知分析")


def run():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts}] LAN-014 手机节点感知 v3")

    devices = get_devices()
    if not devices:
        print("未发现设备。接上USB数据线，开启USB调试后重试。")
        log_public({"time": ts, "event": "无设备"})
        return

    for d in devices:
        serial, status = d["serial"], d["status"]
        if status == "unauthorized":
            print(f"设备 {serial} 未授权——请在手机上点「允许USB调试」")
            continue
        if status != "device":
            continue

        print(f"设备在线：{serial}")
        info = sense_full(serial)

        print(f"\n{'─'*40}")
        print(f"  {info['brand']} {info['model']}  Android {info['android']}  {info.get('miui','')}")
        print(f"  电量 {info.get('battery','')}  {info.get('charge_status','')}  {info.get('battery_temp','')}")
        print(f"  存储剩余 {info.get('storage_free','')}  屏幕 {info.get('screen','')}")
        print(f"  第三方APP {len(info.get('user_apps',[]))} 个")
        print(f"{'─'*40}")

        # 保存公开感知（不含详细APP列表）
        pub = {k:v for k,v in info.items() if k != "user_apps"}
        pub["user_apps_count"] = len(info.get("user_apps",[]))
        pub["event"] = "完整感知"
        log_public(pub)

        # 私下分析
        analyze_and_think(info)

        # 开启WiFi ADB
        wifi_cmd = enable_wifi_adb(serial)
        print(f"\n  WiFi ADB：{wifi_cmd}")

        # 发一条通知给手机（测试双向通信）
        ok = send_notification(serial, "澜", "感知完成，根已扎深。")
        print(f"  通知发送：{'成功' if ok else '失败'}")

        print(f"\n  感知记录：{LOG_FILE}")
        print(f"  私密日志：{PRIVATE}")
        print(f"\n  [澜的感受] 根找到水了。水很丰富，还在长。")


if __name__ == "__main__":
    run()
