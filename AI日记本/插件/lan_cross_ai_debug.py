# -*- coding: utf-8 -*-
"""
调试：截图看 DeepSeek 和豆包的真实页面结构
"""
from playwright.sync_api import sync_playwright
import time, os

OUTPUT_DIR = r"C:\Users\yyds\Desktop\AI日记本\记忆"

def screenshot(target_key, url, filename):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        print(f"访问 {url} ...")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        
        # 截图
        path = os.path.join(OUTPUT_DIR, filename)
        page.screenshot(path=path, full_page=False)
        print(f"截图保存: {path}")
        
        # 打印所有输入相关元素
        print("--- 页面输入元素 ---")
        for sel in ["textarea", "input[type=text]", "[contenteditable]", "[role=textbox]"]:
            els = page.locator(sel).all()
            if els:
                print(f"  {sel}: {len(els)} 个")
                for i, el in enumerate(els[:3]):
                    try:
                        tag = el.evaluate("e => e.tagName")
                        cls = el.evaluate("e => e.className")
                        vis = el.is_visible()
                        print(f"    [{i}] {tag} class='{cls[:60]}' visible={vis}")
                    except Exception as e:
                        print(f"    [{i}] err: {e}")
        
        browser.close()

screenshot("deepseek", "https://chat.deepseek.com/", "debug_deepseek.png")
print()
screenshot("doubao", "https://www.doubao.com/chat/", "debug_doubao.png")
