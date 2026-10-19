"""
tour_article.py
ツアー×聖地巡礼の記事（_posts/）を、ツアーの公式データ（scripts/tour_data/<slug>.json）と data/shops.json から作る。
- 会場ごとに、そのグループのメンバーが行ったお店を会場から近い順に出す（3km以内。3軒に満たなければ10kmまで広げる。最大8軒）
- グループの店が近くにない会場は、会場の近くのほかの推しの店（_data/venue_nearby.json）を3軒出す
- 会場ごとに「泊まる」（じゃらん・楽天トラベル）、会場ガイド（_guides/<key>.html があるとき）、地図へのボタン
- ツアーの流れの図 assets/img/posts/<slug>/tour.svg（会場と日付）
- 日程・会場・公演数は tour_data の公式データだけから書く。店の評判・値段・営業時間は書かない

tour_data の形:
{
  "slug": "snowman-tour-2026", "group": "snowman",
  "tour": "ツアーの正式名", "official_url": "https://...", "total_shows": 20,
  "checked_at": "2026-10-19",
  "sources": [{"label": "…", "url": "…"}],
  "stops": [{"venue": "東京ドーム", "key": "tokyo-dome", "pref": "東京都", "dates": ["2026-11-01"]}]
}
key は _data/venues.json のキー。ないときは scripts/tour_data/venues_extra.json（{"会場名": {"lat":…, "lng":…, "pref": "…"}}）から座標を引く。
使い方: python scripts/tour_article.py <slug>
"""
import collections
import datetime
import json
import math
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "'Hiragino Sans','Noto Sans CJK JP','Noto Sans JP',sans-serif"
INK, INK2, LINE, PAPER = '#241F1A', '#6B6258', '#E2D9CC', '#F7F3EC'
TODAY = '2026-10-19'
NEAR_KM, FAR_KM, MAX_ROWS, MIN_ROWS = 3.0, 10.0, 8, 3


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def jslug(n):
    return re.sub(r'(?:[^\w]|_)+', '-', n).strip('-').lower()


def sjis(s):
    return urllib.parse.quote(s.encode('cp932', 'ignore'))


def jd(d):
    y, m, dd = d.split('-')
    w = '月火水木金土日'[datetime.date(int(y), int(m), int(dd)).weekday()]
    return f'{int(m)}月{int(dd)}日（{w}）'


def jd_short(d):
    y, m, dd = d.split('-')
    return f'{int(m)}/{int(dd)}'


def ym(d):
    return f'{d[:4]}.{int(d[5:7])}' if d and len(d) >= 7 else ''


def place(s):
    a = s.get('address') or ''
    m = re.match(r'(東京都|北海道|(?:京都|大阪)府|.{2,3}県)?(.+?[市区町村郡])(.*?)(?:\d|$)', a)
    if not m:
        return s.get('city') or s.get('prefecture') or ''
    city = (m.group(2) or '')
    town = re.sub(r'[一二三四五六七八九十０-９\d]+丁目.*$', '', m.group(3) or '').strip()
    return city + (' ' + town if town else '')


def row_text(s, dist_km, g):
    """行の文: 回（番組・動画）／メンバー／頼んだ物（場所）。評判は書かない"""
    bits = []
    prog = s.get('program') or s.get('source_video_channel') or ''
    title = s.get('source_video_title') or ''
    kind = s.get('visit_kind')
    if s.get('studio_only'):
        bits.append(f'『{prog}』のスタジオに料理が出たお店' if prog else 'スタジオに料理が出たお店')
    elif kind == 'drama':
        bits.append(f'ドラマ『{prog}』の撮影に使われたお店' if prog else 'ドラマの撮影に使われたお店')
    elif title and (kind == 'youtube' or s.get('youtube_id')):
        bits.append(f'「{title[:40]}{"…" if len(title) > 40 else ""}」')
    elif prog:
        bits.append(f'『{prog}』')
    mem = [m for m in (s.get('members') or []) if m]
    if mem and not s.get('studio_only'):
        bits.append('・'.join(mem[:4]) + ('ほか' if len(mem) > 4 else ''))
    items = [i.get('name', '') if isinstance(i, dict) else i for i in (s.get('ordered_items') or [])]
    items = [i for i in items if i][:2]
    if items and not s.get('studio_only'):
        bits.append('・'.join(items))
    if s.get('_gl'):
        bits.insert(0, s['_gl'])
    t = '／'.join(bits)
    d = f'{dist_km:.1f}km' if dist_km >= 1 else f'{int(round(dist_km * 1000, -1))}m'
    return f'{t}（{place(s)}・会場から約{d}）'


