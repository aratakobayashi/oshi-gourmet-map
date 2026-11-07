"""
venue_hotels_page.py
会場のホテルのページ（/guide/<会場>/hotels/。「東京ドーム ホテル」「京セラドーム 近く 泊まる」などの検索向け）を作る。
_guides/<会場>-hotels.html（guide_category: hotels・venue_key・permalink）と見出し画像 assets/img/guide/<会場>-hotels.webp。

- 宿のデータは _data/venue_hotels.json の all（scripts/fetch_venue_hotels.py。楽天トラベルの公式API）。
  載せるのは 宿名・会場からの直線距離・最寄り駅・宿が出しているアクセスの文（API の値のまま）・画像・楽天トラベルへのリンクだけ。
  料金・空室・口コミ点数・おすすめ順位・体験談は書かない
- 楽天の規約: APIのデータを出す箱（.vhotels）の中には楽天以外へのリンクを置かない（ページ内リンクも置かない）。
  じゃらんのボタンは別の箱。クレジットは公式のHTMLのまま。宿名・駅名・アクセスの文は改変しない
- 要点・FAQ・題名の数は、作ったときのデータから書く。宿のデータを取り直したら、このスクリプトも実行し直す（何度実行しても同じ。公開日は最初のまま）
- 見出し画像に Chromium が要る（scripts/render_png.js。venue_guide_images.py と同じ）。--no-thumb で画像を作らない
使い方: python scripts/venue_hotels_page.py <会場キー> … | --all   [--no-thumb]
"""
import datetime
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import venue_guide_images as V  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()
MIN_HOTELS = 5   # これより少ない会場はページを作らない（会場ガイドの「会場から近い宿」で足りる）


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def esc(s):
    return html.escape(s or '', quote=True)


def dist(m):
    return f'約{m / 1000:.1f}km' if m >= 1000 else f'約{m}m'


def old_date(key):
    p = os.path.join(ROOT, '_guides', f'{key}-hotels.html')
    if os.path.exists(p):
        m = re.search(r'^date: (\S+)', open(p, encoding='utf-8').read(), re.M)
        if m:
            return m.group(1).strip("'\"")
    return None


def sname(s):
    """記事の文（題名・要点・見出し）で使う駅名。APIの「春日（東京）」の区別の括弧を外し「駅」を付ける（宿の行はAPIの値のまま）"""
    return re.sub(r'（[^）]*）$', '', s) + '駅'


def row(h):
    img = (f'<img src="{esc(h["img"])}" alt="" width="56" height="56" loading="lazy" decoding="async">' if h.get('img')
           else '<span class="vhotels__ph" aria-hidden="true">🏨</span>')
    meta = dist(h['m']) + (f'・最寄り {esc(h["st"])}' if h.get('st') else '')
    ac = f'<span class="vhotels__ac">{esc(h["ac"])}</span>' if h.get('ac') else ''
    return (f'    <li><a href="{esc(h["u"])}" target="_blank" rel="sponsored noopener" data-aff="rakuten">{img}'
            f'<span class="vhotels__b"><b>{esc(h["n"])}</b><small>{meta}</small>{ac}</span>'
            f'<span class="vhotels__go" aria-hidden="true">楽天<br>トラベル</span></a></li>')


def thumb_html(name, n, far, stations):
    chips = [f'近い順に{n}軒', '全部 会場から1km以内' if far < 1000 else f'会場から{dist(far)}以内'] + [sname(s) for s in stations[:2]]
    size = 120 if len(name) <= 5 else (100 if len(name) <= 7 else (84 if len(name) <= 9 else 70))
    chip_html = ''.join(f'<span>{V.esc(c)}</span>' for c in chips)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0}}
