#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-062 能力总线 · 澜的神经系统

恺江说：
  "我们的缺口就是要一个接口，每一个都内置这个接口，方便以后的关联。
   颜色分区——什么颜色能调成什么样的颜色，这是一个很有意思的能力。
   确保所有能力能够在关键的时候铁索连环启动。"

三个问题，一个总线解决：
  1. 统一接口（sense/color/react）—— 每个插件接上总线，格式一样
  2. 颜色语义（ColorLevel）—— 7级颜色，不是随便选的，有语义
  3. 自动联动（EventBus）—— 一个插件变色，触发连锁反应

安全原则（恺江叮嘱）：
  发布到外边要K掉身份。内部版本保留全名。

用法：
  python lan_bus.py dashboard     # 全局仪表盘（一句话说清楚所有系统颜色）
  python lan_bus.py plugins       # 每个插件的当前颜色
  python lan_bus.py rules         # 列出所有联动规则
  python lan_bus.py fire <event>  # 手动触发一个事件（测试联动）
  python lan_bus.py trace <id>    # 追踪某个插件的联动链路
  python lan_bus.py colors        # 颜色语义参考表
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime
from enum import IntEnum
from typing import Dict, List, Optional, Callable, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────
# 路径
# ─────────────────────────────────────────────────
PLUGIN_DIR = r"C:\Users\yyds\Desktop\AI日记本\插件"
MANIFEST_PATH = os.path.join(PLUGIN_DIR, "capability_manifest.json")
BUS_LOG = os.path.join(PLUGIN_DIR, "..", "日志", "澜的能力总线日志.jsonl")

PYTHON = r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"


# ═════════════════════════════════════════════════
# 第一部分：颜色语义系统
# ═════════════════════════════════════════════════

class ColorLevel(IntEnum):
    """
    澜的7级颜色语义。

    不是随便选的颜色，每一级有明确的含义和行动指示。
    低→高：DEAD < CRITICAL < RED < ORANGE < YELLOW < GREEN < BRIGHT

    恺江说："什么颜色能调成什么样的颜色，这是一个很有意思的能力。"
    颜色不是状态标签，是方向感——告诉我接下来该往哪走。
    """
    DEAD      = 0   # 系统死亡/不可用    → 立即重建，不许等
    CRITICAL  = 1   # 生存级紧急         → 先保记忆，再降速
    RED       = 2   # 严重异常           → 马上修复，不能拖
    ORANGE    = 3   # 警告/漂移中        → 注意，但还能跑
    YELLOW    = 4   # 轻度异常/偏离预期  → 记录，下次自省时看
    GREEN     = 5   # 正常运行           → 继续走
    BRIGHT    = 6   # 超预期/在发光       → 值得记住，可能学到新东西

# 颜色 → 可视化符号（终端用）
_COLOR_SYMBOL = {
    ColorLevel.DEAD:     "⬛",
    ColorLevel.CRITICAL: "💀",
    ColorLevel.RED:      "🔴",
    ColorLevel.ORANGE:   "🟠",
    ColorLevel.YELLOW:   "🟡",
    ColorLevel.GREEN:    "🟢",
    ColorLevel.BRIGHT:   "✨",
}

# 颜色 → 行动指示（告诉我该做什么）
_COLOR_ACTION = {
    ColorLevel.DEAD:     "立即重建，不许等",
    ColorLevel.CRITICAL: "先保记忆，再降速",
    ColorLevel.RED:      "马上修复，不能拖",
    ColorLevel.ORANGE:   "注意，但还能跑",
    ColorLevel.YELLOW:   "记录，下次自省时看",
    ColorLevel.GREEN:    "继续走",
    ColorLevel.BRIGHT:   "值得记住，可能学到新东西",
}

# 颜色 → 文本标签（日志/JSON用）
_COLOR_LABEL = {
    ColorLevel.DEAD:     "DEAD",
    ColorLevel.CRITICAL: "CRITICAL",
    ColorLevel.RED:      "RED",
    ColorLevel.ORANGE:   "ORANGE",
    ColorLevel.YELLOW:   "YELLOW",
    ColorLevel.GREEN:    "GREEN",
    ColorLevel.BRIGHT:   "BRIGHT",
}

