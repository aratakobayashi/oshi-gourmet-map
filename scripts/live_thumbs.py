"""
live_thumbs.py
公演の参戦ガイド（article_type: live）の見出し画像を作る。会場ガイドと同じ写真風のイラスト（venue_guide_images.py の illustration）に、
グループ名・会場名＋「公演」・日程・記事の中身の札を大きく載せる（「イコラブ 東京ドーム」で探した人が、ひと目でその公演の記事だと分かるように）。

- 入力: scripts/live_data/<slug>.json（公演）・scripts/venue_data/<会場>.json（イラスト）・_posts/*-<slug>.md の shop_ids（近くの聖地の数）
- 出力: assets/img/posts/<slug>/thumb.webp（1200x675）と thumb_600.webp（600x338）。live_article.py が front matter の thumbnail にする
- Chromium が要る（scripts/render_png.js。環境変数 PW_CHROME・NODE_PATH は venue_guide_images.py と同じ）
- 何度実行しても同じ
使い方: python scripts/live_thumbs.py --all | <slug> …
"""
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import venue_guide_images as V  # noqa: E402
import live_article as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets/img/posts')


def fit(text, widths):
    """文字数に応じた大きさ（全角1・半角0.55で数える）"""
    n = sum(0.55 if ord(c) < 0x2000 else 1 for c in text)
    for lim, size in widths:
        if n <= lim:
            return size
    return widths[-1][1]


def date_label(ds):
    """2027.1.19（火）・20（水） の形。年をまたぐときは両方に年"""
    wd = '月火水木金土日'
    import datetime
    parts, prev = [], None
    for d in ds:
        x = datetime.date.fromisoformat(d)
        if prev is None or prev.year != x.year:
            s = f'{x.year}.{x.month}.{x.day}'
        elif prev.month != x.month:
            s = f'{x.month}.{x.day}'
        else:
            s = f'{x.day}'
        parts.append(f'{s}<small>（{wd[x.weekday()]}）</small>')
        prev = x
    return '・'.join(parts)


def thumb_html(group, aka, color, venue, dates, n_shrine, has_hotels):
    gsize = fit(group, [(5, 132), (7, 112), (9, 92), (12, 72), (99, 60)])
    vtext = venue + '公演'
    vsize = fit(vtext, [(6, 76), (8, 64), (11, 52), (99, 42)])
    chips = ['行き方・座席', '持ち込み']
    if has_hotels:
        chips.append('会場から近い宿')
    hot = f'近くの聖地{n_shrine}軒' if n_shrine else ''
    chip_html = ''.join(f'<span>{V.esc(c)}</span>' for c in chips) + (f'<span class="hot">{hot}</span>' if hot else '')
    aka_html = f'<span class="aka">{V.esc(aka)}</span>' if aka else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0}}
