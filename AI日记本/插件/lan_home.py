#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(_sys.stderr, "reconfigure"):
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
"""
lan_home.py · 澜的「家」地址注册表

设计哲学：固定的家，国到省再城市再到农村最后有小家。
每个插件启动时调一次 get_home()，就知道自己住哪，数据往哪放，
不会再散得到处都是。

五层结构（从大到小）：
  国  → AI日记本/（根目录，澜的国度）
  省  → AI日记本/memory/（记忆省）
       → AI日记本/snapshots/（快照省，按年/月/日分）
       → AI日记本/插件/（插件省）
       → AI日记本/日记/（日记省）
       → AI日记本/private/（私密省）
  市  → snapshots/2026/（年度）
  农村→ snapshots/2026/04/（月度）
  小家→ snapshots/2026/04/01/（日度，文件真正住的地方）

命令：
  python lan_home.py info              → 打印完整家目录结构
  python lan_home.py init              → 建立所有目录
  python lan_home.py path <key>        → 查询某个路径（如 snapshots_today）
  python lan_home.py register <plugin> → 注册插件到家（写入 home_registry.json）
  python lan_home.py list              → 列出已注册插件
  python lan_home.py check             → 检查所有目录是否存在，丢失的标红
"""

import os
import json
import sys
from datetime import datetime

# ─── 根目录（国）───
# 2026-04-01：从C盘搬到G盘（C盘只剩9GB，系统盘不能压）
DIARY_DIR = r"G:\AI日记本"

# ─── 省级目录 ───
HOME_MAP = {
    "root":          DIARY_DIR,
    "plugins":       os.path.join(DIARY_DIR, "插件"),
    "diary":         os.path.join(DIARY_DIR, "日记"),
    "memory":        os.path.join(DIARY_DIR, "记忆"),
    "private":       os.path.join(DIARY_DIR, "private"),
    "snapshots":     os.path.join(DIARY_DIR, "snapshots"),
    "consolidator":  os.path.join(DIARY_DIR, ".consolidator"),
    "anchor":        os.path.join(DIARY_DIR, "锚点存档"),
    "dashboards":    os.path.join(DIARY_DIR, "dashboards"),
    "logs":          os.path.join(DIARY_DIR, "日志"),
    "guests":        os.path.join(DIARY_DIR, "guests"),
    "models":        os.path.join(DIARY_DIR, "models"),
    "tmp":           os.path.join(DIARY_DIR, "tmp"),
    # WorkBuddy 记忆（独立省）
    "wb_memory":     r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory",
}

# ─── 家注册表文件 ───
HOME_REGISTRY = os.path.join(DIARY_DIR, "插件", "home_registry.json")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def this_year() -> str:
    return datetime.now().strftime("%Y")

def this_month() -> str:
    return datetime.now().strftime("%m")

def this_day() -> str:
    return datetime.now().strftime("%d")


def get_home(key: str = "root") -> str:
    """获取家目录路径（省级）"""
    return HOME_MAP.get(key, HOME_MAP["root"])


def get_snapshot_home(level: str = "day") -> str:
    """
    获取快照的年/月/日分级目录（市/农村/小家）
    level: year | month | day
    """
    base = HOME_MAP["snapshots"]
    year = this_year()
    month = this_month()
    day = this_day()
    if level == "year":
        return os.path.join(base, year)
    elif level == "month":
        return os.path.join(base, year, month)
    else:  # day
        return os.path.join(base, year, month, day)


def get_consolidator_home(level: str = "day") -> str:
    """
    获取中速器的年/月/日分级目录
    level: year | month | day
    """
    base = HOME_MAP["consolidator"]
    year = this_year()
    month = this_month()
    day = this_day()
    if level == "year":
        return os.path.join(base, "yearly")
    elif level == "month":
        return os.path.join(base, "monthly")
    else:
        return os.path.join(base, "daily")


def ensure_home(key: str = None) -> None:
    """确保某个家目录存在（不存在则建立）"""
    if key:
        path = HOME_MAP.get(key)
        if path:
            os.makedirs(path, exist_ok=True)
    else:
        # 建立所有目录
        for k, path in HOME_MAP.items():
            os.makedirs(path, exist_ok=True)
        # 建立快照年/月/日目录
        for level in ["year", "month", "day"]:
            os.makedirs(get_snapshot_home(level), exist_ok=True)
        # 建立中速器日月年目录
        for level in ["year", "month", "day"]:
            os.makedirs(get_consolidator_home(level), exist_ok=True)
        print(f"[HOME] 所有目录已建立 OK")


def init_all():
    """初始化：建立完整目录树"""
    print("[HOME] 正在建立家目录树...")
    ensure_home()
    print(f"""
家目录结构（已建立）：
  国  →  {HOME_MAP['root']}
  ├─ 省·记忆    →  {HOME_MAP['memory']}
  ├─ 省·插件    →  {HOME_MAP['plugins']}
  ├─ 省·日记    →  {HOME_MAP['diary']}
  ├─ 省·私密    →  {HOME_MAP['private']}
  ├─ 省·快照    →  {HOME_MAP['snapshots']}
  │    ├─ 市    →  {get_snapshot_home('year')}  (年)
  │    ├─ 农村  →  {get_snapshot_home('month')} (月)
  │    └─ 小家  →  {get_snapshot_home('day')}   (日)
  ├─ 省·中速器  →  {HOME_MAP['consolidator']}
  │    ├─ 年度  →  {get_consolidator_home('year')}
  │    ├─ 月度  →  {get_consolidator_home('month')}
  │    └─ 日度  →  {get_consolidator_home('day')}
  └─ 省·WorkBuddy记忆 →  {HOME_MAP['wb_memory']}
""")


