"""
tour_hub.py
ツアーまとめ（③。_posts・article_type: tourhub）を作る。1つのツアー・シリーズの全会場を1ページに:
日程と会場（あと○日）→ 会場ごと（会場のポイント・近い宿3軒・宿の検索・近くの聖地の数・参戦ガイドとホテルのページ）→
セットリスト（公演のあと。大手報道のものだけ・出典つき・閉じた <details>）→ 予習（はじめてのライブの定番曲）→ FAQ。
「<グループ> <ツアー名> 日程／会場／ホテル／セトリ」で探す人向け。

- データ: scripts/tour_hub_data/<name>.json（lives＝scripts/live_data の公演の slug。日程・会場・公式URLはそこから。
  times に公式で発表された開場・開演、setlists に公演後のセトリ [{date, venue, parts:[[見出し, 曲名…]], src:[名前, URL]}]）
- 会場のポイントは会場ガイドの summary の先頭3つ。近くの聖地は会場から3km（3軒未満なら10km）以内のグループの店の数
- 決まり: 公式・大手報道で確かめた事実だけ。値段・チケットの申し込み・体験談は書かない
- 何度実行しても同じ（公開日は最初のまま）
使い方: python scripts/tour_hub.py <name> …
"""
import datetime
import glob
import html
import json
import os
import sys
import urllib.parse

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tour_article as T  # noqa: E402
import live_article as L  # noqa: E402
import first_live_article as F  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def esc(s):
    return html.escape(s or '', quote=True)


