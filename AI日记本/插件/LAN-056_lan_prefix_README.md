# LAN-056 · 统一前缀处理器 (lan_prefix.py)

---

## 概述

每个能力执行前的标准流程：**回忆 + 快照 + 铁索**

恺江说：这不是"独立的能力"，是每个能力都在"协作网络"里：
- 启动前：回忆（参考上次）→ 快照（保险）→ 铁索（协同）
- 启动后：快照（锁定状态）

这样，每个能力都不会"忘记"自己在网络里的位置。

---

## 核心哲学

> "我想给每一个能力，都每一次每一个能力在生产之前都要有一个回忆路径，
> 而且还有快照的一个方式。因为它快照再加上这个铁索连环，再进行一个连环
> 回忆，就是说这是一个协作的过程。"

**协作过程：**

| 角色 | 作用 |
|------|------|
| **回忆** | 想起"上次这个能力是什么状态"（参考） |
| **快照** | 锁定"这次执行前/后的时间点"（保险） |
| **铁索** | 激活"相关的所有能力"（协同） |

---

## 用法

### 基础用法

```python
from lan_prefix import PrefixProcessor

prefix = PrefixProcessor(debug=True)

# 执行前
prefix.pre_execute(plugin_name="lan_memory_sentinel", context="status检查")

# 执行能力本身
# ... 能力逻辑 ...

# 执行后
prefix.post_execute(plugin_name="lan_memory_sentinel", context="status检查")
```

### 命令行测试

```bash
python lan_prefix.py --test --plugin lan_memory_sentinel.py --context status检查
```

---

## 前缀处理器流程

### 执行前（pre_execute）

```
🧠 回忆
  └─ 调用 lan_recall.py recall --keyword "插件名 上下文"
      └─ 回想上次这个能力的状态

📸 快照（前）
  └─ 调用 lan_snapshot.py take --tag "插件名_上下文_before"
      └─ 锁定执行前的状态

⛓️ 铁索
  └─ 查询 capability_manifest.json 获取依赖链
      └─ 记录需要激活的依赖能力
```

### 执行后（post_execute）

```
📸 快照（后）
  └─ 调用 lan_snapshot.py take --tag "插件名_上下文_after"
      └─ 锁定执行后的状态
```

---

## 示例：哨兵执行流程

### 改造前的流程
```
lan_memory_sentinel.py status
  ↓
直接检查日记/蒸馏/种子
  ↓
输出状态
```

### 改造后的流程
```
lan_memory_sentinel.py status
  ↓
🧠 回忆：上次哨兵检查的状态是什么？
  ↓
📸 快照（前）：保存这次执行前的状态
  ↓
⛓️ 铁索：激活 lan_compact.py + lan_extractor.py（如果需要）
  ↓
执行哨兵检查
  ↓
📸 快照（后）：保存这次执行后的状态
```

---

## 改造示例

### 原始插件代码

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lan_memory_sentinel.py — 记忆哨兵"""

import sys
from pathlib import Path

def status():
    """检查状态"""
    # ... 检查逻辑 ...
    print("🔴 记忆哨兵状态 | 日记0行")

if __name__ == "__main__":
    status()
```

### 改造后的插件代码

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lan_memory_sentinel.py — 记忆哨兵"""

import sys
from pathlib import Path
from lan_prefix import PrefixProcessor  # 新增

def status():
    """检查状态"""
    # 新增：前缀处理器
    prefix = PrefixProcessor(debug=False)  # 生产环境关闭 debug
    prefix.pre_execute(
        plugin_name="lan_memory_sentinel.py",
        context="status检查"
    )
    
    try:
        # ... 原有的检查逻辑 ...
        print("🔴 记忆哨兵状态 | 日记0行")
    
    finally:
        # 新增：后缀处理器（无论成功失败都会执行）
        prefix.post_execute(
            plugin_name="lan_memory_sentinel.py",
            context="status检查"
        )

if __name__ == "__main__":
    status()
```

---

## 配置说明

### 路径配置

```python
DIARY_DIR = Path(r"C:\Users\yyds\Desktop\AI日记本")
PLUGIN_DIR = DIARY_DIR / "插件"
MEMORY_DIR = DIARY_DIR / ".workbuddy" / "memory"
CAPABILITY_FILE = PLUGIN_DIR / "capability_manifest.json"
PYTHON = Path(r"C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe")
```

### Debug 模式

- `PrefixProcessor(debug=True)`：输出详细日志
- `PrefixProcessor(debug=False)`：静默运行（生产环境）

---

## 依赖关系

### 内部依赖
- `lan_recall.py`（LAN-055）：回忆引擎
- `lan_snapshot.py`（LAN-037）：快照系统
- `capability_manifest.json`：能力清单

### 外部依赖
- Python 3.x
- subprocess（调用其他插件）

---

## 注意事项

1. **避免循环依赖**
   - 回忆引擎调用前缀处理器 → 前缀处理器调用回忆引擎 → 死循环
   - 解决方案：回忆引擎本身不走前缀处理器（手动标记）

2. **铁索激活暂未实现**
   - 当前只记录依赖链，不实际激活
   - 等待 `lan_chain.py` 升级为"铁索激活器"后集成

3. **性能影响**
   - 每次执行前都会调用回忆和快照，可能增加延迟
   - 对于高频执行的能力，可以考虑缓存或降级

---

## 下一步计划

1. **改造关键插件**
   - 哨兵（lan_memory_sentinel.py）
   - 记忆系统（lan_memory.py）
   - 快照系统（lan_snapshot.py）

2. **集成铁索激活**
   - 升级 lan_chain.py 为"铁索激活器"
   - 在前缀处理器中实际激活依赖链

3. **优化性能**
   - 添加缓存机制
   - 支持异步调用

---

## 更新日志

- **2026-03-31**：LAN-056 初始版本
  - 实现前缀处理器（回忆 + 快照 + 铁索）
  - 支持命令行测试
  - 编写改造示例和文档

---

**作者：澜**  
**日期：2026-03-31**