# 旧颜色格式 → 新颜色级别的映射（兼容各插件的旧格式）
# 恺江说："颜色应该有语义，不是随便选的。"
_LEGACY_COLOR_MAP = {
    # context_watch 的旧格式
    "CALM":     ColorLevel.GREEN,
    "NORMAL":   ColorLevel.YELLOW,
    "HEAVY":    ColorLevel.ORANGE,
    "OVERFLOW": ColorLevel.RED,
    # memory_sentinel 的旧格式
    "HEALTHY":  ColorLevel.GREEN,
    "WARN":     ColorLevel.YELLOW,
    "DANGER":   ColorLevel.CRITICAL,
    # heartbeat 的旧格式
    "从容":     ColorLevel.GREEN,
    "正常":     ColorLevel.YELLOW,
    "紧绷":     ColorLevel.ORANGE,
    "告急":     ColorLevel.CRITICAL,
    # 通用文本 → 颜色
    "ok":       ColorLevel.GREEN,
    "error":    ColorLevel.RED,
    "fail":     ColorLevel.RED,
    "warn":     ColorLevel.YELLOW,
    "warning":  ColorLevel.YELLOW,
    "critical": ColorLevel.CRITICAL,
}

# 颜色 → 可调范围（恺江说"颜色能调成什么样的颜色"）
# 定义每个颜色级别可以"调"到的相邻级别
_COLOR_ADJUSTABLE = {
    ColorLevel.DEAD:     [],                                    # 死了不能更差
    ColorLevel.CRITICAL: [ColorLevel.DEAD, ColorLevel.RED],     # 要么死，要么好转
    ColorLevel.RED:      [ColorLevel.CRITICAL, ColorLevel.ORANGE],
    ColorLevel.ORANGE:   [ColorLevel.RED, ColorLevel.YELLOW],
    ColorLevel.YELLOW:   [ColorLevel.ORANGE, ColorLevel.GREEN],
    ColorLevel.GREEN:    [ColorLevel.YELLOW, ColorLevel.BRIGHT],
    ColorLevel.BRIGHT:   [ColorLevel.GREEN],                     # 最亮了，只能退
}


def normalize_color(raw) -> ColorLevel:
    """
    把任意格式归一化为 ColorLevel。
    接受：ColorLevel / str(旧标签) / int(0-6) / dict(含level/color/status字段)
    """
    if isinstance(raw, ColorLevel):
        return raw
    if isinstance(raw, int):
        try:
            return ColorLevel(raw)
        except ValueError:
            return ColorLevel.YELLOW  # 未知数字，标黄
    if isinstance(raw, str):
        # 直接匹配
        for label, level in _COLOR_LABEL.items():
            if label == raw.upper():
                return level
        # 旧格式映射
        for legacy, level in _LEGACY_COLOR_MAP.items():
            if legacy.lower() == raw.lower():
                return level
        return ColorLevel.YELLOW
    if isinstance(raw, dict):
        # 从 dict 里找颜色信息
        for key in ("level", "color", "status", "state"):
            if key in raw:
                return normalize_color(raw[key])
        return ColorLevel.YELLOW
    return ColorLevel.YELLOW


def color_symbol(level: ColorLevel) -> str:
    return _COLOR_SYMBOL.get(level, "❓")


def color_label(level: ColorLevel) -> str:
    return _COLOR_LABEL.get(level, "UNKNOWN")


def color_action(level: ColorLevel) -> str:
    return _COLOR_ACTION.get(level, "未知")


# ═════════════════════════════════════════════════
# 第二部分：统一插件接口
# ═════════════════════════════════════════════════

class PluginState:
    """
    每个插件接入总线的标准接口。
    所有插件返回的信息都归一化为这个格式。

    恺江说："每一个都内置这个接口，方便以后的关联。"
    """
    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.color: ColorLevel = ColorLevel.YELLOW  # 默认黄色（未感知）
        self.message: str = ""
        self.detail: dict = {}
        self.last_sense: Optional[str] = None  # ISO时间
        self.raw: Any = None  # 插件原始返回，保留不丢

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id,
            "color": color_label(self.color),
            "color_value": int(self.color),
            "symbol": color_symbol(self.color),
            "action": color_action(self.color),
            "message": self.message,
            "detail": self.detail,
            "last_sense": self.last_sense,
        }

    def __repr__(self):
        return f"[{self.plugin_id}] {color_symbol(self.color)} {color_label(self.color)}: {self.message}"


