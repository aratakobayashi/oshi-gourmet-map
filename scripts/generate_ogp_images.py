#!/usr/bin/env python3
"""
generate_ogp_images.py
各グループ・サイトデフォルト用のOGP画像（1200x630 PNG）を生成する。
出力: assets/images/ogp/default.png, assets/images/ogp/{group}.png
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'assets', 'images', 'ogp')
os.makedirs(OUT_DIR, exist_ok=True)

W, H        = 1200, 630
SITE_NAME   = '推しグルメ巡礼MAP'
TAGLINE     = '推しと一緒に巡る、思い出のお店'
SHOP_SUFFIX = 'が訪れたグルメスポット'

FONT_PATH = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'

GROUP_LABELS = {
    'yonino':           'よにのちゃんねる',
    'snowman':          'Snow Man',
    'sixtones':         'SixTONES',
    'naniwa':           'なにわ男子',
    'kamenashi':        '亀梨和也',
    'ginga':            '中丸雄一 銀河チャンネル',
    'kamaitachi':       'かまいたち',
    'kodoku_no_gurume': '孤独のグルメ',
    'heysayjump':       'Hey! Say! JUMP',
    'timelesz':         'timelesz',
    'equal_love':       '=LOVE',
    'notme':            '≠ME',
    'neajoy':           '≒JOY',
    'nogizaka46':       '乃木坂46',
    'hinatazaka46':     '日向坂46',
    'sakurazaka46':     '櫻坂46',
    'shiori':           'しおりのなんとなく日常',
    'kingprince':       'King & Prince',
    'arashi':           '嵐',
    'kimura':           '木村拓哉',
    'kpop_enhypen':     'ENHYPEN',
    'kpop_seventeen':   'SEVENTEEN',
    'kpop_riize':       'RIIZE',
    'kpop_nct':         'NCT',
}

GROUP_COLORS = {
    'yonino':           ('#e8537a', '#f7a1b5'),
    'snowman':          ('#3b82f6', '#93c5fd'),
    'sixtones':         ('#7c3aed', '#a78bfa'),
    'equal_love':       ('#f43f5e', '#fb923c'),
    'notme':            ('#0d9488', '#5eead4'),
    'neajoy':           ('#d946ef', '#f0abfc'),
    'sakurazaka46':     ('#e11d48', '#fda4af'),
    'nogizaka46':       ('#0ea5e9', '#7dd3fc'),
    'hinatazaka46':     ('#f59e0b', '#fde68a'),
    'naniwa':           ('#f97316', '#fbbf24'),
    'kamenashi':        ('#059669', '#6ee7b7'),
    'ginga':            ('#6366f1', '#a5b4fc'),
    'kamaitachi':       ('#8b5cf6', '#c4b5fd'),
    'kodoku_no_gurume': ('#92400e', '#d97706'),
    'heysayjump':       ('#ef4444', '#fbbf24'),
    'timelesz':         ('#1d4ed8', '#60a5fa'),
    'shiori':           ('#ec4899', '#f9a8d4'),
    'kingprince':       ('#f472b6', '#fbcfe8'),
    'arashi':           ('#dc2626', '#fb923c'),
    'kimura':           ('#0891b2', '#67e8f9'),
    'kpop_enhypen':     ('#7c3aed', '#a78bfa'),
    'kpop_seventeen':   ('#0ea5e9', '#7dd3fc'),
    'kpop_riize':       ('#ef4444', '#fca5a5'),
    'kpop_nct':         ('#10b981', '#6ee7b7'),
}

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def make_gradient(c1, c2):
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    for x in range(W):
        t = x / (W - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(x, 0), (x, H)], fill=(r, g, b))
    return img

def add_decorations(draw):
    draw.ellipse([-80, -80, 280, 280],   fill=(255, 255, 255, 13))
    draw.ellipse([950, 380, 1350, 780],  fill=(255, 255, 255, 13))
    draw.ellipse([980, -60, 1200, 160],  fill=(255, 255, 255, 10))

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def draw_centered(draw, y, text, font, fill=(255, 255, 255)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, y), text, font=font, fill=fill)

def generate(path, c1, c2, group_name=None, subtitle=None):
    base = make_gradient(c1, c2)
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    add_decorations(draw)
    img = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

    font_site   = load_font(26)
    font_large  = load_font(88)
    font_medium = load_font(64)
    font_sub    = load_font(30)

    if group_name:
        draw_centered(draw, 58,  SITE_NAME,   font_site,   fill=(255, 255, 255, 200))
        name_font = font_large if len(group_name) <= 8 else font_medium
        bbox = draw.textbbox((0, 0), group_name, font=name_font)
        th = bbox[3] - bbox[1]
        draw_centered(draw, (H - th) // 2 - 30, group_name, name_font)
        if subtitle:
            draw_centered(draw, H - 110, subtitle, font_sub, fill=(255, 255, 255, 200))
    else:
        draw_centered(draw, 200, SITE_NAME, load_font(72))
        draw_centered(draw, 340, TAGLINE,   font_sub, fill=(255, 255, 255, 200))

    img.save(path, 'PNG', optimize=True)
    kb = os.path.getsize(path) / 1024
    print(f"  {os.path.basename(path):30} {kb:6.1f} KB")

# デフォルト
print("生成中...")
generate(os.path.join(OUT_DIR, 'default.png'), '#e8537a', '#7c3aed')

# グループ別
for group, label in sorted(GROUP_LABELS.items()):
    c1, c2 = GROUP_COLORS[group]
    out = os.path.join(OUT_DIR, f'{group}.png')
    generate(out, c1, c2, group_name=label, subtitle=SHOP_SUFFIX)

print(f"\n合計 {1 + len(GROUP_LABELS)} 件 → {OUT_DIR}")
