"""
profile_figures.py
メンバー・グループ紹介（ガイド）の図と見出し画像を作る。
データは scripts/profile_data/<slug>.json（形は teranishi-takuto.json を参照）。

書き出すもの（assets/img/guide/<slug>/ と assets/img/guide/）:
- timeline.svg  歩みの年表（道のりの図）
- food.svg      推しが訪れたお店のジャンル（data/shops.json の members から数える）
- <slug>.webp / <slug>_600.webp  見出し画像（ステージのイラスト＋名前＋記事の中身）

使い方: PW_CHROME=<chromium> NODE_PATH=<playwright の node_modules> python scripts/profile_figures.py <slug>
見出し画像は Chromium で描く。記事の front matter の thumbnail もこの画像に書き換える。
"""
import collections
import json
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "'Hiragino Sans','Noto Sans CJK JP','Noto Sans JP',sans-serif"
SERIF = "'Hiragino Mincho ProN','Noto Serif CJK JP','Noto Serif JP',serif"
INK, INK2, LINE, PAPER = '#241F1A', '#6B6258', '#E2D9CC', '#F7F3EC'


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def tw(s):
    """おおよその表示幅（全角=1, 半角=0.55）"""
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


def timeline(d):
    """縦の道のり。左に年、右に出来事。highlight は色付きの大きな印"""
    c = d['color']
    items = d['timeline']
    W, top, gap = 600, 96, 18
    rows = []
    y = top
    for it in items:
        lines = wrap(it['d'], 25) if it.get('d') else []
        h = 62 + 20 * (len(lines) - 1) if lines else 40
        rows.append((y, h, it, lines))
        y += h + gap
    H = y + 20
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" rx="18" fill="{PAPER}"/>',
         f'<text x="28" y="44" font-size="22" font-weight="800" fill="{INK}" font-family="{SERIF}">{esc(d["timeline_title"])}</text>',
         f'<text x="28" y="68" font-size="13" fill="{INK2}">{esc(d.get("timeline_note", ""))}</text>']
    x = 128
    s.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{y - gap}" stroke="{c}" stroke-width="6" stroke-linecap="round" stroke-dasharray="1 12" opacity=".9"/>')
    for (yy, h, it, lines) in rows:
        cy = yy + 16
        big = it.get('hl')
        s.append(f'<text x="96" y="{cy + 6}" font-size="{19 if big else 16}" font-weight="800" text-anchor="end" fill="{c if big else INK}">{esc(it["y"])}</text>')
        if it.get('m'):
            s.append(f'<text x="96" y="{cy + 24}" font-size="12" text-anchor="end" fill="{INK2}">{esc(it["m"])}</text>')
        if big:
            s.append(f'<circle cx="{x}" cy="{cy}" r="13" fill="{c}"/><circle cx="{x}" cy="{cy}" r="5" fill="#fff"/>')
        else:
            s.append(f'<circle cx="{x}" cy="{cy}" r="8" fill="#fff" stroke="{c}" stroke-width="4"/>')
        bx = 152
        fill = '#fff'
        stroke = c if big else LINE
        s.append(f'<rect x="{bx}" y="{yy - 4}" width="{W - bx - 24}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="{2 if big else 1}"/>')
        s.append(f'<text x="{bx + 16}" y="{yy + 22}" font-size="17" font-weight="800" fill="{INK}">{esc(it["t"])}</text>')
        for i, ln in enumerate(lines):
            s.append(f'<text x="{bx + 16}" y="{yy + 44 + 20 * i}" font-size="13.5" fill="{INK2}">{esc(ln)}</text>')
    s.append('</svg>')
    return '\n'.join(s), W, H


GENRE_COLORS = {'chuka': '#dc2626', 'yakiniku': '#9a3412', 'washoku': '#15803d', 'shokuji': '#2563eb', 'izakaya': '#7c3aed',
                'ramen': '#ca8a04', 'cafe': '#0891b2', 'sweets': '#db2777', 'others': '#64748b'}


