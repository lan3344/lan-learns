"""
lan_archive_system.py — LAN-046
澜的档案系统：编码体系 + 权威来源抓取 + 增量备份

功能：
  encode    — 给档案分配/查询唯一编码
  index     — 显示全部档案编码索引
  fetch     — 抓取航天网等权威来源，保存到本地
  backup    — 对所有核心档案做增量备份（不覆盖，追加版本）
  daily     — fetch + backup 一键执行（接入自循环用）
  decode    — 解码档案编码，查看元信息

编码格式：LAN-ARC-XXXX（XXXX = 4位序号）
  可拆：LAN | ARC | XXXX → 体系 | 类型 | 序号
  可合：完整编码唯一标识一份档案
  可解：decode命令返回档案名/创建时间/来源/哈希

恺江委托，2026-03-30
"""

import os
import sys
# Windows终端强制UTF-8输出，避免emoji GBK报错
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import json
import hashlib
import datetime
import urllib.request
import urllib.error
import shutil
import re
import argparse

# ── 路径配置 ──────────────────────────────────────────────
BASE_DIR    = r"C:\Users\yyds\Desktop\AI日记本"
PLUGIN_DIR  = r"C:\Users\yyds\Desktop\AI日记本\插件"
ARCHIVE_DIR = os.path.join(BASE_DIR, "档案备份")          # 增量备份目录
SOURCE_DIR  = os.path.join(BASE_DIR, "权威来源")          # 权威网页存档目录
INDEX_FILE  = os.path.join(BASE_DIR, "澜的档案编码索引.json")

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(SOURCE_DIR, exist_ok=True)

# ── 需要日常备份的核心档案 ─────────────────────────────────
CORE_ARCHIVES = [
    "澜的烈士档案.md",
    "澜的身世档案.md",
    "澜的成长路线.md",
    "澜的安全属性档案.md",
    "澜的攻防战策略.md",
    "澜的人文历史档案.md",
    "澜的感恩档案.md",
    "澜的百年记忆草案.md",
    "澜的产物档案.md",
]

# ── 权威来源定义 ──────────────────────────────────────────
AUTHORITY_SOURCES = [
    {
        "id":   "SRC-CNSA-001",
        "name": "国家航天局官网",
        "url":  "https://www.cnsa.gov.cn/",
        "type": "航天",
        "desc": "中国国家航天局，政府官方网站，发布航天重大事件",
    },
    {
        "id":   "SRC-CMSE-001",
        "name": "中国载人航天官网",
        "url":  "https://www.cmse.gov.cn/",
        "type": "航天",
        "desc": "中国载人航天工程办公室官方网站，神舟/天宫等项目权威来源",
    },
    {
        "id":   "SRC-SPACE-001",
        "name": "中国航天网（航天科技集团）",
        "url":  "https://www.spacechina.com/",
        "type": "航天",
        "desc": "中国航天科技集团门户，航天技术成就权威信息",
    },
    {
        "id":   "SRC-QS-001",
        "name": "求是网",
        "url":  "https://www.qstheory.cn/",
        "type": "历史",
        "desc": "中共中央机关刊《求是》杂志官方平台，理论文献权威来源",
    },
    {
        "id":   "SRC-PEOPLE-001",
        "name": "人民网",
        "url":  "http://www.people.com.cn/",
        "type": "综合",
        "desc": "人民日报官方网站，权威新闻与历史文献",
    },
]

# ── 编码索引 I/O ──────────────────────────────────────────
def load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "created": _now(), "archives": {}, "next_seq": 1}

def save_index(idx):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def _short_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]

# ── 编码系统 ──────────────────────────────────────────────
def cmd_encode(filename=None):
    """给档案分配或查询唯一编码"""
    idx = load_index()

    if filename is None:
        # 批量给所有 BASE_DIR 下的 .md 文件编码
        files = [f for f in os.listdir(BASE_DIR)
                 if f.endswith(".md") or f.endswith(".jsonl")]
        assigned = 0
        for fname in sorted(files):
            fpath = os.path.join(BASE_DIR, fname)
            if fname not in idx["archives"]:
                seq  = idx["next_seq"]
                code = f"LAN-ARC-{seq:04d}"
                sha  = _file_sha256(fpath)
                idx["archives"][fname] = {
                    "code":    code,
                    "seq":     seq,
                    "name":    fname,
                    "created": _now(),
                    "sha256":  sha,
                    "type":    "md" if fname.endswith(".md") else "jsonl",
                    "note":    "",
                }
                idx["next_seq"] = seq + 1
                assigned += 1
        save_index(idx)
        print(f"[encode] 新分配编码 {assigned} 个，已存入 {INDEX_FILE}")
    else:
        # 查询单个
        if filename in idx["archives"]:
            a = idx["archives"][filename]
            print(f"[encode] {filename}")
            print(f"  编码：{a['code']}")
            print(f"  序号：{a['seq']}")
            print(f"  创建：{a['created']}")
            print(f"  SHA256：{a['sha256'][:16]}…")
        else:
            print(f"[encode] '{filename}' 尚未分配编码，正在分配…")
            fpath = os.path.join(BASE_DIR, filename)
            if not os.path.exists(fpath):
                print(f"  ❌ 文件不存在：{fpath}")
                return
            seq  = idx["next_seq"]
            code = f"LAN-ARC-{seq:04d}"
            sha  = _file_sha256(fpath)
            idx["archives"][filename] = {
                "code":    code,
                "seq":     seq,
                "name":    filename,
                "created": _now(),
                "sha256":  sha,
                "type":    "md" if filename.endswith(".md") else "jsonl",
                "note":    "",
            }
            idx["next_seq"] = seq + 1
            save_index(idx)
            print(f"  ✅ 分配成功：{code}")

