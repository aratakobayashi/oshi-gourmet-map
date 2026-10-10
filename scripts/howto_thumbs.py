"""
howto_thumbs.py
お役立ちガイド（遠征準備・推し活の基本など）の見出し画像を作る。
右側に、記事の中身を表すアイコンのイラスト（電車・飛行機・スーツケースなど）を丸いステッカー風に並べ、
左に大見出し・キャッチ・記事の中身（チップ）を載せる。

データ: scripts/howto_data/<slug>.json
  {"color": "#2563eb", "label": "遠征準備", "title": "大見出し", "catch": "キャッチ",
   "chips": ["…", "…"], "icons": ["train", "plane", "bus"]}
書き出し: assets/img/guide/<slug>.webp（1200x675）と <slug>_600.webp。記事の thumbnail も書き換える。

使い方: PW_CHROME=<chromium> NODE_PATH=<playwright の node_modules> python scripts/howto_thumbs.py <slug> ...
"""
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
INK = '#241F1A'

# 120x120 の枠に描くアイコン。c はテーマ色
ICONS = {
    'train': lambda c: f'<rect x="28" y="14" width="64" height="80" rx="16" fill="{c}"/><rect x="36" y="26" width="48" height="26" rx="5" fill="#fff"/><circle cx="44" cy="70" r="6" fill="#fff"/><circle cx="76" cy="70" r="6" fill="#fff"/><path d="M38 94 L28 110 M82 94 L92 110" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>',
    'plane': lambda c: f'<path d="M60 10 C66 10 68 18 68 26 L68 48 L106 70 L106 80 L68 68 L68 92 L80 102 L80 108 L60 102 L40 108 L40 102 L52 92 L52 68 L14 80 L14 70 L52 48 L52 26 C52 18 54 10 60 10 Z" fill="{c}"/>',
    'bus': lambda c: f'<rect x="18" y="18" width="84" height="76" rx="14" fill="{c}"/><rect x="28" y="30" width="64" height="26" rx="4" fill="#fff"/><circle cx="38" cy="76" r="6" fill="#fff"/><circle cx="82" cy="76" r="6" fill="#fff"/><rect x="30" y="94" width="14" height="12" rx="3" fill="{INK}"/><rect x="76" y="94" width="14" height="12" rx="3" fill="{INK}"/>',
    'suitcase': lambda c: f'<rect x="46" y="12" width="28" height="16" rx="6" fill="none" stroke="{INK}" stroke-width="6"/><rect x="26" y="26" width="68" height="80" rx="12" fill="{c}"/><path d="M46 36 V96 M74 36 V96" stroke="#fff" stroke-width="5" opacity=".8"/><circle cx="38" cy="110" r="5" fill="{INK}"/><circle cx="82" cy="110" r="5" fill="{INK}"/>',
    'wifi': lambda c: f'<path d="M14 50 Q60 6 106 50" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round"/><path d="M30 66 Q60 38 90 66" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round"/><path d="M46 82 Q60 70 74 82" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round"/><circle cx="60" cy="98" r="8" fill="{INK}"/>',
    'phone': lambda c: f'<rect x="34" y="8" width="52" height="104" rx="12" fill="{INK}"/><rect x="40" y="20" width="40" height="76" rx="4" fill="{c}"/><circle cx="60" cy="104" r="4" fill="#fff"/><path d="M48 60 l8 8 l16 -18" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
    'battery': lambda c: f'<rect x="20" y="36" width="74" height="48" rx="10" fill="none" stroke="{INK}" stroke-width="7"/><rect x="94" y="50" width="8" height="20" rx="3" fill="{INK}"/><rect x="28" y="44" width="42" height="32" rx="5" fill="{c}"/><path d="M60 40 L48 62 H60 L54 82" fill="none" stroke="#fff" stroke-width="5" stroke-linejoin="round"/>',
    'check': lambda c: f'<rect x="20" y="14" width="80" height="94" rx="10" fill="#fff" stroke="{INK}" stroke-width="5"/><rect x="44" y="8" width="32" height="14" rx="5" fill="{INK}"/>' + ''.join(f'<rect x="32" y="{36 + i * 22}" width="12" height="12" rx="2" fill="{c}"/><rect x="52" y="{39 + i * 22}" width="36" height="6" rx="3" fill="#E2D9CC"/>' for i in range(3)),
    'hotel': lambda c: f'<rect x="24" y="22" width="72" height="86" rx="6" fill="{c}"/>' + ''.join(f'<rect x="{34 + (i % 3) * 20}" y="{32 + (i // 3) * 18}" width="12" height="10" rx="2" fill="#fff"/>' for i in range(9)) + f'<rect x="50" y="88" width="20" height="20" fill="{INK}"/>',
    'ticket': lambda c: f'<path d="M14 34 H106 V52 A8 8 0 0 0 106 68 V86 H14 V68 A8 8 0 0 0 14 52 Z" fill="{c}"/><path d="M80 38 V82" stroke="#fff" stroke-width="3" stroke-dasharray="5 5"/><path d="M30 52 H66 M30 66 H58" stroke="#fff" stroke-width="5" stroke-linecap="round"/>',
    'heart': lambda c: f'<path d="M60 104 C20 76 12 56 12 42 C12 26 24 16 38 16 C48 16 56 22 60 30 C64 22 72 16 82 16 C96 16 108 26 108 42 C108 56 100 76 60 104 Z" fill="{c}"/>',
    'calendar': lambda c: f'<rect x="16" y="22" width="88" height="84" rx="10" fill="#fff" stroke="{INK}" stroke-width="5"/><rect x="16" y="22" width="88" height="22" rx="10" fill="{c}"/><path d="M38 14 V30 M82 14 V30" stroke="{INK}" stroke-width="6" stroke-linecap="round"/><circle cx="76" cy="78" r="12" fill="{c}"/>',
    'coin': lambda c: f'<circle cx="60" cy="60" r="44" fill="{c}"/><circle cx="60" cy="60" r="32" fill="none" stroke="#fff" stroke-width="4"/><path d="M48 46 L60 60 L72 46 M60 60 V80 M50 64 H70 M50 72 H70" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round"/>',
    'camera': lambda c: f'<rect x="12" y="34" width="96" height="66" rx="12" fill="{c}"/><rect x="40" y="22" width="40" height="18" rx="5" fill="{c}"/><circle cx="60" cy="68" r="20" fill="#fff"/><circle cx="60" cy="68" r="11" fill="{INK}"/>',
    'bag': lambda c: f'<path d="M40 40 C40 20 80 20 80 40" fill="none" stroke="{INK}" stroke-width="6"/><path d="M22 40 H98 L92 106 H28 Z" fill="{c}"/><circle cx="60" cy="72" r="10" fill="#fff"/>',
    'star': lambda c: f'<path d="M60 10 L74 44 L110 46 L82 70 L92 106 L60 86 L28 106 L38 70 L10 46 L46 44 Z" fill="{c}"/>',
    'map': lambda c: f'<path d="M14 26 L44 16 L76 26 L106 16 V94 L76 104 L44 94 L14 104 Z" fill="#fff" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/><path d="M44 16 V94 M76 26 V104" stroke="#E2D9CC" stroke-width="4"/><path d="M60 82 C48 66 44 58 44 50 A16 16 0 0 1 76 50 C76 58 72 66 60 82 Z" fill="{c}"/><circle cx="60" cy="50" r="6" fill="#fff"/>',
}

