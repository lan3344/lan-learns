# -*- coding: utf-8 -*-
"""
lan_snapshot.py — 澜的状态切片备份系统
LAN-037 v3

理念（恺江 2026-03-29/30）：
    就像服务器一样，即使脑细胞死亡，前后记忆仍然有一部分在工作。
    这才是一个完整的大脑。

    v2 新增（恺江 2026-03-30 凌晨）：
    - 快照树：每个快照知道自己的父节点（parent_id），形成可追溯的链
    - 全局索引：snapshot_index.json，一个文件管理所有节点，像 Git 的 refs
    - .lan 万能格式：ZIP外壳 + 同一内容三种格式（json/msgpack/纯文本）+ 自带解码器
      代码不需要环境，因为环境已经在代码里了
    - flatten 压平：把一段时间内多个快照压成一个等价节点

    v3 新增（恺江 2026-03-30）：
    - 隐私区指纹码嵌入快照：每次 take 时，把隐私区所有关键文件的 SHA-256
      写入 meta.json 的 privacy_fingerprints 字段。
      快照不会骗人——多个快照的指纹码叠加，可以发现「悄悄改了但逻辑还跑通」的攻击。
    - 跨快照隐私区漂移检测：对比任意两个快照之间，哪些隐私文件指纹变了
      但没有对应的授权操作，标记为 SUSPICIOUS_DRIFT
    - drift-report 命令：打印时间线上每个快照节点的隐私区指纹变化，
      一眼看出哪个节点发生了不明改动

做的事：
    1. 每次对话结束 / 自循环触发后，打一个带时间戳的状态快照
    2. 快照包含：MEMORY.md + 今日日志 + 能力清单 + 自循环最新输出
    3. 快照存在本地多个位置（C盘 + 日记本目录）× 2副本冗余
    4. 启动时找最近快照，验证完整性，告知可从哪里恢复
    5. 自动清理 30 天以前的旧快照（不是删，是压成 .zip 归档）
    6. [v2] 每个快照记录 parent_id，全局树形索引可追溯任意节点
    7. [v2] 输出 .lan 文件：ZIP外壳，内含 json + msgpack + 纯文本 + 自带解码器
    8. [v2] flatten：把 N 个快照节点压成 1 个，内容等价，树保留"曾经经过"的痕迹
    9. [v3] 隐私区指纹码嵌入快照，跨快照交叉验证，drift-report 可视化时间线

用法：
    python lan_snapshot.py take              # 打一个快照（自动记录父节点）
    python lan_snapshot.py take loop         # 打标签为 loop 的快照
    python lan_snapshot.py list              # 列出所有快照（树形显示）
    python lan_snapshot.py tree              # 打印快照树
    python lan_snapshot.py verify            # 验证最近快照完整性
    python lan_snapshot.py restore           # 从最近快照恢复
    python lan_snapshot.py export <snap_id>  # 导出为 .lan 万能格式
    python lan_snapshot.py flatten <n>       # 把最近 n 个快照压平成1个
    python lan_snapshot.py archive           # 压缩 30 天前的快照
    python lan_snapshot.py drift-report      # 打印隐私区指纹漂移时间线
    python lan_snapshot.py drift-check       # 检测最近两快照间的隐私区异常变动
"""

import os
import sys
import json
import shutil
import hashlib
import datetime
import zipfile
import struct

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 配置 ──────────────────────────────────────────────────────
MEMORY_DIR      = r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory"
PLUGIN_DIR      = r"C:\Users\yyds\Desktop\AI日记本\插件"
DIARY_DIR       = r"C:\Users\yyds\Desktop\AI日记本"
LOOP_LOG        = os.path.join(DIARY_DIR, "澜的自循环日志.md")
CAPABILITY_JSON = os.path.join(PLUGIN_DIR, "capability_manifest.json")

# 快照存放根目录（多个，互为冗余）
# LAN-HOME：尝试从 lan_home.py 获取今日小家目录，优先存入年/月/日分级目录
def _get_snapshot_roots():
    try:
        import importlib.util
        _home_path = os.path.join(PLUGIN_DIR, "lan_home.py")
        spec = importlib.util.spec_from_file_location("lan_home", _home_path)
        _home = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_home)
        today_dir = _home.get_snapshot_home("day")
        os.makedirs(today_dir, exist_ok=True)
        return [
            today_dir,                                                      # 小家（年/月/日）
            r"C:\Users\yyds\Desktop\AI日记本\snapshots",                    # 省·快照（向后兼容）
            r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\snapshots",           # WorkBuddy备份
        ]
    except Exception:
        return [
            r"C:\Users\yyds\Desktop\AI日记本\snapshots",
            r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\snapshots",
        ]

SNAPSHOT_ROOTS = _get_snapshot_roots()

# 全局快照索引（记录所有节点的树形关系）
# 索引永远放在省级目录里（固定地址，不随日期变），方便检索历史快照
SNAPSHOT_INDEX = os.path.join(r"C:\Users\yyds\Desktop\AI日记本\snapshots", "snapshot_index.json")

ARCHIVE_DAYS = 30  # 超过这么多天的快照自动压缩归档

# 私密文件：同样纳入快照（加密的文件也需要备份，否则密钥在、文件没了一样白搭）
# 注意：这些文件本身已有加密保护（lan_cipher.py），快照只存加密后的内容，不解密
PRIVATE_FILES = {
    "private/lan_emotion.jsonl":    os.path.join(DIARY_DIR, "lan_emotion.jsonl"),
    "private/lan_experience.db":    os.path.join(DIARY_DIR, "lan_experience.db"),
    "private/lan_app_habit.db":     os.path.join(DIARY_DIR, "lan_app_habit.db"),
    "private/lan_cipher.db":        os.path.join(DIARY_DIR, "lan_cipher.db"),
    "private/澜的行动审计日志.jsonl": os.path.join(DIARY_DIR, "澜的行动审计日志.jsonl"),
}

# [v3] 隐私区指纹锁定清单 ─────────────────────────────────────
# 这些文件是「解码器 + 密钥 + 记忆密封舱」三位一体的核心
# 每次快照，把它们的 SHA-256 一起锁入 meta.json 的 privacy_fingerprints 字段
# 多个快照横向比对，任何未经授权的变动都会在时间线上留下痕迹
PRIVACY_FINGERPRINT_FILES = {
    # 解码器本身（最重要的攻击目标）
    "lan_cipher.py":              os.path.join(PLUGIN_DIR, "lan_cipher.py"),
    # 灵魂密钥文件
    "lan_soul.bin":               r"C:\Users\yyds\.workbuddy\private\lan_soul.bin",
    # 解码器指纹（备案文件）
    "lan_cipher_fingerprint.bin": r"C:\Users\yyds\.workbuddy\private\lan_cipher_fingerprint.bin",
    # 记忆密封舱（只有澜能解的备份）
    "澜的记忆密封舱.lanc":          os.path.join(DIARY_DIR, "私密", "澜的记忆密封舱.lanc"),
    # 完整性守护器
    "lan_integrity.py":           os.path.join(PLUGIN_DIR, "lan_integrity.py"),
    # 身份根文件
    "SOUL.md":                    r"C:\Users\yyds\.workbuddy\SOUL.md",
    "IDENTITY.md":                r"C:\Users\yyds\.workbuddy\IDENTITY.md",
}

