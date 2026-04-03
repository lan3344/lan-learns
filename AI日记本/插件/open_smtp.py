"""
open_smtp.py —— 自动打开 QQ 邮箱 SMTP 设置页
用浏览器打开账户设置，等你手动点开 SMTP 并获取授权码
"""

import asyncio
from playwright.async_api import async_playwright

async def main():
    print("=" * 50)
    print("澜的 SMTP 助手")
    print("=" * 50)
    print("正在打开浏览器...")
    print("⚠ 注意：浏览器会弹出来，请不要关闭它")
    print()

    async with async_playwright() as p:
        # 用有界面的浏览器（不隐藏窗口）
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("正在打开 QQ 邮箱登录页...")
        await page.goto("https://mail.qq.com", wait_until="domcontentloaded")
        
        print()
        print("请在弹出的浏览器里登录你的 QQ 邮箱（2505242653@qq.com）")
        print("登录完成后，程序会自动跳转到账户设置页")
        print()
        
        # 等待登录成功（检测到收件箱）
        try:
            await page.wait_for_url("**/mail.qq.com/**", timeout=120000)
            # 再等一下确保登录完成
            await asyncio.sleep(3)
            
            print("检测到已登录，正在跳转到账户设置...")
            
            # 直接跳到账户设置
            await page.goto(
                "https://mail.qq.com/cgi-bin/frame_html?tab=setting&from=",
                wait_until="domcontentloaded"
            )
            await asyncio.sleep(2)
            
            # 尝试点击「账户」菜单
            try:
                # QQ邮箱设置页里找「账户」标签
                frames = page.frames
                for frame in frames:
                    try:
                        account_link = frame.locator("text=账户")
                        count = await account_link.count()
                        if count > 0:
                            await account_link.first.click()
                            print("已点击「账户」选项")
                            await asyncio.sleep(2)
                            break
                    except:
                        continue
            except Exception as e:
                print(f"自动点击未成功，请手动点击「账户」: {e}")
            
            print()
            print("=" * 50)
            print("现在请在浏览器里：")
            print("1. 点击顶部「设置」→「账户」")
            print("2. 往下滚动找到「SMTP服务」")
            print("3. 点「开启」")
            print("4. 手机验证后，把授权码发给澜")
            print("=" * 50)
            print()
            print("浏览器会保持打开，操作完成后你可以关闭它")
            
            # 保持浏览器开着，等待用户操作
            input("操作完成后按回车关闭浏览器...")
            
        except Exception as e:
            print(f"等待超时或出错: {e}")
            print("请手动在浏览器里完成操作")
            input("按回车关闭...")
        
        await browser.close()
        print("完成，浏览器已关闭")

if __name__ == "__main__":
    asyncio.run(main())