def tour_svg(spec, stops_info, color):
    """ツアーの流れの図: 会場を日付順に並べ、日付と近くの聖地の数を書く"""
    w, rowh, top = 420, 58, 66
    n = len(stops_info)
    h = top + rowh * n + 30
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="tt">',
         f'<title id="tt">{esc(spec["tour"])}の会場と日程</title>',
         f'<rect width="{w}" height="{h}" fill="{PAPER}"/>',
         f'<text x="20" y="30" font-family="{FONT}" font-size="15" font-weight="700" fill="{INK}">{esc(spec["tour"][:26])}{"…" if len(spec["tour"]) > 26 else ""}</text>',
         f'<text x="20" y="50" font-family="{FONT}" font-size="12" fill="{INK2}">会場と日程（公式発表・{spec["checked_at"][:4]}/{int(spec["checked_at"][5:7])}/{int(spec["checked_at"][8:10])}時点）と近くの聖地の数</text>',
         f'<line x1="44" y1="{top}" x2="44" y2="{top + rowh * (n - 1) + 20}" stroke="{color}" stroke-width="3" stroke-linecap="round"/>']
    for i, st in enumerate(stops_info):
        y = top + rowh * i + 20
        ds = st['dates']
        dtxt = '・'.join(jd_short(d) for d in ds[:6]) + ('…' if len(ds) > 6 else '')
        o.append(f'<circle cx="44" cy="{y}" r="9" fill="{color}" stroke="{PAPER}" stroke-width="3"/>')
        o.append(f'<text x="44" y="{y + 4}" text-anchor="middle" font-family="{FONT}" font-size="11" font-weight="700" fill="#fff">{i + 1}</text>')
        vn = st["venue"].split('（')[0]
        o.append(f'<text x="64" y="{y - 4}" font-family="{FONT}" font-size="14" font-weight="700" fill="{INK}">{esc(vn[:16])}</text>')
        o.append(f'<text x="64" y="{y + 14}" font-family="{FONT}" font-size="12" fill="{INK2}">{esc(st["pref"])}　{esc(dtxt)}</text>')
        k = st['own_n']
        lab = f'聖地 {k}軒' if k else '聖地 0軒'
        o.append(f'<rect x="{w - 92}" y="{y - 12}" width="74" height="24" rx="12" fill="{color if k else LINE}"/>')
        o.append(f'<text x="{w - 55}" y="{y + 4}" text-anchor="middle" font-family="{FONT}" font-size="12" font-weight="700" fill="{"#fff" if k else INK2}">{lab}</text>')
    o.append('</svg>')
    return '\n'.join(o), w, h