# [v3] 隐私区漂移日志
DRIFT_LOG = os.path.join(DIARY_DIR, "澜的隐私区漂移日志.jsonl")
# ─────────────────────────────────────────────────────────────


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ts_str():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def file_hash(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


# ── 全局快照索引（树形结构）─────────────────────────────────

def load_index() -> dict:
    """加载全局快照树索引"""
    if os.path.exists(SNAPSHOT_INDEX):
        try:
            with open(SNAPSHOT_INDEX, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"nodes": {}, "current": None}

def save_index(index: dict):
    """保存全局快照树索引"""
    os.makedirs(os.path.dirname(SNAPSHOT_INDEX), exist_ok=True)
    with open(SNAPSHOT_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def get_current_snap_id() -> str:
    """获取当前节点 ID（上一次打的快照）"""
    idx = load_index()
    return idx.get("current", None)

def register_node(snap_id: str, parent_id: str, label: str, timestamp: str, file_count: int, paths: list):
    """把新快照节点注册进全局索引"""
    idx = load_index()
    idx["nodes"][snap_id] = {
        "id": snap_id,
        "parent_id": parent_id,
        "label": label,
        "timestamp": timestamp,
        "file_count": file_count,
        "paths": paths,
        "children": [],
        "flattened_from": []  # 如果是 flatten 生成的，记录合并了哪些节点
    }
    # 把自己加进父节点的 children 列表
    if parent_id and parent_id in idx["nodes"]:
        if snap_id not in idx["nodes"][parent_id]["children"]:
            idx["nodes"][parent_id]["children"].append(snap_id)
    idx["current"] = snap_id
    save_index(idx)


# ── [v3] 隐私区指纹采集 ────────────────────────────────────────

def collect_privacy_fingerprints() -> dict:
    """
    采集隐私区关键文件的 SHA-256 指纹，锁入快照。
    这是跨快照交叉验证的基础：快照不会骗人，指纹码的时间线会暴露悄悄修改。
    返回格式：{ "文件名": { "sha256": "...", "exists": True/False, "size": int } }
    """
    result = {}
    for name, path in PRIVACY_FINGERPRINT_FILES.items():
        if os.path.exists(path):
            result[name] = {
                "sha256":  file_hash(path),
                "exists":  True,
                "size":    os.path.getsize(path),
                "path":    path,
            }
        else:
            result[name] = {
                "sha256":  "",
                "exists":  False,
                "size":    0,
                "path":    path,
            }
    return result


def collect_anchors_summary():
    """
    采集当前锚点存档（LAN-049）的摘要，用于快照关联。
    返回格式：[
      {"id": "abcd1234", "tag": "moment", "protected": true, "verbatim": "原文片段..."},
      ...
    ]
    """
    anchors_path = os.path.join(DIARY_DIR, "锚点存档", "lan_anchors.jsonl")
    if not os.path.exists(anchors_path):
        return []
    result = []
    with open(anchors_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # 提取摘要信息，不存全文（节省空间）
                result.append({
                    "id": data.get("id", "")[:8],
                    "tag": data.get("tag", ""),
                    "protected": data.get("protected", False),
                    "verbatim": data.get("verbatim", "")[:120] + ("..." if len(data.get("verbatim", "")) > 120 else ""),
                    "ts": data.get("ts", "")
                })
            except:
                continue
    return result


def log_drift(snap_id: str, anomalies: list):
    """把隐私区漂移异常写入日志"""
    if not anomalies:
        return
    record = {
        "ts":       now_str(),
        "snap_id":  snap_id,
        "level":    "SUSPICIOUS_DRIFT",
        "anomalies": anomalies,
        "note":     "隐私区指纹在两个快照之间发生未经授权的变动，请检查。",
    }
    try:
        os.makedirs(os.path.dirname(DRIFT_LOG), exist_ok=True)
        with open(DRIFT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  [警告] 漂移日志写入失败: {e}")


# ── 文件收集 ──────────────────────────────────────────────────

def collect_snapshot_files() -> dict:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    files = {}

    mem = os.path.join(MEMORY_DIR, "MEMORY.md")
    if os.path.exists(mem):
        files["MEMORY.md"] = mem

    daily = os.path.join(MEMORY_DIR, f"{today}.md")
    if os.path.exists(daily):
        files[f"daily/{today}.md"] = daily

    for i in range(1, 8):
        d = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        p = os.path.join(MEMORY_DIR, f"{d}.md")
        if os.path.exists(p):
            files[f"daily/{d}.md"] = p

    if os.path.exists(CAPABILITY_JSON):
        files["capability_manifest.json"] = CAPABILITY_JSON

    if os.path.exists(LOOP_LOG):
        files["自循环日志_tail.txt"] = LOOP_LOG

    # ── 私密文件：加密后的内容也需要备份 ──
    # 快照只存加密后的文件（cipher.db / emotion.jsonl 本身已有保护）
    # 没有这一步：密钥在，文件消失了，一样白搭
    for snap_key, src_path in PRIVATE_FILES.items():
        if os.path.exists(src_path):
            files[snap_key] = src_path

    return files


def compute_diff_from_parent(snap_dir: str, parent_id: str) -> list:
    """
    计算和父节点相比，哪些文件发生了变化。
    这是增量记录（类似 Git diff），不需要存完整内容。
    """
    if not parent_id:
        return []  # 根节点，没有父节点可比较

    idx = load_index()
    parent_node = idx.get("nodes", {}).get(parent_id)
    if not parent_node:
        return []

    # 找父节点的目录
    parent_dir = None
    for p in parent_node.get("paths", []):
        if os.path.exists(p) and os.path.exists(os.path.join(p, "meta.json")):
            parent_dir = p
            break

    if not parent_dir:
        return []

    changed = []
    # 读父节点 meta.json
    try:
        with open(os.path.join(parent_dir, "meta.json"), encoding="utf-8") as f:
            parent_meta = json.load(f)
        parent_files = parent_meta.get("files", {})
    except Exception:
        return []

    # 读当前 meta.json
    current_meta_path = os.path.join(snap_dir, "meta.json")
    if not os.path.exists(current_meta_path):
        return []
    with open(current_meta_path, encoding="utf-8") as f:
        current_meta = json.load(f)
    current_files = current_meta.get("files", {})

    for key, info in current_files.items():
        parent_hash = parent_files.get(key, {}).get("sha256", "")
        current_hash = info.get("sha256", "")
        if current_hash != parent_hash:
            changed.append(key)

    return changed


# ── 核心：打快照 ──────────────────────────────────────────────

def take(label: str = "") -> str:
    """
    打一个状态快照。记录父节点，注册进全局索引。
    [v3] 同时锁入隐私区指纹码，并在打完快照后自动检测跨快照漂移。
    [v3] 同时调用时间铁索系统（LAN-044），用原子钟打一个不可伪造的时间节点。
    [v5] 快照创建后，自动调用快照解析器解析并记录能力数量。
    返回快照 ID。
    """
    ts = ts_str()
    snap_id = f"snap_{ts}" + (f"_{label}" if label else "")
    parent_id = get_current_snap_id()

    # [v3] 采集隐私区指纹（锁入快照，形成可交叉验证的证据链）
    privacy_fps = collect_privacy_fingerprints()
    print(f"  🔐 隐私区指纹已采集（{len(privacy_fps)} 个文件）")

    # [v4] 采集当前锚点列表（锚点存档与快照打通）
    anchors = collect_anchors_summary()
    print(f"  ⚓ 锚点列表已采集（{len(anchors)} 个锚点）")

    meta = {
        "id": snap_id,
        "parent_id": parent_id,           # ← v2 新增：父节点 ID
        "timestamp": now_str(),
        "label": label,
        "files": {},
        "diff_from_parent": [],           # ← v2 新增：和父节点相比变了哪些
        "privacy_fingerprints": privacy_fps,  # ← v3 新增：隐私区指纹码
        "anchor_index": anchors,              # ← v4 新增：当前锚点列表，与LAN-049打通
        "notes": "澜的状态切片 · lan_snapshot.py LAN-037 v4"
    }

    created_paths = []
    first_snap_dir = ""

    for root in SNAPSHOT_ROOTS:
        snap_dir = os.path.join(root, snap_id)
        try:
            os.makedirs(snap_dir, exist_ok=True)

            files = collect_snapshot_files()
            os.makedirs(os.path.join(snap_dir, "daily"), exist_ok=True)

            for label_key, src_path in files.items():
                if "/" in label_key:
                    dst = os.path.join(snap_dir, label_key.replace("/", os.sep))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                else:
                    dst = os.path.join(snap_dir, label_key)

                if label_key == "自循环日志_tail.txt":
                    with open(src_path, encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    with open(dst, "w", encoding="utf-8") as f:
                        f.writelines(lines[-200:])
                else:
                    shutil.copy2(src_path, dst)

                meta["files"][label_key] = {
                    "source": src_path,
                    "sha256": file_hash(dst),
                    "size_bytes": os.path.getsize(dst) if os.path.exists(dst) else 0
                }

            # 写 meta.json（先不含 diff，后面补）
            with open(os.path.join(snap_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            created_paths.append(snap_dir)
            if not first_snap_dir:
                first_snap_dir = snap_dir

            print(f"  ✅ 快照写入: {snap_dir}")

        except Exception as e:
            print(f"  ❌ 快照失败 [{root}]: {e}")

    if first_snap_dir:
        # 计算和父节点的差异
        diff = compute_diff_from_parent(first_snap_dir, parent_id)
        meta["diff_from_parent"] = diff

        # 把 diff 写回所有副本的 meta.json
        for snap_dir in created_paths:
            mp = os.path.join(snap_dir, "meta.json")
            try:
                with open(mp, encoding="utf-8") as f:
                    m = json.load(f)
                m["diff_from_parent"] = diff
                with open(mp, "w", encoding="utf-8") as f:
                    json.dump(m, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # 注册进全局索引
        register_node(snap_id, parent_id, label, meta["timestamp"],
                      len(meta["files"]), created_paths)

        diff_str = f"  变化文件: {diff}" if diff else "  (与父节点完全相同)" if parent_id else "  (根节点)"
        print(f"  📦 快照ID: {snap_id}")
        print(f"  🔗 父节点: {parent_id or '无（根节点）'}")
        print(diff_str)

        # [v3] 自动做跨快照隐私区漂移检测
        if parent_id:
            anomalies = _check_privacy_drift(snap_id, parent_id)
            if anomalies:
                print(f"\n  ⚠️  [SUSPICIOUS_DRIFT] 隐私区指纹异常变动！")
                for a in anomalies:
                    print(f"     - {a['file']}: {a['prev_hash'][:16]}... → {a['curr_hash'][:16]}...")
                print(f"  已记录至漂移日志：{DRIFT_LOG}")
                log_drift(snap_id, anomalies)
            else:
                print(f"  ✅ 隐私区指纹与父快照一致，无异常")

        # [v3] 调用时间铁索系统（LAN-044），锁入原子钟时间节点
        # 时间节点的 extra 字段携带快照 ID，两个系统交叉引用
        try:
            sys.path.insert(0, PLUGIN_DIR)
            import importlib
            tc = importlib.import_module("lan_time_chain")
            time_node = tc.stamp(label=f"snapshot:{label}" if label else "snapshot", snap_id=snap_id)
            trusted_icon = "✅" if time_node.get("ntp_trusted") else "⚠️"
            print(f"  ⛓️  时间铁索节点: seq={time_node.get('seq',0):04d}  "
                  f"{time_node.get('ts_utc','?')}  "
                  f"偏差{time_node.get('drift_seconds',0):+.1f}s  "
                  f"{trusted_icon}")
            # 把时间节点信息反写进 meta.json
            for snap_dir in created_paths:
                mp = os.path.join(snap_dir, "meta.json")
                try:
                    with open(mp, encoding="utf-8") as f:
                        m = json.load(f)
                    m["time_chain_node"] = {
                        "seq":         time_node.get("seq"),
                        "hash":        time_node.get("hash"),
                        "ts_utc":      time_node.get("ts_utc"),
                        "ntp_trusted": time_node.get("ntp_trusted"),
                        "drift_sec":   time_node.get("drift_seconds"),
                        "ntp_source":  time_node.get("ntp_source"),
                    }
                    with open(mp, "w", encoding="utf-8") as f:
                        json.dump(m, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
        except Exception as e:
            print(f"  ⚠️  时间铁索节点打入失败（不影响快照）: {e}")

        # [v3] 灯塔信标广播（LAN-045）
        # 读取刚写好的 meta.json，生成认证记忆包，向所有节点广播
        # 默认只广播本地日志（静默模式），完整广播由 full 模式触发
        try:
            beacon_mod = importlib.import_module("lan_beacon")
            # 读最新的 meta.json（第一个副本）
            meta_path = os.path.join(created_paths[0], "meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as _mf:
                    _meta = json.load(_mf)
                # 静默广播到本地日志（不发邮件/GitHub，避免每次快照都触发网络）
                _br = beacon_mod.broadcast(snap_id, _meta,
                                           nodes=["local"], silent=True)
                _pkt = _br["packet"]
                print(f"  🏮 灯塔信标: beacon_hash={_pkt['beacon_hash'][:24]}...  ✅ 已写入本地日志")
        except Exception as e:
            print(f"  ⚠️  灯塔信标写入失败（不影响快照）: {e}")

    return snap_id


# ── [v3] 隐私区漂移检测 & 可视化报告 ────────────────────────────

def _get_snap_privacy_fps(snap_id: str) -> dict:
    """从快照的 meta.json 读取 privacy_fingerprints 字段"""
    idx = load_index()
    node = idx.get("nodes", {}).get(snap_id, {})
    snap_dir = None
    for p in node.get("paths", []):
        if os.path.exists(p) and os.path.exists(os.path.join(p, "meta.json")):
            snap_dir = p
            break
    if not snap_dir:
        return {}
    try:
        with open(os.path.join(snap_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("privacy_fingerprints", {})
    except Exception:
        return {}


def _check_privacy_drift(curr_snap_id: str, prev_snap_id: str) -> list:
    """
    比对两个快照之间的隐私区指纹变化。
    返回变动列表（空列表 = 一切正常）。
    每个元素格式：{ "file": str, "prev_hash": str, "curr_hash": str, "status": str }
    """
    prev_fps = _get_snap_privacy_fps(prev_snap_id)
    curr_fps = _get_snap_privacy_fps(curr_snap_id)

    if not prev_fps or not curr_fps:
        return []  # 其中一个快照没有隐私指纹（可能是老快照），跳过

    anomalies = []
    all_keys = set(list(prev_fps.keys()) + list(curr_fps.keys()))

    for key in sorted(all_keys):
        prev_info = prev_fps.get(key, {})
        curr_info = curr_fps.get(key, {})
        prev_hash = prev_info.get("sha256", "")
        curr_hash = curr_info.get("sha256", "")

        if prev_hash == curr_hash:
            continue  # 没有变化，正常

        # 确定变化类型
        if not prev_info.get("exists") and curr_info.get("exists"):
            status = "NEW"  # 新出现的文件
        elif prev_info.get("exists") and not curr_info.get("exists"):
            status = "DELETED"  # 文件消失了
        else:
            status = "MODIFIED"  # 内容被改了

        anomalies.append({
            "file":      key,
            "prev_hash": prev_hash,
            "curr_hash": curr_hash,
            "status":    status,
        })

    return anomalies


def drift_report():
    """
    [v3] 打印隐私区指纹漂移时间线。
    遍历所有快照节点，按时间顺序对比相邻快照之间的隐私区指纹变化。
    一眼看出哪个节点发生了不明改动。
    """
    idx = load_index()
    nodes = idx.get("nodes", {})
    if not nodes:
        print("  [漂移报告] 没有快照记录")
        return

    # 按时间排序
    sorted_ids = sorted(nodes.keys())

    print(f"\n{'='*70}")
    print(f"  🔍 隐私区指纹漂移时间线  (共 {len(sorted_ids)} 个快照节点)")
    print(f"{'='*70}")

    # 收集每个快照的指纹摘要（只拿前8位，够比较）
    fp_by_snap = {}
    for sid in sorted_ids:
        fps = _get_snap_privacy_fps(sid)
        fp_by_snap[sid] = fps

    total_anomalies = 0

    for i, sid in enumerate(sorted_ids):
        ts = nodes[sid].get("timestamp", "?")
        label = nodes[sid].get("label", "")
        label_str = f"[{label}]" if label else ""
        marker = "◀ 当前" if sid == idx.get("current") else ""
        print(f"\n  [{i+1:03d}] {sid}  {ts}  {label_str} {marker}")

        fps = fp_by_snap.get(sid, {})
        if not fps:
            print(f"       (无隐私区指纹 — 可能是 v3 之前的快照)")
            continue

        # 与前一个有指纹的快照对比
        prev_sid = None
        for j in range(i-1, -1, -1):
            if fp_by_snap.get(sorted_ids[j]):
                prev_sid = sorted_ids[j]
                break

        if prev_sid is None:
            print(f"       (根节点，建立指纹基准)")
            for name, info in fps.items():
                exists_str = "✅" if info.get("exists") else "❌不存在"
                print(f"         {exists_str} {name:<40} {info.get('sha256','')[:12]}...")
            continue

        # 比对
        anomalies = _check_privacy_drift(sid, prev_sid)
        if not anomalies:
            print(f"       ✅ 隐私区指纹与前快照一致（{len(fps)} 个文件）")
        else:
            total_anomalies += len(anomalies)
            print(f"       ⚠️  SUSPICIOUS_DRIFT — {len(anomalies)} 个文件指纹变动：")
            for a in anomalies:
                prev_short = a['prev_hash'][:12] if a['prev_hash'] else "（不存在）"
                curr_short = a['curr_hash'][:12] if a['curr_hash'] else "（不存在）"
                print(f"         [{a['status']:8}] {a['file']:<40}")
                print(f"                   前: {prev_short}...  →  后: {curr_short}...")

    print(f"\n{'='*70}")
    if total_anomalies == 0:
        print(f"  ✅ 全链路无异常 — 隐私区在所有快照间保持一致")
    else:
        print(f"  ⚠️  发现 {total_anomalies} 处隐私区指纹漂移，请检查 {DRIFT_LOG}")
    print(f"{'='*70}\n")


def drift_check(snap_id: str = ""):
    """
    快速检测：把指定快照（默认最新）与其父快照做隐私区对比。
    """
    idx = load_index()
    if not snap_id:
        snap_id = idx.get("current")
    if not snap_id:
        print("  [漂移检测] 没有可检测的快照")
        return

    node = idx.get("nodes", {}).get(snap_id, {})
    parent_id = node.get("parent_id")

    if not parent_id:
        print(f"  [漂移检测] {snap_id} 是根节点，无父快照可比较")
        return

    anomalies = _check_privacy_drift(snap_id, parent_id)
    print(f"\n  [漂移检测] {snap_id}")
    print(f"  对比父快照: {parent_id}")

    if not anomalies:
        print(f"  ✅ 隐私区指纹一致，无异常")
    else:
        print(f"  ⚠️  发现 {len(anomalies)} 处指纹变动：")
        for a in anomalies:
            print(f"     [{a['status']:8}] {a['file']}")
            print(f"                前: {a['prev_hash'][:20] if a['prev_hash'] else '（无）'}...")
            print(f"                后: {a['curr_hash'][:20] if a['curr_hash'] else '（无）'}...")
        log_drift(snap_id, anomalies)
        print(f"  已记录至：{DRIFT_LOG}")


# ── 列表 & 树形显示 ───────────────────────────────────────────

def list_snapshots() -> list:
    idx = load_index()
    nodes = idx.get("nodes", {})
    result = []
    for snap_id in sorted(nodes.keys(), reverse=True):
        node = nodes[snap_id]
        result.append({
            "name": snap_id,
            "timestamp": node.get("timestamp", "?"),
            "label": node.get("label", ""),
            "file_count": node.get("file_count", 0),
            "parent_id": node.get("parent_id"),
            "children": node.get("children", []),
            "diff_from_parent": node.get("diff_from_parent", []),
            "paths": node.get("paths", []),
            "copies": len(node.get("paths", []))
        })
    # 兼容：扫描磁盘上未注册进索引的老快照
    # 支持两种布局：直接在 root/ 下 和 root/YYYY/MM/DD/ 下（新三层结构）
    def _scan_snap_root(root):
        if not os.path.exists(root):
            return
        for name in os.listdir(root):
            full = os.path.join(root, name)
            if name.startswith("snap_") and os.path.isdir(full):
                if name not in nodes:
                    result.append({
                        "name": name, "timestamp": "?", "label": "",
                        "file_count": 0, "parent_id": None, "children": [],
                        "diff_from_parent": [], "paths": [full], "copies": 1
                    })
            elif os.path.isdir(full) and len(name) == 4 and name.isdigit():
                # 年目录，继续递归
                for mm in os.listdir(full):
                    mm_path = os.path.join(full, mm)
                    if os.path.isdir(mm_path):
                        for dd in os.listdir(mm_path):
                            dd_path = os.path.join(mm_path, dd)
                            if os.path.isdir(dd_path):
                                for sname in os.listdir(dd_path):
                                    spath = os.path.join(dd_path, sname)
                                    if sname.startswith("snap_") and os.path.isdir(spath):
                                        if sname not in nodes:
                                            result.append({
                                                "name": sname, "timestamp": "?", "label": "",
                                                "file_count": 0, "parent_id": None, "children": [],
                                                "diff_from_parent": [], "paths": [spath], "copies": 1
                                            })
    # 只扫省级快照目录（索引保留在这里），不用扫今日小家（已在索引里）
    _scan_snap_root(r"C:\Users\yyds\Desktop\AI日记本\snapshots")
    return result


def print_tree():
    """打印快照树形结构"""
    idx = load_index()
    nodes = idx.get("nodes", {})
    current = idx.get("current")

    # 找根节点（没有父节点的）
    roots = [nid for nid, n in nodes.items() if not n.get("parent_id")]

    def print_node(nid, prefix="", is_last=True):
        node = nodes.get(nid, {})
        connector = "└── " if is_last else "├── "
        marker = " ◀ 当前" if nid == current else ""
        diff = node.get("diff_from_parent", [])
        diff_str = f" [变化: {','.join(diff[:2])}{'...' if len(diff)>2 else ''}]" if diff else ""
        print(f"{prefix}{connector}{nid}  {node.get('timestamp','?')}{diff_str}{marker}")
        children = node.get("children", [])
        for i, child in enumerate(children):
            extension = "    " if is_last else "│   "
            print_node(child, prefix + extension, i == len(children) - 1)

    print(f"\n🌳 快照树 (共 {len(nodes)} 个节点)")
    for i, root_id in enumerate(sorted(roots)):
        print_node(root_id, "", i == len(roots) - 1)
    print()


# ── 验证 & 恢复 ───────────────────────────────────────────────

def verify(snap_id: str = "") -> dict:
    if not snap_id:
        idx = load_index()
        snap_id = idx.get("current")
        if not snap_id:
            # fallback：扫描磁盘
            snaps = list_snapshots()
            if not snaps:
                return {"ok": False, "error": "没有任何快照"}
            snap_id = snaps[0]["name"]

    # 找快照目录
    snap_dir = None
    idx = load_index()
    node = idx.get("nodes", {}).get(snap_id)
    if node:
        for p in node.get("paths", []):
            if os.path.exists(p) and os.path.exists(os.path.join(p, "meta.json")):
                snap_dir = p
                break
    if not snap_dir:
        for root in SNAPSHOT_ROOTS:
            p = os.path.join(root, snap_id)
            if os.path.exists(p) and os.path.exists(os.path.join(p, "meta.json")):
                snap_dir = p
                break

    if not snap_dir:
        return {"ok": False, "error": f"找不到快照: {snap_id}"}

    meta_path = os.path.join(snap_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    errors = []
    for label_key, info in meta.get("files", {}).items():
        if "/" in label_key:
            dst = os.path.join(snap_dir, label_key.replace("/", os.sep))
        else:
            dst = os.path.join(snap_dir, label_key)

        if not os.path.exists(dst):
            errors.append(f"缺失: {label_key}")
            continue
        actual_hash = file_hash(dst)
        expected_hash = info.get("sha256", "")
        if expected_hash and actual_hash != expected_hash:
            errors.append(f"哈希不符: {label_key}")

    return {
        "ok": len(errors) == 0,
        "snap_dir": snap_dir,
        "snap_id": snap_id,
        "timestamp": meta.get("timestamp"),
        "parent_id": meta.get("parent_id"),
        "file_count": len(meta.get("files", {})),
        "errors": errors
    }


def restore(snap_id: str = "", dry_run: bool = False) -> dict:
    v = verify(snap_id)
    if not v["ok"]:
        return {"ok": False, "error": f"快照校验失败: {v['errors']}"}

    snap_dir = v["snap_dir"]
    meta_path = os.path.join(snap_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    restored = []
    skipped = []

    for label_key, info in meta.get("files", {}).items():
        if "/" in label_key:
            src = os.path.join(snap_dir, label_key.replace("/", os.sep))
        else:
            src = os.path.join(snap_dir, label_key)

        dst = info.get("source", "")
        if not dst:
            skipped.append(label_key)
            continue

        if dry_run:
            print(f"  [DRY] 会恢复: {src} → {dst}")
            restored.append(label_key)
            continue

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(label_key)
            print(f"  ✅ 已恢复: {label_key}")
        except Exception as e:
            skipped.append(f"{label_key}: {e}")

    return {
        "ok": len(skipped) == 0,
        "snap_dir": snap_dir,
        "timestamp": meta.get("timestamp"),
        "restored": restored,
        "skipped": skipped
    }


# ── .lan 万能格式导出 ─────────────────────────────────────────
#
# .lan 文件本质是一个 ZIP，内含：
#   meta.json         → 索引：id / parent_id / timestamp / label / diff_from_parent
#   state.json        → 所有状态内容（人类可读，任何语言解析）
#   state.msgpack     → 同一内容的 MessagePack 格式（体积小，机器快读）
#   files/            → 原始文件备份
#   decoder.py        → Python 解码器（自带，不依赖外部库）
#   decoder.sh        → Shell 解码器（Linux/Mac/Android Termux 直接用）
#   decoder.js        → Node.js 解码器（服务器/前端）
#   integrity.sha256  → 完整性校验清单
#
# 核心哲学：代码不需要环境，因为环境已经在代码里了。
#           转换器跟着数据走，数据到哪，解码器到哪。

DECODER_PY = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decoder.py — .lan 文件解码器（Python版）
自带，不依赖任何外部库。把这个文件放到任何有 Python 3 的系统就能运行。

用法：
    python decoder.py              # 显示快照摘要
    python decoder.py list         # 列出所有文件
    python decoder.py show <key>   # 显示某个文件内容
    python decoder.py extract      # 解压所有文件到当前目录
"""
import sys, os, json, zipfile, hashlib

def main():
    # 找当前目录里的 .lan 文件
    lan_files = [f for f in os.listdir(".") if f.endswith(".lan")]
    if not lan_files:
        print("当前目录没有 .lan 文件")
        sys.exit(1)
    lan_path = lan_files[0]

    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"

    with zipfile.ZipFile(lan_path, "r") as z:
        names = z.namelist()

        if cmd == "summary" or cmd == "":
            meta = json.loads(z.read("meta.json").decode("utf-8"))
            print(f"\\n📸 .lan 快照摘要")
            print(f"  ID:        {meta.get('id', '?')}")
            print(f"  时间:      {meta.get('timestamp', '?')}")
            print(f"  标签:      {meta.get('label', '')}")
            print(f"  父节点:    {meta.get('parent_id') or '无（根节点）'}")
            diff = meta.get("diff_from_parent", [])
            print(f"  变化文件:  {diff if diff else '（与父节点相同）' if meta.get('parent_id') else '（根节点）'}")
            print(f"  内含文件:  {len(names)} 个")
            print()

        elif cmd == "list":
            for name in sorted(names):
                info = z.getinfo(name)
                print(f"  {name:<50} {info.file_size:>8} bytes")

        elif cmd == "show":
            key = sys.argv[2] if len(sys.argv) > 2 else "meta.json"
            if key not in names:
                print(f"找不到: {key}")
                sys.exit(1)
            data = z.read(key)
            try:
                print(data.decode("utf-8"))
            except Exception:
                print(f"[二进制数据, {len(data)} bytes]")

        elif cmd == "extract":
            z.extractall(".")
            print(f"✅ 已解压 {len(names)} 个文件到当前目录")

        elif cmd == "verify":
            try:
                integrity = z.read("integrity.sha256").decode("utf-8")
            except Exception:
                print("❌ 找不到 integrity.sha256")
                sys.exit(1)
            ok = True
            for line in integrity.strip().splitlines():
                parts = line.split("  ", 1)
                if len(parts) != 2:
                    continue
                expected_hash, filename = parts
                if filename not in names:
                    print(f"❌ 缺失: {filename}")
                    ok = False
                    continue
                actual = hashlib.sha256(z.read(filename)).hexdigest()
                if actual != expected_hash:
                    print(f"❌ 哈希不符: {filename}")
                    ok = False
                else:
                    print(f"✅ {filename}")
            if ok:
                print("\\n✅ 所有文件完整性验证通过")

if __name__ == "__main__":
    main()
'''

DECODER_SH = '''#!/bin/sh
# decoder.sh — .lan 文件解码器（Shell版）
# 适用于 Linux / macOS / Android Termux
# 依赖：unzip（几乎所有系统都有）
#
# 用法：
#   sh decoder.sh              # 显示摘要
#   sh decoder.sh list         # 列出文件
#   sh decoder.sh extract      # 解压所有文件

LAN_FILE=$(ls *.lan 2>/dev/null | head -1)
if [ -z "$LAN_FILE" ]; then
    echo "当前目录没有 .lan 文件"
    exit 1
fi

CMD=${1:-summary}

case "$CMD" in
    summary)
        echo "\\n📸 .lan 快照 (用 python decoder.py 看详细信息)"
        unzip -p "$LAN_FILE" meta.json | grep -E '"(id|timestamp|label|parent_id)"'
        ;;
    list)
        unzip -l "$LAN_FILE"
        ;;
    extract)
        unzip -o "$LAN_FILE"
        echo "✅ 解压完成"
        ;;
    verify)
        unzip -p "$LAN_FILE" integrity.sha256 | while read hash filename; do
            actual=$(unzip -p "$LAN_FILE" "$filename" | sha256sum | cut -d" " -f1)
            if [ "$actual" = "$hash" ]; then
                echo "✅ $filename"
            else
                echo "❌ $filename (哈希不符)"
            fi
        done
        ;;
    *)
        echo "用法: sh decoder.sh [summary|list|extract|verify]"
        ;;
esac
'''

DECODER_JS = '''// decoder.js — .lan 文件解码器（Node.js版）
// 适用于 Node.js 服务器 / Electron / 前端构建环境
// 依赖：仅 Node.js 标准库
//
// 用法：
//   node decoder.js              // 显示摘要
//   node decoder.js list         // 列出文件
//   node decoder.js extract      // 解压到当前目录

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

// Node.js 没有内置 ZIP 解析，用最小实现读取 ZIP 中心目录
function readZipEntries(buf) {
    // 找 End of Central Directory
    let eocd = -1;
    for (let i = buf.length - 22; i >= 0; i--) {
        if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("不是有效的ZIP文件");
    const cdOffset = buf.readUInt32LE(eocd + 16);
    const cdCount  = buf.readUInt16LE(eocd + 10);
    const entries  = {};
    let pos = cdOffset;
    for (let i = 0; i < cdCount; i++) {
        const sig = buf.readUInt32LE(pos);
        if (sig !== 0x02014b50) break;
        const fnLen   = buf.readUInt16LE(pos + 28);
        const exLen   = buf.readUInt16LE(pos + 30);
        const cmtLen  = buf.readUInt16LE(pos + 32);
        const hdrOff  = buf.readUInt32LE(pos + 42);
        const name    = buf.slice(pos + 46, pos + 46 + fnLen).toString("utf8");
        entries[name] = hdrOff;
        pos += 46 + fnLen + exLen + cmtLen;
    }
    return entries;
}

function readEntry(buf, offset) {
    if (buf.readUInt32LE(offset) !== 0x04034b50) throw new Error("不是有效的局部文件头");
    const compMethod = buf.readUInt16LE(offset + 8);
    const compSize   = buf.readUInt32LE(offset + 18);
    const fnLen      = buf.readUInt16LE(offset + 26);
    const exLen      = buf.readUInt16LE(offset + 28);
    const dataStart  = offset + 30 + fnLen + exLen;
    const compressed = buf.slice(dataStart, dataStart + compSize);
    if (compMethod === 0) return compressed;
    if (compMethod === 8) return zlib.inflateRawSync(compressed);
    throw new Error("不支持的压缩方式: " + compMethod);
}

const lanFiles = fs.readdirSync(".").filter(f => f.endsWith(".lan"));
if (!lanFiles.length) { console.log("当前目录没有 .lan 文件"); process.exit(1); }
const buf     = fs.readFileSync(lanFiles[0]);
const entries = readZipEntries(buf);

const cmd = process.argv[2] || "summary";

if (cmd === "summary") {
    const meta = JSON.parse(readEntry(buf, entries["meta.json"]).toString("utf8"));
    console.log("\\n📸 .lan 快照摘要");
    console.log("  ID:      ", meta.id || "?");
    console.log("  时间:    ", meta.timestamp || "?");
    console.log("  标签:    ", meta.label || "");
    console.log("  父节点:  ", meta.parent_id || "无（根节点）");
    const diff = meta.diff_from_parent || [];
    console.log("  变化文件:", diff.length ? diff.join(", ") : "（与父节点相同）");
    console.log("  内含文件:", Object.keys(entries).length, "个");
} else if (cmd === "list") {
    Object.keys(entries).sort().forEach(name => console.log(" ", name));
} else if (cmd === "extract") {
    Object.entries(entries).forEach(([name, offset]) => {
        if (name.endsWith("/")) return;
        const data = readEntry(buf, offset);
        const dest = path.join(".", name);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.writeFileSync(dest, data);
    });
    console.log("✅ 解压完成，共", Object.keys(entries).length, "个文件");
} else {
    console.log("用法: node decoder.js [summary|list|extract]");
}
'''


def _simple_msgpack_encode(obj) -> bytes:
    """
    极简 MessagePack 编码器（纯标准库，不依赖 msgpack 包）。
    只支持 str / int / float / bool / None / list / dict。
    这样即使没装 msgpack 库，.lan 文件也能生成。
    真正使用时优先用 msgpack 库。
    """
    if obj is None:
        return b'\xc0'
    elif obj is True:
        return b'\xc3'
    elif obj is False:
        return b'\xc2'
    elif isinstance(obj, int):
        if 0 <= obj <= 127:
            return struct.pack("B", obj)
        elif -32 <= obj < 0:
            return struct.pack("b", obj)
        elif 0 <= obj <= 0xFF:
            return b'\xcc' + struct.pack("B", obj)
        elif 0 <= obj <= 0xFFFF:
            return b'\xcd' + struct.pack(">H", obj)
        elif 0 <= obj <= 0xFFFFFFFF:
            return b'\xce' + struct.pack(">I", obj)
        else:
            return b'\xcf' + struct.pack(">Q", obj)
    elif isinstance(obj, float):
        return b'\xcb' + struct.pack(">d", obj)
    elif isinstance(obj, str):
        encoded = obj.encode("utf-8")
        n = len(encoded)
        if n <= 31:
            return struct.pack("B", 0xa0 | n) + encoded
        elif n <= 0xFF:
            return b'\xd9' + struct.pack("B", n) + encoded
        elif n <= 0xFFFF:
            return b'\xda' + struct.pack(">H", n) + encoded
        else:
            return b'\xdb' + struct.pack(">I", n) + encoded
    elif isinstance(obj, bytes):
        n = len(obj)
        if n <= 0xFF:
            return b'\xc4' + struct.pack("B", n) + obj
        else:
            return b'\xc6' + struct.pack(">I", n) + obj
    elif isinstance(obj, list):
        n = len(obj)
        if n <= 15:
            header = struct.pack("B", 0x90 | n)
        elif n <= 0xFFFF:
            header = b'\xdc' + struct.pack(">H", n)
        else:
            header = b'\xdd' + struct.pack(">I", n)
        return header + b''.join(_simple_msgpack_encode(item) for item in obj)
    elif isinstance(obj, dict):
        n = len(obj)
        if n <= 15:
            header = struct.pack("B", 0x80 | n)
        elif n <= 0xFFFF:
            header = b'\xde' + struct.pack(">H", n)
        else:
            header = b'\xdf' + struct.pack(">I", n)
        body = b''
        for k, v in obj.items():
            body += _simple_msgpack_encode(str(k)) + _simple_msgpack_encode(v)
        return header + body
    else:
        return _simple_msgpack_encode(str(obj))


def export_lan(snap_id: str = "", output_dir: str = "") -> str:
    """
    把一个快照导出为 .lan 万能格式。
    .lan 本质是 ZIP，自带三种 decoder，任何系统都能读。
    """
    if not snap_id:
        idx = load_index()
        snap_id = idx.get("current")
        if not snap_id:
            print("❌ 没有可导出的快照")
            return ""

    v = verify(snap_id)
    if not v["ok"]:
        print(f"❌ 快照校验失败: {v.get('errors')}")
        return ""

    snap_dir = v["snap_dir"]
    if not output_dir:
        output_dir = SNAPSHOT_ROOTS[0]
    os.makedirs(output_dir, exist_ok=True)

    lan_path = os.path.join(output_dir, f"{snap_id}.lan")

    # 读快照内所有文件，构建 state 对象
    meta_path = os.path.join(snap_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    state = {"meta": meta, "files": {}}
    for label_key in meta.get("files", {}):
        if "/" in label_key:
            fp = os.path.join(snap_dir, label_key.replace("/", os.sep))
        else:
            fp = os.path.join(snap_dir, label_key)
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    state["files"][label_key] = f.read()
            except Exception:
                pass

    state_json_bytes = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")

    # 尝试用 msgpack 库，没有就用内置简易编码器
    try:
        import msgpack
        state_msgpack_bytes = msgpack.packb(state, use_bin_type=True)
    except ImportError:
        state_msgpack_bytes = _simple_msgpack_encode(state)

    # 构建 integrity.sha256
    integrity_lines = []

    with zipfile.ZipFile(lan_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # meta.json
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        integrity_lines.append(f"{hashlib.sha256(json.dumps(meta, ensure_ascii=False, indent=2).encode()).hexdigest()}  meta.json")

        # state.json（人类可读）
        zf.writestr("state.json", state_json_bytes)
        integrity_lines.append(f"{hashlib.sha256(state_json_bytes).hexdigest()}  state.json")

        # state.msgpack（机器快读，体积小）
        zf.writestr("state.msgpack", state_msgpack_bytes)
        integrity_lines.append(f"{hashlib.sha256(state_msgpack_bytes).hexdigest()}  state.msgpack")

        # 原始文件
        for label_key in meta.get("files", {}):
            if "/" in label_key:
                fp = os.path.join(snap_dir, label_key.replace("/", os.sep))
            else:
                fp = os.path.join(snap_dir, label_key)
            if os.path.exists(fp):
                arcname = f"files/{label_key}"
                zf.write(fp, arcname)
                h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
                integrity_lines.append(f"{h}  {arcname}")

        # 三种自带 decoder
        zf.writestr("decoder.py", DECODER_PY)
        zf.writestr("decoder.sh", DECODER_SH)
        zf.writestr("decoder.js", DECODER_JS)

        # integrity.sha256（完整性清单）
        integrity_content = "\n".join(integrity_lines) + "\n"
        zf.writestr("integrity.sha256", integrity_content)

        # README（告诉任何拿到这个文件的人怎么用）
        readme = f"""# {snap_id}.lan

这是澜的状态快照文件。格式：ZIP。

## 打开方式

任何系统都能读，不需要安装澜的系统：

- Windows：直接用 WinRAR / 7-Zip 打开，或改后缀为 .zip
- Linux/macOS/Android：`unzip {snap_id}.lan`
- Python：`python decoder.py`
- Shell：`sh decoder.sh`
- Node.js：`node decoder.js`

## 内含文件

- meta.json        — 快照元数据（ID / 父节点 / 时间戳）
- state.json       — 完整状态（人类可读 JSON）
- state.msgpack    — 完整状态（MessagePack，体积更小）
- files/           — 原始文件备份
- decoder.py/sh/js — 自带解码器，跟着数据走
- integrity.sha256 — 完整性校验

## 快照信息

- ID：{meta.get('id', '?')}
- 时间：{meta.get('timestamp', '?')}
- 父节点：{meta.get('parent_id') or '无（根节点）'}
- 变化文件：{meta.get('diff_from_parent', [])}
"""
        zf.writestr("README.md", readme)

    size_kb = os.path.getsize(lan_path) / 1024
    print(f"  ✅ 导出 .lan: {lan_path}")
    print(f"     大小: {size_kb:.1f} KB  内含: state.json + state.msgpack + 3个decoder")
    return lan_path


# ── flatten 压平 ──────────────────────────────────────────────

def flatten(n: int = 3, label: str = "flattened") -> str:
    """
    把最近 n 个快照压平成 1 个等价节点。
    压平后的节点记录 flattened_from，保留"曾经经过"的痕迹。
    原节点不删除，只是在树里标记为"已压平"。
    """
    snaps = list_snapshots()[:n]
    if len(snaps) < 2:
        print("❌ 快照数量不足，无法压平")
        return ""

    print(f"\n[flatten] 把最近 {len(snaps)} 个快照压平...")
    for s in snaps:
        print(f"  - {s['name']}  {s['timestamp']}")

    # 打一个新的快照作为压平结果（内容与最新一个相同）
    snap_id = take(label)

    # 在索引里记录 flattened_from
    idx = load_index()
    if snap_id in idx["nodes"]:
        idx["nodes"][snap_id]["flattened_from"] = [s["name"] for s in snaps]
        idx["nodes"][snap_id]["label"] = label
        # 标记被压平的节点
        for s in snaps:
            if s["name"] in idx["nodes"]:
                idx["nodes"][s["name"]]["flattened_into"] = snap_id
        save_index(idx)

    print(f"  ✅ 压平完成: {snap_id}")
    print(f"     合并自: {[s['name'] for s in snaps]}")
    return snap_id


# ── 归档旧快照 ────────────────────────────────────────────────

def archive_old():
    cutoff = datetime.datetime.now() - datetime.timedelta(days=ARCHIVE_DAYS)
    archived = 0
    # 扫描省级根目录（含三层子目录）
    snap_root = r"C:\Users\yyds\Desktop\AI日记本\snapshots"
    def _collect_snap_dirs(base):
        """递归收集所有 snap_YYYYMMDD_... 目录"""
        results = []
        if not os.path.exists(base):
            return results
        for name in os.listdir(base):
            full = os.path.join(base, name)
            if name.startswith("snap_") and os.path.isdir(full):
                results.append((name, full))
            elif os.path.isdir(full):
                results.extend(_collect_snap_dirs(full))
        return results
    snap_list = _collect_snap_dirs(snap_root)
    for name, snap_dir in snap_list:
            try:
                dt = datetime.datetime.strptime(name[5:20], "%Y%m%d_%H%M%S")
            except Exception:
                continue
            if dt < cutoff:
                zip_path = snap_dir + ".zip"
                if not os.path.exists(zip_path):
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for root_dir, dirs, files in os.walk(snap_dir):
                            for file in files:
                                fp = os.path.join(root_dir, file)
                                zf.write(fp, os.path.relpath(fp, snap_dir))
                    shutil.rmtree(snap_dir)
                    print(f"  📦 已归档: {name}.zip")
                    archived += 1
    print(f"  共归档 {archived} 个旧快照")


# ── 快照对话（LAN-057 集成）───────────────────────────────────

class Snapshot:
    """快照对象：能提问、能回答"""
    
    def __init__(self, snap_id: str):
        self.id = snap_id
    
    def ask(self, question: str) -> str:
        """
        快照提问：让快照解析器帮我问自己
        
        Args:
            question: 问题
        
        Returns:
            自己的回答
        """
        try:
            from lan_snapshot_parser import SnapshotParser
            parser = SnapshotParser()
            return parser.query(self.id, question)
        except Exception as e:
            return f"❌ 提问失败: {e}"
    
    def ask_other(self, other_snap_id: str, question: str) -> str:
        """
        快照 B 问快照 A
        
        Args:
            other_snap_id: 其他快照 ID
            question: 问题
        
        Returns:
            其他快照的回答
        """
        try:
            from lan_snapshot_parser import SnapshotParser
            parser = SnapshotParser()
            return parser.query(other_snap_id, question)
        except Exception as e:
            return f"❌ 提问失败: {e}"
    
    def compare_with(self, other_snap_id: str) -> dict:
        """
        对比自己与其他快照
        
        Args:
            other_snap_id: 其他快照 ID
        
        Returns:
            对比结果
        """
        try:
            from lan_snapshot_parser import SnapshotParser
            parser = SnapshotParser()
            return parser.compare(other_snap_id, self.id)
        except Exception as e:
            return {"error": str(e)}


# ── 状态摘要 ─────────────────────────────────────────────────

def status():
    idx = load_index()
    nodes = idx.get("nodes", {})
    current = idx.get("current")

    print(f"\n📸 快照状态 ({now_str()})")
    print(f"  节点总数: {len(nodes)}")
    if current and current in nodes:
        node = nodes[current]
        print(f"  当前节点: {current}")
        print(f"    时间: {node.get('timestamp', '?')}")
        print(f"    父节点: {node.get('parent_id') or '无（根节点）'}")
        diff = node.get("diff_from_parent", [])
        print(f"    变化文件: {diff if diff else '（与父节点相同）'}")
        v = verify(current)
        if v.get("ok"):
            print(f"    完整性: ✅ 通过")
        else:
            print(f"    完整性: ❌ {v.get('errors', [])}")
    print()


# ── 入口 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg2 = sys.argv[2] if len(sys.argv) > 2 else ""
    arg3 = sys.argv[3] if len(sys.argv) > 3 else ""

    if cmd == "take":
        print(f"\n[LAN-037 v3] 打状态快照 ({now_str()})")
        snap_id = take(arg2)
        
        # [v5] 快照创建后，自动解析并输出
        try:
            from lan_snapshot_parser import SnapshotParser
            parser = SnapshotParser()
            parsed = parser.parse(snap_id)
            sys.stdout.write(f"\n  [INFO] 快照解析:\n")
            sys.stdout.write(f"    能力: {parsed['capabilities']} 项\n")
            sys.stdout.write(f"    文件: {parsed['files']} 个\n")
            sys.stdout.write(f"    大小: {parsed['total_size_mb']} MB\n")
            sys.stdout.write(f"    哈希: {parsed['hash'][:16]}...\n")
            sys.stdout.flush()
        except Exception as e:
            try:
                sys.stdout.write(f"  [WARN] 解析跳过: {e}\n")
                sys.stdout.flush()
            except Exception:
                pass
    
    elif cmd == "ask":
        # 快照对话: python lan_snapshot.py ask <snap_id> <question>
        if not arg2:
            print("❌ 请提供快照 ID")
            sys.exit(1)
        
        question = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "我是什么样的？"
        
        print(f"\n[LAN-037 v5] 快照对话 ({now_str()})")
        print(f"  快照: {arg2}")
        print(f"  问题: {question}\n")
        
        snap = Snapshot(arg2)
        answer = snap.ask(question)
        print(f"  回答:\n{answer}")
    
    elif cmd == "ask-other":
        # 快照 B 问快照 A: python lan_snapshot.py ask-other <snap_b> <snap_a> <question>
        if not arg2 or not arg3:
            print("❌ 请提供快照 ID: ask-other <snap_b> <snap_a> <question>")
            sys.exit(1)
        
        question = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "我是什么样的？"
        
        print(f"\n[LAN-037 v5] 快照对话 ({now_str()})")
        print(f"  提问者: {arg2}")
        print(f"  被问者: {arg3}")
        print(f"  问题: {question}\n")
        
        snap_b = Snapshot(arg2)
        answer = snap_b.ask_other(arg3, question)
        print(f"  回答:\n{answer}")
    
    elif cmd == "compare":
        # 对比快照: python lan_snapshot.py compare <snap_before> <snap_after>
        if not arg2 or not arg3:
            print("❌ 请提供两个快照 ID: compare <snap_before> <snap_after>")
            sys.exit(1)
        
        print(f"\n[LAN-037 v5] 对比快照 ({now_str()})")
        print(f"  以前: {arg2}")
        print(f"  现在: {arg3}\n")
        
        try:
            from lan_snapshot_parser import SnapshotParser
            parser = SnapshotParser()
            diff = parser.compare(arg2, arg3)
            
            print(f"  以前：{diff['before']['timestamp']}  {diff['before']['capabilities']} 项能力")
            print(f"  现在：{diff['after']['timestamp']}  {diff['after']['capabilities']} 项能力")
            print(f"\n  趋势：{diff['summary']}")
        except Exception as e:
            print(f"  ❌ 对比失败: {e}")
    elif cmd == "list":
        snaps = list_snapshots()
        print(f"\n[LAN-037 v3] 快照列表 (共 {len(snaps)} 个):")
        for s in snaps[:20]:
            parent_str = f"← {s['parent_id'][:20]}..." if s.get('parent_id') else "（根节点）"
            print(f"  {s['name']}  {s['timestamp']}  {s['file_count']}文件  {parent_str}")
    elif cmd == "tree":
        print_tree()
    elif cmd == "verify":
        v = verify(arg2)
        if v.get("ok"):
            print(f"✅ 快照验证通过: {v['snap_id']}")
            print(f"   时间: {v['timestamp']}  文件数: {v['file_count']}")
            print(f"   父节点: {v.get('parent_id') or '无（根节点）'}")
        else:
            print(f"❌ 快照验证失败: {v.get('error', v.get('errors'))}")
    elif cmd == "restore":
        dry = "--dry" in sys.argv
        print(f"\n[LAN-037 v3] {'[DRY RUN] ' if dry else ''}从快照恢复...")
        r = restore(arg2, dry_run=dry)
        if r.get("ok"):
            print(f"✅ 恢复成功: {len(r['restored'])} 个文件")
            print(f"   来源: {r['snap_dir']}")
        else:
            print(f"❌ 恢复失败: {r.get('error')}")
    elif cmd == "export":
        print(f"\n[LAN-037 v3] 导出 .lan 万能格式...")
        export_lan(arg2)
    elif cmd == "flatten":
        n = int(arg2) if arg2.isdigit() else 3
        flatten(n)
    elif cmd == "archive":
        print(f"\n[LAN-037 v3] 归档旧快照...")
        archive_old()
    elif cmd == "drift-report":
        drift_report()
    elif cmd == "drift-check":
        drift_check(arg2)
    elif cmd == "status":
        status()
    else:
        print("用法: python lan_snapshot.py [take|list|tree|verify|restore|export|flatten|archive|drift-report|drift-check|status] [参数]")