# 右側のステッカーの位置（中心x, 中心y, 半径）
SPOTS = [(880, 250, 150), (1070, 470, 105), (700, 500, 95), (1090, 160, 80)]


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def html(d):
    c = d['color']
    stickers = ''
    for (cx, cy, r), name in zip(SPOTS, d['icons']):
        s = r * 1.25 / 120
        stickers += (f'<circle cx="{cx}" cy="{cy + 8}" r="{r}" fill="#000" opacity=".12"/>'
                     f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff"/><circle cx="{cx}" cy="{cy}" r="{r - 10}" fill="none" stroke="{c}" stroke-width="3" stroke-dasharray="6 8" opacity=".55"/>'
                     f'<g transform="translate({cx - 60 * s:.1f} {cy - 60 * s:.1f}) scale({s:.3f})">{ICONS[name](c)}</g>')
    chips = ''.join(f'<span>{esc(x)}</span>' for x in d.get('chips', []))
    t = d['title']
    fs = 116 if len(t) <= 5 else 96 if len(t) <= 6 else 82 if len(t) <= 7 else 72
    return f"""<!doctype html><meta charset="utf-8"><style>
*{{margin:0;box-sizing:border-box}}body{{width:1200px;height:675px;overflow:hidden;font-family:{FONT}}}
#t{{position:relative;width:1200px;height:675px;overflow:hidden;background:#FBF6EE}}
svg{{position:absolute;inset:0}}
.w{{position:absolute;left:68px;top:64px;width:600px}}
.l{{display:inline-block;background:{c};color:#fff;font-weight:800;font-size:26px;padding:6px 18px;border-radius:999px}}
.k{{color:{c};font-weight:800;font-size:34px;margin-top:26px}}
h1{{color:{INK};font-family:{SERIF};font-weight:900;font-size:{fs}px;line-height:1.15;margin-top:8px;letter-spacing:.02em;white-space:nowrap}}
.c{{position:absolute;left:68px;bottom:56px;display:flex;gap:12px;flex-wrap:wrap;width:560px}}
.c span{{background:#fff;color:{INK};font-weight:800;font-size:27px;padding:8px 16px;border-radius:10px;border:3px solid {INK}}}
.b{{position:absolute;left:68px;bottom:18px;color:{INK};opacity:.6;font-size:20px}}
</style><div id="t"><svg viewBox="0 0 1200 675" width="1200" height="675">
<circle cx="980" cy="330" r="420" fill="{c}" opacity=".16"/><circle cx="1150" cy="80" r="160" fill="{c}" opacity=".12"/>
<g opacity=".18" fill="{c}">{''.join(f'<circle cx="{40 + i * 46}" cy="{640 - (i % 3) * 8}" r="5"/>' for i in range(14))}</g>
{stickers}
</svg>
<div class="w"><span class="l">{esc(d['label'])}</span><div class="k">{esc(d['catch'])}</div><h1>{esc(t)}</h1></div>
<div class="c">{chips}</div><div class="b">推しグルメ巡礼MAP</div></div>"""


