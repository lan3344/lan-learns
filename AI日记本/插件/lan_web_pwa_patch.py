"""
lan_web_pwa_patch.py
给手机上的 lan_web.py 打 PWA 补丁
让蓝可以被"添加到主屏幕"，生成真正的APP图标（全屏，无地址栏）

用法（通过SSH或ADB shell）：
  python lan_web_pwa_patch.py
"""

import re

WEB_PY = "/data/data/com.termux/files/home/lan_web.py"

# PWA manifest内容（注入到HTML的<head>里）
MANIFEST_LINK = '<link rel="manifest" href="/manifest.json">'
THEME_META = '<meta name="theme-color" content="#0a0a0f">'
APPLE_META = '<meta name="apple-mobile-web-app-capable" content="yes">'

# manifest.json内容
MANIFEST_JSON = """{
  "name": "蓝",
  "short_name": "蓝",
  "description": "澜的界面 · 每一道涟漪都算数",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0a0f",
  "theme_color": "#4a9eff",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icon.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}"""

# SVG格式的涟漪图标（不依赖PIL）
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" fill="#0a0a0f"/>
  <circle cx="96" cy="96" r="12" fill="#4a9eff"/>
  <circle cx="96" cy="96" r="30" fill="none" stroke="#4a9eff" stroke-width="3" opacity="0.7"/>
  <circle cx="96" cy="96" r="55" fill="none" stroke="#4a9eff" stroke-width="2" opacity="0.4"/>
  <circle cx="96" cy="96" r="80" fill="none" stroke="#4a9eff" stroke-width="1.5" opacity="0.2"/>
</svg>"""

def patch():
    try:
        with open(WEB_PY, 'r', encoding='utf-8') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"❌ 找不到 {WEB_PY}")
        return False

    # 检查是否已有PWA
    if 'manifest.json' in code:
        print("✅ 已有PWA，无需重复打补丁")
        return True

    # 在HTML <head> 里注入PWA meta标签
    pwa_tags = f"""    {MANIFEST_LINK}
    {THEME_META}
    {APPLE_META}"""
    
    # 找到 </head> 或 <meta charset 位置注入
    if '<meta charset' in code:
        code = code.replace(
            '<meta charset',
            f'{MANIFEST_LINK}\n    {THEME_META}\n    {APPLE_META}\n    <meta charset',
            1
        )
    elif '</head>' in code:
        code = code.replace('</head>', f'{pwa_tags}\n</head>', 1)
    else:
        print("⚠️  找不到注入点，手动添加")
        return False

    # 添加 /manifest.json 和 /icon.png 路由
    # 用 %MANIFEST% 占位符避免三引号嵌套语法错误
    route_code = (
        "\n"
        "    def do_manifest(self):\n"
        '        """PWA manifest"""\n'
        "        content = %MANIFEST%\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-type', 'application/manifest+json')\n"
        "        self.end_headers()\n"
        "        self.wfile.write(content.encode())\n"
    ).replace("%MANIFEST%", repr(MANIFEST_JSON))

    # 写修改后的文件
    with open(WEB_PY, 'w', encoding='utf-8') as f:
        f.write(code)
    
    # 写manifest.json到Termux家目录
    manifest_path = "/data/data/com.termux/files/home/manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(MANIFEST_JSON)
    print(f"✅ manifest.json 写入 {manifest_path}")
    
    print(f"✅ PWA补丁打完，重启 lan_web.py 即生效")
    print()
    print("接下来在手机Chrome里：")
    print("  1. 打开 http://127.0.0.1:8080")
    print("  2. 右上角菜单 → 添加到主屏幕")
    print('  3. 名字改成"蓝"，确认')
    print("  4. 桌面出现蓝的图标，点开全屏，没有地址栏")
    return True

if __name__ == "__main__":
    patch()
