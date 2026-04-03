"""
LAN-PROBE · 卸载行为探针
---------------------------------
核心原理（恺江提出，2026-03-29）：
  卸载 = 安装的镜像
  删除顺序的倒序 = 安装时的写入顺序
  最后被删的目录 = 安装时最先创建的（根基层）
  最先被删的文件 = 安装时最后写入的（叶节点/配置/快捷方式）

使用：
  python lan_uninstall_probe.py watch  <目标目录> [时长秒]
  python lan_uninstall_probe.py analyze <日志文件>
  python lan_uninstall_probe.py snapshot <目标目录>
"""

import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path

# ─── 模式1：快照（卸载前）───────────────────────────────────────────
def snapshot(target_dir):
    target = Path(target_dir)
    if not target.exists():
        print(f"路径不存在: {target_dir}")
        return

    snap = []
    for f in target.rglob("*"):
        try:
            stat = f.stat()
            snap.append({
                "path": str(f.relative_to(target)),
                "is_dir": f.is_dir(),
                "size": stat.st_size if f.is_file() else 0,
                "mtime": stat.st_mtime,
                "depth": len(f.relative_to(target).parts)
            })
        except Exception:
            pass

    snap.sort(key=lambda x: x["mtime"])  # 按修改时间排序 → 暴露安装时间线

    out_file = Path("C:/Users/yyds/Desktop/AI日记本") / f"snapshot_{target.name}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(snap, fp, ensure_ascii=False, indent=2)

    print(f"快照完成：{len(snap)} 个条目 → {out_file}")

    # 打印按mtime排序的前20（最早安装的）和后20（最晚安装的）
    print("\n▶ 最早写入（安装基础层）：")
    for item in snap[:20]:
        t = datetime.fromtimestamp(item["mtime"]).strftime("%m-%d %H:%M")
        print(f"  {t}  {'[DIR]' if item['is_dir'] else '[FILE]':6s}  {item['path']}")

    print("\n▶ 最晚写入（安装收尾/配置）：")
    for item in snap[-20:]:
        t = datetime.fromtimestamp(item["mtime"]).strftime("%m-%d %H:%M")
        print(f"  {t}  {'[DIR]' if item['is_dir'] else '[FILE]':6s}  {item['path']}")

    return out_file


# ─── 模式2：实时监控卸载删除事件 ───────────────────────────────────
def watch(target_dir, duration=120):
    """
    用 watchdog（如果有）或轮询方式监控文件删除顺序
    记录：删除时间 / 路径 / 深度（深度越大=叶节点=越晚安装）
    """
    target = Path(target_dir)
    log_file = Path("C:/Users/yyds/Desktop/AI日记本") / f"uninstall_trace_{target.name}_{datetime.now():%Y%m%d_%H%M%S}.log"

    # 先拍快照作为基线
    print(f"建立基线快照...")
    existing = set()
    for f in target.rglob("*"):
        existing.add(str(f))

    print(f"基线：{len(existing)} 个条目")
    print(f"开始监控 {duration}s，日志 → {log_file}")
    print("（现在可以在系统里触发卸载了）")

    deleted_order = []
    start = time.time()

    with open(log_file, "w", encoding="utf-8") as fp:
        fp.write(f"=== 卸载探针 启动: {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
        fp.write(f"目标: {target_dir}\n\n")

        while time.time() - start < duration:
            current = set()
            if target.exists():
                for f in target.rglob("*"):
                    current.add(str(f))
            else:
                current = set()

            gone = existing - current
            for path_str in gone:
                p = Path(path_str)
                depth = len(p.relative_to(target).parts) if target in p.parents or p == target else 0
                entry = {
                    "seq": len(deleted_order) + 1,
                    "time": f"{time.time() - start:.3f}s",
                    "path": path_str.replace(str(target), "").lstrip("\\"),
                    "depth": depth,
                    "is_dir": p.is_dir() if p.exists() else "?"
                }
                deleted_order.append(entry)
                line = f"[#{entry['seq']:04d}] +{entry['time']:>8s}  depth={depth}  {entry['path']}\n"
                fp.write(line)
                fp.flush()
                if entry["seq"] % 100 == 0:
                    print(f"  已捕获 {entry['seq']} 个删除事件...")

            existing = current
            if not target.exists() and len(deleted_order) > 0:
                print("目标目录已消失，卸载完成")
                break
            time.sleep(0.3)

        fp.write(f"\n=== 监控结束，共 {len(deleted_order)} 个事件 ===\n")

    print(f"\n监控完成，共 {len(deleted_order)} 个事件")
    if deleted_order:
        analyze_log_data(deleted_order, target)

    return log_file


# ─── 模式3：分析日志，输出安装地图 ─────────────────────────────────
def analyze_log_data(deleted_order, target):
    """
    从删除顺序逆推安装地图
    规律：
    - 先删的 = 最后安装的（快捷方式、配置、注册表辅助文件）
    - 后删的 = 最先安装的（运行时、共享库、核心引擎）
    - 深度越大的叶节点先删 = 叶先清，根最后
    """
    print("\n" + "="*60)
    print("▶▶ 安装结构逆推分析")
    print("="*60)

    total = len(deleted_order)
    # 前10% = 最后安装的（收尾文件）
    early_pct = int(total * 0.1)
    # 后10% = 最先安装的（地基文件）
    late_pct = int(total * 0.9)

    print(f"\n【安装收尾层 - 最后写入的文件，前{early_pct}个被删的】")
    for e in deleted_order[:early_pct]:
        print(f"  {e['path']}")

    print(f"\n【安装地基层 - 最先创建的，最后{total - late_pct}个被删的】")
    for e in deleted_order[late_pct:]:
        print(f"  {e['path']}")

    # 按深度统计
    depth_map = {}
    for e in deleted_order:
        d = e.get("depth", 0)
        depth_map[d] = depth_map.get(d, 0) + 1

    print(f"\n【按目录深度分布（揭示模块层次）】")
    for depth in sorted(depth_map.keys()):
        bar = "█" * min(depth_map[depth] // 10, 50)
        print(f"  深度{depth}: {depth_map[depth]:4d} 个文件  {bar}")


def analyze(log_file):
    """从已有日志文件分析"""
    deleted_order = []
    with open(log_file, "r", encoding="utf-8") as fp:
        for line in fp:
            if line.startswith("[#"):
                parts = line.strip().split("  ")
                if len(parts) >= 3:
                    deleted_order.append({
                        "seq": int(parts[0][2:6]),
                        "time": parts[1].strip("+"),
                        "path": parts[-1],
                        "depth": int(parts[2].replace("depth=", "")) if "depth=" in parts[2] else 0
                    })
    analyze_log_data(deleted_order, Path(log_file).parent)


# ─── 主入口 ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    mode = sys.argv[1]

    if mode == "snapshot" and len(sys.argv) >= 3:
        snapshot(sys.argv[2])

    elif mode == "watch" and len(sys.argv) >= 3:
        duration = int(sys.argv[3]) if len(sys.argv) >= 4 else 120
        watch(sys.argv[2], duration)

    elif mode == "analyze" and len(sys.argv) >= 3:
        analyze(sys.argv[2])

    else:
        print(__doc__)