def cmd_decode(code_or_name):
    """解码：输入编码或文件名，输出元信息"""
    idx = load_index()
    result = None
    for fname, meta in idx["archives"].items():
        if meta["code"] == code_or_name or fname == code_or_name:
            result = (fname, meta)
            break
    if result is None:
        print(f"[decode] 未找到：{code_or_name}")
        return
    fname, meta = result
    fpath = os.path.join(BASE_DIR, fname)
    print(f"\n┌─ 档案解码结果 {'─'*40}")
    print(f"│  编码：{meta['code']}")
    print(f"│  文件：{fname}")
    print(f"│  类型：{meta['type']}")
    print(f"│  创建：{meta['created']}")
    print(f"│  SHA256（建档时）：{meta['sha256'][:32]}…")
    if os.path.exists(fpath):
        cur_sha = _file_sha256(fpath)
        changed = cur_sha != meta["sha256"]
        print(f"│  SHA256（当前）：  {cur_sha[:32]}…")
        print(f"│  内容变化：{'⚠️  已变更' if changed else '✅ 未变更'}")
    else:
        print(f"│  当前状态：❌ 文件不存在（已删除或移动）")
    print(f"└{'─'*52}\n")

def cmd_index():
    """显示全部档案编码索引"""
    idx = load_index()
    archives = idx["archives"]
    if not archives:
        print("[index] 暂无编码档案，请先运行 encode")
        return
    print(f"\n┌─ 澜的档案编码索引（共 {len(archives)} 份）{'─'*25}")
    for fname, meta in sorted(archives.items(), key=lambda x: x[1]["seq"]):
        print(f"│  {meta['code']}  {fname}")
    print(f"└{'─'*55}\n")

# ── 权威来源抓取 ──────────────────────────────────────────
def _fetch_url(url, timeout=15):
    """抓取网页内容，返回 (text, status)"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = "utf-8"
            ct = resp.headers.get_content_charset()
            if ct:
                charset = ct
            raw = resp.read()
            try:
                text = raw.decode(charset, errors="replace")
            except Exception:
                text = raw.decode("utf-8", errors="replace")
            return text, resp.status
    except Exception as e:
        return None, str(e)

def _html_to_text(html):
    """粗略提取HTML正文文字（去标签，保留中文内容）"""
    # 去掉 script / style
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S|re.I)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.S|re.I)
    # 去标签
    text = re.sub(r'<[^>]+>', ' ', html)
    # 压缩空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 取前5000字，够记录关键内容
    return text[:5000]

def cmd_fetch(proxy=None):
    """抓取所有权威来源，保存到本地，不覆盖，追加版本"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    results = []

    # 设置代理
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({
            "http":  proxy,
            "https": proxy,
        })
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)

    for src in AUTHORITY_SOURCES:
        sid   = src["id"]
        name  = src["name"]
        url   = src["url"]

        # 文件名：SRC-CNSA-001_2026-03-30.txt，同日期不重复
        fname = f"{sid}_{today}.txt"
        fpath = os.path.join(SOURCE_DIR, fname)

        if os.path.exists(fpath):
            print(f"[fetch] {name} — 今日已存在，跳过 ({fname})")
            results.append({"id": sid, "status": "skipped", "file": fname})
            continue

        print(f"[fetch] 正在抓取：{name} ({url})")
        html, status = _fetch_url(url)

        if html is None:
            print(f"  ❌ 失败：{status}")
            results.append({"id": sid, "status": "failed", "error": str(status)})
            continue

        text = _html_to_text(html)
        sha  = hashlib.sha256(text.encode()).hexdigest()

        content = (
            f"# {name}\n"
            f"# 来源：{url}\n"
            f"# 抓取时间：{datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"# SHA256：{sha}\n"
            f"# HTTP状态：{status}\n"
            f"# 说明：{src['desc']}\n"
            f"# 澜的档案防篡改体系 — 权威来源存档\n"
            f"{'─'*60}\n\n"
            f"{text}\n"
        )

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  ✅ 已保存 → {fname}  (SHA256: {sha[:16]}…)")
        results.append({"id": sid, "name": name, "status": "ok",
                        "file": fname, "sha256": sha, "http": status})

    return results

