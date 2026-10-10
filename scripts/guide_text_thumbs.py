"""
guide_text_thumbs.py
写真やイラストのないガイド記事（グループ・メンバー紹介など）の見出し画像を、文字だけで作る。
データは scripts/guide_thumbs.json（slug → label・title・sub・chips・color）。
assets/img/guide/<slug>.webp（1200x675）と <slug>_600.webp を書き出し、記事の thumbnail を書き換える。

使い方: PW_CHROME=<chromium> NODE_PATH=<playwright の node_modules> python scripts/guide_text_thumbs.py [slug ...]
（scripts/render_png.js と同じく Chromium で描画する）
"""
import json
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'scripts', 'guide_thumbs.json')

JS = r"""
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 675 } });
  for (const f of process.argv.slice(2)) {
    await p.goto('file://' + path.resolve(f));
    await p.waitForTimeout(150);
    await p.screenshot({ path: f.replace(/\.html$/, '.png') });
  }
  await b.close();
})();
"""


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def html(d):
    color = d.get('color', '#1d4ed8')
    size = 132 if len(d['title']) <= 6 else 112 if len(d['title']) <= 9 else 92 if len(d['title']) <= 12 else 76
    chips = ''.join(f'<span>{esc(c)}</span>' for c in d.get('chips', []))
    return f"""<!doctype html><meta charset="utf-8"><style>
*{{margin:0;box-sizing:border-box}}
body{{width:1200px;height:675px;overflow:hidden;font-family:"Noto Sans CJK JP","Hiragino Sans",sans-serif;
background:radial-gradient(circle at 85% 20%,{color}cc 0,transparent 55%),radial-gradient(circle at 10% 110%,{color}99 0,transparent 50%),#14161f;color:#fff}}
.w{{position:absolute;inset:0;padding:70px 84px;display:flex;flex-direction:column}}
.l{{align-self:flex-start;background:#e2553f;font-weight:700;font-size:28px;padding:6px 18px;border-radius:999px}}
h1{{font-family:"Noto Serif CJK JP",serif;font-weight:900;font-size:{size}px;line-height:1.15;margin-top:36px;letter-spacing:.02em}}
.s{{font-weight:700;font-size:40px;color:#ffd27a;margin-top:18px}}
.c{{margin-top:auto;display:flex;flex-wrap:wrap;gap:12px}}
.c span{{background:#fff;color:#14161f;font-weight:700;font-size:28px;padding:8px 16px;border-radius:8px}}
.b{{position:absolute;right:40px;bottom:28px;font-size:22px;opacity:.75}}
.r{{position:absolute;right:-120px;top:-120px;width:520px;height:520px;border-radius:50%;border:2px solid #ffffff33}}
.r2{{position:absolute;right:-40px;top:-40px;width:360px;height:360px;border-radius:50%;border:2px solid #ffffff22}}
</style><div class="r"></div><div class="r2"></div><div class="w"><div class="l">{esc(d.get('label', '推し活ガイド'))}</div>
<h1>{esc(d['title'])}</h1><div class="s">{esc(d.get('sub', ''))}</div><div class="c">{chips}</div></div>
<div class="b">推しグルメ巡礼MAP</div>"""


def main():
    data = json.load(open(DATA, encoding='utf-8'))
    slugs = sys.argv[1:] or list(data)
    tmp = tempfile.mkdtemp()
    files = []
    for s in slugs:
        f = os.path.join(tmp, s + '.html')
        open(f, 'w', encoding='utf-8').write(html(data[s]))
        files.append(f)
    js = os.path.join(tmp, 'r.js')
    open(js, 'w').write(JS)
    subprocess.run(['node', js] + files, check=True)
    for s, f in zip(slugs, files):
        im = Image.open(f.replace('.html', '.png')).convert('RGB')
        out = os.path.join(ROOT, 'assets', 'img', 'guide', s)
        im.save(out + '.webp', quality=82)
        im.resize((600, 338), Image.LANCZOS).save(out + '_600.webp', quality=80)
        g = os.path.join(ROOT, '_guides', s + '.html')
        t = open(g, encoding='utf-8').read()
        t = re.sub(r'^thumbnail: .*$', f'thumbnail: /assets/img/guide/{s}.webp', t, count=1, flags=re.M)
        open(g, 'w', encoding='utf-8').write(t)
        print(s, '→', out + '.webp')


if __name__ == '__main__':
    main()
