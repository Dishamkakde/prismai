"""
Generate PRISM AI logo — crystal AI with rainbow prism effect.
Matches the official PRISM AI branding.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os

W, H = 800, 450

# ── Base — dark space background ──────────────────────────────
img = Image.new('RGBA', (W, H), (8, 12, 28, 255))
draw = ImageDraw.Draw(img)

# Subtle dark teal gradient overlay
for y in range(H):
    alpha = int(30 * (1 - y / H))
    draw.line([(0, y), (W, y)], fill=(0, 40, 60, alpha))

# Scattered star dots
import random
random.seed(42)
for _ in range(120):
    x = random.randint(0, W)
    y = random.randint(0, H - 130)
    r = random.choice([1, 1, 1, 2])
    bright = random.randint(120, 255)
    draw.ellipse([x-r, y-r, x+r, y+r], fill=(bright, bright, bright, random.randint(80, 200)))

# ── Crystal AI letters ─────────────────────────────────────────
# Draw the "A" shape (prism / triangle form)
cx = 310   # center x of the A
top_y = 55
bot_y = 320
left_x = cx - 130
right_x = cx + 130

# Crystal facets for "A" — layered polygons with different shades
facets_A = [
    # left face
    [(cx, top_y), (left_x, bot_y), (cx - 40, bot_y), (cx - 10, top_y + 60)],
    # right face
    [(cx, top_y), (right_x, bot_y), (cx + 40, bot_y), (cx + 10, top_y + 60)],
    # crossbar area
    [(cx - 65, top_y + 145), (cx + 65, top_y + 145), (cx + 55, top_y + 175), (cx - 55, top_y + 175)],
    # top highlight
    [(cx, top_y), (cx - 20, top_y + 50), (cx + 20, top_y + 50)],
    # inner left
    [(cx - 10, top_y + 60), (left_x + 35, bot_y), (cx - 40, bot_y)],
    # inner right
    [(cx + 10, top_y + 60), (right_x - 35, bot_y), (cx + 40, bot_y)],
]
facet_colors = [
    (140, 180, 210, 190),
    (160, 200, 230, 200),
    (120, 160, 200, 180),
    (200, 220, 240, 220),
    (100, 140, 180, 160),
    (120, 160, 200, 170),
]
for facet, color in zip(facets_A, facet_colors):
    draw.polygon(facet, fill=color)

# A outline
draw.polygon([(cx, top_y), (left_x, bot_y), (right_x, bot_y)], outline=(230, 240, 255, 220), width=4)
# crossbar
draw.line([(cx - 65, top_y + 155), (cx + 65, top_y + 155)], fill=(220, 235, 250, 200), width=8)

# "I" letter — right of A
ix = cx + 190
i_top = top_y + 10
i_bot = bot_y - 10
i_w   = 28

# I body with crystal shading
draw.rectangle([ix - i_w//2, i_top, ix + i_w//2, i_bot], fill=(150, 190, 220, 200))
draw.rectangle([ix - i_w//2 + 2, i_top, ix - 2, i_bot], fill=(180, 210, 235, 220))
# top and bottom serifs
draw.rectangle([ix - i_w, i_top, ix + i_w, i_top + 18], fill=(170, 205, 230, 210))
draw.rectangle([ix - i_w, i_bot - 18, ix + i_w, i_bot], fill=(170, 205, 230, 210))
# outline
draw.rectangle([ix - i_w//2, i_top, ix + i_w//2, i_bot], outline=(220, 235, 250, 200), width=3)
draw.rectangle([ix - i_w, i_top, ix + i_w, i_top + 18], outline=(220, 235, 250, 200), width=3)
draw.rectangle([ix - i_w, i_bot - 18, ix + i_w, i_bot], outline=(220, 235, 250, 200), width=3)

# ── Rainbow beam from prism ────────────────────────────────────
ray_origin_x = cx + 10
ray_origin_y = top_y + 15

rainbow_colors = [
    (255, 30,  30,  180),   # Red
    (255, 140,  0,  170),   # Orange
    (255, 220,  0,  170),   # Yellow
    (30,  200, 30,  160),   # Green
    (30,  80,  255, 160),   # Blue
    (148,  0,  211, 155),   # Violet
]
n = len(rainbow_colors)
spread = 55
for i, color in enumerate(rainbow_colors):
    angle = math.radians(-15 + (spread / (n - 1)) * i)
    length = 340
    ex = int(ray_origin_x + length * math.cos(angle))
    ey = int(ray_origin_y + length * math.sin(angle))
    # Draw thick rainbow ray
    for thickness in range(7, 0, -2):
        a = max(0, color[3] - thickness * 15)
        draw.line([(ray_origin_x, ray_origin_y), (ex, ey)],
                  fill=(color[0], color[1], color[2], a), width=thickness)

# White light beam coming in from left
for thickness in range(12, 0, -3):
    a = 220 - thickness * 12
    draw.line([(0, ray_origin_y - 20), (ray_origin_x, ray_origin_y)],
              fill=(255, 255, 255, max(0, a)), width=thickness)

# Sparkle at prism tip
for r, a in [(18, 60), (10, 120), (5, 200)]:
    draw.ellipse([ray_origin_x - r, ray_origin_y - r,
                  ray_origin_x + r, ray_origin_y + r],
                 fill=(255, 255, 255, a))
# 4-point star
star_len = 30
for angle in [0, 90, 45, 135]:
    rad = math.radians(angle)
    x2 = int(ray_origin_x + star_len * math.cos(rad))
    y2 = int(ray_origin_y + star_len * math.sin(rad))
    x3 = int(ray_origin_x - star_len * math.cos(rad))
    y3 = int(ray_origin_y - star_len * math.sin(rad))
    draw.line([(x2, y2), (x3, y3)], fill=(255, 255, 255, 180), width=2)

# ── Text — PRISM AI ────────────────────────────────────────────
text_y = bot_y + 18
try:
    font_large = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 72)
    font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    font_tag   = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
except:
    font_large = ImageFont.load_default()
    font_small = font_large
    font_tag   = font_large

# "PRISM" in white bold
draw.text((W//2 - 170, text_y), "PRISM", font=font_large, fill=(255, 255, 255, 255))
# "AI" in purple bold
draw.text((W//2 + 72,  text_y), "AI",    font=font_large, fill=(160, 100, 230, 255))

# Tagline
draw.text((W//2 - 155, text_y + 78), "BUILD. INNOVATE. INTELLIGENTLY.",
          font=font_tag, fill=(180, 180, 200, 200))

# ── Small sparkle bottom right ─────────────────────────────────
sx, sy = W - 40, H - 45
for length, a in [(18, 220), (10, 150)]:
    for angle in [0, 90, 45, 135]:
        rad = math.radians(angle)
        draw.line([(int(sx + length*math.cos(rad)), int(sy + length*math.sin(rad))),
                   (int(sx - length*math.cos(rad)), int(sy - length*math.sin(rad)))],
                  fill=(255, 255, 255, a), width=2)

# ── Slight glow / blur on base then composite ─────────────────
glow = img.copy().filter(ImageFilter.GaussianBlur(radius=3))
img = Image.blend(glow, img, alpha=0.75)

# ── Save ───────────────────────────────────────────────────────
os.makedirs('app/static/img', exist_ok=True)
img.save('app/static/img/logo.png', 'PNG')

# Also save a square icon version for favicon / nav
icon = img.crop((cx - 170, top_y - 20, cx + 230, bot_y + 20))
icon = icon.resize((256, 256), Image.LANCZOS)
icon.save('app/static/img/logo_icon.png', 'PNG')

print("Logo saved:  app/static/img/logo.png")
print("Icon saved:  app/static/img/logo_icon.png")
print("Done!")
