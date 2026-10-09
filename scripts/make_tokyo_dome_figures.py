"""
make_tokyo_dome_figures.py
東京ドームの会場ガイド（_guides/tokyo-dome.html）に載せる図を SVG で作る。

- access.svg   駅と東京ドームの位置関係（駅の位置は国土地理院アドレス検索の座標から計算）
- seats.svg    座席のつくり（断面のイメージ）
- rules.svg    持ち込めないもの
- prepare.svg  当日の準備（お金・荷物・服装）
内容は東京ドーム公式サイトで確かめた事実だけ（ガイド本文と同じ出典）。

使い方:
  python scripts/make_tokyo_dome_figures.py   # assets/img/guide/tokyo-dome/ に書き出す
"""

import math
import os

OUT = 'assets/img/guide/tokyo-dome'
FONT = "'Hiragino Sans','Hiragino Kaku Gothic ProN','Noto Sans JP','Yu Gothic','Meiryo',sans-serif"
INK, INK2, LINE, BG, CARD = '#241F1A', '#6B6258', '#E2D9CC', '#F7F2EA', '#FFFFFF'
ACC, ACC_L = '#C2532F', '#FBE6DD'
BLUE, GREEN, PURPLE, ORANGE = '#2F6FB5', '#2E8B57', '#7A4FB5', '#D9822B'


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{title}" font-family="{FONT}">'
            f'<title>{title}</title><rect width="{w}" height="{h}" rx="24" fill="{BG}"/>{body}</svg>')


