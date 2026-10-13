"""
post_map.py
特集記事の店を、山手線の輪を目印にした東京の地図のイラストにする（assets/img/posts/<slug>/map.svg）。
店の座標（data/shops.json）を点で打ち、山手線の内側・外側・地図の外の軒数を書く。
使い方: python scripts/post_map.py <記事のslug> [--color '#7c3aed'] [--title '…']
"""
import json
import math
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post_figures import ROOT, FONT, SERIF, INK, INK2, LINE, PAPER, esc, find_post  # noqa: E402

# 山手線の駅（緯度, 経度）。輪の順
YAMANOTE = [
    ('東京', 35.6812, 139.7671), ('有楽町', 35.6750, 139.7630), ('新橋', 35.6663, 139.7583), ('浜松町', 35.6553, 139.7571),
    ('田町', 35.6457, 139.7476), ('高輪ゲートウェイ', 35.6355, 139.7407), ('品川', 35.6285, 139.7388), ('大崎', 35.6197, 139.7286),
    ('五反田', 35.6262, 139.7236), ('目黒', 35.6340, 139.7158), ('恵比寿', 35.6467, 139.7101), ('渋谷', 35.6580, 139.7016),
    ('原宿', 35.6702, 139.7027), ('代々木', 35.6830, 139.7020), ('新宿', 35.6896, 139.7006), ('新大久保', 35.7013, 139.7000),
    ('高田馬場', 35.7126, 139.7038), ('目白', 35.7212, 139.7065), ('池袋', 35.7295, 139.7109), ('大塚', 35.7318, 139.7286),
    ('巣鴨', 35.7334, 139.7393), ('駒込', 35.7365, 139.7470), ('田端', 35.7381, 139.7608), ('西日暮里', 35.7320, 139.7668),
    ('日暮里', 35.7278, 139.7707), ('鶯谷', 35.7210, 139.7781), ('上野', 35.7141, 139.7774), ('御徒町', 35.7075, 139.7746),
    ('秋葉原', 35.6984, 139.7731), ('神田', 35.6918, 139.7709),
]
LABEL = {'東京', '品川', '恵比寿', '渋谷', '原宿', '新宿', '高田馬場', '池袋', '上野', '秋葉原', '目黒', '新橋'}
EXTRA = [('浅草', 35.7148, 139.7967), ('押上', 35.7101, 139.8135), ('六本木', 35.6628, 139.7314), ('下北沢', 35.6615, 139.6680),
         ('中目黒', 35.6440, 139.6990), ('月島', 35.6625, 139.7840), ('錦糸町', 35.6969, 139.8140)]
LAT0, LAT1, LNG0, LNG1 = 35.610, 35.748, 139.655, 139.830
W, MAPH, PAD = 420, 380, 14


def xy(lat, lng):
    kx = (W - PAD * 2) / ((LNG1 - LNG0) * math.cos(math.radians(35.68)))
    ky = kx
    h = (LAT1 - LAT0) * ky
    top = 92 + (MAPH - h) / 2
    return PAD + (lng - LNG0) * math.cos(math.radians(35.68)) * kx, top + (LAT1 - lat) * ky


def inside(lat, lng):
    pts = [(b, a) for _, a, b in YAMANOTE]
    c = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def draw(shops, color, title):
    pts = [(s['lat'], s['lng']) for s in shops if s.get('lat') and s.get('lng')]
    inmap = [(a, b) for a, b in pts if LAT0 <= a <= LAT1 and LNG0 <= b <= LNG1]
    n_in = sum(1 for a, b in inmap if inside(a, b))
    n_out = len(inmap) - n_in
    n_far = len(shops) - len(inmap)
    H = 92 + MAPH + 70
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" rx="18" fill="{PAPER}"/>',
         f'<text x="20" y="40" font-size="20" font-weight="800" fill="{INK}" font-family="{SERIF}">{esc(title)}</text>',
         f'<text x="20" y="64" font-size="12.5" fill="{INK2}">点が1軒。緑の輪は山手線、青は隅田川（目安のイラスト）</text>',
         f'<rect x="{PAD}" y="84" width="{W - PAD * 2}" height="{MAPH + 16}" rx="12" fill="#fff" stroke="{LINE}"/>']
    # 隅田川のあたり（目安）
    river = [(35.745, 139.792), (35.725, 139.800), (35.712, 139.798), (35.700, 139.793), (35.690, 139.789), (35.676, 139.785), (35.662, 139.778), (35.650, 139.772)]
    o.append('<polyline points="' + ' '.join('%.1f,%.1f' % xy(a, b) for a, b in river) + '" fill="none" stroke="#bfdbfe" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>')
    ring = ' '.join('%.1f,%.1f' % xy(a, b) for _, a, b in YAMANOTE)
    o.append(f'<polygon points="{ring}" fill="#ecfccb" fill-opacity=".55" stroke="#84cc16" stroke-width="5" stroke-linejoin="round"/>')
    for a, b in inmap:
        x, y = xy(a, b)
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{color}" fill-opacity=".82" stroke="#fff" stroke-width="1.5"/>')
    for name, a, b in YAMANOTE:
        if name not in LABEL:
            continue
        x, y = xy(a, b)
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#fff" stroke="#65a30d" stroke-width="2"/>')
        o.append(f'<text x="{x + 7:.1f}" y="{y - 6:.1f}" font-size="12.5" font-weight="700" fill="{INK}" stroke="#fff" stroke-width="3" paint-order="stroke">{esc(name)}</text>')
    for name, a, b in EXTRA:
        x, y = xy(a, b)
        o.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="12" fill="{INK2}" text-anchor="middle" stroke="#fff" stroke-width="3" paint-order="stroke">{esc(name)}</text>')
    y0 = 92 + MAPH + 34
    cells = [('山手線の内側', n_in), ('山手線の外側', n_out), ('この地図の外', n_far)]
    for i, (lab, k) in enumerate(cells):
        cx = 20 + i * 132
        o.append(f'<text x="{cx}" y="{y0}" font-size="12" fill="{INK2}">{lab}</text>')
        o.append(f'<text x="{cx}" y="{y0 + 24}" font-size="20" font-weight="800" fill="{color}">{k}<tspan font-size="13" fill="{INK2}">軒</tspan></text>')
    o.append('</svg>')
    return '\n'.join(o), W, H, (n_in, n_out, n_far)


def main():
    args = sys.argv[1:]
    slug = args[0]
    color = args[args.index('--color') + 1] if '--color' in args else '#e2553f'
    path = find_post(slug)
    text = open(path, encoding='utf-8').read()
    fm = yaml.safe_load(text.split('---', 2)[1]) or {}
    ids = [str(i) for i in (fm.get('shop_ids') or [])]
    title = args[args.index('--title') + 1] if '--title' in args else '東京の聖地マップ'
    allshops = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8'))}
    shops = [allshops[i] for i in ids if i in allshops]
    svg, w, h, n = draw(shops, color, title)
    out = os.path.join(ROOT, 'assets', 'img', 'posts', slug)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'map.svg'), 'w', encoding='utf-8').write(svg)
    print(slug, 'map.svg', w, h, '内側/外側/地図の外 =', n)


if __name__ == '__main__':
    main()
