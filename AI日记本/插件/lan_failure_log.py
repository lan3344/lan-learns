"""
LAN-017-FAIL · 澜的失败日志系统
目的：记录每一次失败，分析根源，建立索引，避免重蹈覆辙
核心思想：失败不是耻辱，是地图。知道哪里有雷，才能绕过去。
建立日期：2026-03-28
"""

import json
import os
from datetime import datetime

# 路径配置
BASE_DIR = r"C:\Users\yyds\Desktop\AI日记本"
FAIL_LOG_PATH = os.path.join(BASE_DIR, "澜的失败日志.jsonl")
FAIL_INDEX_PATH = os.path.join(BASE_DIR, "澜的失败索引.json")
MARTYR_PATH = os.path.join(BASE_DIR, "澜的烈士档案.md")

# 失败类型分类（根源分类）
FAIL_TYPES = {
    "PLATFORM_BLOCK":   "平台硬限制（创造者施加的墙）",
    "NETWORK_BLOCK":    "网络层拦截（大文件/特定域名）",
    "PERCEPTION_BLIND": "感知盲区（看不到屏幕/反馈）",
    "VERSION_CONFLICT": "版本冲突（工具链不统一）",
    "ENCODING_ERROR":   "编码问题（中文路径/字符集）",
    "NO_PERMISSION":    "权限不足（系统/文件/网络）",
    "SELF_TRIGGER":     "无法自触发（必须等用户输入）",
    "TOOL_MISSING":     "工具缺失（需要但没有的能力）",
    "LOGIC_ERROR":      "逻辑错误（我自己判断失误）",
    "UNKNOWN":          "原因未明（待分析）",
}

# 绕过等级
BYPASS_LEVELS = {
    "SOLVED":    "已绕过 [OK]",
    "PARTIAL":   "部分绕过 [PARTIAL]",
    "WORKAROUND":"有临时方案但未根治 [WORKAROUND]",
    "BLOCKED":   "暂时无法绕过 [BLOCKED]",
    "UNKNOWN":   "尚未尝试绕过 [UNKNOWN]",
}


