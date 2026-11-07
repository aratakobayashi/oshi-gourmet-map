"""
first_live_thumb.py
「はじめてのライブ」（_guides/<group>-first-live.html）の見出し画像。グループの画像（assets/images/groups/<group>.jpg。
トップやグループのカードと同じもの）を、ペンライトの光の中に大きく置き、題と公演の札を載せる。メンバーの写真は使わない。

- 中身は scripts/guide_thumbs.json の <slug>（label・title・sub・chips・color）と group（グループID）。lights にペンライトの色（任意）
- 出力: assets/img/guide/<slug>.webp（1200x675）と <slug>_600.webp
- Chromium（Playwright）で描く。NODE_PATH に playwright、PW_CHROME に実行ファイル（なければ既定）
使い方: python scripts/first_live_thumb.py <slug> …
"""
import base64
import html
import json
import os
import random
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JS = r'''
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 675 } });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(300);
  await (await p.$('#t')).screenshot({ path: process.argv[3] });
  await b.close();
})();
'''


def page(d, img_b64):
    e = html.escape
    color = d.get('color', '#f43f5e')
    rnd = random.Random(d['title'])
    lights = d.get('lights') or [color, '#ffffff', '#ffd1e0']
    dots = ''.join(
        f'<i style="left:{rnd.uniform(0, 1200):.0f}px;top:{rnd.uniform(380, 700):.0f}px;'
        f'width:{(w := rnd.uniform(5, 12)):.0f}px;height:{w * 3.2:.0f}px;background:{rnd.choice(lights)};'
        f'transform:rotate({rnd.uniform(-35, 35):.0f}deg);opacity:{rnd.uniform(.45, .95):.2f}"></i>' for _ in range(150))
    chips = ''.join(f'<span>{e(c)}</span>' for c in d.get('chips', []))
    t = d['title']
    size = 150 if len(t) <= 6 else (116 if len(t) <= 9 else 92)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0}}
#t{{position:relative;width:1200px;height:675px;overflow:hidden;font-family:"IPAPGothic","IPAGothic","Hiragino Sans","Noto Sans JP",sans-serif;
  background:radial-gradient(circle at 78% 30%, {color}cc 0, {color}55 26%, transparent 52%),
             radial-gradient(circle at 20% 110%, #ff9ec466 0, transparent 45%),
             linear-gradient(160deg,#2a0f22 0%,#3b0f2c 45%,#16091a 100%)}}
.beam{{position:absolute;top:-80px;width:220px;height:900px;background:linear-gradient(180deg,rgba(255,255,255,.28),rgba(255,255,255,0) 75%);filter:blur(6px);transform-origin:top center}}
.dots i{{position:absolute;border-radius:6px;filter:blur(.6px);box-shadow:0 0 14px currentColor}}
.logo{{position:absolute;right:70px;top:70px;width:440px;height:440px;border-radius:50%;background:#fff;
  box-shadow:0 0 0 10px rgba(255,255,255,.18),0 0 90px {color};transform:rotate(-6deg);overflow:hidden}}
.logo img{{width:100%;height:100%;object-fit:cover}}
.badge{{position:absolute;left:80px;top:62px;background:#fff;color:{color};font-size:34px;font-weight:700;padding:8px 26px;border-radius:999px;letter-spacing:.06em}}
.t1{{position:absolute;left:74px;top:126px;color:#fff;font-size:{size}px;font-weight:700;-webkit-text-stroke:3px #fff;text-shadow:0 8px 30px rgba(0,0,0,.45);white-space:nowrap}}
.t2{{position:absolute;left:80px;top:{126 + size + 30}px;width:640px;color:#FFE08A;font-size:46px;font-weight:700;line-height:1.3;-webkit-text-stroke:1px #FFE08A;text-shadow:0 4px 18px rgba(0,0,0,.5)}}
.chips{{position:absolute;left:80px;bottom:66px;width:1040px;display:flex;flex-wrap:wrap;gap:12px}}
.chips span{{background:rgba(255,255,255,.95);color:#2a0f22;font-size:30px;font-weight:700;padding:7px 20px;border-radius:12px;-webkit-text-stroke:.6px #2a0f22}}
.chips span:first-child{{background:{color};color:#fff;-webkit-text-stroke:.6px #fff}}
.site{{position:absolute;right:56px;top:22px;color:rgba(255,255,255,.8);font-size:22px}}
</style></head><body><div id="t">
<div class="beam" style="left:640px;transform:rotate(18deg)"></div><div class="beam" style="left:900px;transform:rotate(-14deg)"></div><div class="beam" style="left:300px;transform:rotate(10deg);opacity:.6"></div>
<div class="dots">{dots}</div>
<div class="logo"><img src="data:image/jpeg;base64,{img_b64}" alt=""></div>
<div class="badge">{e(d.get('label', 'はじめてのライブ'))}</div>
<div class="t1">{e(t)}</div>
<div class="t2">{e(d.get('sub', '')).replace(chr(10), '<br>')}</div>
<div class="chips">{chips}</div>
<div class="site">推しグルメ巡礼MAP</div>
</div></body></html>'''


def main():
    data = json.load(open(os.path.join(ROOT, 'scripts/guide_thumbs.json'), encoding='utf-8'))
    from PIL import Image
    for slug in sys.argv[1:]:
        d = data[slug]
        src = os.path.join(ROOT, 'assets/images/groups', d['group'] + '.jpg')
        img = base64.b64encode(open(src, 'rb').read()).decode()
        with tempfile.TemporaryDirectory() as tmp:
            hp, js, png = os.path.join(tmp, 't.html'), os.path.join(tmp, 'r.js'), os.path.join(tmp, 't.png')
            open(hp, 'w', encoding='utf-8').write(page(d, img))
            open(js, 'w').write(JS)
            subprocess.run(['node', js, hp, png], check=True, cwd=ROOT)
            im = Image.open(png).convert('RGB')
            out = os.path.join(ROOT, 'assets/img/guide', slug)
            im.save(out + '.webp', 'WEBP', quality=84, method=6)
            im.resize((600, 338), Image.LANCZOS).save(out + '_600.webp', 'WEBP', quality=84, method=6)
            print(slug, '→', out + '.webp')


if __name__ == '__main__':
    main()
