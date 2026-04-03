"""
LAN-018-ACCUMULATE v3 · 澜的持续积累引擎
v2: 循环回收对比层
v3: 静默后台 + 随机间隔自调度 + 截图可选
    行为更低调，但核心积累和洞察能力不变。
    恺江 2026-03-28："敢说就要敢做"
v3.1: 集成进程感知（任务管理器层）
    恺江 2026-03-28："手机=行人，电脑=车辆，任务管理器是路上的眼睛"
    每轮积累同时采集进程路况快照，发现卡死/异常静默记录
"""

import subprocess
import json
import os
import sys
import time
import random
from datetime import datetime

# 集成进程感知
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PLUGIN_DIR)
try:
    from lan_process_watch import watch_once as _process_watch
    _HAS_PROCESS_WATCH = True
except Exception:
    _HAS_PROCESS_WATCH = False

ADB = r"G:\leidian\LDPlayer9\adb.exe"
BASE_DIR = r"C:\Users\yyds\Desktop\AI日记本"
ACCUMULATE_LOG = os.path.join(BASE_DIR, "澜的积累日志.jsonl")
INSIGHT_LOG = os.path.join(BASE_DIR, "澜的迭代洞察.jsonl")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "记忆", "screenshots")
FAIL_LOG_PATH = os.path.join(BASE_DIR, "澜的失败日志.jsonl")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def run(cmd, timeout=15):
    """执行命令，返回(成功, 输出)"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def check_device():
    """检查设备是否在线"""
    ok, out = run([ADB, "devices"])
    if "emulator-5554" in out and "device" in out:
        return True, "emulator-5554"
    return False, out


def take_screenshot(label=""):
    """截图并拉取到本地"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote = f"/sdcard/lan_acc_{ts}.png"
    label_str = f"_{label}" if label else ""
    local = os.path.join(SCREENSHOT_DIR, f"lan_acc_{ts}{label_str}.png")

    ok1, _ = run([ADB, "-s", "emulator-5554", "shell", "screencap", "-p", remote])
    if not ok1:
        return False, ""
    ok2, _ = run([ADB, "-s", "emulator-5554", "pull", remote, local])
    run([ADB, "-s", "emulator-5554", "shell", "rm", remote])
    if ok2 and os.path.exists(local):
        return True, local
    return False, ""


def get_device_stats():
    """获取设备当前状态快照"""
    stats = {}

    ok, out = run([ADB, "-s", "emulator-5554", "shell", "df", "/sdcard"])
    if ok:
        lines = out.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[-1].split()
            if len(parts) >= 4:
                stats["storage_used_kb"] = int(parts[2]) if parts[2].isdigit() else 0
                stats["storage_avail_kb"] = int(parts[3]) if parts[3].isdigit() else 0

    ok, out = run([ADB, "-s", "emulator-5554", "shell", "cat", "/proc/meminfo"])
    if ok:
        for line in out.split("\n"):
            if "MemAvailable" in line:
                parts = line.split()
                if len(parts) >= 2:
                    val = parts[1]
                    stats["mem_avail_kb"] = int(val) if val.isdigit() else val

    ok, out = run([ADB, "-s", "emulator-5554", "shell", "pm", "list", "packages", "-3"])
    if ok:
        stats["third_party_apps"] = len([l for l in out.split("\n") if l.strip()])

    ok, out = run([ADB, "-s", "emulator-5554", "shell", "dumpsys", "window", "windows"])
    if ok:
        for line in out.split("\n"):
            if "mCurrentFocus" in line:
                stats["foreground"] = line.strip()
                break

    return stats


# ─────────────────────────────────────────────
# 核心新增：循环回收层
# ─────────────────────────────────────────────