def text(x, y, s, size=24, color=INK, weight=400, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{s}</text>'


def access():
    # 東京ドームの中心と各駅（国土地理院アドレス検索 / 住所から）。北が上
    dome = (35.70557, 139.75197)
    st = [
        ('JR 水道橋駅', '西口（東口もあり）', (35.70190, 139.75369), BLUE, (320, 612)),
        ('都営三田線 水道橋駅', 'A2出口', (35.70337, 139.75248), GREEN, (30, 470)),
        ('東京メトロ 後楽園駅', '2番出口', (35.70702, 139.75079), ORANGE, (30, 178)),
        ('都営大江戸線 春日駅', '6番出口', (35.70819, 139.75194), PURPLE, (320, 178)),
    ]
    W, H = 600, 790
    cx, cy, k = 300, 390, 0.5   # 1m = 0.5px

    def xy(p):
        return cx + (p[1] - dome[1]) * 90600 * k, cy - (p[0] - dome[0]) * 111000 * k
    b = text(30, 58, '東京ドームと最寄り4駅', 30, INK, 700)
    b += text(30, 92, '北が上。位置関係のイメージです', 20, INK2)
    b += f'<rect x="20" y="118" width="560" height="582" rx="18" fill="{CARD}" stroke="{LINE}"/>'
    b += f'<path d="M{cx - 120} 119 L{cx - 120} 699" stroke="{LINE}" stroke-width="20"/>'
    b += text(cx - 110, 268, '白山通り', 18, INK2)
    b += '<path d="M21 680 L579 680" stroke="#D6E6F5" stroke-width="18"/>'
    b += text(34, 668, '神田川（南側）', 17, INK2)
    b += f'<ellipse cx="{cx}" cy="{cy}" rx="70" ry="64" fill="#EEF2F7" stroke="#9AA8BA" stroke-width="3"/>'
    for i in range(1, 4):
        b += f'<ellipse cx="{cx}" cy="{cy}" rx="{70 - i * 17}" ry="{64 - i * 15}" fill="none" stroke="#C8D2DE" stroke-width="1.5"/>'
    b += text(cx, cy + 9, '東京ドーム', 24, INK, 700, 'middle')
    b += f'<path d="M530 330 L544 366 L530 358 L516 366 Z" fill="{INK}"/>' + text(530, 390, 'N', 18, INK, 700, 'middle')
    b += f'<path d="M490 430 L{490 + 100 * k:.0f} 430" stroke="{INK}" stroke-width="3"/>' + text(490 + 50 * k, 420, '100m', 16, INK2, 400, 'middle')
    for name, ex, p, col, (lx, ly) in st:
        x, y = xy(p)
        tx, ty = (lx + 125, ly + 64) if ly < y else (lx + 125, ly)
        b += f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{tx}" y2="{ty}" stroke="{col}" stroke-width="2.5" stroke-dasharray="6 5"/>'
        b += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="11" fill="{col}" stroke="#fff" stroke-width="4"/>'
        b += f'<rect x="{lx}" y="{ly}" width="250" height="64" rx="12" fill="#fff" stroke="{col}" stroke-width="2.5"/>'
        b += text(lx + 14, ly + 28, name, 21, col, 700) + text(lx + 14, ly + 54, ex, 18, INK2)
    b += f'<rect x="20" y="714" width="560" height="62" rx="12" fill="{ACC_L}"/>'
    b += text(36, 740, 'JR水道橋駅の西口はエレベーターなし', 19, ACC, 700)
    b += text(36, 766, '段差を避けるなら東口か後楽園駅から', 19, ACC, 700)
    return svg(W, H, b, '東京ドームと最寄り4駅の位置関係')


def seats():
    W, H = 600, 700
    b = text(30, 58, '座席のつくり（断面のイメージ）', 28, INK, 700)
    b += text(30, 92, 'アリーナ席の並びは公演ごとに変わります', 20, INK2)
    b += f'<rect x="20" y="118" width="560" height="300" rx="18" fill="{CARD}" stroke="{LINE}"/>'
    b += '<path d="M40 400 L40 220 Q300 110 560 220 L560 400 Z" fill="#EEF2F7"/>'
    b += '<path d="M40 220 Q300 110 560 220" fill="none" stroke="#9AA8BA" stroke-width="4"/>'
    b += f'<path d="M48 258 L150 306 L150 324 L48 286 Z" fill="{PURPLE}"/><path d="M552 258 L450 306 L450 324 L552 286 Z" fill="{PURPLE}"/>'
    b += f'<rect x="48" y="296" width="56" height="12" rx="4" fill="{ORANGE}"/><rect x="496" y="296" width="56" height="12" rx="4" fill="{ORANGE}"/>'
    b += f'<path d="M48 326 L190 384 L190 400 L48 400 Z" fill="{BLUE}"/><path d="M552 326 L410 384 L410 400 L552 400 Z" fill="{BLUE}"/>'
    b += f'<rect x="190" y="384" width="220" height="16" fill="{GREEN}"/>'
    b += '<rect x="250" y="350" width="100" height="34" rx="4" fill="#3B3346"/>' + text(300, 373, 'ステージの例', 15, '#fff', 700, 'middle')
    items = [(PURPLE, '2階席スタンド', '4階コンコースから入る'),
             (ORANGE, 'バルコニー席', 'プレミアムラウンジ'),
             (BLUE, '1階席スタンド・外野席', '1階／2階コンコースから入る'),
             (GREEN, 'アリーナ席', 'グラウンドに置く席。配置は公演ごと')]
    for i, (c, a, d) in enumerate(items):
        y = 462 + i * 62
        b += f'<rect x="30" y="{y - 24}" width="28" height="28" rx="7" fill="{c}"/>'
        b += text(72, y - 2, a, 22, INK, 700) + text(72, y + 24, d, 18, INK2)
    return svg(W, H, b, '東京ドームの座席のつくり')


def icon_bottle(x, y, frozen=False, big=False):
    s = f'<g transform="translate({x},{y})"><rect x="-14" y="-38" width="28" height="12" rx="3" fill="{BLUE}"/>'
    s += f'<path d="M-18 -26 L18 -26 L22 -10 L22 {44 if big else 34} Q22 {50 if big else 40} 16 {50 if big else 40} L-16 {50 if big else 40} Q-22 {50 if big else 40} -22 {44 if big else 34} L-22 -10 Z" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/>'
    if frozen:
        s += '<path d="M0 -4 L0 26 M-13 4 L13 18 M13 4 L-13 18" stroke="#5BA3E0" stroke-width="3"/>'
    if big:
        s += text(0, 24, '1L超', 16, BLUE, 700, 'middle')
    return s + '</g>'


def ng(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="58" fill="none" stroke="{ACC}" stroke-width="7"/>'
            f'<line x1="{x - 41}" y1="{y + 41}" x2="{x + 41}" y2="{y - 41}" stroke="{ACC}" stroke-width="7"/>')


def rules():
    W, H = 600, 800
    b = text(30, 58, '持ち込めないもの', 30, INK, 700)
    b += text(30, 92, '公演ごとのルールは主催者の案内で', 20, INK2)
    cells = [
        ('凍らせた<br>ペットボトル', lambda x, y: icon_bottle(x, y, frozen=True)),
        ('1,000mlを超える<br>ペットボトル', lambda x, y: icon_bottle(x, y, big=True)),
        ('ビン・缶', lambda x, y: f'<g transform="translate({x},{y})"><rect x="-34" y="-30" width="30" height="62" rx="6" fill="#E8EDF2" stroke="{INK2}" stroke-width="3"/><rect x="6" y="-40" width="26" height="72" rx="8" fill="#D8F0E2" stroke="{GREEN}" stroke-width="3"/><rect x="12" y="-50" width="14" height="12" fill="{GREEN}"/></g>'),
        ('アルコール類', lambda x, y: f'<g transform="translate({x},{y})"><path d="M-24 -30 L24 -30 L18 40 L-18 40 Z" fill="#FFF1C9" stroke="{ORANGE}" stroke-width="3"/><path d="M-24 -30 Q-12 -46 0 -34 Q12 -48 24 -30" fill="#fff" stroke="{ORANGE}" stroke-width="3"/><path d="M24 -10 Q40 -10 40 8 Q40 24 22 24" fill="none" stroke="{ORANGE}" stroke-width="4"/></g>'),
        ('ペットなどの動物<br>（補助犬をのぞく）', lambda x, y: f'<g transform="translate({x},{y})"><ellipse cx="0" cy="12" rx="30" ry="24" fill="#F3E2CF" stroke="#A9744A" stroke-width="3"/><circle cx="0" cy="-22" r="20" fill="#F3E2CF" stroke="#A9744A" stroke-width="3"/><path d="M-18 -34 L-24 -52 L-6 -40 M18 -34 L24 -52 L6 -40" fill="#F3E2CF" stroke="#A9744A" stroke-width="3"/></g>'),
        ('危険物・<br>大きすぎる荷物', lambda x, y: f'<g transform="translate({x},{y})"><rect x="-34" y="-26" width="68" height="62" rx="8" fill="#EDE6F7" stroke="{PURPLE}" stroke-width="3"/><path d="M-14 -26 L-14 -40 L14 -40 L14 -26" fill="none" stroke="{PURPLE}" stroke-width="4"/><path d="M0 -12 L12 14 L-12 14 Z" fill="{ORANGE}"/><rect x="-2" y="-4" width="4" height="10" fill="#fff"/></g>'),
    ]
    for i, (label, draw) in enumerate(cells):
        col, row = i % 2, i // 2
        x0, y0 = 20 + col * 285, 118 + row * 225
        b += f'<rect x="{x0}" y="{y0}" width="275" height="212" rx="18" fill="{CARD}" stroke="{LINE}"/>'
        cx, cy = x0 + 137, y0 + 78
        b += draw(cx, cy) + ng(cx, cy)
        for j, ln in enumerate(label.split('<br>')):
            b += text(cx, y0 + 170 + j * 28, ln, 22, INK, 700, 'middle')
    return svg(W, H, b, '東京ドームに持ち込めないもの')


def prepare():
    W, H = 600, 740
    b = text(30, 58, '当日の準備 4つ', 30, INK, 700)
    b += text(30, 92, '東京ドーム公式サイトの案内より', 20, INK2)
    tiles = [
        (ACC, '場内は完全キャッシュレス', ['現金は使えない。カード・電子マネー・', 'コード決済を用意'],
         f'<rect x="-40" y="-26" width="80" height="52" rx="8" fill="{ACC_L}" stroke="{ACC}" stroke-width="3"/><rect x="-40" y="-14" width="80" height="10" fill="{ACC}"/><rect x="-30" y="8" width="24" height="8" rx="2" fill="{ACC}"/>'),
        (BLUE, 'ロッカーは交通系ICで', ['Suica・PASMOなどで払う', '数に限りあり'],
         f'<rect x="-36" y="-36" width="72" height="72" rx="8" fill="#DCEBFA" stroke="{BLUE}" stroke-width="3"/><line x1="0" y1="-36" x2="0" y2="36" stroke="{BLUE}" stroke-width="3"/><line x1="-36" y1="0" x2="36" y2="0" stroke="{BLUE}" stroke-width="3"/><circle cx="-8" cy="-18" r="3" fill="{BLUE}"/><circle cx="28" cy="-18" r="3" fill="{BLUE}"/>'),
        (GREEN, '大きな荷物は駅かホテルへ', ['東京ドームシティの施設では', '手荷物を預かっていない'],
         f'<rect x="-30" y="-30" width="60" height="70" rx="10" fill="#D8F0E2" stroke="{GREEN}" stroke-width="3"/><path d="M-12 -30 L-12 -44 L12 -44 L12 -30" fill="none" stroke="{GREEN}" stroke-width="4"/><circle cx="-18" cy="44" r="5" fill="{GREEN}"/><circle cx="18" cy="44" r="5" fill="{GREEN}"/>'),
        (PURPLE, '脱ぎ着しやすい服で', ['場内の目安は', '夏 約28℃・冬 約18℃'],
         f'<path d="M-36 -26 L-14 -38 Q0 -28 14 -38 L36 -26 L28 -6 L18 -10 L18 38 L-18 38 L-18 -10 L-28 -6 Z" fill="#EDE6F7" stroke="{PURPLE}" stroke-width="3"/>'),
    ]
    for i, (c, title, lines, icon) in enumerate(tiles):
        x0, y0 = 20, 118 + i * 154
        b += f'<rect x="{x0}" y="{y0}" width="560" height="140" rx="18" fill="{CARD}" stroke="{LINE}"/>'
        b += f'<rect x="{x0}" y="{y0}" width="8" height="140" rx="4" fill="{c}"/>'
        b += f'<g transform="translate({x0 + 70},{y0 + 72}) scale(.9)">{icon}</g>'
        b += text(x0 + 130, y0 + 46, title, 24, c, 700)
        for j, ln in enumerate(lines):
            b += text(x0 + 130, y0 + 86 + j * 30, ln, 20, INK)
    return svg(W, H, b, '東京ドームに行く日の準備')


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [('access', access), ('seats', seats), ('rules', rules), ('prepare', prepare)]:
        with open(os.path.join(OUT, name + '.svg'), 'w', encoding='utf-8') as f:
            f.write(fn())
        print('書き出し:', os.path.join(OUT, name + '.svg'))


if __name__ == '__main__':
    main()