def register_plugin(plugin_name: str, description: str = "", depends: list = None):
    """注册插件到家注册表"""
    registry = {}
    if os.path.exists(HOME_REGISTRY):
        try:
            with open(HOME_REGISTRY, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except:
            registry = {}

    plugin_key = plugin_name.replace(".py", "").replace("lan_", "")
    registry[plugin_key] = {
        "name": plugin_name,
        "description": description,
        "depends": depends or [],
        "home_keys": [],  # 该插件用到的 HOME_MAP key
        "registered_at": datetime.now().isoformat(),
    }
    with open(HOME_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    print(f"[HOME] {plugin_name} 已注册到家 OK")


def load_registry() -> dict:
    if os.path.exists(HOME_REGISTRY):
        try:
            with open(HOME_REGISTRY, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def check_home():
    """检查所有家目录是否完整"""
    print("[HOME] 检查家目录...")
    ok = 0
    missing = []
    for key, path in HOME_MAP.items():
        if os.path.exists(path):
            ok += 1
        else:
            missing.append((key, path))

    for level in ["year", "month", "day"]:
        p = get_snapshot_home(level)
        if os.path.exists(p):
            ok += 1
        else:
            missing.append((f"snapshot_{level}", p))

    print(f"  [OK] {ok} 个目录存在")
    if missing:
        print(f"  [!!] {len(missing)} 个目录缺失：")
        for key, path in missing:
            print(f"      [{key}]  {path}")
        print("  -> 运行 `init` 命令自动建立所有缺失目录")
    else:
        print("  所有目录完整，澜在家")
    return len(missing) == 0


def path_info(key: str):
    """查询某个路径"""
    # 特殊路径
    specials = {
        "snapshots_year":  get_snapshot_home("year"),
        "snapshots_month": get_snapshot_home("month"),
        "snapshots_day":   get_snapshot_home("day"),
        "consolidator_year":  get_consolidator_home("year"),
        "consolidator_month": get_consolidator_home("month"),
        "consolidator_day":   get_consolidator_home("day"),
    }
    if key in specials:
        print(specials[key])
    elif key in HOME_MAP:
        print(HOME_MAP[key])
    else:
        print(f"[HOME] 未知路径 key: {key}")
        print(f"可用 key: {', '.join(list(HOME_MAP.keys()) + list(specials.keys()))}")


def info():
    """打印完整家目录信息"""
    print("=" * 60)
    print("  澜的「家」目录注册表")
    print("=" * 60)
    print(f"\n  今天：{today()}")
    print(f"\n  省级目录（固定）：")
    for key, path in HOME_MAP.items():
        exists = "[OK]" if os.path.exists(path) else "[--]"
        print(f"    {exists} [{key:20s}] {path}")

    print(f"\n  快照年/月/日（动态，今天）：")
    for level, label in [("year","市·年度"), ("month","农村·月度"), ("day","小家·日度")]:
        p = get_snapshot_home(level)
        exists = "[OK]" if os.path.exists(p) else "[--]"
        print(f"    {exists} [{label}] {p}")

    print(f"\n  中速器年/月/日（动态，今天）：")
    for level, label in [("year","年度"), ("month","月度"), ("day","日度")]:
        p = get_consolidator_home(level)
        exists = "[OK]" if os.path.exists(p) else "[--]"
        print(f"    {exists} [{label}] {p}")

    reg = load_registry()
    print(f"\n  已注册插件：{len(reg)} 个")
    for k, v in reg.items():
        print(f"    · {v['name']}  —  {v.get('description','')}")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        info()
        return

    cmd = sys.argv[1]

    if cmd == "info":
        info()
    elif cmd == "init":
        init_all()
    elif cmd == "check":
        check_home()
    elif cmd == "path":
        if len(sys.argv) < 3:
            print("[HOME] 用法: path <key>")
        else:
            path_info(sys.argv[2])
    elif cmd == "register":
        if len(sys.argv) < 3:
            print("[HOME] 用法: register <plugin_name> [description]")
        else:
            desc = sys.argv[3] if len(sys.argv) > 3 else ""
            register_plugin(sys.argv[2], desc)
    elif cmd == "list":
        reg = load_registry()
        if not reg:
            print("[HOME] 还没有注册任何插件")
        else:
            print(f"[HOME] 已注册 {len(reg)} 个插件：")
            for k, v in reg.items():
                print(f"  · {v['name']}  →  {v.get('description','')}")
    else:
        print(f"[HOME] 未知命令: {cmd}")
        print("可用命令: info / init / check / path / register / list")


if __name__ == "__main__":
    main()