#t{{position:relative;width:1200px;height:675px;overflow:hidden;font-family:"IPAPGothic","IPAGothic","Hiragino Sans","Noto Sans JP",sans-serif}}
#t img{{position:absolute;top:0;width:1200px;height:675px}}
#t .bg{{left:-420px;filter:blur(3px)}}
#t .fg{{left:260px;-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 140px)}}
.shade{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,14,34,.97) 0%,rgba(18,14,34,.9) 44%,rgba(18,14,34,.35) 68%,rgba(18,14,34,0) 84%)}}
.badge{{position:absolute;left:96px;top:62px;background:#2F6F8F;color:#fff;font-size:32px;font-weight:700;padding:8px 24px;border-radius:999px;letter-spacing:.06em}}
.t1{{position:absolute;left:92px;top:{140 + (120 - size) // 2}px;color:#fff;font-size:{size}px;font-weight:700;-webkit-text-stroke:3px #fff;text-shadow:0 6px 24px rgba(0,0,0,.45);white-space:nowrap}}
.t2{{position:absolute;left:96px;top:300px;color:#FFD27A;font-size:84px;font-weight:700;-webkit-text-stroke:1.5px #FFD27A}}
.chips{{position:absolute;left:96px;top:440px;width:760px;display:flex;flex-wrap:wrap;gap:12px}}
.chips span{{background:rgba(255,255,255,.95);color:#241F1A;font-size:30px;font-weight:700;padding:6px 18px;border-radius:12px;-webkit-text-stroke:.6px #241F1A}}
.site{{position:absolute;right:60px;top:610px;color:rgba(255,255,255,.85);font-size:24px;background:rgba(18,14,34,.55);padding:6px 16px;border-radius:999px}}
</style></head><body><div id="t">
<img class="bg" src="illust.png"><img class="fg" src="illust.png"><div class="shade"></div>
<div class="badge">ライブ遠征で泊まる</div>
<div class="t1">{V.esc(name)}</div>
<div class="t2">近くのホテル</div>
<div class="chips">{chip_html}</div>
<div class="site">推しグルメ巡礼MAP</div>
</div></body></html>'''


def build(key, venues, hotels, vnear):
    vh = hotels.get(key) or {}
    allh = vh.get('all') or []
    if len(allh) < MIN_HOTELS:
        print(key, f'宿が{len(allh)}軒なので作らない')
        return None
    v = venues[key]
    vname = v['name']
    at = vh.get('at') or TODAY
    atl = f'{at[:4]}年{int(at[5:7])}月'
    n = len(allh)
    far = allh[-1]['m']
    # 最寄り駅ごと（いちばん近い宿の順）。1〜2軒の駅は「そのほかの駅」にまとめる
    groups, order = {}, []
    for h in allh:
        st = h.get('st') or ''
        if st not in groups:
            groups[st] = []
            order.append(st)
        groups[st].append(h)
    big = [s for s in order if s and len(groups[s]) >= 3]
    rest = [h for s in order if s not in big for h in groups[s]]
    sections = [(s, f'{sname(s)}が最寄りの宿', groups[s]) for s in big]
    if rest:
        sections.append(('', 'そのほかの駅が最寄りの宿' if big else '会場から近い宿', rest))
    top_st = sorted(big, key=lambda s: -len(groups[s]))
    near1, near2 = allh[0], allh[1]
    has_guide = os.path.exists(os.path.join(ROOT, '_guides', f'{key}.html'))
    vn = vnear.get(key) or {}
    hk, hj = vn.get('hk') or vname, vn.get('hj') or ''

    st_txt = '・'.join(sname(s) for s in top_st[:3])
    title = (f'{vname}の近くのホテル｜会場から近い宿{n}軒を最寄り駅ごとに（{st_txt}）' if st_txt
             else f'{vname}の近くのホテル｜会場から近い宿{n}軒（最寄り駅・アクセスつき）')
    desc = (f'{vname}でライブがある日に泊まる宿を探す人へ。楽天トラベルに載っている宿のうち、{vname}から近い順に{n}軒'
            f'（いちばん遠い宿で{dist(far)}・直線距離）を、最寄り駅ごとに、宿が案内しているアクセスと一緒にまとめました（{atl}時点）。')
    summary = [f'{vname}からいちばん近いのは{near1["n"]}（{dist(near1["m"])}）、次が{near2["n"]}（{dist(near2["m"])}）。距離は会場からの直線距離',
               f'この記事では、楽天トラベルに載っている宿を会場から近い順に{n}軒（いちばん遠い宿で{dist(far)}）、最寄り駅ごとに載せています（{atl}時点）']
    if top_st:
        summary.append('最寄り駅で多いのは ' + '、'.join(f'{sname(s)}（{len(groups[s])}軒）' for s in top_st[:3]))
    summary.append('料金・空室は日によって変わるので、楽天トラベルの宿のページで確かめてください')

    faq = [{'q': f'{vname}からいちばん近い宿はどこですか？',
            'a': f'楽天トラベルに載っている宿では、{near1["n"]}（会場から{dist(near1["m"])}・直線距離）です。次が{near2["n"]}（{dist(near2["m"])}）です（{atl}時点）。'}]
    if top_st:
        faq.append({'q': f'{vname}の近くの宿は、どの駅の近くに多いですか？',
                    'a': f'この記事に載せた{n}軒では、最寄り駅が' + '、'.join(f'{sname(s)}の宿が{len(groups[s])}軒' for s in top_st[:3]) + f'です（{atl}時点・楽天トラベルの情報）。'})
    faq.append({'q': '宿の料金や空室はこの記事でわかりますか？',
                'a': '料金・空室は日によって変わるので載せていません。宿の名前を押すと楽天トラベルの宿のページが開くので、そこで泊まる日の料金と空室を確かめてください。'})
    if has_guide:
        faq.append({'q': f'{vname}への行き方や持ち込めないものは？',
                    'a': f'「{vname} ライブ参戦ガイド」に、最寄り駅と出口・ゲートと座席・持ち込めないもの・当日の準備をまとめています。'})

    fm = {'title': title, 'description': desc, 'date': old_date(key) or TODAY, 'last_modified_at': TODAY,
          'guide_category': 'hotels', 'venue_key': key, 'permalink': f'/guide/{key}/hotels/',
          'thumbnail': f'/assets/img/guide/{key}-hotels.webp', 'thumbnail_note': f'イラスト（{vname}と周辺のイメージ）',
          'checked_at': at, 'pr': True,
          'sources': [{'label': '楽天トラベル（楽天ウェブサービスの施設検索）', 'url': 'https://travel.rakuten.co.jp/'}],
          'summary': summary, 'faq': faq}
    import yaml
    fm_txt = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)

    b = [f'<p>{esc(vname)}でライブがある日に、終演後の移動を少なくしたい人へ。楽天トラベルに載っている宿のうち、'
         f'会場から近い順に{n}軒を、最寄り駅ごとにまとめました。それぞれの宿が案内しているアクセス（駅から徒歩何分か）も載せています。'
         f'宿の名前を押すと、楽天トラベルの宿のページが開きます。</p>']
    if len(sections) > 1:
        b.append('<nav class="live-jump" aria-label="最寄り駅で選ぶ">' + ''.join(
            f'<a class="chip chip--area" href="#st{i + 1}">{esc(sname(s)) if s else "そのほか"}<span class="cnt">{len(hs)}</span></a>'
            for i, (s, _, hs) in enumerate(sections)) + '</nav>')
    b.append('<h2 id="hotels">最寄り駅ごとの宿</h2>')
    for i, (s, label, hs) in enumerate(sections):
        b.append(f'<div class="vhotels vhotels--full" id="st{i + 1}">\n  <h3 class="vhotels__h">{esc(label)}<span>{len(hs)}軒・会場から近い順</span><small class="stay-in__pr">PR</small></h3>\n  <ul>')
        b += [row(h) for h in hs]
        b.append('  </ul>\n</div>')
    b.append(f'<p class="note vhotels__credit">宿の情報は{atl}時点の楽天トラベルの情報です。距離は{esc(vname)}からの直線距離で、歩く距離とは違います。'
             '最寄り駅とアクセスは各宿の案内です。料金・空室は楽天トラベルで確かめてください。'
             '<a href="https://developers.rakuten.com/" target="_blank">Supported by Rakuten Developers</a></p>')

    b.append('<h2 id="search">じゃらん・楽天トラベルで探す</h2>')
    b.append(f'<p>この記事に載せた{n}軒のほかにも、{esc(vname)}の周辺には宿があります。泊まる日を決めて空室を探すなら、宿の予約サイトで検索できます。</p>')
    b.append('<div class="stay-in">\n  <p class="stay-in__h"><span aria-hidden="true">🛏</span> ' + esc(hk) + '周辺に泊まる<small class="stay-in__pr">PR</small></p>\n  <div class="btn-row">\n'
             + (f'    {{% include affiliate-link.html url="https://www.jalan.net/uw/uwp2011/uww2011init.do?keyword={hj}" label="じゃらんで探す" class="btn btn--accent" service="jalan" %}}\n' if hj else '')
             + f'    {{% include affiliate-link.html url="https://kw.travel.rakuten.co.jp/keyword/Search.do?charset=utf-8&f_query={urllib.parse.quote(hk)}" label="楽天トラベルで探す" class="btn" service="rakuten" %}}\n'
             '  </div>\n</div>')

    b.append(f'{{% include live-list.html venue="{key}" title="{esc(vname)}でこれからある公演" %}}')

    b.append('<h2 id="more">会場への行き方・持ち込み</h2>')
    more = []
    if has_guide:
        more.append(f'<li><a href="/guide/{key}/">{esc(vname)} ライブ参戦ガイド</a>：最寄り駅と出口・ゲートと座席・持ち込めないもの・当日の準備</li>')
    more += ['<li><a href="/guide/live-ensei-checklist/">ライブ遠征の準備チェックリスト</a>：持ち物・宿・当日の動き方</li>',
             '<li><a href="/guide/live-ensei-transport/">ライブ遠征の交通手段ガイド</a>：新幹線・飛行機・高速バスの使い分け</li>',
             '<li><a href="/ensei/">ライブ遠征×聖地巡礼</a>：全国の会場の近くの聖地と宿</li>']
    b.append('<ul>\n' + '\n'.join('  ' + x for x in more) + '\n</ul>')

    out = os.path.join(ROOT, '_guides', f'{key}-hotels.html')
    open(out, 'w', encoding='utf-8').write('---\n' + fm_txt + '---\n' + '\n\n'.join(b) + '\n')
    print(out, f'{n}軒・{len(sections)}区分')
    vd = os.path.join(ROOT, 'scripts/venue_data', key + '.json')
    if os.path.exists(vd):
        vv = J(f'scripts/venue_data/{key}.json')
        return key, vv, thumb_html(vv.get('short', vname), n, far, top_st)
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    venues, hotels, vnear = J('_data/venues.json'), J('_data/venue_hotels.json'), J('_data/venue_nearby.json')
    keys = sorted(hotels) if '--all' in sys.argv else args
    jobs = [j for j in (build(k, venues, hotels, vnear) for k in keys) if j]
    if '--no-thumb' in sys.argv or not jobs:
        return
    tmp = os.environ.get('HOTELS_TMP', '/tmp/venue_hotels_thumbs')
    dirs = []
    for key, vv, th in jobs:
        d = os.path.join(tmp, key)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'illust.svg'), 'w', encoding='utf-8').write(V.illustration(vv))
        open(os.path.join(d, 'thumb.html'), 'w', encoding='utf-8').write(th)
        dirs.append((key, d))
    os.chdir(ROOT)
    subprocess.run(['node', 'scripts/render_png.js'] + [d for _, d in dirs], check=True)
    from PIL import Image
    for key, d in dirs:
        im = Image.open(os.path.join(d, 'thumb.png')).convert('RGB')
        im.save(os.path.join(ROOT, 'assets/img/guide', f'{key}-hotels.webp'), 'WEBP', quality=82, method=6)
        im.resize((600, 338), Image.LANCZOS).save(os.path.join(ROOT, 'assets/img/guide', f'{key}-hotels_600.webp'), 'WEBP', quality=82, method=6)
        print(f'{key}: assets/img/guide/{key}-hotels.webp')


if __name__ == '__main__':
    main()
