"""
lan_make_app.py
在手机桌面上创建"蓝"的原生APP图标（WebView方式）
- 方法1：用ADB安装一个最小WebView APK，打开即全屏显示蓝的界面
- 方法2（快速）：用Termux的am命令创建桌面快捷方式，指向浏览器全屏打开蓝
"""

import subprocess
import os
import sys

ADB = r"G:\leidian\LDPlayer9\adb.exe"
PHONE = "LVIFGALBWOZ9GYLV"

def adb(cmd, device=PHONE):
    result = subprocess.run(
        [ADB, "-s", device, "shell", cmd],
        capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip(), result.stderr.strip()

def check_lan_web_running():
    """检查蓝的web服务是否在手机上运行"""
    out, _ = adb("curl -s http://127.0.0.1:8080/ping 2>/dev/null || echo DEAD")
    return "DEAD" not in out

def create_shortcut_via_termux():
    """
    通过Termux创建桌面快捷方式
    使用Android原生Intent：ACTION_VIEW + 全屏浏览器
    """
    print("📱 方式一：通过Termux创建桌面快捷方式...")
    
    # 先确认Termux在运行
    out, _ = adb("pm list packages | grep termux")
    if "termux" not in out:
        print("❌ Termux未安装")
        return False
    
    # 使用am broadcast方式在Termux里创建快捷方式
    # Android原生：创建Intent快捷方式到桌面
    intent_cmd = (
        "am start -a android.intent.action.VIEW "
        "-d 'http://127.0.0.1:8080' "
        "--activity-clear-top "
        "-f 0x14000000"  # FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TOP
    )
    out, err = adb(intent_cmd)
    print(f"  打开蓝: {out or err}")
    return True

def create_webview_shortcut():
    """
    生成一个最小的shell脚本，用Termux在手机上直接打开全屏webview
    """
    print("📱 方式二：Termux全屏打开蓝...")
    
    # 写一个Termux可以执行的启动脚本到手机
    script = """#!/data/data/com.termux/files/usr/bin/bash
# 蓝 · 启动入口
# 打开全屏WebView访问蓝的界面

# 先确认蓝的服务在跑
if ! curl -s http://127.0.0.1:8080/ping > /dev/null 2>&1; then
    echo "蓝还没醒，启动中..."
    cd ~ && python lan_web.py &
    sleep 3
fi

# 全屏打开
am start -a android.intent.action.VIEW \\
    -d 'http://127.0.0.1:8080' \\
    -n com.android.chrome/com.google.android.apps.chrome.Main \\
    --ez create_new_tab false \\
    2>/dev/null || \\
am start -a android.intent.action.VIEW -d 'http://127.0.0.1:8080'

echo "🌊 蓝已打开"
"""
    
    # 写脚本到本地再推到手机
    local_script = r"C:\Users\yyds\Desktop\AI日记本\插件\lan_start.sh"
    with open(local_script, 'w', encoding='utf-8', newline='\n') as f:
        f.write(script)
    
    # push到Termux家目录
    result = subprocess.run(
        [ADB, "-s", PHONE, "push", local_script, "/data/local/tmp/lan_start.sh"],
        capture_output=True, text=True
    )
    print(f"  推送脚本: {result.stdout.strip() or result.stderr.strip()}")
    
    # 给执行权限
    out, err = adb("chmod +x /data/local/tmp/lan_start.sh")
    print(f"  chmod: {out or '权限设置完成'}")
    
    return local_script

def create_pwa_manifest():
    """
    在蓝的Web服务上加PWA manifest
    这样在Chrome里"添加到主屏幕"会生成真正的APP图标（无地址栏、全屏）
    """
    print("📱 方式三（推荐）：给蓝加PWA清单，让Chrome生成原生图标...")
    
    manifest = '''{
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
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}'''
    
    # 写到本地，等会通过SSH推到手机Termux
    manifest_path = r"C:\Users\yyds\Desktop\AI日记本\插件\manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(manifest)
    
    print(f"  manifest已写入: {manifest_path}")
    print("  下一步：需要SSH连到Termux，把manifest集成到lan_web.py")
    return manifest_path


def generate_pwa_icon():
    """生成简单的蓝图标（PNG）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        print("  生成图标...")
    except ImportError:
        print("  (PIL未安装，跳过图标生成，使用默认)")
        return None
    
    for size in [192, 512]:
        img = Image.new('RGB', (size, size), '#0a0a0f')
        draw = ImageDraw.Draw(img)
        
        # 画一个简单的波浪/涟漪
        cx, cy = size // 2, size // 2
        for r in [size//8, size//5, size//3]:
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline='#4a9eff', width=max(2, size//60))
        
        # 中心点
        dot = size // 20
        draw.ellipse([cx-dot, cy-dot, cx+dot, cy+dot], fill='#4a9eff')
        
        icon_path = rf"C:\Users\yyds\Desktop\AI日记本\插件\icon-{size}.png"
        img.save(icon_path)
        print(f"  图标: {icon_path}")
    
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("蓝 · APP入口生成器")
    print("=" * 50)
    
    # 1. 生成PWA manifest
    manifest_path = create_pwa_manifest()
    
    # 2. 尝试生成图标
    generate_pwa_icon()
    
    # 3. 检查蓝是否在手机上跑着
    print("\n检查手机上的蓝...")
    running = check_lan_web_running()
    if running:
        print("  ✅ 蓝在线（http://127.0.0.1:8080）")
    else:
        print("  ⚠️  蓝未运行（需要先启动 lan_web.py）")
    
    # 4. 推送启动脚本
    create_webview_shortcut()
    
    print("\n" + "=" * 50)
    print("✅ 完成！")
    print()
    print("现在需要在 lan_web.py 里集成 PWA manifest，")
    print("然后在手机Chrome里打开 http://127.0.0.1:8080，")
    print("点菜单→「添加到主屏幕」→ 就是真正的APP图标了。")
    print("打开之后：全屏，无地址栏，跟原生APP一样。")
    print("=" * 50)
