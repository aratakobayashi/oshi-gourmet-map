"""
ward_tilemap.py
記事の店を、東京23区のタイル地図（1区＝1マス、おおよその位置）と、23区の外の地域の棒で表す図にする。
店が多いほど色が濃い。assets/img/posts/<slug>/wards.svg に書き出し、記事の本文の同じ図の width/height も合わせる。
山手線の地図（post_map.py）では店の多くが地図の外になる番組（町中華で飲ろうぜ など）向け。

使い方: python scripts/ward_tilemap.py <記事のslug> [--color '#dc2626'] [--title '…']
"""
import argparse, collections, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "'Hiragino Sans','Noto Sans CJK JP','Noto Sans JP',sans-serif"
SERIF = "'Hiragino Mincho ProN','Noto Serif CJK JP','Noto Serif JP',serif"
INK, INK2, LINE, PAPER = '#241F1A', '#6B6258', '#E2D9CC', '#F7F3EC'
# (区, 列, 行) おおよその位置
TILES = [
    ('練馬', 1, 0), ('板橋', 2, 0), ('北', 3, 0), ('足立', 4, 0),
    ('杉並', 0, 1), ('中野', 1, 1), ('豊島', 2, 1), ('文京', 3, 1), ('荒川', 4, 1), ('葛飾', 5, 1),
    ('新宿', 2, 2), ('千代田', 3, 2), ('台東', 4, 2), ('墨田', 5, 2), ('江戸川', 6, 2),
    ('世田谷', 0, 3), ('渋谷', 1, 3), ('港', 2, 3), ('中央', 3, 3), ('江東', 4, 3),
    ('目黒', 1, 4), ('品川', 2, 4),
    ('大田', 1, 5),
]


def mix(c, t):
    """色 c を白と t（0〜1）の割合で混ぜる"""
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    f = lambda x: round(255 + (x - 255) * t)
    return '#%02x%02x%02x' % (f(r), f(g), f(b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slug'); ap.add_argument('--color', default='#c2410c'); ap.add_argument('--title', default='')
    a = ap.parse_args()
    path = glob.glob(os.path.join(ROOT, '_posts', f'*-{a.slug}.md'))[0]
    fm = open(path, encoding='utf-8').read().split('---')[1]
    ids = [x.strip().strip('"\'') for x in re.findall(r'^\s+-\s+(.+)$', fm.split('shop_ids:')[1], re.M)]
    S = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'data/shops.json'), encoding='utf-8'))}
    shops = [S[i] for i in ids if i in S]
    ward = collections.Counter(s['city'][:-1] for s in shops if s.get('prefecture') == '東京都' and (s.get('city') or '').endswith('区'))
    other = collections.Counter()
    for s in shops:
        p = s.get('prefecture') or ''
        if p == '東京都':
            if not (s.get('city') or '').endswith('区'):
                other['東京の市部・島'] += 1
        elif p in ('神奈川県', '埼玉県', '千葉県'):
            other[p] += 1
        else:
            other['そのほかの道府県'] += 1
    n23 = sum(ward.values())
    mx = max(ward.values()) if ward else 1

    W, T, G = 420, 50, 4          # 幅・マスの大きさ・すき間
    x0 = (W - (7 * T + 6 * G)) // 2
    y0 = 96
    out = []
    H_map = y0 + 6 * (T + G)
    for name, cx, cy in TILES:
        n = ward.get(name, 0)
        t = 0.08 + 0.92 * (n / mx) ** 0.8 if n else 0.04
        fill = mix(a.color, t)
        fg = '#fff' if t > 0.5 else INK
        x, y = x0 + cx * (T + G), y0 + cy * (T + G)
        out.append(f'<rect x="{x}" y="{y}" width="{T}" height="{T}" rx="8" fill="{fill}"/>')
        fs = 13 if len(name) <= 2 else 11.5
        out.append(f'<text x="{x + T/2}" y="{y + 22}" font-size="{fs}" font-weight="700" text-anchor="middle" fill="{fg}">{name}</text>')
        out.append(f'<text x="{x + T/2}" y="{y + 43}" font-size="15" font-weight="800" text-anchor="middle" fill="{fg}">{n}</text>')
    # 凡例
    ly = H_map + 8
    out.append(f'<text x="{x0}" y="{ly + 12}" font-size="12" fill="{INK2}">少ない</text>')
    for i, t in enumerate([0.12, 0.35, 0.58, 0.8, 1.0]):
        out.append(f'<rect x="{x0 + 44 + i * 26}" y="{ly + 1}" width="22" height="14" rx="3" fill="{mix(a.color, t)}"/>')
    out.append(f'<text x="{x0 + 44 + 5 * 26 + 6}" y="{ly + 12}" font-size="12" fill="{INK2}">多い（数字は軒数）</text>')
    # 23区の外
    by = ly + 44
    out.append(f'<text x="20" y="{by}" font-size="15" font-weight="800" fill="{INK}">23区の外</text>')
    rows = sorted(other.items(), key=lambda kv: (kv[0] == 'そのほかの道府県', -kv[1]))
    bm = max(other.values()) if other else 1
    for i, (k, v) in enumerate(rows):
        y = by + 16 + i * 32
        out.append(f'<text x="20" y="{y + 17}" font-size="13.5" fill="{INK}">{k}</text>')
        w = max(6, round(200 * v / bm))
        out.append(f'<rect x="150" y="{y + 4}" width="{w}" height="18" rx="5" fill="{mix(a.color, 0.75)}"/>')
        out.append(f'<text x="{150 + w + 8}" y="{y + 18}" font-size="14" font-weight="800" fill="{a.color}">{v}軒</text>')
    H = by + 16 + len(rows) * 32 + 18
    title = a.title or 'お店の場所'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">'
           f'<rect width="{W}" height="{H}" rx="18" fill="{PAPER}"/>'
           f'<text x="20" y="42" font-size="21" font-weight="800" fill="{INK}" font-family="{SERIF}">{title}</text>'
           f'<text x="20" y="66" font-size="12.5" fill="{INK2}">東京23区は1区＝1マス（位置はおおよそ）。23区に{n23}軒</text>'
           + ''.join(out) + '</svg>')
    d = os.path.join(ROOT, 'assets/img/posts', a.slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'wards.svg'), 'w', encoding='utf-8').write(svg)
    t = open(path, encoding='utf-8').read()
    t2 = re.sub(r'(wards\.svg"[^>]*?width=")\d+(" height=")\d+', lambda m: f'{m.group(1)}{W}{m.group(2)}{H}', t)
    if t2 != t:
        open(path, 'w', encoding='utf-8').write(t2)
    print(a.slug, 'wards.svg', W, H, dict(ward.most_common(3)), dict(other))


if __name__ == '__main__':
    main()
