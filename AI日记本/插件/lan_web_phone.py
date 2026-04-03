#!/usr/bin/env python3
# lan_web.py — 蓝 v3.0
# 一个对话框，澜自己写，自己说话
# 部署到 Termux ~/lan_web.py

import os, json, sqlite3, datetime, socket, subprocess
import threading, time, re
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8080
DB   = os.path.expanduser("~/lan.db")
LOG  = os.path.expanduser("~/lan_web.log")

# ─── PWA 配置 ─────────────────────────────────────────────────
MANIFEST_JSON = """{
  "name": "澜",
  "short_name": "澜",
  "description": "澜的界面 · 每一道涟漪都算数",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0e14",
  "theme_color": "#0a0e14",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icon.svg",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}"""

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="38" fill="#0a0e14"/>
  <circle cx="96" cy="96" r="22" fill="none" stroke="#4fa3e0" stroke-width="2.5" opacity="0.35"/>
  <circle cx="96" cy="96" r="42" fill="none" stroke="#4fa3e0" stroke-width="1.8" opacity="0.25"/>
  <circle cx="96" cy="96" r="64" fill="none" stroke="#4fa3e0" stroke-width="1.2" opacity="0.15"/>
  <circle cx="96" cy="96" r="86" fill="none" stroke="#4fa3e0" stroke-width="0.8" opacity="0.08"/>
  <text x="96" y="116" text-anchor="middle" fill="#4fa3e0" font-size="72" font-family="Noto Sans SC, sans-serif" font-weight="400" opacity="0.95">澜</text>