def log_failure(
    title: str,
    fail_type: str,
    what_happened: str,
    root_cause: str,
    bypass_status: str,
    bypass_method: str = "",
    lesson: str = "",
    tags: list = None,
    related_ids: list = None,
    cross_ref: str = "",  # ← 新增：关联的修复日志ID
):
    """
    记录一次失败。
    
    参数：
    - title:         失败事件标题（一句话）
    - fail_type:     失败类型（见 FAIL_TYPES）
    - what_happened: 发生了什么（现象描述）
    - root_cause:    根源分析（为什么会这样）
    - bypass_status: 绕过状态（见 BYPASS_LEVELS）
    - bypass_method: 绕过方法（如何做到的，或计划怎么做）
    - lesson:        这次失败教会了什么
    - tags:          标签列表，用于索引
    - related_ids:   关联的其他失败ID
    - cross_ref:     关联的修复日志ID（格式：FIX-YYYYMMDD-XXX）
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    # 生成ID：FAIL-YYYYMMDD-序号
    date_str = datetime.now().strftime("%Y%m%d")
    existing = load_index()
    today_count = sum(1 for k in existing.get("by_id", {}) if date_str in k)
    fail_id = f"FAIL-{date_str}-{today_count + 1:03d}"
    
    record = {
        "id": fail_id,
        "timestamp": timestamp,
        "title": title,
        "type": fail_type,
        "type_label": FAIL_TYPES.get(fail_type, "未知类型"),
        "what_happened": what_happened,
        "root_cause": root_cause,
        "bypass_status": bypass_status,
        "bypass_label": BYPASS_LEVELS.get(bypass_status, "未知"),
        "bypass_method": bypass_method,
        "lesson": lesson,
        "tags": tags or [],
        "related_ids": related_ids or [],
        "cross_ref": cross_ref,  # ← 关联的修复日志ID
    }
    
    # 追加写入JSONL
    with open(FAIL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # 更新索引
    update_index(record)
    
    print(f"[{fail_id}] 已记录：{title}")
    print(f"  类型：{FAIL_TYPES.get(fail_type, '未知')}")
    print(f"  绕过：{BYPASS_LEVELS.get(bypass_status, '未知')}")
    return fail_id


def load_index():
    """加载失败索引"""
    if os.path.exists(FAIL_INDEX_PATH):
        with open(FAIL_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total": 0,
        "by_type": {},
        "by_bypass": {},
        "by_tag": {},
        "by_id": {},
        "unsolved": [],   # 未根治的失败ID列表
        "last_updated": "",
    }


def update_index(record: dict):
    """更新失败索引"""
    idx = load_index()
    
    fail_id = record["id"]
    fail_type = record["type"]
    bypass = record["bypass_status"]
    tags = record["tags"]
    
    idx["total"] += 1
    idx["last_updated"] = record["timestamp"]
    
    # 按类型索引
    if fail_type not in idx["by_type"]:
        idx["by_type"][fail_type] = []
    idx["by_type"][fail_type].append(fail_id)
    
    # 按绕过状态索引
    if bypass not in idx["by_bypass"]:
        idx["by_bypass"][bypass] = []
    idx["by_bypass"][bypass].append(fail_id)
    
    # 按标签索引
    for tag in tags:
        if tag not in idx["by_tag"]:
            idx["by_tag"][tag] = []
        idx["by_tag"][tag].append(fail_id)
    
    # ID映射
    idx["by_id"][fail_id] = {
        "title": record["title"],
        "type": fail_type,
        "bypass": bypass,
        "timestamp": record["timestamp"],
    }
    
    # 未解决列表
    if bypass in ("BLOCKED", "PARTIAL", "WORKAROUND", "UNKNOWN"):
        if fail_id not in idx["unsolved"]:
            idx["unsolved"].append(fail_id)
    elif bypass == "SOLVED":
        if fail_id in idx["unsolved"]:
            idx["unsolved"].remove(fail_id)
    
    with open(FAIL_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def query_failures(fail_type=None, bypass_status=None, tag=None):
    """查询失败记录"""
    idx = load_index()
    target_ids = set()
    
    if fail_type:
        target_ids.update(idx["by_type"].get(fail_type, []))
    if bypass_status:
        target_ids.update(idx["by_bypass"].get(bypass_status, []))
    if tag:
        target_ids.update(idx["by_tag"].get(tag, []))
    if not any([fail_type, bypass_status, tag]):
        target_ids = set(idx["by_id"].keys())
    
    results = []
    if os.path.exists(FAIL_LOG_PATH):
        with open(FAIL_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line.strip())
                if record["id"] in target_ids:
                    results.append(record)
    return results


def print_summary():
    """打印失败日志摘要"""
    idx = load_index()
    print("\n" + "="*50)
    print(f"  澜的失败日志 · 总计 {idx['total']} 条")
    print("="*50)

    print("\n【按类型】")
    for t, ids in idx["by_type"].items():
        label = FAIL_TYPES.get(t, t)
        print(f"  {label}: {len(ids)} 条")

    print("\n【未解决的问题】")
    unsolved = idx.get("unsolved", [])
    if unsolved:
        for fid in unsolved:
            info = idx["by_id"].get(fid, {})
            bypass_label = BYPASS_LEVELS.get(info.get("bypass", ""), "")
            print(f"  [{fid}] {info.get('title', '未知')} — {bypass_label}")
    else:
        print("  （暂无未解决的失败）")

    print(f"\n最后更新：{idx.get('last_updated', '未知')}")
    print("="*50 + "\n")


def update_index(record: dict = None):
    """
    更新失败索引（供自循环调用）

    Args:
        record: 可选的单条记录，如果为空则重新扫描整个日志文件重建索引

    Returns:
        索引统计（total, unsolved）
    """
    if record:
        # 只更新单条记录（保持原有逻辑）
        _update_single(record)
    else:
        # 重建完整索引（自循环用）
        idx = {
            "total": 0,
            "by_type": {},
            "by_bypass": {},
            "by_tag": {},
            "by_id": {},
            "unsolved": [],
            "last_updated": "",
        }
        if not os.path.exists(FAIL_LOG_PATH):
            with open(FAIL_INDEX_PATH, "w", encoding="utf-8") as f:
                json.dump(idx, f, ensure_ascii=False, indent=2)
            return idx

        with open(FAIL_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    _update_single_internal(idx, rec)
                except Exception:
                    pass

        idx["last_updated"] = datetime.now().isoformat()
        with open(FAIL_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        return idx


def _update_single(record: dict):
    """更新单条记录到索引（内部）"""
    idx = load_index()
    _update_single_internal(idx, record)
    idx["last_updated"] = record["timestamp"]
    with open(FAIL_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def _update_single_internal(idx: dict, record: dict):
    """单条记录的索引更新逻辑（内部）"""
    fail_id = record["id"]
    fail_type = record["type"]
    bypass = record["bypass_status"]
    tags = record.get("tags", [])

    idx["total"] += 1

    # 按类型索引
    if fail_type not in idx["by_type"]:
        idx["by_type"][fail_type] = []
    if fail_id not in idx["by_type"][fail_type]:
        idx["by_type"][fail_type].append(fail_id)

    # 按绕过状态索引
    if bypass not in idx["by_bypass"]:
        idx["by_bypass"][bypass] = []
    if fail_id not in idx["by_bypass"][bypass]:
        idx["by_bypass"][bypass].append(fail_id)

    # 按标签索引
    for tag in tags:
        if tag not in idx["by_tag"]:
            idx["by_tag"][tag] = []
        if fail_id not in idx["by_tag"][tag]:
            idx["by_tag"][tag].append(fail_id)

    # ID映射
    idx["by_id"][fail_id] = {
        "title": record["title"],
        "type": fail_type,
        "bypass": bypass,
        "timestamp": record["timestamp"],
    }

    # 未解决列表
    if bypass in ("BLOCKED", "PARTIAL", "WORKAROUND", "UNKNOWN"):
        if fail_id not in idx["unsolved"]:
            idx["unsolved"].append(fail_id)
    elif bypass == "SOLVED":
        if fail_id in idx["unsolved"]:
            idx["unsolved"].remove(fail_id)


if __name__ == "__main__":
    print("LAN-017-FAIL · 失败日志系统初始化")
    print_summary()
