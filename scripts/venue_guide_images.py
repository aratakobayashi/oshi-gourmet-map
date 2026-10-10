"""
venue_guide_images.py
会場ガイド（_guides/<slug>.html）の画像を、会場ごとのデータ scripts/venue_data/<slug>.json から作る。

作るもの（assets/img/guide/ の下）
- <slug>/access.svg   駅と会場の位置関係（駅の座標は国土地理院アドレス検索などで調べた値）
- <slug>/seats.svg    座席のつくり（断面のイメージ）
- <slug>/rules.svg    持ち込めないもの
- <slug>/prepare.svg  当日の準備
- <slug>.webp / <slug>_600.webp  サムネイル（写真風イラスト＋会場名＋記事の中身）
- src/<slug>.svg      サムネイルの元のイラスト（サイトには出さない）

図に書く内容はすべて venue_data の値（公式情報で確かめたもの）。このスクリプトは中身を足さない。

使い方:
  python scripts/venue_guide_images.py kyocera-dome-osaka [...]
  python scripts/venue_guide_images.py --all
サムネイルの書き出しに Chromium（Playwright）を使う。環境変数 PW_CHROME に実行ファイル、
NODE_PATH に playwright のある node_modules を指定する（scripts/render_png.js）。

venue_data の形（例は scripts/venue_data/tokyo-dome.json）
{
  "slug": "tokyo-dome", "name": "東京ドーム", "short": "東京ドーム",   # short はサムネイルの大見出し
  "type": "dome",            # dome / arena / hall / budokan / messe / stadium（イラストと断面図の形）
  "center": [35.70557, 139.75197], "size_m": 120,
  "stations": [{"name": "JR 水道橋駅", "exit": "西口", "lat": 35.7019, "lng": 139.75369}, ...],  # 最大6
  "access_note": ["1行目（26文字まで）", "2行目"],
  "seats": {"note": "図の説明（26文字まで）", "tiers": [{"label": "2階席", "desc": "..."}, ...]},  # 上の段から。最後が床面
  "rules": {"source": "出典の名前", "items": [{"icon": "bottle_frozen", "label": "凍らせた<br>ペットボトル"}, ...]},  # 6つまで
  "prepare": {"source": "出典の名前", "items": [{"icon": "card", "title": "...", "lines": ["...", "..."]}, ...]},  # 4つまで
  "thumb": {"chips": ["最寄り4駅と出口", ...], "sky": "dusk"},   # sky: dusk / blue / night
  "illust": {"tower": true, "wheel": true, "forest": false}
}
"""

import json
import math
import os
import random
import subprocess
import sys

DATA_DIR = 'scripts/venue_data'
IMG = os.environ.get('VENUE_IMG', 'assets/img/guide')
FONT = "'Hiragino Sans','Hiragino Kaku Gothic ProN','Noto Sans JP','Yu Gothic','Meiryo',sans-serif"
INK, INK2, LINE, BG, CARD = '#241F1A', '#6B6258', '#E2D9CC', '#F7F2EA', '#FFFFFF'
ACC, ACC_L = '#C2532F', '#FBE6DD'
BLUE, GREEN, PURPLE, ORANGE, TEAL, RED = '#2F6FB5', '#2E8B57', '#7A4FB5', '#D9822B', '#1F8A8A', '#C23B5A'
COLORS = [BLUE, GREEN, ORANGE, PURPLE, TEAL, RED]


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def tw(s):
    """文字列のおおよその幅（全角1・半角0.58）"""
    return sum(.58 if ord(c) < 128 else 1 for c in str(s))


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(title)}" font-family="{FONT}">'
            f'<title>{esc(title)}</title><rect width="{w}" height="{h}" rx="24" fill="{BG}"/>{body}</svg>')