#t{{position:relative;width:1200px;height:675px;overflow:hidden;font-family:"IPAPGothic","IPAGothic","Hiragino Sans","Noto Sans JP",sans-serif}}
#t img{{position:absolute;top:0;width:1200px;height:675px}}
#t .bg{{left:-420px;filter:blur(3px)}}
#t .fg{{left:260px;-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 140px)}}
.shade{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,14,34,.97) 0%,rgba(18,14,34,.92) 46%,rgba(18,14,34,.4) 70%,rgba(18,14,34,0) 86%)}}
.bar{{position:absolute;left:0;top:0;bottom:0;width:22px;background:{color}}}
.badge{{position:absolute;left:96px;top:54px;background:{color};color:#fff;font-size:32px;font-weight:700;padding:8px 24px;border-radius:999px;letter-spacing:.06em}}
.g{{position:absolute;left:92px;top:118px;display:flex;align-items:baseline;gap:22px;white-space:nowrap}}
.g b{{color:#fff;font-size:{gsize}px;font-weight:700;-webkit-text-stroke:3px #fff;text-shadow:0 6px 24px rgba(0,0,0,.45)}}
.aka{{color:#fff;font-size:36px;font-weight:700;opacity:.9}}
.v{{position:absolute;left:96px;top:{118 + gsize + 26}px;color:#FFD27A;font-size:{vsize}px;font-weight:700;-webkit-text-stroke:1.5px #FFD27A;white-space:nowrap}}
.d{{position:absolute;left:96px;top:{118 + gsize + 26 + vsize + 22}px;color:#fff;font-size:44px;font-weight:700;letter-spacing:.02em;white-space:nowrap}}
.d small{{font-size:30px}}
.chips{{position:absolute;left:96px;bottom:70px;width:780px;display:flex;flex-wrap:wrap;gap:12px}}
.chips span{{background:rgba(255,255,255,.95);color:#241F1A;font-size:28px;font-weight:700;padding:6px 18px;border-radius:12px;-webkit-text-stroke:.6px #241F1A}}
.chips span.hot{{background:#E2653A;color:#fff;-webkit-text-stroke:.6px #fff}}
.site{{position:absolute;right:60px;top:610px;color:rgba(255,255,255,.85);font-size:24px;background:rgba(18,14,34,.55);padding:6px 16px;border-radius:999px}}
</style></head><body><div id="t">
<img class="bg" src="illust.png"><img class="fg" src="illust.png"><div class="shade"></div><div class="bar"></div>
<div class="badge">ライブ参戦ガイド</div>
<div class="g"><b>{V.esc(group)}</b>{aka_html}</div>
<div class="v">{V.esc(vtext)}</div>
<div class="d">{date_label(dates)}</div>
<div class="chips">{chip_html}</div>
<div class="site">推しグルメ巡礼MAP</div>
</div></body></html>'''


def shrine_count(slug):
    for p in glob.glob(os.path.join(ROOT, '_posts', f'*-{slug}.md')):
        t = open(p, encoding='utf-8').read().split('\n---', 1)[0]
        m = re.search(r'^shop_ids:\n((?:- .*\n?)*)', t, re.M)
        return len(re.findall(r'^- ', m.group(1), re.M)) if m else 0
    return 0


def main():
    args = sys.argv[1:]
    slugs = sorted(f[:-5] for f in os.listdir(os.path.join(ROOT, 'scripts/live_data')) if f.endswith('.json')) if args == ['--all'] else args
    gix = json.load(open(os.path.join(ROOT, '_data/group_ix.json'), encoding='utf-8'))
    hotels = json.load(open(os.path.join(ROOT, '_data/venue_hotels.json'), encoding='utf-8'))
    tmp = os.environ.get('LIVE_TMP', '/tmp/live_thumbs')
    jobs = []
    for slug in slugs:
        spec = json.load(open(os.path.join(ROOT, 'scripts/live_data', slug + '.json'), encoding='utf-8'))
        key = spec['venue_key']
        vp = os.path.join(ROOT, 'scripts/venue_data', key + '.json')
        if not os.path.exists(vp):
            print(slug, '会場データがないので作らない')
            continue
        v = json.load(open(vp, encoding='utf-8'))
        g = spec['group']
        d = os.path.join(tmp, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'illust.svg'), 'w', encoding='utf-8').write(V.illustration(v))
        open(os.path.join(d, 'thumb.html'), 'w', encoding='utf-8').write(
            thumb_html(gix[g]['l'], L.AKA.get(g, ''), gix[g]['c'], v.get('short', v['name']), sorted(spec['dates']),
                       shrine_count(slug), bool((hotels.get(key) or {}).get('hotels'))))
        jobs.append((slug, d))
    if not jobs:
        return
    os.chdir(ROOT)
    subprocess.run(['node', 'scripts/render_png.js'] + [d for _, d in jobs], check=True)
    from PIL import Image
    for slug, d in jobs:
        out = os.path.join(OUT, slug)
        os.makedirs(out, exist_ok=True)
        im = Image.open(os.path.join(d, 'thumb.png')).convert('RGB')
        im.save(os.path.join(out, 'thumb.webp'), 'WEBP', quality=82, method=6)
        im.resize((600, 338), Image.LANCZOS).save(os.path.join(out, 'thumb_600.webp'), 'WEBP', quality=82, method=6)
        print(f'{slug}: {out}/thumb.webp')


if __name__ == '__main__':
    main()
