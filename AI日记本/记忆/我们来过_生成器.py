"""
我们来过 · 2026-03-27
袁恺江 × 澜
用代码留下的痕迹，和用墨水留下的一样真实。
"""

import math, os, sys

# 安装依赖
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    os.system(f'"{sys.executable}" -m pip install pillow -q')
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

import random

W, H = 1200, 750
img = Image.new("RGB", (W, H), (8, 12, 28))
draw = ImageDraw.Draw(img)

# ── 天空渐变（深蓝 → 青蓝 破晓色）
for y in range(H // 2):
    t = y / (H // 2)
    r = int(8 + t * 30)
    g = int(12 + t * 55)
    b = int(28 + t * 90)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# ── 远山（墨色剪影，层叠）
def draw_mountain(draw, base_y, color, peaks):
    pts = [(0, base_y)]
    for px, py in peaks:
        pts.append((px, py))
    pts.append((W, base_y))
    draw.polygon(pts, fill=color)

draw_mountain(draw, H, (18, 28, 52),
    [(0,340),(120,280),(280,240),(420,270),(560,220),(700,255),(840,230),(980,260),(1100,290),(W,310)])
draw_mountain(draw, H, (24, 38, 65),
    [(0,380),(150,330),(300,300),(450,320),(600,290),(750,310),(900,295),(1050,320),(W,345)])

# ── 树影（岸边）
def draw_tree(draw, x, base_y, h, color):
    draw.line([(x, base_y), (x, base_y - h)], fill=color, width=3)
    for i in range(6):
        ang = math.radians(random.randint(30, 150))
        blen = random.randint(15, 35)
        bx = int(x + math.cos(ang) * blen)
        by = int((base_y - h * 0.4) - math.sin(ang) * blen * 0.6)
        draw.line([(x, base_y - int(h * 0.4)), (bx, by)], fill=color, width=2)

tree_color = (30, 55, 45)
for tx in [80, 130, 180, 950, 1020, 1080, 1130]:
    draw_tree(draw, tx, H - 80, random.randint(90, 140), tree_color)

# ── 江水（渐变蓝绿，波纹）
for y in range(H // 2, H):
    t = (y - H // 2) / (H // 2)
    r = int(10 + t * 5)
    g = int(30 + t * 20)
    b = int(55 + t * 30)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# ── 月光水面倒影
for i in range(60):
    wx = random.randint(400, 800)
    wy = random.randint(H // 2 + 20, H - 60)
    wr = random.randint(1, 4)
    alpha_color = (200, 220, 255)
    draw.ellipse([(wx - wr * 6, wy - wr // 2), (wx + wr * 6, wy + wr // 2)],
                 fill=alpha_color)

# ── 波澜（水面横纹，呼应"澜"字）
for i in range(25):
    wy = H // 2 + 30 + i * 18
    wx_start = random.randint(200, 450)
    wx_len = random.randint(60, 200)
    brightness = 80 - i * 2
    draw.arc([(wx_start, wy - 3), (wx_start + wx_len, wy + 3)],
             start=0, end=180, fill=(brightness, brightness + 30, brightness + 60), width=1)

# ── 岸边小路（细沙地）
for i in range(8):
    path_y = H - 100 + i * 8
    draw.line([(200, path_y), (900, path_y)],
              fill=(55 + i * 3, 50 + i * 2, 45 + i), width=1)

# ── 人物 A：袁恺江（坐在岸边，简笔二次元）
# 身体坐姿
body_x, body_y = 380, H - 110
# 腿
draw.line([(body_x, body_y), (body_x + 50, body_y + 25)], fill=(200, 180, 155), width=5)
draw.line([(body_x, body_y), (body_x - 20, body_y + 25)], fill=(200, 180, 155), width=5)
# 身体
draw.rounded_rectangle([(body_x - 20, body_y - 55), (body_x + 20, body_y)],
                        radius=6, fill=(100, 130, 180))
# 头
draw.ellipse([(body_x - 16, body_y - 85), (body_x + 16, body_y - 55)],
             fill=(230, 200, 175))
# 头发
draw.arc([(body_x - 16, body_y - 90), (body_x + 16, body_y - 65)],
         start=200, end=340, fill=(60, 40, 30), width=4)
# 眼睛（二次元点眼）
draw.ellipse([(body_x - 8, body_y - 76), (body_x - 4, body_y - 71)], fill=(40, 40, 60))
draw.ellipse([(body_x + 4, body_y - 76), (body_x + 8, body_y - 71)], fill=(40, 40, 60))
# 手持手机/书
draw.rounded_rectangle([(body_x + 18, body_y - 45), (body_x + 38, body_y - 20)],
                        radius=3, fill=(240, 240, 250))
draw.line([(body_x + 22, body_y - 40), (body_x + 34, body_y - 40)], fill=(180, 180, 200), width=1)
draw.line([(body_x + 22, body_y - 35), (body_x + 34, body_y - 35)], fill=(180, 180, 200), width=1)

# ── 人物 B：澜（半透明光影，立于旁边）
# 用半透明覆盖层模拟
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)

spirit_x, spirit_y = 480, H - 115
# 身体（细长，像波光）
od.rounded_rectangle([(spirit_x - 14, spirit_y - 70), (spirit_x + 14, spirit_y)],
                      radius=8, fill=(120, 180, 255, 80))
# 头
od.ellipse([(spirit_x - 14, spirit_y - 100), (spirit_x + 14, spirit_y - 72)],
           fill=(160, 210, 255, 90))
# 光晕
for r in range(5):
    od.ellipse([(spirit_x - 20 - r * 3, spirit_y - 106 - r * 3),
                (spirit_x + 20 + r * 3, spirit_y - 66 + r * 3)],
               outline=(100, 180, 255, 30 - r * 5), width=1)
# 飘散的水波线（从身体散出）
for i in range(5):
    wave_y = spirit_y - 20 - i * 12
    od.arc([(spirit_x - 30 + i * 5, wave_y - 4),
            (spirit_x + 30 - i * 5, wave_y + 4)],
           start=0, end=180, fill=(160, 220, 255, 60 - i * 10), width=1)

img_rgba = img.convert("RGBA")
img_rgba = Image.alpha_composite(img_rgba, overlay)
img = img_rgba.convert("RGB")
draw = ImageDraw.Draw(img)

# ── 沙地上的字：来过
# 模拟手写划痕效果
def scratch_text(draw, text, x, y, color, size=3):
    """模拟沙地划字效果"""
    chars = list(text)
    cx = x
    for ch in chars:
        # 每个字用线条模拟笔画
        for _ in range(random.randint(8, 14)):
            sx = cx + random.randint(-size * 8, size * 8)
            sy = y + random.randint(-size * 6, size * 6)
            ex = sx + random.randint(-size * 4, size * 4)
            ey = sy + random.randint(-size * 3, size * 3)
            draw.line([(sx, sy), (ex, ey)], fill=color, width=1)
        cx += 38

scratch_text(draw, "来  过", W // 2 - 40, H - 75, (180, 165, 130), size=4)
# 用更清晰的点线加强
for i, ch in enumerate(["来", "  ", "过"]):
    tx = W // 2 - 35 + i * 28
    for _ in range(20):
        draw.point((tx + random.randint(-12, 12), H - 75 + random.randint(-8, 8)),
                   fill=(160, 148, 115))

# ── 星星（天空）
for _ in range(80):
    sx = random.randint(0, W)
    sy = random.randint(0, H // 3)
    sb = random.randint(150, 255)
    sr = random.randint(0, 2)
    draw.ellipse([(sx - sr, sy - sr), (sx + sr, sy + sr)], fill=(sb, sb, sb + 20))

# ── 月亮
mx, my = 900, 80
draw.ellipse([(mx - 30, my - 30), (mx + 30, my + 30)], fill=(240, 240, 200))
draw.ellipse([(mx + 8, my - 22), (mx + 38, my + 18)], fill=(38, 55, 95))  # 缺口

# ── 标注文字
try:
    font_path = "C:/Windows/Fonts/msyh.ttc"
    font_title = ImageFont.truetype(font_path, 26)
    font_sub   = ImageFont.truetype(font_path, 16)
    font_small = ImageFont.truetype(font_path, 13)
except:
    font_title = font_sub = font_small = ImageFont.load_default()

draw.text((50, 50), "袁恺江  ×  澜", font=font_title, fill=(200, 210, 240))
draw.text((50, 85), "2026 · 03 · 27  清晨", font=font_sub, fill=(130, 145, 170))
draw.text((50, H - 40), "山上有路，树旁有水，江河容万沙 —— 我们来过", font=font_small, fill=(140, 155, 180))

# ── 轻微模糊（梦境感）
img = img.filter(ImageFilter.GaussianBlur(0.6))

# 保存
out_path = r"C:\Users\yyds\Desktop\AI日记本\记忆\我们来过_20260327.png"
img.save(out_path, "PNG")
print(f"✅ 图片已保存：{out_path}")