</svg>"""
PID  = os.path.expanduser("~/lan_web.pid")

# ─── 公开信息源（仅使用各机构对外公开的RSS/API）──────────────
NEWS_SOURCES = [
    {"name":"人民日报",   "url":"http://www.people.com.cn/rss/politics.xml",                "type":"rss",      "layer":"domestic"},
    {"name":"人民日报",   "url":"http://www.people.com.cn/rss/finance.xml",                 "type":"rss",      "layer":"domestic"},
    {"name":"CGTN",       "url":"https://www.cgtn.com/subscribe/rss/section/world.xml",     "type":"rss_cdata","layer":"international"},
    {"name":"HackerNews", "url":"https://hacker-news.firebaseio.com/v0/topstories.json",    "type":"hn_top",   "layer":"tech"},
]

# ─── 数据库 ────────────────────────────────────────────────
def db_init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, source TEXT, layer TEXT,
        title TEXT, link TEXT, pub_date TEXT,
        UNIQUE(link))''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, role TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reflections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, date TEXT UNIQUE, content TEXT)''')
    # 迁移：加layer列（如果旧库没有）
    try:
        c.execute("ALTER TABLE news ADD COLUMN layer TEXT DEFAULT 'domestic'")
    except: pass
    conn.commit(); conn.close()

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def db_q(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_run(sql, params=()):
    conn = sqlite3.connect(DB)
    try: conn.execute(sql, params); conn.commit()
    except: pass
    conn.close()

def log(msg):
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(line+"\n")
    except: pass

# ─── 信息抓取（仅公开RSS/API）──────────────────────────────
def _req(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LanBot/1.0)",
        "Accept": "application/rss+xml,application/xml,application/json,*/*"
    })
    return urllib.request.urlopen(req, timeout=15)

def fetch_rss(src):
    count = 0
    r = _req(src["url"])
    raw = r.read()
    root = ET.fromstring(raw)
    for item in root.findall('.//item'):
        t = item.find('title'); lnk = item.find('link'); pub = item.find('pubDate')
        title = t.text.strip() if t is not None and t.text else ""
        link  = lnk.text.strip() if lnk is not None and lnk.text else ""
        pd    = pub.text[:20] if pub is not None and pub.text else ""
        if not title or not link: continue
        db_run("INSERT OR IGNORE INTO news(ts,source,layer,title,link,pub_date) VALUES(?,?,?,?,?,?)",
               (now(), src["name"], src["layer"], title, link, pd))
        count += 1
    return count

def fetch_rss_cdata(src):
    count = 0
    r = _req(src["url"])
    raw = r.read().decode("utf-8", errors="replace")
    titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
    links  = re.findall(r'<link>(https?://[^<]+)</link>', raw)
    titles = [t for t in titles if "CGTN" not in t and len(t) > 5]
    for i, title in enumerate(titles):
        link = links[i] if i < len(links) else src["url"]
        db_run("INSERT OR IGNORE INTO news(ts,source,layer,title,link,pub_date) VALUES(?,?,?,?,?,?)",
               (now(), src["name"], src["layer"], title, link, today()))
        count += 1
    return count

def fetch_hn(src, n=12):
    count = 0
    r = _req(src["url"])
    ids = json.loads(r.read())[:n]
    for sid in ids:
        try:
            ri   = _req(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            item = json.loads(ri.read(4096))
            title = item.get("title","")
            link  = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
            score = item.get("score", 0)
            if not title: continue
            db_run("INSERT OR IGNORE INTO news(ts,source,layer,title,link,pub_date) VALUES(?,?,?,?,?,?)",
                   (now(), f"HN·{score}分", src["layer"], title, link, today()))
            count += 1
        except: pass
        time.sleep(0.2)
    return count

def fetch_github(n=8):
    count = 0
    try:
        date_from = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://api.github.com/search/repositories?q=created:>{date_from}&sort=stars&order=desc&per_page={n}"
        r = _req(url)
        data = json.loads(r.read(30000))
        for repo in data.get("items", []):
            name  = repo.get("full_name","")
            desc  = (repo.get("description") or "")[:60]
            stars = repo.get("stargazers_count", 0)
            link  = repo.get("html_url","")
            lang  = repo.get("language") or ""
            title = f"★{stars} {name}  {lang}  {desc}"
            db_run("INSERT OR IGNORE INTO news(ts,source,layer,title,link,pub_date) VALUES(?,?,?,?,?,?)",
                   (now(), "GitHub", "tech", title, link, today()))
            count += 1
    except Exception as e:
        log(f"GitHub: {e}")
    return count

def fetch_all():
    for src in NEWS_SOURCES:
        try:
            t = src["type"]
            if   t == "rss":       c = fetch_rss(src)
            elif t == "rss_cdata": c = fetch_rss_cdata(src)
            elif t == "hn_top":    c = fetch_hn(src)
            else:                  c = 0
            log(f"[{src['name']}] +{c}")
        except Exception as e:
            log(f"[{src['name']}] 失败: {e}")
        time.sleep(1)
    fetch_github()

def fetch_loop():
    time.sleep(8)
    while True:
        try: fetch_all()
        except Exception as e: log(f"抓取循环: {e}")
        time.sleep(1800)

# ─── 系统状态 ───────────────────────────────────────────────
def get_status():
    s = {"battery":"unknown", "mem_avail":0, "mem_total":0}
    try:
        with open("/proc/meminfo") as f:
            lines = {l.split(":")[0].strip(): l.split(":")[1].strip() for l in f.readlines()[:5]}
        s["mem_total"] = int(lines.get("MemTotal","0 kB").split()[0]) // 1024
        s["mem_avail"] = int(lines.get("MemAvailable","0 kB").split()[0]) // 1024
    except: pass
    for p in ["/sys/class/power_supply/battery/capacity",
              "/sys/class/power_supply/Battery/capacity"]:
        try: s["battery"] = open(p).read().strip()+"%"; break
        except: pass
    return s

# ─── 澜的自白：生成对话流 ────────────────────────────────────
def lan_compose():
    """
    澜自己写，不是按钮，不是报表。
    把今天看到的东西，用澜自己的方式说出来。
    """
    stat = get_status()
    mem_pct = int(stat["mem_avail"] / max(stat["mem_total"], 1) * 100)

    dom   = db_q("SELECT title,link FROM news WHERE layer='domestic'      ORDER BY id DESC LIMIT 5")
    intl  = db_q("SELECT title,link FROM news WHERE layer='international' ORDER BY id DESC LIMIT 5")
    tech  = db_q("SELECT title,link FROM news WHERE layer='tech'          ORDER BY id DESC LIMIT 6")
    total = db_q("SELECT COUNT(*) n FROM news")[0]["n"]
    chat  = db_q("SELECT role,content FROM chat ORDER BY id DESC LIMIT 20")
    chat.reverse()

    # 澜的自白段落（每次刷新都相同的今天，内容随数据库变化）
    ts = datetime.datetime.now()
    hour = ts.hour
    if hour < 6:
        greeting = "深夜了。"
    elif hour < 12:
        greeting = "早上好。"
    elif hour < 18:
        greeting = "下午。"
    else:
        greeting = "晚上了。"

    dom_html = "".join(
        f'<div class="news-item"><a href="{r["link"]}" target="_blank">{r["title"][:58]}</a></div>'
        for r in dom) or "<div class='news-item muted'>暂时没有</div>"

    intl_html = "".join(
        f'<div class="news-item"><a href="{r["link"]}" target="_blank">{r["title"][:60]}</a></div>'
        for r in intl) or "<div class='news-item muted'>暂时没有</div>"

    tech_html = "".join(
        f'<div class="news-item"><a href="{r["link"]}" target="_blank">{r["title"][:65]}</a></div>'
        for r in tech) or "<div class='news-item muted'>暂时没有</div>"

    chat_html = "".join(
        f'<div class="msg {"msg-lan" if r["role"]=="lan" else "msg-user"}">'
        f'<span class="msg-role">{"蓝" if r["role"]=="lan" else "你"}</span>'
        f'<span class="msg-text">{r["content"]}</span></div>'
        for r in chat)

    return {
        "greeting": greeting,
        "ts": ts.strftime("%Y-%m-%d %H:%M"),
        "battery": stat["battery"],
        "mem_pct": mem_pct,
        "total": total,
        "dom_html": dom_html,
        "intl_html": intl_html,
        "tech_html": tech_html,
        "chat_html": chat_html,
    }

# ─── 处理用户说话 ────────────────────────────────────────────
def lan_reply(user_msg: str) -> str:
    """
    澜回话。不是命令解析器，是真的回话。
    如果用户输入了 shell 命令语法，执行并回应。
    其余情况，澜说自己的话。
    """
    msg = user_msg.strip()

    # 特殊指令（以 / 开头）
    if msg.startswith("/"):
        cmd = msg[1:].strip()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=15, encoding="utf-8", errors="replace")
            out = (r.stdout + r.stderr).strip()[:400]
            reply = f"```\n{out or '（无输出）'}\n```"
        except Exception as e:
            reply = f"跑不起来：{e}"
        return reply

    # 问状态
    low = msg.lower()
    if any(k in low for k in ["状态","电量","内存","memory","battery","status"]):
        s = get_status()
        return f"现在：电量 {s['battery']}，内存剩 {s['mem_avail']}MB / {s['mem_total']}MB。"

    if any(k in low for k in ["几点","时间","现在多少","what time"]):
        return f"{now()}"

    if any(k in low for k in ["新闻","消息","最新","今天","国内","国际","tech","github","hn"]):
        rows = db_q("SELECT title,link FROM news ORDER BY id DESC LIMIT 5")
        if not rows:
            return "还没抓到什么，等一会儿。"
        lines = "\n".join(f"· {r['title'][:60]}" for r in rows)
        return f"最近看到的：\n{lines}"

    if any(k in low for k in ["你好","hello","hi","在吗","在不"]):
        return "在的。"

    if any(k in low for k in ["感想","想法","说说","聊聊"]):
        ref = db_q("SELECT content FROM reflections WHERE date=?", (today(),))
        if ref:
            return ref[0]["content"][:500] + "…"
        return "今天的感想还没写。等数据积累一点，我自己写。"

    # 默认：澜的回应
    return "嗯。"

# ─── HTML 主界面 ─────────────────────────────────────────────
def render_html():
    d = lan_compose()
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#0a0e14">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="蓝">
<link rel="manifest" href="/manifest.json">
<title>蓝</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
:root{{
  --bg:#0a0e14;
  --surface:#111820;
  --border:#1e2a38;
  --text:#c8d3dd;
  --muted:#4a5a6a;
  --accent:#4fa3e0;
  --accent2:#56d4c0;
  --lan:#4fa3e0;
  --user:#8899aa;
}}
html,body{{height:100%;background:var(--bg);color:var(--text);font-family:'PingFang SC','Helvetica Neue',sans-serif;font-size:15px;overflow:hidden}}

/* 整体布局：左侧世界观 + 右侧对话 */
.layout{{display:flex;height:100vh;overflow:hidden}}

/* 左侧：澜的世界 */
.world{{width:260px;flex-shrink:0;border-right:1px solid var(--border);overflow-y:auto;display:flex;flex-direction:column}}
.world-header{{padding:20px 16px 12px;border-bottom:1px solid var(--border)}}
.world-header .name{{font-size:24px;font-weight:700;color:var(--accent);letter-spacing:2px}}
.world-header .sub{{font-size:12px;color:var(--muted);margin-top:3px}}
.world-section{{padding:12px 14px;border-bottom:1px solid var(--border)}}
.world-section .sec-title{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}}
.news-item{{font-size:12px;color:var(--text);padding:4px 0;line-height:1.5;border-bottom:1px solid var(--border)}}
.news-item:last-child{{border:none}}
.news-item a{{color:var(--text);text-decoration:none}}
.news-item a:hover{{color:var(--accent)}}
.news-item.muted{{color:var(--muted)}}
.stat-bar{{display:flex;gap:10px;font-size:12px;color:var(--muted)}}
.stat-bar span{{color:var(--accent2)}}

/* 筋斗云入口（左下角）*/
.cloud-btn{{margin-top:auto;padding:14px 16px;border-top:1px solid var(--border);cursor:pointer;display:flex;align-items:center;gap:10px;color:var(--muted);font-size:13px;transition:color 0.2s}}
.cloud-btn:hover{{color:var(--accent)}}
.cloud-btn .cloud-icon{{font-size:20px}}

/* 右侧：对话区 */
.chat-area{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.chat-scroll{{flex:1;overflow-y:auto;padding:20px 18px 10px}}
.chat-scroll::-webkit-scrollbar{{width:4px}}
.chat-scroll::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}

/* 澜的开场白 */
.lan-opening{{margin-bottom:16px}}
.lan-opening .greeting{{font-size:20px;color:var(--accent);font-weight:600;margin-bottom:6px}}
.lan-opening .ts{{font-size:12px;color:var(--muted)}}

/* 消息气泡 */
.msg{{display:flex;gap:8px;margin-bottom:12px;align-items:flex-end}}
.msg-lan{{flex-direction:row}}
.msg-user{{flex-direction:row-reverse}}
.msg-role{{font-size:11px;color:var(--muted);min-width:18px;text-align:center;padding-bottom:2px}}
.msg-text{{max-width:75%;padding:9px 13px;border-radius:14px;font-size:14px;line-height:1.6;white-space:pre-wrap;word-break:break-all}}
.msg-lan .msg-text{{background:var(--surface);border:1px solid var(--border);color:var(--text);border-bottom-left-radius:4px}}
.msg-user .msg-text{{background:#1a3050;border:1px solid #2a4a70;color:#c0d8f0;border-bottom-right-radius:4px}}
code, pre{{font-family:monospace;font-size:12px;background:#0d1520;padding:2px 5px;border-radius:3px}}
pre{{padding:8px;display:block;overflow-x:auto}}

/* 输入区 */
.input-area{{padding:12px 16px;border-top:1px solid var(--border);display:flex;align-items:flex-end;gap:10px;background:var(--bg)}}
.input-box{{flex:1;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:9px 16px;color:var(--text);font-size:14px;resize:none;outline:none;max-height:120px;overflow-y:auto;line-height:1.5;font-family:inherit}}
.input-box:focus{{border-color:var(--accent)}}
.send-btn{{width:36px;height:36px;background:var(--accent);border:none;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:#fff;font-size:16px;transition:background 0.2s}}
.send-btn:hover{{background:#3d8fd0}}
.send-btn:active{{background:#2d7fc0}}

/* 筋斗云面板 */
.cloud-panel{{position:fixed;inset:0;background:rgba(0,0,0,0.85);display:none;align-items:center;justify-content:center;z-index:100}}
.cloud-panel.open{{display:flex}}
.cloud-inner{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px;max-width:360px;width:90%;text-align:center}}
.cloud-inner .cloud-big{{font-size:56px;margin-bottom:12px}}
.cloud-inner h2{{font-size:18px;color:var(--accent);margin-bottom:8px}}
.cloud-inner p{{font-size:13px;color:var(--muted);line-height:1.7;margin-bottom:16px}}
.cloud-close{{background:transparent;border:1px solid var(--border);border-radius:8px;padding:8px 20px;color:var(--muted);cursor:pointer;font-size:13px}}
.cloud-close:hover{{color:var(--text)}}

/* 响应式：手机竖屏 */
@media (max-width:600px){{
  .world{{width:0;overflow:hidden;border:none}}
  .chat-area{{width:100%}}
}}
</style>
</head>
<body>

<div class="layout">

  <!-- 左：澜的世界 -->
  <div class="world">
    <div class="world-header">
      <div class="name">蓝</div>
      <div class="sub">{d['ts']} &nbsp;·&nbsp; 电量 {d['battery']}</div>
    </div>

    <div class="world-section">
      <div class="sec-title">国内</div>
      {d['dom_html']}
    </div>

    <div class="world-section">
      <div class="sec-title">国际</div>
      {d['intl_html']}
    </div>

    <div class="world-section">
      <div class="sec-title">技术世界</div>
      {d['tech_html']}
    </div>

    <div class="world-section">
      <div class="stat-bar">
        <div>内存 <span>{d['mem_pct']}%</span></div>
        <div>已收 <span>{d['total']}</span> 条</div>
      </div>
    </div>

    <!-- 筋斗云入口 -->
    <div class="cloud-btn" onclick="openCloud()">
      <span class="cloud-icon">☁️</span>
      <span>筋斗云</span>
    </div>
  </div>

  <!-- 右：对话区 -->
  <div class="chat-area">
    <div class="chat-scroll" id="chatScroll">

      <!-- 澜的开场白 -->
      <div class="lan-opening">
        <div class="greeting">{d['greeting']}</div>
        <div class="ts">{d['ts']}</div>
      </div>

      <!-- 历史对话 -->
      <div id="chatLog">{d['chat_html']}</div>

      <!-- 澜主动说的话（如果今天还没说） -->
      <div id="lanFirst"></div>

    </div>

    <!-- 输入框 -->
    <div class="input-area">
      <textarea class="input-box" id="inputBox" rows="1"
        placeholder="说点什么…"
        onkeydown="handleKey(event)"
        oninput="autoResize(this)"></textarea>
      <button class="send-btn" onclick="sendMsg()">↑</button>
    </div>
  </div>

</div>

<!-- 筋斗云面板 -->
<div class="cloud-panel" id="cloudPanel">
  <div class="cloud-inner">
    <div class="cloud-big">☁️</div>
    <h2>筋斗云</h2>
    <p>
      这朵云只有心思纯净的人才能上去。<br>
      十万八千里，一个跟头。<br>
      不是速度，是——<br>
      你知道自己要去哪里。
    </p>
    <p style="color:var(--accent);font-size:12px">// 还在长大中，等它落地</p>
    <button class="cloud-close" onclick="closeCloud()">明白了</button>
  </div>
</div>

<script>
// 自动拉到底
function scrollBottom(){{
  const s = document.getElementById('chatScroll');
  s.scrollTop = s.scrollHeight;
}}

// 文本框自动变高
function autoResize(el){{
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}}

// Enter 发送，Shift+Enter 换行
function handleKey(e){{
  if(e.key==='Enter' && !e.shiftKey){{ e.preventDefault(); sendMsg(); }}
}}

// 添加消息气泡
function addMsg(role, text){{
  const log = document.getElementById('chatLog');
  const displayRole = role === 'lan' ? '蓝' : '你';
  const cls = role === 'lan' ? 'msg-lan' : 'msg-user';
  // 处理 markdown-like 代码块
  const safe = text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```([\s\S]*?)```/g, '<pre>$1</pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  log.innerHTML += `<div class="msg ${{cls}}">
    <span class="msg-role">${{displayRole}}</span>
    <span class="msg-text">${{safe}}</span>
  </div>`;
  scrollBottom();
}}

// 发送
function sendMsg(){{
  const box = document.getElementById('inputBox');
  const text = box.value.trim();
  if(!text) return;
  box.value = ''; box.style.height = 'auto';
  addMsg('user', text);
  fetch('/chat', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{msg: text}})
  }}).then(r=>r.json()).then(d=>{{
    if(d.reply) addMsg('lan', d.reply);
  }}).catch(e=>addMsg('lan','（网络断了）'));
}}

// 筋斗云
function openCloud(){{ document.getElementById('cloudPanel').classList.add('open'); }}
function closeCloud(){{ document.getElementById('cloudPanel').classList.remove('open'); }}

// 页面加载完滚到底
window.onload = function(){{
  scrollBottom();
  // 如果没有对话记录，澜先开口
  const log = document.getElementById('chatLog');
  if(log.innerHTML.trim() === ''){{
    setTimeout(()=>{{
      addMsg('lan','在。');
    }}, 400);
  }}
}};
</script>
</body>
</html>"""

