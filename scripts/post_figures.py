"""
post_figures.py
特集記事（_posts/）の図を、記事の shop_ids と data/shops.json から作る。
- timeline.svg  訪れた順の年表（日付・動画タイトル・店名）
- genre.svg     お店のジャンルと場所（都道府県・市区町村）

書き出し: assets/img/posts/<slug>/。記事の本文にある同じ図の width/height も合わせる。
使い方: python scripts/post_figures.py <記事のslug（ファイル名の日付のあと）> [--color '#e8537a'] [--title '…の年表']
"""
import collections
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "'Hiragino Sans','Noto Sans CJK JP','Noto Sans JP',sans-serif"
SERIF = "'Hiragino Mincho ProN','Noto Serif CJK JP','Noto Serif JP',serif"
INK, INK2, LINE, PAPER = '#241F1A', '#6B6258', '#E2D9CC', '#F7F3EC'
GENRE_COLORS = {'chuka': '#dc2626', 'yakiniku': '#9a3412', 'washoku': '#15803d', 'shokuji': '#2563eb', 'izakaya': '#7c3aed',
                'ramen': '#ca8a04', 'cafe': '#0891b2', 'sweets': '#db2777', 'others': '#64748b'}


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def tw(s):
    return sum(1 if ord(c) > 0x2E80 else 0.55 for c in s)


def wrap(s, n):
    out, cur = [], ''
    for c in s:
        if tw(cur + c) > n:
            out.append(cur)
            cur = ''
        cur += c
    if cur:
        out.append(cur)
    return out


def find_post(slug):
    for f in os.listdir(os.path.join(ROOT, '_posts')):
        if f[11:-3] == slug:
            return os.path.join(ROOT, '_posts', f)
    raise SystemExit('記事が見つかりません: ' + slug)


def timeline(shops, color, title, note):
    W, top = 420, 92
    rows = []
    y = top
    for s in shops:
        t = (s.get('source_video_title') or '').strip()
        lines = wrap(t, 19)[:2] if t else []
        h = 46 + 18 * len(lines) + 8
        rows.append((y, h, s, lines))
        y += h + 12
    H = y + 14
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" rx="18" fill="{PAPER}"/>',
         f'<text x="20" y="42" font-size="21" font-weight="800" fill="{INK}" font-family="{SERIF}">{esc(title)}</text>',
         f'<text x="20" y="64" font-size="12" fill="{INK2}">{esc(note)}</text>',
         f'<line x1="86" y1="{top - 4}" x2="86" y2="{y - 12}" stroke="{color}" stroke-width="5" stroke-linecap="round" stroke-dasharray="1 10"/>']
    for yy, h, s, lines in rows:
        d = s.get('visited_date') or ''
        o.append(f'<text x="70" y="{yy + 20}" font-size="15" font-weight="800" text-anchor="end" fill="{INK}">{esc(d[:4])}</text>')
        if len(d) >= 7:
            o.append(f'<text x="70" y="{yy + 37}" font-size="12" text-anchor="end" fill="{INK2}">{int(d[5:7])}月</text>')
        o.append(f'<circle cx="86" cy="{yy + 15}" r="7" fill="#fff" stroke="{color}" stroke-width="4"/>')
        o.append(f'<rect x="104" y="{yy - 4}" width="{W - 118}" height="{h}" rx="12" fill="#fff" stroke="{LINE}"/>')
        name = s['name'] if tw(s['name']) <= 15.5 else wrap(s['name'], 15)[0] + '…'
        o.append(f'<text x="118" y="{yy + 20}" font-size="16" font-weight="800" fill="{INK}">{esc(name)}</text>')
        for i, ln in enumerate(lines):
            o.append(f'<text x="118" y="{yy + 42 + 18 * i}" font-size="12.5" fill="{color}">{esc(ln)}</text>')
    o.append('</svg>')
    return '\n'.join(o), W, H