def text(x, y, s, size=24, color=INK, weight=400, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>'


# ---------------------------------------------------------------- 位置関係
def access(v):
    lat0, lng0 = v['center']
    st = v['stations'][:6]
    W = 600
    # 会場と駅をまとめて囲む範囲の真ん中を地図の中心にする
    lats = [lat0] + [s['lat'] for s in st]
    lngs = [lng0] + [s['lng'] for s in st]
    clat, clng = (max(lats) + min(lats)) / 2, (max(lngs) + min(lngs)) / 2
    # 駅の印が左右のラベルの間（中央の幅140px）に収まるように縮尺を決める
    span_x = max(60, (max(lngs) - min(lngs)) * 90600 / 2)
    span_y = max(150, (max(lats) - min(lats)) * 111000 / 2)
    k = min(0.6, 72 / span_x, 250 / span_y)
    mx = 300
    half_h = max(150, span_y * k + 60)
    top = 118
    my = top + half_h + 10
    bottom = int(my + half_h + 10)

    def xy(lat, lng):
        return mx + (lng - clng) * 90600 * k, my - (lat - clat) * 111000 * k
    vx, vy = xy(lat0, lng0)
    pts = [(s, *xy(s['lat'], s['lng']), COLORS[i % len(COLORS)]) for i, s in enumerate(st)]
    title = f"{v['name']}と最寄り駅"
    b = text(30, 58, title, min(30, int(470 / tw(title))), INK, 700)
    b += text(30, 92, '北が上。位置関係のイメージです', 20, INK2)
    far = max(span_x, span_y) * 2
    sb = 100 if far < 1200 else 500
    b += f'<path d="M560 30 L572 60 L560 53 L548 60 Z" fill="{INK}"/>' + text(560, 80, 'N', 16, INK, 700, 'middle')
    b += f'<path d="M{530 - sb * k:.0f} 98 L530 98" stroke="{INK}" stroke-width="3"/>' + text(530 - sb * k / 2, 90, f'{sb}m', 15, INK2, 400, 'middle')
    b += f'<rect x="20" y="{top}" width="560" height="{bottom - top}" rx="18" fill="{CARD}" stroke="{LINE}"/>'
    r = max(26, min(64, v.get('size_m', 100) * k))
    b += f'<ellipse cx="{vx:.0f}" cy="{vy:.0f}" rx="{r:.0f}" ry="{r * .9:.0f}" fill="#EEF2F7" stroke="#9AA8BA" stroke-width="3"/>'
    for i in range(1, 3):
        b += f'<ellipse cx="{vx:.0f}" cy="{vy:.0f}" rx="{r - i * r / 3.2:.0f}" ry="{(r - i * r / 3.2) * .9:.0f}" fill="none" stroke="#C8D2DE" stroke-width="1.5"/>'
    vn = v.get('short', v['name'])
    fs = 18 if tw(vn) <= 7 else 15
    vw = 24 + tw(vn) * fs
    b += f'<rect x="{vx - vw / 2:.0f}" y="{vy + r * .9 + 6:.0f}" width="{vw:.0f}" height="32" rx="16" fill="#fff" stroke="#9AA8BA"/>'
    b += text(vx, vy + r * .9 + 28, vn, fs, INK, 700, 'middle')
    # ラベルは左右に振り分けて、重ならないように縦に並べる
    sides = {'L': [], 'R': []}
    for p in pts:
        sides['L' if p[1] < mx else 'R'].append(p)
    for side, items in sides.items():
        items.sort(key=lambda p: p[2])
        lx = 30 if side == 'L' else 380
        y_prev = top - 70
        boxes = []
        for p in items:
            y = max(p[2] - 32, y_prev + 74, top + 12)
            boxes.append([p, y])
            y_prev = y
        over = boxes[-1][1] + 64 - (bottom - 12) if boxes else 0
        if over > 0:
            for bx in boxes:
                bx[1] -= over
        for (s, x, y, col), by in boxes:
            ex, ey = (lx + 190 if side == 'L' else lx), by + 32
            nm, ex_t = s['name'], s.get('exit', '')
            b += f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{ex}" y2="{ey}" stroke="{col}" stroke-width="2.5" stroke-dasharray="6 5"/>'
            b += f'<rect x="{lx}" y="{by}" width="190" height="64" rx="12" fill="#fff" stroke="{col}" stroke-width="2.5"/>'
            b += text(lx + 10, by + 27, nm, min(19, int(170 / max(1, tw(nm)))), col, 700)
            b += text(lx + 10, by + 52, ex_t, min(16, int(170 / max(1, tw(ex_t)))), INK2)
        for (s, x, y, col), by in boxes:
            b += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="11" fill="{col}" stroke="#fff" stroke-width="4"/>'
    note = v.get('access_note') or []
    H = bottom + 20
    if note:
        b += f'<rect x="20" y="{bottom + 12}" width="560" height="{14 + 28 * len(note)}" rx="12" fill="{ACC_L}"/>'
        for i, ln in enumerate(note):
            b += text(36, bottom + 38 + i * 28, ln, min(19, int(520 / max(1, tw(ln)))), ACC, 700)
        H = bottom + 40 + 28 * len(note)
    return W, H, svg(W, H, b, f"{v['name']}と最寄り駅の位置関係")


# ---------------------------------------------------------------- 座席の断面
def seats(v):
    t = v['seats']['tiers']
    typ = v.get('type', 'dome')
    W = 600
    cols = [PURPLE, ORANGE, BLUE, TEAL, RED, GREEN]
    b = text(30, 58, '座席のつくり（断面のイメージ）', 28, INK, 700)
    b += text(30, 92, v['seats'].get('note', ''), 20, INK2)
    b += f'<rect x="20" y="118" width="560" height="300" rx="18" fill="{CARD}" stroke="{LINE}"/>'
    if typ == 'stadium':
        b += '<rect x="40" y="170" width="520" height="230" fill="#E6F0FA"/>'  # 屋根なし
    elif typ in ('dome', 'arena', 'budokan'):
        peak = 120 if typ == 'dome' else 150
        b += f'<path d="M40 400 L40 220 Q300 {peak - 10} 560 220 L560 400 Z" fill="#EEF2F7"/>'
        b += f'<path d="M40 220 Q300 {peak - 10} 560 220" fill="none" stroke="#9AA8BA" stroke-width="4"/>'
    else:
        b += '<rect x="40" y="170" width="520" height="230" fill="#EEF2F7"/><path d="M40 170 L560 170" stroke="#9AA8BA" stroke-width="4"/>'
    stands = t[:-1]
    floor = t[-1]
    n = max(1, len(stands))
    # 上の段から順に、左右の斜めの帯で描く
    for i, tier in enumerate(stands):
        c = cols[i % len(cols)]
        y1 = 250 + i * (130 / n)
        h = 130 / n - 10
        x2 = 150 + i * (60 / n) + 30
        b += f'<path d="M48 {y1:.0f} L{x2:.0f} {y1 + 50:.0f} L{x2:.0f} {y1 + 50 + h * .5:.0f} L48 {y1 + h:.0f} Z" fill="{c}"/>'
        b += f'<path d="M552 {y1:.0f} L{600 - x2:.0f} {y1 + 50:.0f} L{600 - x2:.0f} {y1 + 50 + h * .5:.0f} L552 {y1 + h:.0f} Z" fill="{c}"/>'
    b += f'<rect x="200" y="384" width="200" height="16" fill="{GREEN}"/>'
    b += '<rect x="250" y="350" width="100" height="34" rx="4" fill="#3B3346"/>' + text(300, 373, 'ステージの例', 15, '#fff', 700, 'middle')
    items = [(cols[i % len(cols)], s['label'], s.get('desc', '')) for i, s in enumerate(stands)] + [(GREEN, floor['label'], floor.get('desc', ''))]
    for i, (c, a, d) in enumerate(items):
        y = 462 + i * 62
        b += f'<rect x="30" y="{y - 24}" width="28" height="28" rx="7" fill="{c}"/>'
        b += text(72, y - 2, a, 22, INK, 700) + text(72, y + 24, d, 18 if len(d) <= 26 else 16, INK2)
    H = 462 + len(items) * 62
    return W, H, svg(W, H, b, f"{v['name']}の座席のつくり")


# ---------------------------------------------------------------- アイコン
def ic_bottle(frozen=False, big=False):
    h2 = 50 if big else 40
    s = f'<rect x="-14" y="-38" width="28" height="12" rx="3" fill="{BLUE}"/>'
    s += f'<path d="M-18 -26 L18 -26 L22 -10 L22 {h2 - 6} Q22 {h2} 16 {h2} L-16 {h2} Q-22 {h2} -22 {h2 - 6} L-22 -10 Z" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/>'
    if frozen:
        s += '<path d="M0 -4 L0 26 M-13 4 L13 18 M13 4 L-13 18" stroke="#5BA3E0" stroke-width="3"/>'
    if big:
        s += text(0, 24, '大', 18, BLUE, 700, 'middle')
    return s


ICONS = {
    'bottle': lambda: ic_bottle(),
    'bottle_frozen': lambda: ic_bottle(frozen=True),
    'bottle_big': lambda: ic_bottle(big=True),
    'bottle_can': lambda: f'<rect x="-34" y="-30" width="30" height="62" rx="6" fill="#E8EDF2" stroke="{INK2}" stroke-width="3"/><rect x="6" y="-40" width="26" height="72" rx="8" fill="#D8F0E2" stroke="{GREEN}" stroke-width="3"/><rect x="12" y="-50" width="14" height="12" fill="{GREEN}"/>',
    'alcohol': lambda: f'<path d="M-24 -30 L24 -30 L18 40 L-18 40 Z" fill="#FFF1C9" stroke="{ORANGE}" stroke-width="3"/><path d="M-24 -30 Q-12 -46 0 -34 Q12 -48 24 -30" fill="#fff" stroke="{ORANGE}" stroke-width="3"/><path d="M24 -10 Q40 -10 40 8 Q40 24 22 24" fill="none" stroke="{ORANGE}" stroke-width="4"/>',
    'pet': lambda: '<ellipse cx="0" cy="12" rx="30" ry="24" fill="#F3E2CF" stroke="#A9744A" stroke-width="3"/><circle cx="0" cy="-22" r="20" fill="#F3E2CF" stroke="#A9744A" stroke-width="3"/><path d="M-18 -34 L-24 -52 L-6 -40 M18 -34 L24 -52 L6 -40" fill="#F3E2CF" stroke="#A9744A" stroke-width="3"/>',
    'danger': lambda: f'<rect x="-34" y="-26" width="68" height="62" rx="8" fill="#EDE6F7" stroke="{PURPLE}" stroke-width="3"/><path d="M-14 -26 L-14 -40 L14 -40 L14 -26" fill="none" stroke="{PURPLE}" stroke-width="4"/><path d="M0 -12 L12 14 L-12 14 Z" fill="{ORANGE}"/><rect x="-2" y="-4" width="4" height="10" fill="#fff"/>',
    'food': lambda: f'<rect x="-36" y="-10" width="72" height="44" rx="8" fill="#FFF1C9" stroke="{ORANGE}" stroke-width="3"/><path d="M-30 -10 Q0 -40 30 -10" fill="#FFE29A" stroke="{ORANGE}" stroke-width="3"/>',
    'camera': lambda: f'<rect x="-38" y="-22" width="76" height="52" rx="8" fill="#E8EDF2" stroke="{INK2}" stroke-width="3"/><circle cx="0" cy="4" r="15" fill="#fff" stroke="{INK2}" stroke-width="3"/><rect x="-16" y="-32" width="24" height="10" rx="3" fill="{INK2}"/>',
    'stick': lambda: f'<rect x="-6" y="-46" width="12" height="80" rx="5" fill="#E8EDF2" stroke="{INK2}" stroke-width="3"/><rect x="-20" y="-56" width="40" height="22" rx="5" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/>',
    'chair': lambda: f'<path d="M-26 -30 L-26 36 M26 -30 L26 36 M-26 4 L26 4 M-26 -30 L26 -30" stroke="{INK2}" stroke-width="5" fill="none"/>',
    'umbrella': lambda: f'<path d="M-40 4 Q0 -50 40 4 Z" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/><path d="M0 4 L0 34 Q0 42 -8 42" stroke="{INK2}" stroke-width="4" fill="none"/>',
    'card': lambda: f'<rect x="-40" y="-26" width="80" height="52" rx="8" fill="{ACC_L}" stroke="{ACC}" stroke-width="3"/><rect x="-40" y="-14" width="80" height="10" fill="{ACC}"/><rect x="-30" y="8" width="24" height="8" rx="2" fill="{ACC}"/>',
    'locker': lambda: f'<rect x="-36" y="-36" width="72" height="72" rx="8" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/><line x1="0" y1="-36" x2="0" y2="36" stroke="{BLUE}" stroke-width="3"/><line x1="-36" y1="0" x2="36" y2="0" stroke="{BLUE}" stroke-width="3"/><circle cx="-8" cy="-18" r="3" fill="{BLUE}"/><circle cx="28" cy="-18" r="3" fill="{BLUE}"/>',
    'luggage': lambda: f'<rect x="-30" y="-30" width="60" height="70" rx="10" fill="#D8F0E2" stroke="{GREEN}" stroke-width="3"/><path d="M-12 -30 L-12 -44 L12 -44 L12 -30" fill="none" stroke="{GREEN}" stroke-width="4"/><circle cx="-18" cy="44" r="5" fill="{GREEN}"/><circle cx="18" cy="44" r="5" fill="{GREEN}"/>',
    'shirt': lambda: f'<path d="M-36 -26 L-14 -38 Q0 -28 14 -38 L36 -26 L28 -6 L18 -10 L18 38 L-18 38 L-18 -10 L-28 -6 Z" fill="#EDE6F7" stroke="{PURPLE}" stroke-width="3"/>',
    'train': lambda: f'<rect x="-30" y="-38" width="60" height="64" rx="12" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/><rect x="-22" y="-28" width="44" height="22" rx="4" fill="#fff" stroke="{BLUE}" stroke-width="2"/><circle cx="-14" cy="12" r="5" fill="{BLUE}"/><circle cx="14" cy="12" r="5" fill="{BLUE}"/><path d="M-20 26 L-30 42 M20 26 L30 42" stroke="{BLUE}" stroke-width="4"/>',
    'clock': lambda: f'<circle cx="0" cy="0" r="36" fill="#FFF1C9" stroke="{ORANGE}" stroke-width="3"/><path d="M0 -22 L0 0 L16 10" stroke="{ORANGE}" stroke-width="4" fill="none"/>',
    'info': lambda: f'<circle cx="0" cy="0" r="36" fill="#D8F0E2" stroke="{GREEN}" stroke-width="3"/><circle cx="0" cy="-16" r="5" fill="{GREEN}"/><rect x="-5" y="-6" width="10" height="28" rx="3" fill="{GREEN}"/>',
    'car': lambda: f'<path d="M-40 10 L-30 -16 L30 -16 L40 10 L40 26 L-40 26 Z" fill="#E8EDF2" stroke="{INK2}" stroke-width="3"/><circle cx="-22" cy="28" r="8" fill="{INK2}"/><circle cx="22" cy="28" r="8" fill="{INK2}"/>',
    'bus': lambda: f'<rect x="-38" y="-30" width="76" height="56" rx="10" fill="#D8F0E2" stroke="{GREEN}" stroke-width="3"/><rect x="-30" y="-22" width="60" height="20" rx="3" fill="#fff" stroke="{GREEN}" stroke-width="2"/><circle cx="-20" cy="30" r="7" fill="{GREEN}"/><circle cx="20" cy="30" r="7" fill="{GREEN}"/>',
    'plane': lambda: f'<path d="M-40 6 L40 -6 L46 0 L40 6 L-40 -6 Z M-6 0 L-22 -32 L-10 -32 L14 0 L-10 32 L-22 32 Z" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/>',
    'smoke': lambda: f'<rect x="-40" y="4" width="80" height="14" rx="3" fill="#E8EDF2" stroke="{INK2}" stroke-width="3"/><path d="M28 -4 Q20 -18 30 -30" stroke="{INK2}" stroke-width="3" fill="none"/>',
}


def icon(name):
    return ICONS.get(name, ICONS['info'])()


def ng(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="58" fill="none" stroke="{ACC}" stroke-width="7"/>'
            f'<line x1="{x - 41}" y1="{y + 41}" x2="{x + 41}" y2="{y - 41}" stroke="{ACC}" stroke-width="7"/>')


def rules(v):
    items = v['rules']['items'][:6]
    W = 600
    b = text(30, 58, '持ち込めないもの', 30, INK, 700)
    b += text(30, 92, v['rules'].get('note', '公演ごとのルールは主催者の案内で'), 20, INK2)
    for i, it in enumerate(items):
        col, row = i % 2, i // 2
        x0, y0 = 20 + col * 285, 118 + row * 225
        b += f'<rect x="{x0}" y="{y0}" width="275" height="212" rx="18" fill="{CARD}" stroke="{LINE}"/>'
        cx, cy = x0 + 137, y0 + 78
        b += f'<g transform="translate({cx},{cy})">{icon(it["icon"])}</g>' + ng(cx, cy)
        for j, ln in enumerate(it['label'].split('<br>')):
            b += text(cx, y0 + 170 + j * 28, ln, 22 if len(ln) <= 10 else 19, INK, 700, 'middle')
    H = 118 + ((len(items) + 1) // 2) * 225 + 10
    return W, H, svg(W, H, b, f"{v['name']}に持ち込めないもの")


def prepare(v):
    items = v['prepare']['items'][:4]
    W = 600
    cols = [ACC, BLUE, GREEN, PURPLE]
    b = text(30, 58, f'当日の準備 {len(items)}つ', 30, INK, 700)
    b += text(30, 92, v['prepare'].get('source', ''), 20, INK2)
    for i, it in enumerate(items):
        c = cols[i % 4]
        x0, y0 = 20, 118 + i * 154
        b += f'<rect x="{x0}" y="{y0}" width="560" height="140" rx="18" fill="{CARD}" stroke="{LINE}"/>'
        b += f'<rect x="{x0}" y="{y0}" width="8" height="140" rx="4" fill="{c}"/>'
        b += f'<g transform="translate({x0 + 70},{y0 + 72}) scale(.9)">{icon(it["icon"])}</g>'
        b += text(x0 + 130, y0 + 46, it['title'], 24 if len(it['title']) <= 15 else 20, c, 700)
        for j, ln in enumerate(it['lines'][:2]):
            b += text(x0 + 130, y0 + 86 + j * 30, ln, 20 if len(ln) <= 20 else 18, INK)
    H = 118 + len(items) * 154 + 6
    return W, H, svg(W, H, b, f"{v['name']}に行く日の準備")


# ---------------------------------------------------------------- 写真風イラスト
SKIES = {
    'dusk': ['#17213f', '#4a4676', '#c97f78', '#f2b07e', '#f7cf9b'],
    'blue': ['#0f1d3d', '#26407a', '#4f78b3', '#93b7d9', '#d9e6f0'],
    'night': ['#0b1024', '#1b2350', '#3a3f7a', '#6a5a8f', '#a07a9a'],
}


def building(typ, cx, base, rnd, opt):
    r = rnd.uniform
    if typ == 'dome':
        rx, ry = 345, 150
        roof = f'M{cx - rx},{base} A{rx},{ry} 0 0 1 {cx + rx},{base} Z'
        s = f'<path d="M{cx - rx - 6},{base} L{cx - rx + 14},{base + 62} L{cx + rx - 14},{base + 62} L{cx + rx + 6},{base} Z" fill="url(#wall)"/>'
        if opt.get('open_sides'):
            s += ''.join(f'<rect x="{cx - rx + 10 + i * 46}" y="{base}" width="10" height="62" fill="#8b97a8"/>' for i in range(15))
        else:
            s += ''.join(f'<rect x="{cx - rx + 26 + i * 24}" y="{base + 18}" width="14" height="22" rx="2" fill="#ffe2b0" opacity="{r(.55, 1):.2f}"/>' for i in range(28))
        s += f'<path d="{roof}" fill="url(#roof)"/><path d="{roof}" fill="url(#rim)"/>'
        for i in range(1, 15):
            xx = cx - rx + 2 * rx * i / 15
            top = base - ry * math.sqrt(max(0, 1 - ((xx - cx) / rx) ** 2))
            s += f'<path d="M{xx:.1f},{base} L{xx:.1f},{top:.1f}" stroke="#9fb0c4" stroke-width="1.2" opacity=".35"/>'
        s += f'<path d="M{cx - rx - 8},{base} L{cx + rx + 8},{base}" stroke="#e8edf3" stroke-width="5"/>'
        return s
    if typ == 'arena':
        w, h = 620, 120
        x0 = cx - w / 2
        s = f'<rect x="{x0}" y="{base - h + 62}" width="{w}" height="{h}" rx="14" fill="url(#wall)"/>'
        s += f'<path d="M{x0 - 20},{base - h + 66} Q{cx},{base - h - 40} {x0 + w + 20},{base - h + 66} Z" fill="url(#roof)"/>'
        for i in range(1, 12):
            xx = x0 - 20 + (w + 40) * i / 12
            s += f'<path d="M{xx:.0f},{base - h + 66} L{cx + (xx - cx) * .6:.0f},{base - h - 12}" stroke="#9fb0c4" stroke-width="1.2" opacity=".4"/>'
        s += f'<rect x="{x0 + 20}" y="{base - h + 84}" width="{w - 40}" height="40" fill="#2c3550" opacity=".85"/>'
        s += ''.join(f'<rect x="{x0 + 26 + i * 25}" y="{base - h + 90}" width="17" height="28" fill="#ffe2b0" opacity="{r(.45, 1):.2f}"/>' for i in range(23))
        s += f'<rect x="{cx - 120}" y="{base + 30}" width="240" height="32" fill="#ffe7bd" opacity=".9"/><path d="M{cx - 150},{base + 30} L{cx + 150},{base + 30}" stroke="#e8edf3" stroke-width="6"/>'
        return s
    if typ == 'hall':
        w, h = 520, 230
        x0 = cx - w / 2
        s = f'<rect x="{x0}" y="{base + 62 - h}" width="{w}" height="{h}" rx="10" fill="url(#wall)"/>'
        # 劇場らしいガラスの大きな正面（縦長のガラスと明かり）
        s += f'<rect x="{x0 + 30}" y="{base + 62 - h + 40}" width="{w - 60}" height="{h - 70}" fill="#2c3550"/>'
        for i in range(19):
            s += f'<rect x="{x0 + 36 + i * 24.4:.0f}" y="{base + 62 - h + 46}" width="18" height="{h - 82}" fill="#ffe2b0" opacity="{r(.35, .9):.2f}"/>'
        s += f'<rect x="{x0 + 30}" y="{base + 62 - h + 40 + (h - 70) * .45:.0f}" width="{w - 60}" height="6" fill="#d6dde7"/>'
        s += f'<path d="M{x0 - 30},{base + 62 - h} L{x0 + w + 30},{base + 62 - h}" stroke="#e8edf3" stroke-width="8"/>'
        s += f'<path d="M{x0 - 40},{base + 20} L{x0 + w + 40},{base + 20}" stroke="#d6dde7" stroke-width="10"/>'
        return s
    if typ == 'budokan':
        s = f'<path d="M{cx - 250},{base + 62} L{cx - 230},{base - 20} L{cx + 230},{base - 20} L{cx + 250},{base + 62} Z" fill="url(#wall)"/>'
        s += ''.join(f'<rect x="{cx - 220 + i * 30}" y="{base}" width="16" height="40" fill="#ffe2b0" opacity="{r(.5, 1):.2f}"/>' for i in range(15))
        s += f'<path d="M{cx - 300},{base - 16} Q{cx - 150},{base - 40} {cx - 60},{base - 150} L{cx + 60},{base - 150} Q{cx + 150},{base - 40} {cx + 300},{base - 16} Z" fill="url(#roof)"/>'
        s += f'<path d="M{cx - 300},{base - 16} L{cx + 300},{base - 16}" stroke="#e8edf3" stroke-width="6"/>'
        s += f'<path d="M{cx - 60},{base - 150} L{cx + 60},{base - 150}" stroke="#cfd8e4" stroke-width="4"/>'
        s += f'<circle cx="{cx}" cy="{base - 178}" r="20" fill="#e3b54a"/><path d="M{cx},{base - 220} Q{cx + 10},{base - 198} {cx},{base - 192} Q{cx - 10},{base - 198} {cx},{base - 220} Z" fill="#e3b54a"/><rect x="{cx - 8}" y="{base - 162}" width="16" height="14" fill="#c99a35"/>'
        return s
    if typ == 'stadium':
        # 屋根のない競技場: すり鉢形のスタンドと照明塔
        w = 760
        x0 = cx - w / 2
        s = f'<path d="M{x0},{base + 62} L{x0 + 40},{base - 70} L{x0 + w - 40},{base - 70} L{x0 + w},{base + 62} Z" fill="url(#wall)"/>'
        s += f'<path d="M{x0 + 40},{base - 70} Q{cx},{base - 110} {x0 + w - 40},{base - 70}" fill="none" stroke="#e8edf3" stroke-width="8"/>'
        s += f'<path d="M{x0 + 60},{base - 60} L{x0 + w - 60},{base - 60} L{x0 + w - 110},{base + 10} L{x0 + 110},{base + 10} Z" fill="#3a4a66" opacity=".8"/>'
        s += ''.join(f'<rect x="{x0 + 30 + i * 26}" y="{base + 24}" width="14" height="20" fill="#ffe2b0" opacity="{r(.45, 1):.2f}"/>' for i in range(28))
        for lx in (x0 + 20, x0 + w - 20):
            s += f'<path d="M{lx},{base - 40} L{lx},{base - 200}" stroke="#cfd8e4" stroke-width="6"/>'
            s += f'<rect x="{lx - 34}" y="{base - 230}" width="68" height="34" rx="4" fill="#fff7dc"/><ellipse cx="{lx}" cy="{base - 214}" rx="120" ry="60" fill="url(#lamp)" opacity=".7"/>'
        return s
    if typ == 'messe':
        w = 980
        x0 = cx - w / 2
        s = f'<rect x="{x0}" y="{base - 20}" width="{w}" height="82" fill="url(#wall)"/>'
        wave = f'M{x0 - 10},{base - 18} ' + ' '.join(f'Q{x0 + i * 140 + 70},{base - 90} {x0 + (i + 1) * 140},{base - 18}' for i in range(7)) + ' Z'
        s += f'<path d="{wave}" fill="url(#roof)"/>'
        s += ''.join(f'<rect x="{x0 + 14 + i * 32}" y="{base}" width="22" height="34" fill="#ffe2b0" opacity="{r(.4, 1):.2f}"/>' for i in range(30))
        return s
    return ''


def illustration(v):
    rnd = random.Random(v['slug'])
    r = rnd.uniform
    W, H = 1200, 675
    cx, base = 590, 470
    opt = v.get('illust', {})
    sky = SKIES.get(v.get('thumb', {}).get('sky', 'dusk'), SKIES['dusk'])
    bld, x = [], -20
    while x < W + 20:
        w = rnd.randint(36, 100)
        h = rnd.randint(70, 240)
        bld.append((x, w, h))
        x += w + rnd.randint(-8, 4)
    if opt.get('forest'):
        far = ''.join(f'<ellipse cx="{x + w / 2}" cy="{452 - h * .3}" rx="{w * .8:.0f}" ry="{h * .35:.0f}" fill="#1f3a2e" opacity=".9"/>' for x, w, h in bld)
        wins = ''
    else:
        far = ''.join(f'<rect x="{x}" y="{452 - h}" width="{w}" height="{h + 10}" fill="url(#far)"/>' for x, w, h in bld)
        wins = ''.join(f'<rect x="{xx}" y="{yy}" width="4" height="6" fill="#ffd9a0" opacity="{r(.25, .8):.2f}"/>'
                       for x, w, h in bld for yy in range(452 - h + 10, 446, 12) for xx in range(x + 5, x + w - 5, 9) if rnd.random() < .28)
    stars = ''.join(f'<circle cx="{r(0, W):.0f}" cy="{r(0, 170):.0f}" r="{r(.4, 1.1):.1f}" fill="#fff" opacity="{r(.2, .7):.2f}"/>' for _ in range(70))
    extra = ''
    if opt.get('tower'):
        extra += '<path d="M150,140 L272,140 L272,488 L150,488 Z" fill="url(#tower)"/>' + ''.join(
            f'<rect x="{159 + c * 15}" y="{154 + rr * 17}" width="8" height="9" fill="#ffe2b0" opacity="{r(.2, .95):.2f}"/>' for rr in range(19) for c in range(7) if rnd.random() < .55)
    if opt.get('wheel'):
        extra += '<g opacity=".9"><circle cx="1015" cy="290" r="128" fill="none" stroke="#dfe6ef" stroke-width="7"/>' + ''.join(
            f'<line x1="1015" y1="290" x2="{1015 + 128 * math.cos(a * math.pi / 14):.1f}" y2="{290 + 128 * math.sin(a * math.pi / 14):.1f}" stroke="#cfd8e4" stroke-width="1.2" opacity=".55"/>' for a in range(28)) + '<path d="M985,420 L1015,290 L1045,420" stroke="#cfd8e4" stroke-width="5" fill="none"/></g>'
    if opt.get('sea'):
        extra += f'<rect x="0" y="{base + 20}" width="{W}" height="60" fill="#2a4a6e" opacity=".6"/>'
    trees = ''.join(f'<ellipse cx="{x}" cy="{base + 70}" rx="{r(22, 34):.0f}" ry="{r(18, 26):.0f}" fill="#1f2a2a" opacity=".9"/>' for x in range(-10, W + 30, 58))
    lamps = ''.join(f'<g><line x1="{x}" y1="{base + 120}" x2="{x}" y2="{base + 72}" stroke="#2a2733" stroke-width="3"/><circle cx="{x}" cy="{base + 70}" r="16" fill="url(#lamp)"/><circle cx="{x}" cy="{base + 70}" r="3" fill="#fff2cc"/></g>' for x in range(60, W, 140))
    crowd = ''.join(f'<ellipse cx="{r(40, W - 40):.0f}" cy="{r(base + 112, H - 8):.0f}" rx="{r(1.5, 3):.1f}" ry="{r(3, 6):.1f}" fill="#{rnd.choice(["f7d9b5", "e9b7c8", "c9d6ef", "f4efe6"])}" opacity="{r(.35, .85):.2f}"/>' for _ in range(420))
    s0, s1, s2, s3, s4 = sky
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{s0}"/><stop offset=".4" stop-color="{s1}"/><stop offset=".68" stop-color="{s2}"/><stop offset=".82" stop-color="{s3}"/><stop offset="1" stop-color="{s4}"/></linearGradient>
<linearGradient id="far" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a4568"/><stop offset="1" stop-color="#2e2b47"/></linearGradient>
<linearGradient id="tower" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#262a46"/><stop offset=".55" stop-color="#454a70"/><stop offset="1" stop-color="#23263f"/></linearGradient>
<radialGradient id="roof" cx=".38" cy=".15" r="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#f1f4f9"/><stop offset=".8" stop-color="#cdd6e2"/><stop offset="1" stop-color="#a9b5c6"/></radialGradient>
<linearGradient id="rim" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f6b98a" stop-opacity="0"/><stop offset=".75" stop-color="#f6b98a" stop-opacity="0"/><stop offset="1" stop-color="#f6b98a" stop-opacity=".5"/></linearGradient>
<linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c6cfdb"/><stop offset="1" stop-color="#6f7a8d"/></linearGradient>
<linearGradient id="ground" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3348"/><stop offset="1" stop-color="#15121f"/></linearGradient>
<radialGradient id="lamp" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffe9b8" stop-opacity=".9"/><stop offset="1" stop-color="#ffe9b8" stop-opacity="0"/></radialGradient>
<radialGradient id="sun" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffe2b0" stop-opacity=".8"/><stop offset="1" stop-color="#ffe2b0" stop-opacity="0"/></radialGradient>
<filter id="soft"><feGaussianBlur stdDeviation="1.4"/></filter>
<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .5  0 0 0 0 .5  0 0 0 0 .5  0 0 0 .07 0"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
{stars}
<circle cx="900" cy="430" r="160" fill="url(#sun)"/>
<g filter="url(#soft)">{far}</g>
{wins}
{extra}
<ellipse cx="{cx}" cy="{base + 30}" rx="465" ry="80" fill="url(#lamp)" opacity=".5"/>
{building(v.get('type', 'dome'), cx, base, rnd, opt)}
<rect x="0" y="{base + 62}" width="{W}" height="{H - base - 62}" fill="url(#ground)"/>
{trees}{lamps}{crowd}
<rect width="{W}" height="{H}" filter="url(#grain)"/>
</svg>'''


def thumb_html(v, n_nearby):
    chips = list(v.get('thumb', {}).get('chips', []))
    hot = f'周辺の聖地グルメ{n_nearby}軒' if n_nearby else ''
    name = v.get('short', v['name'])
    size = 146 if len(name) <= 5 else (118 if len(name) <= 7 else (96 if len(name) <= 9 else 78))
    chip_html = ''.join(f'<span>{esc(c)}</span>' for c in chips) + (f'<span class="hot">{hot}</span>' if hot else '')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0}}
#t{{position:relative;width:1200px;height:675px;overflow:hidden;font-family:"IPAPGothic","IPAGothic","Hiragino Sans","Noto Sans JP",sans-serif}}
#t img{{position:absolute;top:0;width:1200px;height:675px}}
#t .bg{{left:-420px;filter:blur(3px)}}
#t .fg{{left:260px;-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 140px)}}
.shade{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,14,34,.97) 0%,rgba(18,14,34,.9) 42%,rgba(18,14,34,.35) 66%,rgba(18,14,34,0) 82%)}}
.badge{{position:absolute;left:166px;top:62px;background:#E2653A;color:#fff;font-size:34px;font-weight:700;padding:10px 26px;border-radius:999px;letter-spacing:.06em}}
.t1{{position:absolute;left:160px;top:{128 + (146 - size) // 2}px;color:#fff;font-size:{size}px;font-weight:700;letter-spacing:.02em;-webkit-text-stroke:3px #fff;text-shadow:0 6px 24px rgba(0,0,0,.45);white-space:nowrap}}
.t2{{position:absolute;left:166px;top:312px;color:#FFD27A;font-size:76px;font-weight:700;-webkit-text-stroke:1.5px #FFD27A}}
.chips{{position:absolute;left:166px;top:436px;width:700px;display:flex;flex-wrap:wrap;gap:14px}}
.chips span{{background:rgba(255,255,255,.95);color:#241F1A;font-size:32px;font-weight:700;padding:8px 20px;border-radius:12px;-webkit-text-stroke:.6px #241F1A}}
.chips span.hot{{background:#E2653A;color:#fff;-webkit-text-stroke:.6px #fff}}
.site{{position:absolute;right:166px;top:600px;color:rgba(255,255,255,.85);font-size:26px;background:rgba(18,14,34,.55);padding:6px 16px;border-radius:999px}}
</style></head><body><div id="t">
<img class="bg" src="illust.png"><img class="fg" src="illust.png"><div class="shade"></div>
<div class="badge">会場ガイド</div>
<div class="t1">{esc(name)}</div>
<div class="t2">ライブ参戦ガイド</div>
<div class="chips">{chip_html}</div>
<div class="site">推しグルメ巡礼MAP</div>
</div></body></html>'''


def build(slug, tmp):
    v = json.load(open(os.path.join(DATA_DIR, slug + '.json'), encoding='utf-8'))
    out = os.path.join(IMG, slug)
    os.makedirs(out, exist_ok=True)
    sizes = {}
    for name, fn in [('access', access), ('seats', seats), ('rules', rules), ('prepare', prepare)]:
        if name in ('seats', 'rules') and not v.get(name):
            continue
        w, h, s = fn(v)
        open(os.path.join(out, name + '.svg'), 'w', encoding='utf-8').write(s)
        sizes[name] = (w, h)
    os.makedirs(os.path.join(IMG, 'src'), exist_ok=True)
    open(os.path.join(IMG, 'src', slug + '.svg'), 'w', encoding='utf-8').write(illustration(v))
    try:
        n = json.load(open('_data/venue_nearby.json', encoding='utf-8')).get(slug, {}).get('n', 0)
    except FileNotFoundError:
        n = 0
    d = os.path.join(tmp, slug)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'illust.svg'), 'w', encoding='utf-8').write(illustration(v))
    open(os.path.join(d, 'thumb.html'), 'w', encoding='utf-8').write(thumb_html(v, n))
    # 記事の <img> の width/height を図の大きさに合わせる
    gp = os.path.join('_guides', slug + '.html')
    if os.path.exists(gp):
        import re
        t = open(gp, encoding='utf-8').read()
        for name, (w, h) in sizes.items():
            t = re.sub(rf'(/assets/img/guide/{re.escape(slug)}/{name}\.svg"[^>]*?)width="\d+" height="\d+"', rf'\1width="{w}" height="{h}"', t)
        open(gp, 'w', encoding='utf-8').write(t)
    print(f'{slug}: 図 {", ".join(f"{k} {w}x{h}" for k, (w, h) in sizes.items())} / 周辺 {n}軒')
    return d, sizes


def main():
    args = sys.argv[1:]
    slugs = sorted(f[:-5] for f in os.listdir(DATA_DIR) if f.endswith('.json')) if args == ['--all'] else args
    tmp = os.environ.get('VENUE_TMP', '/tmp/venue_images')
    jobs = [build(s, tmp) for s in slugs]
    # PNG にしてから webp へ（Chromium で描画）
    subprocess.run(['node', 'scripts/render_png.js'] + [d for d, _ in jobs], check=True)
    from PIL import Image
    for s, (d, _) in zip(slugs, jobs):
        im = Image.open(os.path.join(d, 'thumb.png')).convert('RGB')
        im.save(os.path.join(IMG, s + '.webp'), 'WEBP', quality=82, method=6)
        im.resize((600, 338), Image.LANCZOS).save(os.path.join(IMG, s + '_600.webp'), 'WEBP', quality=82, method=6)
        print(f'{s}: サムネイル {IMG}/{s}.webp')
    json.dump({s: v for s, (_, v) in zip(slugs, jobs)}, open(os.path.join(tmp, 'sizes.json'), 'w'))


if __name__ == '__main__':
    main()