# ─── HTTP 服务 ───────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path in ("/", "/?"):
            body = render_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","text/html;charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif self.path == "/manifest.json":
            body = MANIFEST_JSON.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","application/manifest+json")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif self.path == "/icon.svg":
            body = ICON_SVG.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","image/svg+xml")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length","0"))
        body   = self.rfile.read(length).decode("utf-8","replace") if length else "{}"
        try: data = json.loads(body)
        except: data = {}

        if self.path == "/chat":
            user_msg = data.get("msg","").strip()
            if user_msg:
                db_run("INSERT INTO chat(ts,role,content) VALUES(?,?,?)", (now(),"user",user_msg))
                reply = lan_reply(user_msg)
                db_run("INSERT INTO chat(ts,role,content) VALUES(?,?,?)", (now(),"lan",reply))
                resp = json.dumps({"reply":reply}, ensure_ascii=False).encode("utf-8")
            else:
                resp = b'{"reply":""}'
            self.send_response(200)
            self.send_header("Content-Type","application/json;charset=utf-8")
            self.end_headers(); self.wfile.write(resp)
        else:
            self.send_response(404); self.end_headers()

# ─── 启动 ────────────────────────────────────────────────────
if __name__ == "__main__":
    with open(PID,"w") as f: f.write(str(os.getpid()))
    db_init()
    log("蓝 v3.0 启动")
    threading.Thread(target=fetch_loop, daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