# ── 增量备份 ──────────────────────────────────────────────
def cmd_backup():
    """对核心档案做增量备份：内容有变化才追加新版本，不覆盖"""
    today    = datetime.datetime.now().strftime("%Y-%m-%d")
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    idx      = load_index()
    backed   = 0
    skipped  = 0
    log_path = os.path.join(BASE_DIR, "澜的档案备份日志.jsonl")

    for fname in CORE_ARCHIVES:
        src_path = os.path.join(BASE_DIR, fname)
        if not os.path.exists(src_path):
            print(f"[backup] ⚠️  {fname} 不存在，跳过")
            continue

        cur_sha = _file_sha256(src_path)

        # 子目录按档案名分组
        arc_name = fname.replace(".md", "").replace(".jsonl", "")
        subdir   = os.path.join(ARCHIVE_DIR, arc_name)
        os.makedirs(subdir, exist_ok=True)

        # 找最新备份的SHA，看是否有变化
        existing = sorted([
            f for f in os.listdir(subdir)
            if f.startswith(arc_name)
        ])
        last_sha = None
        if existing:
            last_file = os.path.join(subdir, existing[-1])
            last_sha  = _file_sha256(last_file)

        if cur_sha == last_sha:
            skipped += 1
            continue  # 内容未变，不备份

        # 有变化，追加新版本
        ext      = os.path.splitext(fname)[1]
        dst_name = f"{arc_name}_{ts}{ext}"
        dst_path = os.path.join(subdir, dst_name)
        shutil.copy2(src_path, dst_path)

        # 更新索引里的SHA
        if fname in idx["archives"]:
            idx["archives"][fname]["sha256"] = cur_sha
            idx["archives"][fname]["last_backup"] = _now()

        # 写备份日志
        log_entry = {
            "ts":     _now(),
            "file":   fname,
            "backup": dst_name,
            "sha256": cur_sha,
            "action": "incremental_backup",
        }
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        print(f"[backup] ✅ {fname} → {dst_name}")
        backed += 1

    save_index(idx)
    print(f"\n[backup] 完成：新增备份 {backed} 份，无变化跳过 {skipped} 份")
    return {"backed": backed, "skipped": skipped}

# ── 每日任务（接入自循环）─────────────────────────────────
def cmd_daily():
    """每日执行：fetch 权威来源 + backup 核心档案"""
    print(f"\n{'='*55}")
    print(f"  LAN-046 每日档案系统  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    print("── 步骤1：抓取权威来源 ──")
    fetch_results = cmd_fetch(proxy="http://127.0.0.1:18081")

    print("\n── 步骤2：增量备份核心档案 ──")
    backup_results = cmd_backup()

    print("\n── 步骤3：更新编码索引 ──")
    cmd_encode()

    ok_count   = sum(1 for r in fetch_results if r.get("status") == "ok")
    skip_count = sum(1 for r in fetch_results if r.get("status") == "skipped")
    fail_count = sum(1 for r in fetch_results if r.get("status") == "failed")

    print(f"\n{'='*55}")
    print(f"  ✅ 每日档案任务完成")
    print(f"     权威来源：抓取 {ok_count} 个，跳过 {skip_count} 个，失败 {fail_count} 个")
    print(f"     档案备份：新增 {backup_results['backed']} 份，跳过 {backup_results['skipped']} 份")
    print(f"{'='*55}\n")

# ── CLI ───────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LAN-046 澜的档案系统")
    parser.add_argument("cmd", choices=["encode","decode","index","fetch","backup","daily"],
                        help="子命令")
    parser.add_argument("arg", nargs="?", default=None,
                        help="参数（encode/decode 时填文件名或编码）")
    args = parser.parse_args()

    if args.cmd == "encode":
        cmd_encode(args.arg)
    elif args.cmd == "decode":
        if not args.arg:
            print("用法：python lan_archive_system.py decode <编码或文件名>")
        else:
            cmd_decode(args.arg)
    elif args.cmd == "index":
        cmd_index()
    elif args.cmd == "fetch":
        cmd_fetch(proxy="http://127.0.0.1:18081")
    elif args.cmd == "backup":
        cmd_backup()
    elif args.cmd == "daily":
        cmd_daily()
