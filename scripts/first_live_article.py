"""
first_live_article.py
グループ別「はじめてのライブ」（④。_guides/<slug>.html・guide_category: firstlive）を、データ scripts/first_live_data/<group>.json から作る。
ほかのグループに広げるときは、同じ形のデータを書いて実行するだけ（=LOVE の equal-love.json が見本）。

章: ヒーロー（ドーム・アリーナなど次の公演。あと○日）→ 章のボタン → まず押さえる3つ → 当日の流れ・持ち物チェック → 席の種類 →
    ライブ中の決まり（✕/◯）→ ペンライトの色 → メンバー → コールと予習の動画 → 定番曲（大手報道のセトリ）→ グッズ →
    会場のポイント（会場ガイドの要点）・これからの公演 → 泊まる（会場ごと）→ 聖地 → 公式のリンク
決まり: 公式・大手報道で確かめた事実だけ（データに書くときに確かめる）。値段・体験談・ファンのコール表・歌詞は書かない。
        セトリは大手報道のものを出典つきで閉じた <details> に。ペンライトの色の見本はイメージと注記。
- 会場のポイントは会場ガイド（_guides/<会場>.html）の summary の先頭4つ。泊まるは _data/venue_nearby.json（じゃらん・楽天の検索語）と venue-hotels.html
- 見出し画像は scripts/first_live_thumb.py（scripts/guide_thumbs.json）
- 何度実行しても同じ（公開日は最初のまま。last_modified_at は内容が変わったときだけ今日）
使い方: python scripts/first_live_article.py <group> …   （例: equal-love）
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.parse

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()
WD = '月火水木金土日'


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def esc(s):
    return html.escape(s or '', quote=True)


def ext(url, label):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{label}</a>'


def md(d):
    x = datetime.date.fromisoformat(d)
    return f'{x.month}.{x.day}', WD[x.weekday()]


def jdate(ds):
    out, prev = [], None
    for d in ds:
        x = datetime.date.fromisoformat(d)
        s = (f'{x.year}年{x.month}月{x.day}日' if prev is None or prev.year != x.year else
             f'{x.month}月{x.day}日' if prev.month != x.month else f'{x.day}日')
        out.append(f'{s}（{WD[x.weekday()]}）')
        prev = x
    return '・'.join(out)


def guide_summary(key):
    p = os.path.join(ROOT, '_guides', f'{key}.html')
    if not os.path.exists(p):
        return []
    fm = yaml.safe_load(open(p, encoding='utf-8').read().split('\n---', 1)[0].lstrip('-'))
    return (fm or {}).get('summary') or []


def hero(d, shows):
    nxt = shows[0]
    days = ''.join(f'<div><b>{a}</b><small>{b}</small></div>' for a, b in (md(x) for x in nxt['dates']))
    tm = (f'<div class="fl-hero__time"><span>開場 <b>{esc(nxt["open"])}</b></span><span>開演 <b>{esc(nxt["start"])}</b></span></div>'
          if nxt.get('open') and nxt.get('start') else (f'<div class="fl-hero__time"><span>開演 <b>{esc(nxt["start"])}</b></span><span>開場は未発表</span></div>' if nxt.get('start') else '<div class="fl-hero__time"><span>開場・開演の時刻は未発表</span></div>'))
    others = ''.join(
        f'<a class="fl-hero__next" href="#stay-{esc(s["venue_key"])}"><small>NEXT</small><b>{esc(s["label"])}</b><span>{jdate(s["dates"])}</span></a>'
        for s in shows[1:])
    return f'''<section class="fl-hero" aria-label="次の大きな公演">
  <p class="fl-hero__k">NEXT LIVE</p>
  <p class="fl-hero__v">{esc(nxt["label"])}</p>
  <p class="fl-hero__t">{esc(nxt["title"])}</p>
  <div class="fl-hero__days">{days}</div>
  {tm}
  <p class="live-cd" data-d="{nxt["dates"][0]}" data-e="{nxt["dates"][-1]}"><b>公演日</b>{jdate(nxt["dates"])}</p>
  {others}
  <p class="fl-hero__src">{(nxt["time_note"] + "。") if nxt.get("time_note") else ("両日とも同じ時刻。" if len(nxt["dates"]) > 1 and nxt.get("open") else "")}{ext(nxt["src"], nxt["src_label"]) if nxt.get("src_label") else d["name"] + "公式の" + ext(nxt["src"], "公演のお知らせ")}より（{d["checked_at"][:4]}年{int(d["checked_at"][5:7])}月{int(d["checked_at"][8:])}日確認）。{nxt.get("end_note") or "終演の時刻は未発表"}</p>
</section>'''


def build(gid):
    d = J(f'scripts/first_live_data/{gid}.json')
    slug, color, name = d['slug'], d['color'], d['name']
    shows = [s for s in d['shows'] if s['dates'][-1] >= TODAY] or d['shows'][-1:]
    venues, vnear = J('_data/venues.json'), J('_data/venue_nearby.json')
    ckl = f'{d["checked_at"][:4]}年{int(d["checked_at"][5:7])}月{int(d["checked_at"][8:])}日'
    b = [f'<div class="pf fl" style="--pc:{color}">', hero(d, shows)]
    jumps = [('entry', '🎫 入場'), ('flow', '🕓 当日の流れ'), ('seats', '💺 席'), ('rules', '🙅 決まり'), ('penlight', '🔦 ペンライト'),
             ('call', '📣 コール'), ('setlist', '🎵 定番曲'), ('past', '🎬 前回のライブ'), ('album', '🎧 アルバム'), ('goods', '🛍 グッズ'), ('venue', '🏟 会場と宿'), ('seichi', '🍽 聖地')]
    jumps = [j for j in jumps if j[0] not in ('seats', 'past', 'album') or d.get(j[0])]
    b.append('<nav class="live-jump" aria-label="この記事の章">' + ''.join(f'<a class="chip chip--area" href="#{i}">{t}</a>' for i, t in jumps) + '</nav>')
    b.append(f'<p>{d["intro"].rstrip("。")}（{ckl}時点）。</p>')
    if d.get('tour_page'):
        b.append(f'<p class="first-live">全会場の日程・時刻・セトリは：{d["tour_page"]}</p>')

    b.append('<h2 id="entry">🎫 まず押さえる3つ</h2>')
    b.append(f'<p>{d["entry_lead"]}</p>')
    if d.get('ticket_link'):
        b.append(f'<p class="first-live">🎫 チケットの受付（先行の種類・期間・対象）は：{d["ticket_link"]}</p>')
    b.append('<ol class="fl-three">\n' + ''.join(f'  <li><b>{esc(t)}</b><span>{esc(s)}</span></li>\n' for t, s in d['three']) + '</ol>')
    if d.get('three_more'):
        b.append(f'<details class="fl-more">\n  <summary>{esc(d["three_more"]["q"])}</summary>\n  <p>{esc(d["three_more"]["a"])}</p>\n</details>')

    nxt = shows[0]
    b.append('<h2 id="flow">🕓 当日の流れ</h2>')
    flow = []
    for k, t, s in d['flow']:
        k = k.replace('{open}', nxt.get('open') or '開場').replace('{start}', nxt.get('start') or '開演')
        flow.append(f'  <li><i>{esc(k)}</i><b>{esc(t)}</b><span>{s}</span></li>\n')
    b.append('<ol class="fl-flow">\n' + ''.join(flow) + '</ol>')
    b.append('<h3 class="fl-h3">持ち物チェック</h3>')
    b.append(f'<ul class="fl-check" data-store="{slug}">\n' + ''.join(
        f'  <li><label><input type="checkbox" data-k="{k}"> {esc(t)}</label></li>\n' for k, t in d['check']) + '</ul>')
    b.append('<p class="note">チェックはこの端末にだけ保存されます。</p>')

    if d.get('seats'):
        b.append('<h2 id="seats">💺 席の種類</h2>')
        b.append(f'<p>{d["seats_lead"]}</p>')
        b.append('<div class="fl-seats">' + ''.join(f'<div><b>{esc(t)}</b><span>{esc(s)}</span></div>' for t, s in d['seats']) + '</div>')
        if d.get('seats_note'):
            b.append(f'<p class="note">{esc(d["seats_note"])}</p>')

    r = d['rules']
    b.append('<h2 id="rules">🙅 ライブ中の決まり</h2>')
    b.append('<div class="fl-rules">'
             f'<div class="fl-rule fl-rule--ng"><b>✕ 持ち込めない</b><ul>{"".join(f"<li>{esc(x)}</li>" for x in r["ng_items"])}</ul></div>'
             f'<div class="fl-rule fl-rule--ng"><b>✕ してはいけない</b><ul>{"".join(f"<li>{esc(x)}</li>" for x in r["ng_acts"])}</ul></div>'
             f'<div class="fl-rule fl-rule--ok"><b>◯ できること</b><ul>{"".join(f"<li>{x}</li>" for x in r["ok"])}</ul></div></div>')
    b.append(f'<p class="note">{r["note"]}</p>')

    p = d['penlight']
    # 色の一覧が公式にないとき（colors が空）は、光り方（modes）を並べる
    b.append(f'<h2 id="penlight">🔦 {esc(p["heading"])}</h2>' if p.get('heading') else f'<h2 id="penlight">🔦 ペンライト（{len(p["colors"])}色）</h2>' if p.get('colors') else '<h2 id="penlight">🔦 ペンライト</h2>')
    b.append(f'<p>{p["text"]}</p>')
    if p.get('colors'):
        b.append('<ol class="fl-colors">' + ''.join(f'<li style="--c:{c}">{esc(n)}</li>' for n, c in p['colors']) + '</ol>')
    elif p.get('modes'):
        b.append('<ul class="setl-top">' + ''.join(f'<li>{esc(x)}</li>' for x in p['modes']) + '</ul>')
    b.append(f'<p class="note">{p["note"]}</p>')

    m = d['members']
    b.append(f'<h3 class="fl-h3">メンバー{len(m["list"])}人</h3>')
    b.append('<ul class="fl-members">' + ''.join(
        (f'<li class="is-c" style="--c:{m["colors"][x]}">' if x in m.get('colors', {}) else '<li>') + esc(x)
        + (f'<small>{esc(m["birth"][x])}</small>' if x in m.get('birth', {}) else '') + '</li>' for x in m['list']) + '</ul>')
    b.append(f'<p class="note">{m["note"]}</p>')

    c = d['call']
    b.append('<h2 id="call">📣 コールと声出し・予習の動画</h2>')
    b.append(f'<p>{c["text"]}</p>')
    b.append(f'<div class="pf-quote"><p>{esc(c["memo"])}</p><footer>— 推しグルメ巡礼MAP 編集部のメモ</footer></div>')
    b.append('<div class="pf-videos">\n' + ''.join(
        f'  <figure><button type="button" class="yt" data-yt="{v}" aria-label="「{esc(t)}」のライブ映像を再生"><img src="https://i.ytimg.com/vi_webp/{v}/hqdefault.webp" alt="" width="480" height="360" loading="lazy" decoding="async"><span class="play"></span></button><figcaption><b>「{esc(t)}」</b>{esc(cap)}</figcaption></figure>\n'
        for v, t, cap in c['videos']) + '</div>')
    b.append(f'<p class="note">動画はすべて「{esc(c["channel"])}」のものです（タップすると再生します）。</p>')

    s = d['setlist']
    with_video = {t.replace('“', '"').replace('”', '"') for _, t, _ in c['videos']}
    b.append('<h2 id="setlist">🎵 定番曲（大手報道のセットリストから）</h2>')
    b.append(f'<p>{s["intro"]}</p>')
    b.append('<ol class="fl-tracks">\n' + ''.join(
        f'  <li><b>{esc(t)}</b>{"<a href=\"#call\">▶ 映像</a>" if t in with_video else ""}</li>\n' for t in s['top']) + '</ol>')
    if s.get('two'):
        b.append(f'<p>{esc(s["two"])}</p>')
    det = []
    for st in s['sets']:
        det.append(f'  <h3>{esc(st["title"])}</h3>')
        det += [f'  <p><b>{esc(k)}</b>：{esc(v)}</p>' for k, v in st['parts']]
        lab, url, n = st['src']
        det.append(f'  <p class="note">出典：{ext(url, esc(lab))}{"（" + esc(n) + "）" if n else ""}</p>')
    b.append(f'<details class="setl">\n  <summary>{len(s["sets"])}公演のセットリストを見る（曲名だけ・ネタバレ注意）</summary>\n' + '\n'.join(det) + '\n</details>')
    if d.get('tour_page'):
        b.append(f'<p>ドーム公演の日程・会場・宿をまとめた{d["tour_page"]}もあります。</p>')

    if d.get('past'):
        # 前回のライブはこんなライブ（大手報道で確かめた事実だけ。[題, 文, 出典名, URL]）
        b.append('<h2 id="past">🎬 前回のライブはこんなライブ</h2>')
        if d.get('past_lead'):
            b.append(f'<p>{d["past_lead"]}</p>')
        b.append('<div class="fl-goods">' + ''.join(f'<div><b>{esc(t)}</b><span>{esc(x)}（{ext(u, esc(lab))}）</span></div>' for t, x, lab, u in d['past']) + '</div>')
    if d.get('album'):
        al = d['album']
        live = set(al.get('live_songs') or [])
        b.append(f'<h2 id="album">🎧 予習するなら『{esc(al["title"])}』</h2>')
        b.append(f'<p>{al["text"]}</p>')
        b.append('<ol class="fl-tracks">\n' + ''.join(
            f'  <li><b>{esc(t)}</b>{"<small>ツアーで披露</small>" if t in live else ""}</li>\n' for t in al['tracks']) + '</ol>')
        b.append(f'<p class="note">{al["note"]}</p>')

    b.append('<h2 id="goods">🛍 グッズの買い方</h2>')
    b.append('<div class="fl-goods">' + ''.join(f'<div><b>{esc(t)}</b><span>{x}</span></div>' for t, x in d['goods']) + '</div>')
    if d.get('fc_note'):
        b.append(f'<p class="note">{d["fc_note"]}</p>')

    # 会場と泊まる場所（会場の細かい案内・近い宿の一覧は、参戦ガイド・会場のホテルのページにある。ここは入口だけにして同じ中身を繰り返さない）
    b.append('<h2 id="venue">🏟 会場と泊まる場所</h2>')
    b.append(f'<p id="stay">{d["stay_text"]}</p>')
    for sh in shows:
        key = sh['venue_key']
        vname = sh.get('venue_name') or venues[key]['name']
        vn = vnear.get(key) or {}
        hk, hj = vn.get('hk') or vname, vn.get('hj') or ''
        live = ('{% for p in site.posts %}{% if p.article_type == \'live\' and p.group == \'' + d['group'] + '\' and p.venue_key == \'' + key +
                '\' %}<a class="btn" href="{{ p.url }}">' + esc(name) + ' ' + esc(vname) + '公演 参戦ガイド（座席・アクセス・近い宿）</a>{% endif %}{% endfor %}')
        hotels = (f'<a class="btn" href="/guide/{key}/hotels/">{esc(vname)}の近くのホテル（最寄り駅ごと）</a>'
                  if os.path.exists(os.path.join(ROOT, '_guides', f'{key}-hotels.html')) else '')
        b.append(f'<div class="fl-venue" id="stay-{key}">\n  <p class="fl-venue__h"><b>{esc(vname)}</b><span>{jdate(sh["dates"])}</span></p>\n'
                 f'  <div class="btn-row">{live}{hotels}<a class="btn" href="/guide/{key}/">{esc(vname)} ライブ参戦ガイド</a></div>\n'
                 '  <div class="stay-in">\n    <p class="stay-in__h"><span aria-hidden="true">🛏</span> ' + esc(hk) + '周辺に泊まる<small class="stay-in__pr">PR</small></p>\n    <div class="btn-row">\n'
                 + (f'      {{% include affiliate-link.html url="https://www.jalan.net/uw/uwp2011/uww2011init.do?keyword={hj}" label="じゃらんで探す" class="btn btn--accent" service="jalan" %}}\n' if hj else '')
                 + f'      {{% include affiliate-link.html url="https://kw.travel.rakuten.co.jp/keyword/Search.do?charset=utf-8&f_query={urllib.parse.quote(hk)}" label="楽天トラベルで探す" class="btn" service="rakuten" %}}\n'
                 '    </div>\n  </div>\n</div>')
    b.append(f'{{% include live-list.html group="{d["group"]}" title="{esc(name)}のこれからの公演（参戦ガイド）" %}}')

    b.append(f'<h2 id="seichi">🍽 ライブの前後に、メンバーが行ったお店へ</h2>')
    b.append(f'<p>{esc(name)}のメンバーが番組やYouTubeで訪れたお店を、このサイトで{{{{ site.data.group_ix.{d["group"]}.n }}}}軒載せています。会場の近くのお店は、各公演の参戦ガイドの「会場の近くの{esc(name)}の聖地」にまとめています。</p>')
    # 会場ごとに、近くのグループの店3軒（3km以内が3軒未満なら10kmまで）
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import tour_article as TA
    S_, cards_ = J('data/shops.json'), J('_data/shop_cards.json')
    own = [x for x in S_ if d['group'] in (x.get('groups') or [x.get('group')]) and not x.get('closed') and x.get('lat') and x.get('lng')
           and x['id'] in cards_ and not x.get('location_unverified')]
    for sh in shows:
        v_ = venues[sh['venue_key']]
        ds_ = sorted(((TA.km((v_['lat'], v_['lng']), (x['lat'], x['lng'])), x) for x in own), key=lambda y: y[0])
        near = [y for y in ds_ if y[0] <= 3]
        r_ = 3
        if len(near) < 3:
            near, r_ = [y for y in ds_ if y[0] <= 10], 10
        if not near:
            continue
        b.append(f'<h3 class="fl-h3">{esc(sh.get("venue_name") or v_["name"])}の近く（{r_}km以内に{len(near)}軒）</h3>')
        b.append('<ul class="wrs">' + ''.join(
            f'<li class="wr">{{% include wr-open.html id="{x["id"]}" %}}<span class="wr__k">{TA.ym(x.get("visited_date"))}</span><b class="wr__name">{esc(x["name"])}</b>'
            f'<span class="wr__t">{esc(TA.row_text(x, km_, d["group"]))}</span>{{% include wr-close.html id="{x["id"]}" %}}</li>' for km_, x in near[:3]) + '</ul>')
    b.append(f'<div class="pf-cta">\n  <p>{esc(name)}の聖地を探す</p>\n  <span>メンバーが行ったお店を、地図やまとめ記事で。</span>\n'
             + (f'  <a class="btn" href="{d["matome_url"]}">{esc(name)}の聖地巡礼まとめ</a>\n' if d.get('matome_url') else '')
             + f'  <a class="btn" href="/shops/?g={d["group"]}&amp;view=map">地図で{esc(name)}のお店を見る</a>\n</div>')

    if d.get('official_links'):
        b.append('<h2 id="official">🔗 公式のリンク</h2>')
        b.append('<ul class="fl-links">' + ''.join(f'<li>{ext(u, "<b>" + esc(t) + "</b>")}<span>{esc(n)}</span></li>' for t, u, n in d['official_links']) + '</ul>')
    b.append(f'<p class="note">このページは{ckl}に、{esc(name)}公式サイト・公式ショップ・公式YouTubeと、大手報道のライブレポートで確かめた内容です。公演ごとの注意事項は変わることがあるので、行く前に公式の最新の案内を確かめてください。</p>')
    b.append('</div>')
    body = '\n\n'.join(b) + '\n'

    out = os.path.join(ROOT, '_guides', f'{slug}.html')
    old_date, old_body, old_lm = d['checked_at'], None, None
    if os.path.exists(out):
        t = open(out, encoding='utf-8').read()
        mm = re.search(r'^date: (\S+)', t, re.M)
        old_date = mm.group(1).strip("'\"") if mm else old_date
        ml = re.search(r'^last_modified_at: (\S+)', t, re.M)
        old_lm = ml.group(1).strip("'\"") if ml else None
        old_body = t.split('\n---\n', 1)[1] if '\n---\n' in t else None
    fm = {'title': d['title'], 'description': d['description'], 'date': old_date,
          'last_modified_at': old_lm if (old_body == body and old_lm) else TODAY,
          'guide_category': 'firstlive', 'group': d['group'], 'thumbnail': f'/assets/img/guide/{slug}.webp',
          'checked_at': d['checked_at'], 'pr': True,
          'sources': [{'label': l, 'url': u} for l, u in d['sources']],
          'summary': d['summary'], 'faq': [{'q': q, 'a': a} for q, a in d['faq']]}
    open(out, 'w', encoding='utf-8').write('---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + '---\n' + body)
    print(out)


if __name__ == '__main__':
    for g in sys.argv[1:]:
        build(g)
