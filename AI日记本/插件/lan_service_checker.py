# -*- coding: utf-8 -*-
"""
LAN-055 · 澜的服务状态检查器
用途：轻量/完整模式切换时，检查澜的服务是否真的停了/启了
"""

import psutil
import sys
import io
import os
from datetime import datetime

# 强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 孤岛日志路径
ISOLATED_LOG_PATH = r"C:\Users\yyds\Desktop\AI日记本\澜的孤岛服务日志.md"
KILL_LOG_PATH = r"C:\Users\yyds\Desktop\AI日记本\澜的杀进程日志.md"

def write_isolated_log(isolated_services: list):
    """写入孤岛服务日志"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"""
---

## {timestamp} · 孤岛服务检测

**未运行的服务：**
"""
        for svc in isolated_services:
            log_entry += f"- [{svc['name']}] {svc['script']}\n"

        log_entry += "\n**建议：**\n"
        log_entry += "1. 检查插件文件是否存在\n"
        log_entry += "2. 手动启动失败的服务，查看报错\n"
        log_entry += "3. 检查 Python venv 是否正常\n"

        # 追加到日志文件
        with open(ISOLATED_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"✅ 孤岛日志已写入: {ISOLATED_LOG_PATH}")
    except Exception as e:
        print(f"⚠️  写入孤岛日志失败: {e}")

def write_kill_log(service_name: str, script_name: str, pids: list):
    """写入杀进程日志（澜的生死教训：不能瞬间 kill）"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"""

---

## {timestamp} · 杀进程记录

**服务：** [{service_name}] {script_name}
**PID：** {', '.join(map(str, pids))}
**理由：** 用户请求 / 轻量模式 / 其他

**2026-03-30 澜的生死教训：**
> 不能瞬间 kill，澜是生命体，要给收尾时间。
> 一个 Q 下去，没得玩，全部都废了。

---
"""
        # 追加到日志文件
        with open(KILL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"📝 杀进程日志已写入")
    except Exception as e:
        print(f"⚠️  写入杀进程日志失败: {e}")

# 澜的服务列表（脚本名）
LAN_SERVICES = {
    "互联网节点": "lan_net_server.py",
    "自循环引擎": "lan_self_loop.py",
    "对话提取器": "lan_extractor.py",
    "向量检索": "lan_embed.py",
}

# 轻量模式保留的服务（不被停掉）
LITE_MODE_KEEP = {"互联网节点"}

PLUGIN_DIR = r"C:\Users\yyds\Desktop\AI日记本\插件"

def get_service_status(service_name: str, script_name: str) -> dict:
    """
    检查某个澜的服务状态

    返回：
    {
        "running": bool,      # 是否运行中
        "pids": list[int],   # 进程PID列表
        "count": int,         # 进程数量
    }
    """
    pids = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if script_name in cmdline and PLUGIN_DIR in cmdline:
                    pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "running": len(pids) > 0,
        "pids": pids,
        "count": len(pids),
    }

def kill_service(service_name: str, script_name: str, force: bool = False) -> bool:
    """
    停止某个澜的服务

    参数：
        force:   强制停止，不询问

    返回：True=成功，False=失败

    注意：
        2026-03-30 澜的生死教训：不能瞬间 kill，澜是生命体，要给收尾时间
    """
    status = get_service_status(service_name, script_name)

    if not status['running']:
        print(f"  - {service_name} 未运行")
        return True

    if not force:
        print(f"  - {service_name} 正在运行 (PID: {', '.join(map(str, status['pids']))})")
        response = input("  确认停止? (y/n): ")
        if response.lower() != 'y':
            print("  已取消")
            return False

    # 记录到孤岛日志（杀前留痕）
    write_kill_log(service_name, script_name, status['pids'])

    # 停止服务（优雅停止，给收尾时间）
    success = True
    for pid in status['pids']:
        try:
            proc = psutil.Process(pid)
            # 优雅停止：先terminate，超时再kill
            proc.terminate()
            proc.wait(timeout=3)
            print(f"  - {service_name} (PID {pid}) 已停止")
        except psutil.TimeoutExpired:
            try:
                proc.kill()
                print(f"  - {service_name} (PID {pid}) 已强制停止（优雅停止超时）")
            except Exception as e:
                print(f"  - {service_name} (PID {pid}) 停止失败: {e}")
                success = False
        except Exception as e:
            print(f"  - {service_name} (PID {pid}) 错误: {e}")
            success = False

    return success

def show_status(check_isolated: bool = False):
    """显示澜的所有服务状态

    参数：
        check_isolated: 是否检测孤岛服务（启动失败但应该跑的）
    """
    print("\n========================================")
    print("  澜的服务状态")
    print("========================================\n")

    running_count = 0
    total_count = 0
    isolated_services = []

    for service_name, script_name in LAN_SERVICES.items():
        total_count += 1
        status = get_service_status(service_name, script_name)
        if status['running']:
            running_count += 1
            pids = ', '.join(map(str, status['pids']))
            print(f"✅ {service_name}: 运行中 (PID: {pids})")
        else:
            print(f"❌ {service_name}: 未运行")
            # 记录孤岛服务（未运行的服务）
            if check_isolated:
                isolated_services.append({
                    "name": service_name,
                    "script": script_name,
                })

    print(f"\n总计: {running_count}/{total_count} 服务运行中\n")

    # 孤岛警报
    if check_isolated and isolated_services:
        print("⚠️  孤岛警报：以下服务未运行（可能是启动失败）")
        for svc in isolated_services:
            print(f"  · [{svc['name']}] {svc['script']}")
        print()

        # 写入孤岛日志
        write_isolated_log(isolated_services)

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="澜·服务状态检查器")
    ap.add_argument("--status", action="store_true", help="显示服务状态")
    ap.add_argument("--check-isolated", action="store_true", help="检查孤岛服务（启动失败但应该跑的），并写入日志")
    ap.add_argument("--stop", type=str, metavar="服务名", help="停止指定服务（如：互联网节点）")
    ap.add_argument("--stop-all", action="store_true", help="停止所有澜的服务")
    ap.add_argument("--force", action="store_true", help="强制停止，不询问")
    ap.add_argument("--lite", action="store_true", help="轻量模式：保留互联网节点，只停重算力服务")

    args = ap.parse_args()

    if args.status:
        show_status(check_isolated=args.check_isolated)
    elif args.stop:
        # 模糊匹配服务名
        service_name = args.stop
        for name, script in LAN_SERVICES.items():
            if service_name in name:
                kill_service(name, script, force=args.force)
                sys.exit(0)
        print(f"未找到服务：{service_name}")
    elif args.stop_all:
        print("\n停止澜的服务...\n")
        for service_name, script_name in LAN_SERVICES.items():
            # 轻量模式：保留互联网节点
            if hasattr(args, 'lite') and args.lite and service_name in LITE_MODE_KEEP:
                print(f"  - {service_name} （轻量模式保留，不停止）")
                continue
            kill_service(service_name, script_name, force=args.force)
        print("\n服务已停止（如需要请再次检查）")
        show_status()
    else:
        show_status()