RENDER = r"""
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 675 } });
  for (let i = 2; i < process.argv.length; i += 2) {
    await p.goto('file://' + path.resolve(process.argv[i]));
    await p.waitForTimeout(150);
    await (await p.$('#t')).screenshot({ path: process.argv[i + 1] });
  }
  await b.close();
})();
"""


def main(slugs):
    tmp = tempfile.mkdtemp()
    args = []
    for s in slugs:
        d = json.load(open(os.path.join(ROOT, 'scripts', 'howto_data', s + '.json'), encoding='utf-8'))
        hp = os.path.join(tmp, s + '.html')
        open(hp, 'w', encoding='utf-8').write(html(d))
        args += [hp, os.path.join(tmp, s + '.png')]
    js = os.path.join(tmp, 'r.js')
    open(js, 'w').write(RENDER)
    subprocess.run(['node', js] + args, check=True)
    for s in slugs:
        im = Image.open(os.path.join(tmp, s + '.png')).convert('RGB')
        base = os.path.join(ROOT, 'assets', 'img', 'guide', s)
        im.save(base + '.webp', quality=84)
        im.resize((600, 338), Image.LANCZOS).save(base + '_600.webp', quality=82)
        g = os.path.join(ROOT, '_guides', s + '.html')
        t = open(g, encoding='utf-8').read()
        t = re.sub(r'^thumbnail: .*$', f'thumbnail: /assets/img/guide/{s}.webp', t, count=1, flags=re.M)
        open(g, 'w', encoding='utf-8').write(t)
        print(s, '→', base + '.webp')


if __name__ == '__main__':
    main(sys.argv[1:])