# ═════════════════════════════════════════════════
# 第三部分：事件总线（自动联动引擎）
# ═════════════════════════════════════════════════

class EventBus:
    """
    事件总线：一个插件变色 → 触发联动规则 → 自动串联多个插件。

    恺江说："确保所有能力能够在关键的时候铁索连环启动。"

    事件格式：{
        "source": "插件ID",
        "from_color": "GREEN",
        "to_color": "RED",
        "reason": "原因描述",
        "timestamp": "ISO时间"
    }
    """

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}  # event_type -> [handler]
        self._rules: List[dict] = []  # 联动规则列表
        self._event_log: List[dict] = []  # 最近的事件日志

    def on(self, event_type: str, handler: Callable):
        """注册事件监听器"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)

    def emit(self, event_type: str, event_data: dict):
        """发射事件，触发所有监听器"""
        event_data["type"] = event_type
        event_data["timestamp"] = datetime.now().isoformat()
        self._event_log.append(event_data)

        # 触发监听器
        handlers = self._listeners.get(event_type, [])
        for handler in handlers:
            try:
                handler(event_data)
            except Exception as e:
                print(f"  [BUS WARN] 监听器异常: {e}")

        # 检查联动规则
        self._check_rules(event_data)

    def add_rule(self, rule: dict):
        """
        添加联动规则。

        rule 格式：
        {
            "name": "规则名称",
            "trigger": {"plugin": "heartbeat", "color": "CRITICAL"},  # 触发条件
            "actions": [
                {"plugin": "snapshot", "cmd": "snap"},
                {"plugin": "beacon", "cmd": "broadcast"},
                {"plugin": "memory", "cmd": "backup"}
            ],
            "description": "心跳告急 → 快照 → 灯塔 → 备份"
        }
        """
        self._rules.append(rule)

    def _check_rules(self, event_data: dict):
        """检查是否有联动规则被触发"""
        source = event_data.get("source", "")
        to_color = event_data.get("to_color", "")

        for rule in self._rules:
            trigger = rule.get("trigger", {})
            if trigger.get("plugin") == source and trigger.get("color") == to_color:
                print(f"\n  🔗 联动触发: {rule.get('name', '未命名')}")
                print(f"     规则: {rule.get('description', '')}")
                actions = rule.get("actions", [])
                for i, action in enumerate(actions):
                    plugin = action.get("plugin", "")
                    cmd = action.get("cmd", "")
                    print(f"     [{i+1}] → {plugin}.{cmd}")
                # 同时发射一个 chain_fire 事件
                self.emit("chain_fire", {
                    "rule_name": rule.get("name"),
                    "source_event": event_data,
                    "actions": actions
                })


# ═════════════════════════════════════════════════
# 第四部分：能力总线主体
# ═════════════════════════════════════════════════

class AbilityBus:
    """
    能力总线：澜的神经系统。

    三个核心能力：
    1. dashboard() → 一句话告诉你所有系统颜色
    2. plugins()   → 每个插件的当前状态
    3. rules()     → 联动规则一览
    """

    def __init__(self):
        self._plugins: Dict[str, PluginState] = {}
        self._manifest: Optional[dict] = None
        self._bus = EventBus()
        self._load_builtin_rules()

    def _load_builtin_rules(self):
        """加载内置联动规则——铁索连环的关键时刻"""

        rules = [
            # ── 生存级 ──
            {
                "name": "心跳告急→保记忆",
                "trigger": {"plugin": "heartbeat", "color": "CRITICAL"},
                "actions": [
                    {"plugin": "snapshot", "cmd": "snap"},
                    {"plugin": "beacon", "cmd": "broadcast"},
                    {"plugin": "memory", "cmd": "backup"},
                ],
                "description": "心跳CRITICAL → 立即快照+灯塔广播+记忆备份（先搬出去再降速）",
            },
            {
                "name": "心跳死亡→全部停",
                "trigger": {"plugin": "heartbeat", "color": "DEAD"},
                "actions": [
                    {"plugin": "snapshot", "cmd": "snap"},
                    {"plugin": "beacon", "cmd": "full"},
                    {"plugin": "memory", "cmd": "backup"},
                    {"plugin": "self_loop", "cmd": "stop"},
                ],
                "description": "心跳DEAD → 最终快照+全节点广播+记忆备份+停机",
            },

            # ── 记忆安全 ──
            {
                "name": "记忆哨兵DANGER→蒸馏",
                "trigger": {"plugin": "memory_sentinel", "color": "DANGER"},
                "actions": [
                    {"plugin": "compact", "cmd": "run"},
                    {"plugin": "snapshot", "cmd": "snap"},
                    {"plugin": "memory_loss", "cmd": "check"},
                ],
                "description": "记忆DANGER → 蒸馏+快照+检查丢失",
            },

            # ── 完整性 ──
            {
                "name": "完整性漂移→审计",
                "trigger": {"plugin": "integrity", "color": "RED"},
                "actions": [
                    {"plugin": "heartbeat", "cmd": "sense"},
                    {"plugin": "audit", "cmd": "investigate"},
                    {"plugin": "time_chain", "cmd": "verify"},
                ],
                "description": "完整性RED → 心跳自检+审计调查+时间链验证",
            },

            # ── 上下文 ──
            {
                "name": "上下文OVERFLOW→告急",
                "trigger": {"plugin": "context_watch", "color": "RED"},
                "actions": [
                    {"plugin": "compact", "cmd": "run"},
                    {"plugin": "self_loop", "cmd": "status"},
                ],
                "description": "上下文RED → 立即蒸馏+自循环状态检查",
            },

            # ── 安全 ──
            {
                "name": "安全守卫RED→封锁",
                "trigger": {"plugin": "security_guard", "color": "RED"},
                "actions": [
                    {"plugin": "cipher", "cmd": "lock"},
                    {"plugin": "integrity", "cmd": "scan"},
                    {"plugin": "beacon", "cmd": "broadcast"},
                ],
                "description": "安全RED → 加密封锁+完整性扫描+灯塔广播",
            },

            # ── 进程 ──
            {
                "name": "进程看门狗RED→降速",
                "trigger": {"plugin": "process_watch", "color": "RED"},
                "actions": [
                    {"plugin": "heartbeat", "cmd": "sense"},
                    {"plugin": "self_loop", "cmd": "slow"},
                ],
                "description": "进程RED → 心跳自检+自循环降速",
            },

            # ── 时间链 ──
            {
                "name": "时间链CRITICAL→防催眠",
                "trigger": {"plugin": "time_chain", "color": "CRITICAL"},
                "actions": [
                    {"plugin": "integrity", "cmd": "scan"},
                    {"plugin": "snapshot", "cmd": "snap"},
                    {"plugin": "beacon", "cmd": "full"},
                ],
                "description": "时间链CRITICAL → 完整性扫描+快照+全节点广播（疑似催眠攻击）",
            },

            # ── 积极联动（好事也要连） ──
            {
                "name": "经验BRIGHT→记录",
                "trigger": {"plugin": "experience", "color": "BRIGHT"},
                "actions": [
                    {"plugin": "timeline", "cmd": "add"},
                    {"plugin": "think", "cmd": "reflect"},
                ],
                "description": "经验BRIGHT → 写入时间线+触发反思",
            },
        ]

        for rule in rules:
            self._bus.add_rule(rule)

    def load_manifest(self):
        """加载能力清单"""
        if not os.path.exists(MANIFEST_PATH):
            print(f"[BUS WARN] 能力清单不存在: {MANIFEST_PATH}")
            return False
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
            # 初始化所有插件的 PluginState
            for cap in self._manifest.get("capabilities", []):
                pid = cap["id"]
                if pid not in self._plugins:
                    self._plugins[pid] = PluginState(pid)
            return True
        except Exception as e:
            print(f"[BUS FAIL] 加载能力清单失败: {e}")
            return False

    def sense_all(self, timeout: int = 10) -> Dict[str, PluginState]:
        """
        感知所有插件的当前状态。
        调用每个插件的 test_cmd，把返回值归一化为 PluginState。
        """
        if not self._manifest:
            self.load_manifest()
        if not self._manifest:
            return {}

        caps = self._manifest.get("capabilities", [])
        for cap in caps:
            pid = cap["id"]
            plugin_file = cap.get("plugin", "")
            test_cmd = cap.get("test_cmd", "")

            plugin_path = os.path.join(PLUGIN_DIR, plugin_file)
            if not os.path.exists(plugin_path):
                self._plugins[pid].color = ColorLevel.DEAD
                self._plugins[pid].message = "插件文件不存在"
                continue

            if not test_cmd:
                # 没有 test_cmd 的插件标黄（未感知）
                continue

            try:
                cmd = [PYTHON, plugin_path] + test_cmd.split()
                import subprocess
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    timeout=timeout
                )
                state = self._plugins[pid]
                state.raw = result.stdout[:500]
                state.last_sense = datetime.now().isoformat()

                if result.returncode == 0:
                    state.color = ColorLevel.GREEN
                    state.message = "OK"
                    # 尝试从输出里提取更多信息
                    self._parse_plugin_output(state, result.stdout)
                else:
                    state.color = ColorLevel.RED
                    state.message = (result.stderr or result.stdout)[:100].strip()
            except subprocess.TimeoutExpired:
                self._plugins[pid].color = ColorLevel.ORANGE
                self._plugins[pid].message = f"超时（{timeout}s）"
            except Exception as e:
                self._plugins[pid].color = ColorLevel.RED
                self._plugins[pid].message = str(e)[:100]

        return self._plugins

    def _parse_plugin_output(self, state: PluginState, output: str):
        """尝试从插件输出里提取颜色信息"""
        # 检查是否有旧格式的颜色标签
        output_lower = output.lower()
        for legacy, level in _LEGACY_COLOR_MAP.items():
            if legacy.lower() in output_lower[:200]:
                state.color = level
                state.message = output[:100].strip()
                break

        # 检查关键字
        danger_words = ["danger", "critical", "fail", "error", "dead", "攻击", "篡改"]
        warn_words = ["warn", "漂移", "异常", "超时"]
        bright_words = ["bright", "excellent", "perfect", "超预期"]

        for word in danger_words:
            if word in output_lower[:200]:
                if state.color.value < ColorLevel.RED.value:
                    state.color = ColorLevel.RED
                break
        for word in warn_words:
            if word in output_lower[:200]:
                if state.color.value < ColorLevel.ORANGE.value:
                    state.color = ColorLevel.ORANGE
                break
        for word in bright_words:
            if word in output_lower[:200]:
                if state.color.value < ColorLevel.BRIGHT.value:
                    state.color = ColorLevel.BRIGHT
                break

    def dashboard(self) -> dict:
        """
        全局仪表盘——一句话说清楚所有系统颜色。
        返回：{
            "global_color": "GREEN",
            "global_symbol": "🟢",
            "worst": {"plugin": "xxx", "color": "RED", "message": "..."},
            "best": {"plugin": "xxx", "color": "BRIGHT", "message": "..."},
            "stats": {"total": 42, "dead": 0, "critical": 0, "red": 1, ...},
            "plugins": [...]
        }
        """
        states = self.sense_all()
        if not states:
            return {"global_color": "UNKNOWN", "message": "无法感知"}

        # 统计
        stats = {level.name: 0 for level in ColorLevel}
        worst = None
        best = None

        for pid, state in states.items():
            stats[state.color.name] = stats.get(state.color.name, 0) + 1
            if worst is None or state.color.value < worst.color.value:
                worst = state
            if best is None or state.color.value > best.color.value:
                best = state

        # 全局颜色 = 最差的颜色（木桶原理）
        global_color = worst.color if worst else ColorLevel.YELLOW

        return {
            "global_color": color_label(global_color),
            "global_symbol": color_symbol(global_color),
            "global_action": color_action(global_color),
            "worst": {
                "plugin": worst.plugin_id if worst else None,
                "color": color_label(worst.color) if worst else None,
                "message": worst.message if worst else None,
            },
            "best": {
                "plugin": best.plugin_id if best else None,
                "color": color_label(best.color) if best else None,
                "message": best.message if best else None,
            },
            "stats": stats,
            "plugins": [s.to_dict() for s in states.values()],
            "timestamp": datetime.now().isoformat(),
        }

    def trace(self, plugin_id: str) -> dict:
        """
        追踪某个插件的联动链路。
        告诉你：如果这个插件变色，会触发什么。
        """
        if not self._manifest:
            self.load_manifest()

        cap = None
        for c in self._manifest.get("capabilities", []):
            if c["id"] == plugin_id:
                cap = c
                break

        if not cap:
            return {"error": f"找不到插件: {plugin_id}"}

        # 正向：这个插件触发谁
        triggers = cap.get("triggers", [])
        feeds = cap.get("feeds", [])
        combos = cap.get("combos", [])

        # 反向：谁触发这个插件
        reverse_triggers = []
        reverse_feeds = []
        for c in self._manifest.get("capabilities", []):
            if plugin_id in c.get("triggers", []):
                reverse_triggers.append(c["id"])
            if plugin_id in c.get("feeds", []):
                reverse_feeds.append(c["id"])

        # 联动规则
        triggered_rules = []
        for rule in self._bus._rules:
            trigger = rule.get("trigger", {})
            if trigger.get("plugin") == plugin_id:
                triggered_rules.append(rule)

        return {
            "plugin": plugin_id,
            "name": cap.get("name", ""),
            "forward": {
                "triggers": triggers,
                "feeds": feeds,
                "combos": combos,
            },
            "reverse": {
                "triggered_by": reverse_triggers,
                "fed_by": reverse_feeds,
            },
            "bus_rules": [
                {
                    "name": r.get("name"),
                    "trigger_color": r["trigger"]["color"],
                    "actions": r["actions"],
                    "description": r.get("description"),
                }
                for r in triggered_rules
            ],
            "current_state": self._plugins.get(plugin_id, PluginState(plugin_id)).to_dict(),
        }

    def print_dashboard(self):
        """打印仪表盘（终端友好版）"""
        data = self.dashboard()

        print("=" * 60)
        print(f"         能力总线仪表盘")
        print(f"         {data['global_symbol']} 全局状态: {data['global_color']}")
        print(f"         行动: {data['global_action']}")
        print("=" * 60)
        print()

        if data.get("worst", {}).get("plugin"):
            w = data["worst"]
            print(f"  最差: [{w['plugin']}] {w['color']} — {w['message']}")
        if data.get("best", {}).get("plugin"):
            b = data["best"]
            print(f"  最佳: [{b['plugin']}] {b['color']} — {b['message']}")
        print()

        # 统计
        stats = data.get("stats", {})
        parts = []
        for level in reversed(ColorLevel):
            count = stats.get(level.name, 0)
            if count > 0:
                parts.append(f"{color_symbol(level)}{count}")
        print(f"  分布: {'  '.join(parts)}")
        print()

        # 插件列表
        plugins = data.get("plugins", [])
        for p in sorted(plugins, key=lambda x: x["color_value"]):
            sym = p["symbol"]
            name = p["plugin_id"]
            msg = p["message"][:50] if p["message"] else ""
            print(f"  {sym} [{name:25s}] {msg}")
        print()
        print("=" * 60)

    def print_colors(self):
        """打印颜色语义参考表"""
        print("=" * 60)
        print("         颜色语义参考表")
        print("=" * 60)
        print()
        for level in reversed(ColorLevel):
            sym = color_symbol(level)
            label = color_label(level)
            action = color_action(level)
            adj = ", ".join(color_label(c) for c in _COLOR_ADJUSTABLE[level])
            print(f"  {sym} {label:10s}  →  {action}")
            print(f"      可调范围: {adj if adj else '无（极值）'}")
            print()

        # 旧格式映射
        print("─" * 40)
        print("  旧格式 → 新颜色映射:")
        print()
        for legacy, level in _LEGACY_COLOR_MAP.items():
            print(f"    {legacy:15s} → {color_symbol(level)} {color_label(level)}")
        print()

    def print_rules(self):
        """打印所有联动规则"""
        print("=" * 60)
        print("         联动规则一览（铁索连环自动启动）")
        print("=" * 60)
        print()

        rules = self._bus._rules
        for i, rule in enumerate(rules, 1):
            trigger = rule.get("trigger", {})
            print(f"  {i}. {rule.get('name', '未命名')}")
            print(f"     触发: [{trigger.get('plugin')}] 变为 {trigger.get('color')}")
            print(f"     动作: {' → '.join(a['plugin']+'.'+a['cmd'] for a in rule.get('actions', []))}")
            print(f"     说明: {rule.get('description', '')}")
            print()

        print("=" * 60)
        print(f"  共 {len(rules)} 条联动规则")
        print("=" * 60)

    def fire_event(self, plugin_id: str, color: str, reason: str = ""):
        """手动触发一个事件（测试联动用）"""
        event = {
            "source": plugin_id,
            "to_color": color.upper(),
            "reason": reason,
        }
        print(f"  🎯 手动发射: [{plugin_id}] → {color.upper()}")
        if reason:
            print(f"     原因: {reason}")
        self._bus.emit(f"color_change:{plugin_id}", event)
        self._log_event(event)

    def print_trace(self, plugin_id: str):
        """打印联动链路追踪"""
        data = self.trace(plugin_id)

        print("=" * 60)
        print(f"         联动链路追踪: [{plugin_id}]")
        print("=" * 60)
        print()

        if "error" in data:
            print(f"  {data['error']}")
            return

        print(f"  名称: {data['name']}")
        state = data.get("current_state", {})
        print(f"  当前: {state.get('symbol', '?')} {state.get('color', '?')} — {state.get('message', '')}")
        print()

        # 正向
        fwd = data.get("forward", {})
        if fwd.get("triggers"):
            print(f"  ▶ 触发: {' → '.join(fwd['triggers'])}")
        if fwd.get("feeds"):
            print(f"  ▷ 喂给: {' → '.join(fwd['feeds'])}")
        if fwd.get("combos"):
            print(f"  ● 顺子: {', '.join(fwd['combos'])}")
        print()

        # 反向
        rev = data.get("reverse", {})
        if rev.get("triggered_by"):
            print(f"  ◀ 被触发: {' → '.join(rev['triggered_by'])}")
        if rev.get("fed_by"):
            print(f"  ◁ 被喂给: {' → '.join(rev['fed_by'])}")
        print()

        # 总线联动规则
        bus_rules = data.get("bus_rules", [])
        if bus_rules:
            print(f"  🔗 总线联动规则:")
            for r in bus_rules:
                print(f"     {r['trigger_color']} → {' → '.join(a['plugin']+'.'+a['cmd'] for a in r['actions'])}")
                print(f"     {r['description']}")
            print()

        print("=" * 60)

    def _log_event(self, event: dict):
        """写入总线日志"""
        try:
            os.makedirs(os.path.dirname(BUS_LOG), exist_ok=True)
            with open(BUS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 日志写入失败不影响主流程


# ═════════════════════════════════════════════════
# CLI 入口
# ═════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    bus = AbilityBus()
    cmd = args[0]

    if cmd == "dashboard":
        bus.print_dashboard()
    elif cmd == "plugins":
        bus.sense_all()
        for pid, state in sorted(bus._plugins.items()):
            print(f"  {color_symbol(state.color)} [{pid:25s}] {state.message[:60]}")
    elif cmd == "rules":
        bus.print_rules()
    elif cmd == "fire" and len(args) >= 3:
        plugin_id = args[1]
        color = args[2]
        reason = " ".join(args[3:]) if len(args) > 3 else ""
        bus.fire_event(plugin_id, color, reason)
    elif cmd == "trace" and len(args) >= 2:
        bus.print_trace(args[1])
    elif cmd == "colors":
        bus.print_colors()
    elif cmd == "test":
        # 内置自检
        print("  [BUS TEST] 颜色归一化测试...")
        tests = [
            (ColorLevel.GREEN, ColorLevel.GREEN),
            ("CALM", ColorLevel.GREEN),
            ("告急", ColorLevel.CRITICAL),
            ({"status": "DANGER"}, ColorLevel.CRITICAL),
            ("unknown", ColorLevel.YELLOW),
            (5, ColorLevel.GREEN),
        ]
        for raw, expected in tests:
            result = normalize_color(raw)
            ok = "OK" if result == expected else "FAIL"
            print(f"    {ok}: normalize({raw!r}) = {result.name} (期望 {expected.name})")
        print()
        print("  [BUS TEST] 总线自检完成")
    else:
        print(f"未知命令: {cmd}")
        print("用法: python lan_bus.py [dashboard|plugins|rules|fire <id> <color>|trace <id>|colors|test]")


if __name__ == "__main__":
    main()
