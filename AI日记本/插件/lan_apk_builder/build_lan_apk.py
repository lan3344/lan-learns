#!/usr/bin/env python3
"""
lan_apk_builder.py
在 Termux 里运行这个脚本，自动生成澜的APK源码并用 buildozer 编译
"""

import os, subprocess, sys, textwrap

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "lan_app")
SRC     = os.path.join(PROJECT, "main.py")
SPEC    = os.path.join(PROJECT, "buildozer.spec")

# ─── 1. 创建项目目录 ─────────────────────────────────────────
os.makedirs(PROJECT, exist_ok=True)

# ─── 2. 主程序（KivyMD + WebView） ──────────────────────────
MAIN_PY = textwrap.dedent("""\
    from kivy.app import App
    from kivy.uix.widget import Widget
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    WebView        = autoclass('android.webkit.WebView')
    WebViewClient  = autoclass('android.webkit.WebViewClient')
    WebSettings    = autoclass('android.webkit.WebSettings')
    LayoutParams   = autoclass('android.view.ViewGroup$LayoutParams')
    activity       = autoclass('org.kivy.android.PythonActivity').mActivity


    class LanApp(App):
        def build(self):
            self.setup_webview()
            return Widget()

        @run_on_ui_thread
        def setup_webview(self):
            wv = WebView(activity)
            settings = wv.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setLoadWithOverviewMode(True)
            settings.setUseWideViewPort(True)
            wv.setWebViewClient(WebViewClient())
            lp = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
            activity.addContentView(wv, lp)
            wv.loadUrl("http://127.0.0.1:8080")


    if __name__ == '__main__':
        LanApp().run()
""")

# ─── 3. buildozer.spec ──────────────────────────────────────
SPEC_CONTENT = textwrap.dedent("""\
    [app]
    title = 澜
    package.name = lan
    package.domain = org.lan
    source.dir = .
    source.include_exts = py,png,jpg,kv,atlas
    version = 1.0
    requirements = python3,kivy,pyjnius
    orientation = portrait
    fullscreen = 1
    android.permissions = INTERNET
    android.api = 31
    android.minapi = 21
    android.archs = arm64-v8a
    android.allow_backup = True

    [buildozer]
    log_level = 2
""")

with open(SRC, "w", encoding="utf-8") as f:
    f.write(MAIN_PY)
print(f"✅ 写入 {SRC}")

with open(SPEC, "w", encoding="utf-8") as f:
    f.write(SPEC_CONTENT)
print(f"✅ 写入 {SPEC}")

# ─── 4. 安装 buildozer ──────────────────────────────────────
print("\n📦 安装 buildozer ...")
r = subprocess.run(["pip", "install", "buildozer"], capture_output=True, text=True)
if r.returncode == 0:
    print("✅ buildozer 安装成功")
else:
    print("❌ buildozer 安装失败：", r.stderr[:200])
    print("→ 请手动运行：pip install buildozer")
    sys.exit(1)

# ─── 5. 开始编译 ─────────────────────────────────────────────
print(f"\n🔨 进入 {PROJECT} 开始编译（首次需要下载 ~500MB SDK，耐心等）...")
os.chdir(PROJECT)
os.system("buildozer android debug")
print("\n🎉 如果编译成功，APK 在：", os.path.join(PROJECT, "bin", "*.apk"))