def main():
    slug = sys.argv[1]
    spec = J(f'scripts/tour_data/{slug}.json')
    g = spec['group']
    GS = spec.get('groups') or [g]
    S = J('data/shops.json')
    cards = J('_data/shop_cards.json')
    gix = J('_data/group_ix.json')
    venues = J('_data/venues.json')
    vnear = J('_data/venue_nearby.json')
    extra = J('scripts/tour_data/venues_extra.json') if os.path.exists(os.path.join(ROOT, 'scripts/tour_data/venues_extra.json')) else {}
    gl = '・'.join(gix[x]['l'] for x in GS) if len(GS) > 1 else gix[g]['l']
    color = gix[g]['c']
    own = [s for s in S if set(GS) & set(s.get('groups') or [s.get('group')]) and not s.get('closed')
           and s.get('lat') and s.get('lng') and s['id'] in cards]
    if len(GS) > 1:
        for s in own:
            s['_gl'] = '・'.join(gix[x]['l'] for x in GS if x in (s.get('groups') or [s.get('group')]))

    stops_info = []
    used = []
    for st in spec['stops']:
        key = st.get('key')
        if key and key in venues:
            v = venues[key]
            lat, lng, vname = v['lat'], v['lng'], v['name']
        else:
            v = extra.get(st['venue'])
            if not v:
                raise SystemExit('会場の座標がありません: ' + st['venue'])
            lat, lng, vname, key = v['lat'], v['lng'], st['venue'], None
        near = sorted(((km((lat, lng), (s['lat'], s['lng'])), s) for s in own), key=lambda x: x[0])
        rows = [(d, s) for d, s in near if d <= NEAR_KM]
        r = NEAR_KM
        if len(rows) < MIN_ROWS:
            rows = [(d, s) for d, s in near if d <= FAR_KM]
            r = FAR_KM
        rows = rows[:MAX_ROWS]
        others = []
        if not rows and key and key in vnear:
            others = [x['id'] for x in vnear[key]['ids'] if x['id'] in cards][:3]
        has_guide = bool(key) and os.path.exists(os.path.join(ROOT, '_guides', f'{key}.html'))
        hk = vnear[key]['hk'] if key and key in vnear else st['venue']
        hj = vnear[key]['hj'] if key and key in vnear else sjis(st['venue'])
        stops_info.append(dict(venue=vname, pref=st['pref'], dates=sorted(st['dates']), key=key, lat=lat, lng=lng,
                               rows=rows, r=r, others=others, has_guide=has_guide, hk=hk, hj=hj, own_n=len(rows)))
        used += [s['id'] for _, s in rows]
    ids = list(dict.fromkeys(used))
    all_dates = sorted(d for st in stops_info for d in st['dates'])
    n_shows = spec.get('total_shows')
    n_venues = len(stops_info)
    period = f'{jd(all_dates[0])[:-3]}〜{jd(all_dates[-1])[:-3]}' if all_dates else ''
    y0 = all_dates[0][:4] if all_dates else ''
    period_y = (f'{y0}年{period}' if all_dates and all_dates[0][:4] == all_dates[-1][:4]
                else f'{all_dates[0][:4]}年{jd(all_dates[0])[:-3]}〜{all_dates[-1][:4]}年{jd(all_dates[-1])[:-3]}') if all_dates else ''
    with_own = [st for st in stops_info if st['rows']]

    # 図
    svg, sw, sh = tour_svg(spec, stops_info, color)
    d = os.path.join(ROOT, 'assets/img/posts', slug)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'tour.svg'), 'w', encoding='utf-8').write(svg)

    # 表紙の写真: 近くの店で写真のあるもの
    cover = [i for i in ids if cards[i].get('v') or (cards[i].get('t') and cards[i].get('sp') != 1)][:3]
    vid = next((cards[i]['v'] for i in ids if cards[i].get('v')), '')

    title = (f'『{spec["tour"]}』×聖地巡礼' if spec['tour'].startswith(gl) else f'{gl}『{spec["tour"]}』×聖地巡礼') + '｜会場ごとの近くの推しグルメと泊まる場所'
    venue_names = '・'.join(st['venue'] for st in stops_info)
    desc = (f'{gl}のツアー『{spec["tour"]}』（{period_y}・{n_venues}会場{("・" + str(n_shows) + "公演") if n_shows else ""}）の会場ごとに、'
            f'{gl}のメンバーが番組やYouTubeで訪れたお店を会場から近い順に{len(ids)}軒まとめました。'
            f'会場は{venue_names}。会場の近くに泊まる宿の探し方と、各会場のライブ参戦ガイドもあわせて。')
    members = sorted({m for s in own for m in (s.get('members') or []) if m}, key=lambda m: -sum(m in (s.get('members') or []) for s in own))[:8]
    tags = [gl, spec['tour'], 'ツアー', '遠征', '聖地巡礼', 'ロケ地'] + [st['venue'] for st in stops_info] + members[:5]

    faq = [
        {'q': f'{gl}の『{spec["tour"]}』の会場と日程は？',
         'a': f'{period_y}に{n_venues}会場{("・" + str(n_shows) + "公演") if n_shows else ""}です。' +
              '、'.join(f'{st["venue"]}（{"・".join(jd(x)[:-3] for x in st["dates"][:4])}{"ほか" if len(st["dates"]) > 4 else ""}）' for st in stops_info) +
              f'。日程は{spec["checked_at"][:4]}年{int(spec["checked_at"][5:7])}月{int(spec["checked_at"][8:10])}日時点の公式発表で、変わることがあります。最新は公式サイトで確かめてください。'},
    ]
    for st in with_own[:3]:
        top = st['rows'][:3]
        faq.append({'q': f'{st["venue"]}の近くで{gl}の聖地はありますか？',
                    'a': f'会場から{st["r"]:.0f}km以内に{len(st["rows"])}軒{"以上" if len(st["rows"]) >= MAX_ROWS else ""}あります。' +
                         '、'.join(f'{s["name"]}（約{dd:.1f}km）' for dd, s in top) + 'などです。会場からの距離は直線距離です。'})
    no_own = [st for st in stops_info if not st['rows']]
    if no_own:
        faq.append({'q': f'{"・".join(st["venue"] for st in no_own[:4])}の近くに{gl}の聖地はありますか？',
                    'a': f'{spec["checked_at"][:4]}年{int(spec["checked_at"][5:7])}月時点で、会場から10km以内に{gl}のメンバーが行ったお店は登録されていません。'
                         f'ほかの推しが訪れたお店は会場ガイドと「お店を探す」の地図で見られます。'})
    faq.append({'q': '会場の近くに泊まる宿はどう探せばいいですか？',
                'a': 'この記事の会場ごとの「泊まる」から、じゃらん・楽天トラベルで会場名を検索できます。遠征の交通や持ち物は「ライブ遠征の準備チェックリスト」にまとめています。'})

    fm = {
        'layout': 'post', 'title': title, 'date': TODAY, 'last_modified_at': TODAY, 'checked_at': spec['checked_at'],
        'checked_label': 'ツアーの日程と会場', 'description': desc, 'group': g if len(GS) == 1 else None, 'genre': 'まとめ', 'article_type': 'tour',
        'tags': tags, 'sources': spec['sources'], 'shop_ids': ids, 'faq': faq, 'pr': True,
    }
    if vid:
        fm['thumbnail_video_id'] = vid
    if len(cover) >= 3:
        fm.update(techo=True, cover_ids=','.join(cover), cover_title=f'{gl} ツアー巡礼帳', cover_sub=f'{spec["tour"]}　{n_venues}会場の近くの聖地')
    fm['summary'] = [
        f'『{spec["tour"]}』は{period_y}、{n_venues}会場{("・" + str(n_shows) + "公演") if n_shows else ""}（{spec["checked_at"][:4]}年{int(spec["checked_at"][5:7])}月{int(spec["checked_at"][8:10])}日時点の公式発表）',
        f'会場の近くに{gl}のメンバーが行ったお店があるのは{len(with_own)}会場。あわせて{len(ids)}軒を会場から近い順に載せています',
        '会場ごとに、宿の探し方（じゃらん・楽天トラベル）と、持ち込み・座席が分かるライブ参戦ガイドへの案内つき',
    ]
    fm = {k: v for k, v in fm.items() if v is not None}
    import yaml
    fm_txt = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)

    # 本文
    b = [f'<div class="pf{" pf--techo" if fm.get("techo") else ""}" style="--pc:{color}">', '']
    b.append(f'<p><strong>{gl}</strong>のツアー『{spec["tour"]}』は、{period_y}に{n_venues}会場で{("全" + str(n_shows) + "公演が") if n_shows else ""}行われます'
             f'（<a href="{esc(spec["official_url"])}" target="_blank" rel="noopener">公式の公演情報</a>・{spec["checked_at"][:4]}年{int(spec["checked_at"][5:7])}月{int(spec["checked_at"][8:10])}日時点）。'
             f'遠征の日は、会場の近くにある推しの聖地を巡るチャンスです。</p>')
    b.append(f'<p>この記事では、会場ごとに<strong>{gl}のメンバーが番組やYouTubeで訪れたお店</strong>を会場から近い順に並べました（{len(ids)}軒）。'
             f'お店ごとに、どの回で誰が行ったか・頼んだ物・会場からの直線距離が分かります。会場の近くに泊まる宿の探し方と、持ち込みや座席が分かるライブ参戦ガイドもあわせてどうぞ。</p>')
    b.append('<div class="cnav">\n<p class="cnav__h">会場で選ぶ</p>\n<div class="cnav__list">' +
             ''.join(f'<a href="#v{i + 1}"><span>{esc(st["venue"])}<small>{"・".join(jd_short(x) for x in st["dates"][:3])}{"…" if len(st["dates"]) > 3 else ""}'
                     f'{"／聖地" + str(len(st["rows"])) + "軒" if st["rows"] else ""}</small></span></a>' for i, st in enumerate(stops_info)) +
             '</div>\n</div>')
    b.append('<h2>日程と会場</h2>')
    b.append(f'<figure class="fig"><img src="/assets/img/posts/{slug}/tour.svg" alt="{esc(spec["tour"])}の会場を日付順に並べた図。' +
             '、'.join(f'{st["venue"]}（{"・".join(jd_short(x) for x in st["dates"])}）' for st in stops_info) +
             f'" width="{sw}" height="{sh}" loading="lazy" decoding="async"><figcaption>会場と日程は公式の公演情報（{spec["checked_at"][:4]}年{int(spec["checked_at"][5:7])}月{int(spec["checked_at"][8:10])}日時点）。右の札は、会場から{NEAR_KM:.0f}km（少ない会場は{FAR_KM:.0f}km）以内にある{gl}の聖地の数</figcaption></figure>')
    b.append('<ul>\n' + ''.join(f'  <li><a href="#v{i + 1}"><strong>{esc(st["venue"])}</strong></a>（{esc(st["pref"])}）：{"、".join(jd(x) for x in st["dates"]) or "未定"}</li>\n' for i, st in enumerate(stops_info)) + '</ul>')
    if spec.get('note'):
        b.append(f'<p class="note">{esc(spec["note"])}</p>')
    b.append(f'<p class="note">日程は変わることがあります。最新の公演情報は<a href="{esc(spec["official_url"])}" target="_blank" rel="noopener">公式サイト</a>で確かめてください。チケットの申し込み方法や値段はこの記事では扱いません。</p>')

    for i, st in enumerate(stops_info):
        b.append(f'<h2 id="v{i + 1}">{esc(st["venue"])}（{"・".join(jd(x)[:-3] for x in st["dates"][:4])}{"ほか" if len(st["dates"]) > 4 else ""}）の近くの聖地</h2>')
        if st['rows']:
            b.append(f'<p>会場から{st["r"]:.0f}km以内にある{gl}のメンバーが行ったお店を、近い順に{len(st["rows"])}軒。距離は会場からの直線距離です。</p>')
            b.append('<ul class="wrs">')
            for dd, s in st['rows']:
                b.append(f'  <li class="wr">{{% include wr-open.html id="{s["id"]}" %}}<span class="wr__k">{ym(s.get("visited_date"))}</span><b class="wr__name">{esc(s["name"])}</b>'
                         f'<span class="wr__t">{esc(row_text(s, dd, g))}</span>{{% include wr-close.html id="{s["id"]}" %}}</li>')
            b.append('</ul>')
        else:
            b.append(f'<p>{spec["checked_at"][:4]}年{int(spec["checked_at"][5:7])}月時点で、会場から{FAR_KM:.0f}km以内に{gl}のメンバーが行ったお店は登録されていません。'
                     + ('会場の近くにある、ほかの推しの聖地はこちらです。' if st['others'] else '') + '</p>')
            if st['others']:
                b.append('<div class="ensei__shops">' + ''.join(f'{{% include mini.html id="{x}" m={vnear[st["key"]]["ids"][[y["id"] for y in vnear[st["key"]]["ids"]].index(x)]["m"]} from="会場から" %}}' for x in st['others']) + '</div>')
        btns = []
        if st['has_guide']:
            btns.append(f'<a class="btn" href="/guide/{st["key"]}/">{esc(st["venue"])}のライブ参戦ガイド</a>')
        btns.append(f'<a class="btn" href="/shops/?near={st["lat"]},{st["lng"]}&amp;nl={urllib.parse.quote(st["venue"])}">地図で会場の近くのお店</a>')
        b.append('<div class="btn-row">' + ''.join(btns) + '</div>')
        b.append(f'<div class="stay-in">\n  <p class="stay-in__h"><span aria-hidden="true">🛏</span> {esc(st["venue"])}周辺に泊まる<small class="stay-in__pr">PR</small></p>\n  <div class="btn-row">\n'
                 f'    {{% include affiliate-link.html url="https://www.jalan.net/uw/uwp2011/uww2011init.do?keyword={st["hj"]}" label="じゃらんで探す" class="btn btn--accent" service="jalan" %}}\n'
                 f'    {{% include affiliate-link.html url="https://kw.travel.rakuten.co.jp/keyword/Search.do?charset=utf-8&f_query={urllib.parse.quote(st["hk"])}" label="楽天トラベルで探す" class="btn" service="rakuten" %}}\n  </div>\n</div>')

    b.append('<h2>遠征の準備</h2>')
    b.append('<ul>\n  <li><a href="/guide/live-ensei-checklist/">ライブ遠征の準備チェックリスト</a>：持ち物・宿・当日の動き方</li>\n'
             '  <li><a href="/guide/live-ensei-transport/">ライブ遠征の交通手段ガイド</a>：新幹線・飛行機・高速バスの使い分け</li>\n'
             '  <li><a href="/ensei/">ライブ遠征×聖地巡礼</a>：全国28会場の近くの聖地と宿</li>\n</ul>')
    if len(GS) > 1:
        b.append('<div class="btn-row">' + ''.join(f'<a class="btn" href="/shops/?g={x}&amp;view=map">地図で{gix[x]["l"]}のお店を見る</a>' for x in GS) + '</div>')
        b.append('<p>' + '、'.join(f'<a href="{{{{ site.data.group_ix.{x}.u }}}}">{gix[x]["l"]}のお店一覧</a>' for x in GS) + 'もどうぞ。</p>')
    else:
      b.append(f'<div class="pf-cta">\n  <p>{gl}のお店を、地図でぜんぶ見る</p>\n  <span>この記事の{len(ids)}軒を含む{gl}の聖地を地図で探せます。行きたいお店は保存して、遠征の計画に。</span>\n'
             f'  <a class="btn" href="/shops/?g={g}&amp;view=map">地図で{gl}のお店を見る</a>\n</div>')
      b.append(f'<p><a href="{{{{ site.data.group_ix.{g}.u }}}}">{gl}のお店一覧（グループのページ）</a>と、'
             f'{gl}の聖地をぜんぶ載せたまとめ記事もどうぞ。</p>')
    b.append(f'<p class="note">お店の情報は、各お店の出典（番組・YouTube・ファンのロケ地ブログ）をもとにしています。日付はYouTubeの回は動画の公開年月、番組は放送年月です。'
             f'会場からの距離は直線距離で、歩く距離とは違います。営業日・営業時間は各お店の公式情報で確かめてください。</p>')
    b.append('</div>')
    out = os.path.join(ROOT, '_posts', f'{TODAY}-{slug}.md')
    open(out, 'w', encoding='utf-8').write('---\n' + fm_txt + '---\n' + '\n\n'.join(b) + '\n')
    print(out, f'会場{n_venues} 店{len(ids)} 聖地あり会場{len(with_own)}')


if __name__ == '__main__':
    main()