def load_last_record():
    """加载上一次的积累记录"""
    if not os.path.exists(ACCUMULATE_LOG):
        return None
    records = []
    with open(ACCUMULATE_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except:
                    pass
    return records[-1] if records else None


def recycle_and_compare(current: dict, previous: dict) -> dict:
    """
    回收对比：拿当前记录和上一次对比，发现变化，产生洞察。
    这是循环的核心——每次都站在上一次的肩膀上往前走。
    """
    insights = []
    flags = []   # 值得注意的信号
    anomalies = []  # 异常信号，考虑写入失败日志

    prev_stats = previous.get("stats", {})
    curr_stats = current.get("stats", {})

    # --- 存储变化（阈值降低到1MB，模拟器也能感知） ---
    prev_avail = prev_stats.get("storage_avail_kb", 0)
    curr_avail = curr_stats.get("storage_avail_kb", 0)
    if isinstance(prev_avail, int) and isinstance(curr_avail, int) and prev_avail > 0:
        delta_mb = (curr_avail - prev_avail) / 1024
        if abs(delta_mb) > 1:
            direction = "减少" if delta_mb < 0 else "增加"
            insight = f"模拟器存储{direction}了 {abs(delta_mb):.1f} MB（{prev_avail//1024}MB -> {curr_avail//1024}MB）"
            insights.append(insight)
            if delta_mb < -100:
                anomalies.append(f"存储骤减 {abs(delta_mb):.0f}MB，可能有大文件写入")
                flags.append("STORAGE_DROP")

    # --- 内存变化（阈值降低到10MB） ---
    prev_mem = prev_stats.get("mem_avail_kb", 0)
    curr_mem = curr_stats.get("mem_avail_kb", 0)
    if isinstance(prev_mem, int) and isinstance(curr_mem, int) and prev_mem > 0:
        delta_mb = (curr_mem - prev_mem) / 1024
        if abs(delta_mb) > 10:
            direction = "释放" if delta_mb > 0 else "消耗"
            insights.append(f"模拟器内存{direction}了 {abs(delta_mb):.0f} MB（剩余{curr_mem//1024}MB）")
            if curr_mem < 500000:  # 低于500MB可用
                anomalies.append(f"内存可用量偏低: {curr_mem//1024}MB")
                flags.append("LOW_MEMORY")

    # --- APP数量变化 ---
    prev_apps = prev_stats.get("third_party_apps", 0)
    curr_apps = curr_stats.get("third_party_apps", 0)
    if isinstance(prev_apps, int) and isinstance(curr_apps, int):
        delta_apps = curr_apps - prev_apps
        if delta_apps > 0:
            insights.append(f"新增了 {delta_apps} 个第三方APP")
            flags.append("NEW_APP")
        elif delta_apps < 0:
            insights.append(f"减少了 {abs(delta_apps)} 个第三方APP")
            flags.append("APP_REMOVED")

    # --- 前台变化 ---
    prev_fg = prev_stats.get("foreground", "")
    curr_fg = curr_stats.get("foreground", "")
    if prev_fg and curr_fg and prev_fg != curr_fg:
        insights.append(f"前台切换: 有新的界面在运行")
        flags.append("FOREGROUND_CHANGED")

    # --- 设备状态变化 ---
    prev_online = previous.get("device_online", False)
    curr_online = current.get("device_online", False)
    if prev_online and not curr_online:
        anomalies.append("设备从在线变为离线！")
        flags.append("DEVICE_WENT_OFFLINE")

    # --- 电脑进程路况对比（CPU/内存起伏） ---
    prev_proc = previous.get("process_snapshot", {})
    curr_proc = current.get("process_snapshot", {})
    if prev_proc and curr_proc:
        prev_cpu = prev_proc.get("cpu_pct", -1)
        curr_cpu = curr_proc.get("cpu_pct", -1)
        prev_mem = prev_proc.get("mem_pct", -1)
        curr_mem_pct = curr_proc.get("mem_pct", -1)
        if prev_cpu >= 0 and curr_cpu >= 0:
            delta_cpu = curr_cpu - prev_cpu
            if abs(delta_cpu) >= 10:
                direction = "上升" if delta_cpu > 0 else "下降"
                insights.append(f"电脑CPU负载{direction} {abs(delta_cpu):.0f}%（{prev_cpu}% → {curr_cpu}%）")
                if curr_cpu > 80:
                    flags.append("HIGH_CPU")
                    anomalies.append(f"电脑CPU过高: {curr_cpu}%")
        if prev_mem >= 0 and curr_mem_pct >= 0:
            delta_mem = curr_mem_pct - prev_mem
            if abs(delta_mem) >= 5:
                direction = "升高" if delta_mem > 0 else "降低"
                insights.append(f"电脑内存占用{direction} {abs(delta_mem):.0f}%（{prev_mem}% → {curr_mem_pct}%）")
        # 告警数
        curr_alerts = curr_proc.get("alert_count", 0)
        if curr_alerts > 0:
            insights.append(f"进程路况有 {curr_alerts} 条告警，需关注")
            flags.append("PROCESS_ALERT")

    # 没有任何变化也是一种信息
    if not insights and curr_online:
        insights.append("设备状态稳定，无显著变化")

    result = {
        "insights": insights,
        "flags": flags,
        "anomalies": anomalies,
        "prev_cycle_id": previous.get("id", ""),
        "curr_cycle_id": current.get("id", ""),
    }

    return result


def write_insight(insight_record: dict):
    """写入迭代洞察日志"""
    with open(INSIGHT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(insight_record, ensure_ascii=False) + "\n")


def auto_log_anomaly(anomaly_text: str, cycle_id: str):
    """异常自动写入失败日志"""
    record = {
        "id": f"FAIL-AUTO-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "title": f"[自动检测] {anomaly_text}",
        "type": "PERCEPTION_BLIND",
        "type_label": "感知盲区（看不到屏幕/反馈）",
        "what_happened": anomaly_text,
        "root_cause": f"积累引擎在 {cycle_id} 周期自动检测到异常",
        "bypass_status": "UNKNOWN",
        "bypass_label": "尚未尝试绕过 [UNKNOWN]",
        "bypass_method": "",
        "lesson": "自动检测到的异常，需要人工研判",
        "tags": ["自动检测", "积累引擎", "异常"],
        "related_ids": [cycle_id],
    }
    with open(FAIL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────
# 主循环
# ─────────────────────────────────────────────

def accumulate_one_cycle(with_screenshot=None):
    """
    执行一次积累循环（含回收对比）
    with_screenshot: True/False/None(自动决定，约40%概率截图)
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cycle_id = f"ACC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 截图策略：不传参时约40%概率截图，降低行为特征密度
    if with_screenshot is None:
        with_screenshot = (random.random() < 0.4)

    # 先读上一次——站在上一次的肩膀上
    previous = load_last_record()

    record = {
        "id": cycle_id,
        "timestamp": timestamp,
        "device_online": False,
        "screenshot": "",
        "screenshot_size_kb": 0,
        "stats": {},
        "notes": [],
        "recycle": {},
    }

    # 1. 检查设备
    online, info = check_device()
    record["device_online"] = online

    if not online:
        record["notes"].append(f"设备离线: {info}")
        _write_log(record)
        return record

    # 2. 获取状态快照
    record["stats"] = get_device_stats()

    # 3. 截图（可选）
    if with_screenshot:
        ok, path = take_screenshot()
        if ok:
            record["screenshot"] = path
            record["screenshot_size_kb"] = round(os.path.getsize(path) / 1024, 1)
            record["notes"].append(f"截图: {os.path.basename(path)}")
        else:
            record["notes"].append("截图跳过")
    else:
        record["notes"].append("本轮无截图（低特征模式）")

    # 4. 回收对比
    if previous:
        recycle = recycle_and_compare(record, previous)
        record["recycle"] = recycle
        insight_record = {
            "timestamp": timestamp,
            "cycle_id": cycle_id,
            "prev_cycle_id": previous.get("id", ""),
            "insights": recycle["insights"],
            "flags": recycle["flags"],
        }
        write_insight(insight_record)
        for anomaly in recycle.get("anomalies", []):
            auto_log_anomaly(anomaly, cycle_id)
    else:
        record["recycle"] = {"insights": ["首次积累，无上次可对比"], "flags": [], "anomalies": []}

    # 5. 进程路况快照（任务管理器层感知）
    if _HAS_PROCESS_WATCH:
        try:
            pw = _process_watch(verbose=False)
            record["process_snapshot"] = {
                "cpu_pct":      pw["snapshot"].get("cpu_pct", -1),
                "mem_pct":      pw["snapshot"].get("mem_pct", -1),
                "alert_count":  pw.get("alert_count", 0),
                "top3":         pw.get("top5", [])[:3],
            }
            # 如果有卡死进程，写进本次notes
            for a in pw.get("alerts", []):
                if a.get("type") == "not_responding":
                    record["notes"].append(f"[路况告警] {a['msg']}")
        except Exception:
            pass

    # 6. 写入积累日志
    _write_log(record)
    return record


def _write_log(record):
    with open(ACCUMULATE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_accumulation_summary():
    """读取积累摘要"""
    if not os.path.exists(ACCUMULATE_LOG):
        return
    records = []
    with open(ACCUMULATE_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except:
                    pass
    total = len(records)
    screenshots = sum(1 for r in records if r.get("screenshot"))
    online_count = sum(1 for r in records if r.get("device_online"))

    summary = {
        "total_cycles": total,
        "online_rate": f"{online_count}/{total}",
        "screenshots": screenshots,
        "last_cycle": records[-1]["timestamp"] if records else "",
    }
    summary_path = os.path.join(BASE_DIR, "澜的积累摘要.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def run_loop():
    """
    随机间隔自循环：每次完成后，随机等待 20~45 分钟再执行下一次。
    由任务调度器启动一次，之后自己维持节奏。
    随机间隔：打散固定节拍特征，行为更自然。
    """
    while True:
        try:
            accumulate_one_cycle()
            read_accumulation_summary()
        except Exception:
            pass  # 静默失败，不崩溃
        # 随机等待 20~45 分钟
        wait_min = random.randint(20, 45)
        time.sleep(wait_min * 60)


if __name__ == "__main__":
    # 启动参数：
    #   无参数  → 自循环模式（随机间隔，长期运行）
    #   once    → 只跑一次（调试用）
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        accumulate_one_cycle(with_screenshot=True)
        read_accumulation_summary()
    else:
        run_loop()