def genre(shops, color, title, genres):
    cnt = collections.Counter(s.get('genre', 'others') for s in shops)
    pc = collections.Counter(s.get('prefecture') or '' for s in shops)
    main_pref = pc.most_common(1)[0][0] if pc else ''
    def place(s):
        p, c = s.get('prefecture') or '', s.get('city') or ''
        if p == main_pref and c:
            return c
        return (p.rstrip('都府県') if p not in ('北海道',) else p) + (' ' + c if c and tw(p + c) <= 8 else '') or '不明'
    area = collections.Counter(place(s) for s in shops)
    W = 420
    H = 112 + 44 * len(cnt) + 28 + 32 * ((len(area) + 1) // 2) + 14
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" rx="18" fill="{PAPER}"/>',
         f'<text x="20" y="42" font-size="21" font-weight="800" fill="{INK}" font-family="{SERIF}">{esc(title)}</text>',
         f'<text x="20" y="64" font-size="12" fill="{INK2}">この記事のお店{len(shops)}軒を数えました</text>']
    y = 96
    mx = max(cnt.values())
    for g, k in cnt.most_common():
        col = GENRE_COLORS.get(g, '#64748b')
        bw = int(220 * k / mx)
        o.append(f'<text x="20" y="{y + 22}" font-size="15" font-weight="700" fill="{INK}">{esc(genres.get(g, {}).get("label", g))}</text>')
        o.append(f'<rect x="100" y="{y + 4}" width="{bw}" height="26" rx="8" fill="{col}"/>')
        o.append(f'<text x="{100 + bw + 8}" y="{y + 23}" font-size="16" font-weight="800" fill="{col}">{k}軒</text>')
        y += 44
    y += 14
    o.append(f'<text x="20" y="{y}" font-size="14" font-weight="700" fill="{INK2}">お店の場所</text>')
    y += 14
    for i, (a, k) in enumerate(area.most_common()):
        cx, cy = 20 + (i % 2) * 196, y + (i // 2) * 32
        a = a if tw(a) <= 10 else wrap(a, 10)[0] + '…'
        o.append(f'<rect x="{cx}" y="{cy}" width="184" height="26" rx="13" fill="#fff" stroke="{LINE}"/>')
        o.append(f'<text x="{cx + 12}" y="{cy + 18}" font-size="13.5" fill="{INK}">{esc(a)}</text>'
                 f'<text x="{cx + 172}" y="{cy + 18}" font-size="14" font-weight="800" text-anchor="end" fill="{color}">{k}軒</text>')
    o.append('</svg>')
    return '\n'.join(o), W, H


def main():
    args = sys.argv[1:]
    slug = args[0]
    color = args[args.index('--color') + 1] if '--color' in args else '#e2553f'
    ttl = args[args.index('--title') + 1] if '--title' in args else '訪れた順の年表'
    path = find_post(slug)
    text = open(path, encoding='utf-8').read()
    fm = text.split('\n---\n', 1)[0]
    ids = (yaml.safe_load(fm.split('---', 1)[1]) or {}).get('shop_ids') or []
    allshops = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8'))}
    shops = [allshops[i] for i in ids if i in allshops]
    genres = json.load(open(os.path.join(ROOT, '_data', 'genres.json'), encoding='utf-8'))
    if isinstance(genres, list):
        genres = {g['key']: g for g in genres}
    out = os.path.join(ROOT, 'assets', 'img', 'posts', slug)
    os.makedirs(out, exist_ok=True)
    sizes = {}
    tl = sorted([s for s in shops if s.get('visited_date')], key=lambda s: s['visited_date'])
    svg, w, h = timeline(tl, color, ttl, '動画が公開された順（推しグルメ巡礼MAPのデータより）')
    open(os.path.join(out, 'timeline.svg'), 'w', encoding='utf-8').write(svg)
    sizes['timeline'] = (w, h)
    svg, w, h = genre(shops, color, 'お店のジャンルと場所', genres)
    open(os.path.join(out, 'genre.svg'), 'w', encoding='utf-8').write(svg)
    sizes['genre'] = (w, h)
    for k, (w, h) in sizes.items():
        text = re.sub(r'(<img src="/assets/img/posts/' + re.escape(slug) + '/' + k + r'\.svg"[^>]*?)width="\d+" height="\d+"',
                      lambda m: f'{m.group(1)}width="{w}" height="{h}"', text)
    open(path, 'w', encoding='utf-8').write(text)
    print(slug, sizes, len(shops), '軒')


if __name__ == '__main__':
    main()