def food(d, shops, genres):
    """訪れたお店のジャンルの帯グラフ＋場所の一覧"""
    mine = [s for s in shops if d['member'] in (s.get('members') or [])]
    cnt = collections.Counter(s.get('genre', 'others') for s in mine)
    pref = collections.Counter((s.get('prefecture') or '').replace('都', '').replace('府', '').replace('県', '') for s in mine if s.get('prefecture'))
    W = 600
    s_ = []
    n = len(mine)
    H = 100 + 46 * len(cnt) + 28 + 30 * ((len(pref) + 2) // 3) + 14
    s_.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">')
    s_.append(f'<rect width="{W}" height="{H}" rx="18" fill="{PAPER}"/>')
    s_.append(f'<text x="28" y="44" font-size="22" font-weight="800" fill="{INK}" font-family="{SERIF}">{esc(d["food_title"])}</text>')
    s_.append(f'<text x="28" y="68" font-size="13" fill="{INK2}">推しグルメ巡礼MAPに登録されているお店{n}軒（{d["checked"]}時点）を数えました</text>')
    y = 100
    mx = max(cnt.values()) if cnt else 1
    for g, k in cnt.most_common():
        label = genres.get(g, {}).get('label', g)
        col = GENRE_COLORS.get(g, '#64748b')
        bw = int(330 * k / mx)
        s_.append(f'<text x="28" y="{y + 22}" font-size="15" font-weight="700" fill="{INK}">{esc(label)}</text>')
        s_.append(f'<rect x="130" y="{y + 4}" width="{bw}" height="26" rx="8" fill="{col}"/>')
        s_.append(f'<text x="{130 + bw + 10}" y="{y + 23}" font-size="16" font-weight="800" fill="{col}">{k}軒</text>')
        y += 46
    y += 14
    s_.append(f'<text x="28" y="{y}" font-size="14" font-weight="700" fill="{INK2}">訪れた場所</text>')
    y += 14
    for i, (p, k) in enumerate(pref.most_common()):
        cx = 28 + (i % 3) * 184
        cy = y + (i // 3) * 30
        s_.append(f'<rect x="{cx}" y="{cy}" width="172" height="24" rx="12" fill="#fff" stroke="{LINE}"/>')
        s_.append(f'<text x="{cx + 14}" y="{cy + 17}" font-size="13" fill="{INK}">{esc(p)}</text><text x="{cx + 158}" y="{cy + 17}" font-size="13" font-weight="800" text-anchor="end" fill="{d["color"]}">{k}軒</text>')
    s_.append('</svg>')
    return '\n'.join(s_), W, H, n


def thumb_html(d, n):
    c = d['color']
    t = d['thumb']
    chips = ''.join(f'<span>{esc(x)}</span>' for x in t['chips'] + ([f'訪れたお店{n}軒'] if n else []))
    # ペンライトの光（客席）
    import random
    rnd = random.Random(7)
    dots = ''.join(f'<circle cx="{rnd.randint(0, 1200)}" cy="{rnd.randint(560, 675)}" r="{rnd.choice([2, 2.5, 3, 3.5])}" fill="{c if rnd.random() < .7 else "#fff"}" opacity="{rnd.uniform(.5, 1):.2f}"/>' for _ in range(420))
    return f"""<!doctype html><meta charset="utf-8"><style>
*{{margin:0;box-sizing:border-box}}body{{width:1200px;height:675px;overflow:hidden;font-family:{FONT};background:#0d1020}}
#t{{position:relative;width:1200px;height:675px;overflow:hidden}}
svg.bg{{position:absolute;inset:0}}
.w{{position:absolute;left:72px;top:58px;right:420px}}
.l{{display:inline-block;background:#e2553f;color:#fff;font-weight:700;font-size:26px;padding:5px 16px;border-radius:999px}}
.k{{color:{c};font-weight:800;font-size:34px;margin-top:26px;text-shadow:0 2px 12px rgba(0,0,0,.5)}}
h1{{color:#fff;font-family:{SERIF};font-weight:900;font-size:128px;line-height:1.1;margin-top:6px;letter-spacing:.04em;text-shadow:0 4px 24px rgba(0,0,0,.55)}}
.s{{color:#fff;font-weight:700;font-size:30px;margin-top:10px;opacity:.92}}
.c{{position:absolute;left:72px;bottom:46px;display:flex;gap:12px;flex-wrap:wrap;right:360px}}
.c span{{background:#fff;color:#14161f;font-weight:800;font-size:26px;padding:7px 15px;border-radius:8px}}
.c span:last-child{{background:{c};color:#0d1020}}
.b{{position:absolute;right:34px;bottom:20px;color:#fff;opacity:.7;font-size:20px}}
</style><div id="t"><svg class="bg" viewBox="0 0 1200 675" width="1200" height="675">
<defs><radialGradient id="sp" cx=".5" cy="0" r="1"><stop offset="0" stop-color="{c}" stop-opacity=".75"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>
<linearGradient id="fl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1b2236"/><stop offset="1" stop-color="#0d1020"/></linearGradient>
<radialGradient id="gl" cx=".78" cy=".42" r=".5"><stop offset="0" stop-color="{c}" stop-opacity=".55"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient></defs>
<rect width="1200" height="675" fill="url(#fl)"/><rect width="1200" height="675" fill="url(#gl)"/>
<polygon points="760,0 840,0 1080,520 700,520" fill="url(#sp)" opacity=".55"/>
<polygon points="980,0 1040,0 1160,520 880,520" fill="url(#sp)" opacity=".4"/>
<polygon points="560,0 620,0 900,520 640,520" fill="url(#sp)" opacity=".3"/>
<ellipse cx="900" cy="520" rx="300" ry="34" fill="#fff" opacity=".10"/>
<rect x="600" y="505" width="600" height="20" fill="#2a3150"/>
<g fill="#0a0c18"><circle cx="900" cy="378" r="30"/><path d="M866 412 Q900 398 934 412 L950 505 L850 505 Z"/><path d="M934 420 L990 360 L998 368 L948 440 Z"/></g>
<circle cx="996" cy="356" r="9" fill="{c}"/><circle cx="996" cy="356" r="22" fill="{c}" opacity=".35"/>
{dots}
</svg>
<div class="w"><span class="l">{esc(t['label'])}</span><div class="k">{esc(t['catch'])}</div><h1>{esc(d['name'])}</h1><div class="s">{esc(t['sub'])}</div></div>
<div class="c">{chips}</div><div class="b">推しグルメ巡礼MAP</div></div>"""


RENDER = r"""
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 675 } });
  await p.goto('file://' + path.resolve(process.argv[2]));
  await p.waitForTimeout(200);
  await (await p.$('#t')).screenshot({ path: process.argv[3] });
  await b.close();
})();
"""


def main(slug):
    d = json.load(open(os.path.join(ROOT, 'scripts', 'profile_data', slug + '.json'), encoding='utf-8'))
    shops = json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8'))
    genres = json.load(open(os.path.join(ROOT, '_data', 'genres.json'), encoding='utf-8'))
    if isinstance(genres, list):
        genres = {g['key']: g for g in genres}
    out = os.path.join(ROOT, 'assets', 'img', 'guide', slug)
    os.makedirs(out, exist_ok=True)
    sizes = {}
    svg, w, h = timeline(d)
    open(os.path.join(out, 'timeline.svg'), 'w', encoding='utf-8').write(svg)
    sizes['timeline'] = (w, h)
    n = 0
    if d.get('member'):
        svg, w, h, n = food(d, shops, genres)
        open(os.path.join(out, 'food.svg'), 'w', encoding='utf-8').write(svg)
        sizes['food'] = (w, h)
    tmp = tempfile.mkdtemp()
    hp, pp, js = os.path.join(tmp, 't.html'), os.path.join(tmp, 't.png'), os.path.join(tmp, 'r.js')
    open(hp, 'w', encoding='utf-8').write(thumb_html(d, n))
    open(js, 'w').write(RENDER)
    subprocess.run(['node', js, hp, pp], check=True)
    im = Image.open(pp).convert('RGB')
    base = os.path.join(ROOT, 'assets', 'img', 'guide', slug)
    im.save(base + '.webp', quality=84)
    im.resize((600, 338), Image.LANCZOS).save(base + '_600.webp', quality=82)
    # 記事の thumbnail と図の width/height を合わせる
    g = os.path.join(ROOT, '_guides', slug + '.html')
    t = open(g, encoding='utf-8').read()
    t = re.sub(r'^thumbnail: .*$', f'thumbnail: /assets/img/guide/{slug}.webp', t, count=1, flags=re.M)
    for k, (w, h) in sizes.items():
        t = re.sub(r'(<img src="/assets/img/guide/' + re.escape(slug) + '/' + k + r'\.svg"[^>]*?)width="\d+" height="\d+"',
                   lambda m: f'{m.group(1)}width="{w}" height="{h}"', t)
    open(g, 'w', encoding='utf-8').write(t)
    print(slug, sizes, 'shops', n)


if __name__ == '__main__':
    for s in sys.argv[1:]:
        main(s)