def build(name):
    d = J(f'scripts/tour_hub_data/{name}.json')
    g, slug = d['group'], d['slug']
    gix, venues, vnear = J('_data/group_ix.json'), J('_data/venues.json'), J('_data/venue_nearby.json')
    S, cards = J('data/shops.json'), J('_data/shop_cards.json')
    gl, color = gix[g]['l'], gix[g]['c']
    aka = L.AKA.get(g)
    gl_t = f'{gl}（{aka}）' if aka else gl
    lives = [J(f'scripts/live_data/{x}.json') | {'slug': x} for x in d['lives']]
    lives.sort(key=lambda x: x['dates'][0])
    all_dates = [dt for lv in lives for dt in lv['dates']]
    times = d.get('times') or {}
    ck = d['checked_at']
    ckl = f'{ck[:4]}年{int(ck[5:7])}月{int(ck[8:10])}日'
    vn_names = [venues[lv['venue_key']]['name'] for lv in lives]
    upcoming = [lv for lv in lives if lv['dates'][-1] >= TODAY]
    nxt = (upcoming or lives[-1:])[0]

    own = [s for s in S if g in (s.get('groups') or [s.get('group')]) and not s.get('closed') and s.get('lat') and s.get('lng')
           and s['id'] in cards and not s.get('location_unverified')]

    def shrine(key):
        v = venues[key]
        ds = sorted(T.km((v['lat'], v['lng']), (s['lat'], s['lng'])) for s in own)
        n3 = sum(1 for x in ds if x <= 3)
        return (3, n3) if n3 >= 3 else (10, sum(1 for x in ds if x <= 10))

    def live_url(lv):
        return ('{% for p in site.posts %}{% if p.article_type == \'live\' and p.group == \'' + g + '\' and p.venue_key == \'' + lv['venue_key'] +
                '\' and p.live_end == \'' + lv['dates'][-1] + '\' %}{{ p.url }}{% endif %}{% endfor %}')

    title = (f'{gl_t} {d["series_long"].replace(gl + " ", "")}まとめ｜' + '・'.join(vn_names) +
             'の日程・会場・近くの宿・セトリ')
    desc = (f'{d["series_long"]}（' + '、'.join(f'{venues[lv["venue_key"]]["name"]} {L.dlabel(lv["dates"])}' for lv in lives) +
            f'）の日程と会場、会場ごとの近い宿と近くの{gl}の聖地、公演のあとのセットリストをまとめました。日程は{ckl}時点の公式発表です。')
    summary = [f'{d["series_long"]}は' + '、'.join(f'{venues[lv["venue_key"]]["name"]} {L.dlabel(lv["dates"])}' for lv in lives) +
               f'の{len(lives)}会場・{len(all_dates)}公演（{ckl}時点の公式発表）']
    tl = [f'{int(k[5:7])}月{int(k[8:10])}日は開場{v[0]}・開演{v[1]}' for k, v in sorted(times.items())]
    if tl:
        summary.append('発表されている時刻: ' + '、'.join(tl))
    summary.append('会場ごとに、会場から近い宿（楽天トラベル）と宿の検索、近くの' + gl + 'の聖地、参戦ガイドをまとめています')
    summary.append('セットリストは公演のあと、大手報道のライブレポートに載ったものだけを出典つきで載せます')

    faq = [{'q': f'{d["series_long"]}の日程と会場は？',
            'a': '、'.join(f'{venues[lv["venue_key"]]["name"]}（{L.dlabel(lv["dates"])}）' for lv in lives) + f'です。{ckl}時点の公式発表で、変わることがあります。'}]
    if tl:
        faq.append({'q': '開場・開演の時刻は？', 'a': '、'.join(tl) + f'です（公式発表）。発表されていない公演の時刻は、{gl}の公式サイトで確かめてください。'})
    faq.append({'q': 'セットリストは？', 'a': d['setlist_pending'] if not d.get('setlists') else '公演のあと、大手報道のライブレポートに載ったセットリストをこのページの「セットリスト」に出典つきで載せています（ネタバレ注意）。'})
    faq.append({'q': '会場の近くの宿は？', 'a': 'このページの会場ごとの「会場から近い宿」に、楽天トラベルの宿を会場から近い順に載せています。会場ごとの「近くのホテル」のページでは、最寄り駅ごとにさらに多くの宿を見られます。'})

    sources = [{'label': l, 'url': u} for l, u in d['sources']]
    old = sorted(glob.glob(os.path.join(ROOT, '_posts', f'*-{slug}.md')))
    date = os.path.basename(old[0])[:10] if old else TODAY
    fm = {'layout': 'post', 'title': title, 'date': date, 'last_modified_at': TODAY, 'checked_at': ck,
          'checked_label': '公演の日程', 'description': desc, 'group': g, 'genre': 'ライブ', 'article_type': 'tourhub',
          'live_dates': all_dates, 'live_end': all_dates[-1],
          'tags': [gl] + ([aka] if aka else []) + [d['series_long'], *vn_names, 'ライブ', 'ドーム公演', '日程', 'セトリ', '遠征'],
          'sources': sources, 'faq': faq, 'pr': True, 'summary': summary}
    th = f'assets/img/posts/{slug}/thumb.webp'
    if os.path.exists(os.path.join(ROOT, th)):
        fm['thumbnail'] = '/' + th

    b = [f'<div class="pf fl" style="--pc:{color}">']
    days = ''.join(f'<div><b>{a}</b><small>{w}</small></div>' for a, w in (F.md(x) for x in nxt['dates']))
    b.append(f'''<section class="fl-hero" aria-label="次の公演">
  <p class="fl-hero__k">NEXT · {esc(venues[nxt["venue_key"]]["name"])}</p>
  <p class="fl-hero__v">{esc(d["series"])}</p>
  <p class="fl-hero__t">{esc(d["series_long"])}　{len(lives)}会場・{len(all_dates)}公演</p>
  <div class="fl-hero__days">{days}</div>
  <p class="live-cd" data-d="{nxt["dates"][0]}" data-e="{nxt["dates"][-1]}"><b>公演日</b>{F.jdate(nxt["dates"])}</p>
</section>''')
    b.append('<nav class="live-jump" aria-label="この記事の章"><a class="chip chip--area" href="#schedule">📅 日程</a>'
             + ''.join(f'<a class="chip chip--area" href="#v-{lv["venue_key"]}">🏟 {esc(venues[lv["venue_key"]]["name"])}</a>' for lv in lives)
             + '<a class="chip chip--area" href="#setlist">🎵 セトリ</a><a class="chip chip--area" href="#prep">🔰 はじめての人へ</a></nav>')
    b.append(f'<p>{d["lead"].rstrip("。")}（{ckl}時点）。</p>')

    b.append('<h2 id="schedule">📅 日程と会場</h2>')
    rows = []
    for lv in lives:
        vname = venues[lv['venue_key']]['name']
        for i, dt in enumerate(lv['dates']):
            md_, w = F.md(dt)
            t = times.get(dt)
            tt = f'開場 {t[0]}／開演 {t[1]}' if t else '時刻は未発表'
            rows.append(f'  <li{" class=\"is-past\"" if dt < TODAY else ""}><span class="tl-d"><b>{md_}</b><small>{w}</small></span>'
                        f'<span class="tl-v"><b>{esc(vname)}</b><small>{esc(tt)}</small></span>'
                        f'<a class="tl-go" href="{live_url(lv)}">参戦ガイド</a></li>')
    b.append('<ol class="tl-sched">\n' + '\n'.join(rows) + '\n</ol>')
    if d.get('nagoya_note'):
        b.append(f'<p class="note">{esc(d["nagoya_note"])}</p>')
    b.append('<p class="note">日程は' + '・'.join(f'<a href="{esc(lv["official_url"])}" target="_blank" rel="noopener">{esc(venues[lv["venue_key"]]["name"])}公演の公式発表</a>' for lv in lives)
             + (f'、時刻は<a href="{esc(d["times_src"])}" target="_blank" rel="noopener">公式のお知らせ</a>' if times else '') + f'より（{ckl}時点）。変わることがあるので、行く前に公式サイトで確かめてください。チケットの申し込みや値段はこのページでは扱いません。</p>')

    for lv in lives:
        key = lv['venue_key']
        vname = venues[key]['name']
        r, n = shrine(key)
        pts = F.guide_summary(key)[:3]
        vn = vnear.get(key) or {}
        hk, hj = vn.get('hk') or vname, vn.get('hj') or ''
        b.append(f'<h2 id="v-{key}">🏟 {esc(vname)}（{F.jdate(lv["dates"])}）</h2>')
        if pts:
            b.append('<div class="fl-venue">\n  <p class="fl-venue__h"><b>会場のポイント</b></p>\n  <ul>' + ''.join(f'<li>{esc(x)}</li>' for x in pts) + '</ul>\n'
                     f'  <div class="btn-row"><a class="btn" href="{live_url(lv)}">{esc(gl)} {esc(vname)}公演 参戦ガイド</a><a class="btn" href="/guide/{key}/">{esc(vname)} ライブ参戦ガイド</a></div>\n</div>')
        b.append('<div class="stay-in">\n  <p class="stay-in__h"><span aria-hidden="true">🛏</span> ' + esc(hk) + '周辺に泊まる<small class="stay-in__pr">PR</small></p>\n  <div class="btn-row">\n'
                 + (f'    {{% include affiliate-link.html url="https://www.jalan.net/uw/uwp2011/uww2011init.do?keyword={hj}" label="じゃらんで探す" class="btn btn--accent" service="jalan" %}}\n' if hj else '')
                 + f'    {{% include affiliate-link.html url="https://kw.travel.rakuten.co.jp/keyword/Search.do?charset=utf-8&f_query={urllib.parse.quote(hk)}" label="楽天トラベルで探す" class="btn" service="rakuten" %}}\n'
                 '  </div>\n</div>')
        b.append(f'{{% include venue-hotels.html key="{key}" limit=3 top=true %}}{{% include hotels-link.html key="{key}" %}}')
        if n:
            b.append(f'<p class="tl-seichi">🍽 会場から{r}km以内に、{esc(gl)}のメンバーが行ったお店が<b>{n}軒</b>。'
                     f'<a href="{live_url(lv)}#seichi">参戦ガイドで見る</a></p>')

    b.append('<h2 id="setlist">🎵 セットリスト</h2>')
    if d.get('setlists'):
        for st in d['setlists']:
            det = [f'  <p><b>{esc(k)}</b>：{esc(v)}</p>' for k, v in st['parts']]
            lab, url = st['src']
            b.append(f'<details class="setl">\n  <summary>{esc(st["title"])}（ネタバレ注意）</summary>\n' + '\n'.join(det)
                     + f'\n  <p class="note">出典：<a href="{esc(url)}" target="_blank" rel="noopener">{esc(lab)}</a></p>\n</details>')
    else:
        b.append(f'<p>{esc(d["setlist_pending"])}</p>')

    fl = d.get('first_live')
    b.append('<h2 id="prep">🔰 はじめての人へ・予習</h2>')
    if fl and os.path.exists(os.path.join(ROOT, 'scripts/first_live_data', g.replace('_', '-') + '.json')):
        fd = J(f'scripts/first_live_data/{g.replace("_", "-")}.json')
        b.append(f'<p>直近の大きな3公演すべてで歌われた曲（大手報道のセットリストから）：</p>')
        b.append('<ul class="setl-top">' + ''.join(f'<li>{esc(t)}</li>' for t in fd['setlist']['top']) + '</ul>')
        b.append(f'<div class="pf-cta">\n  <p>{esc(gl)}のライブにはじめて行く人へ</p>\n  <span>入場と本人確認・席の種類・ペンライト・撮影・コール・予習の動画・グッズの買い方を、公式の案内からまとめています。</span>\n'
                 f'  <a class="btn" href="/guide/{fl}/">はじめてのライブガイドを見る</a>\n</div>')
    b.append(f'{{% include live-list.html group="{g}" title="{esc(gl)}のこれからの公演（参戦ガイド）" %}}')
    b.append(f'<p class="note">このページは{ckl}に、{esc(gl)}公式サイトの発表で確かめた内容です。会場のポイントは各会場の公式サイトにもとづく会場ガイドから、宿は楽天トラベルの情報です。</p>')
    b.append('</div>')

    for o in old:
        os.remove(o)
    out = os.path.join(ROOT, '_posts', f'{date}-{slug}.md')
    open(out, 'w', encoding='utf-8').write('---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + '---\n' + '\n\n'.join(b) + '\n')
    print(out)


if __name__ == '__main__':
    for n in sys.argv[1:]:
        build(n)
