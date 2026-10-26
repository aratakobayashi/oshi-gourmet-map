"""
live_article.py
グループ×会場の「公演の参戦ガイド」記事（_posts/、article_type: live）を作る。
「イコラブ バンテリンドーム」のように「グループ名＋会場名」で探す人に向けた1公演（同じ会場の連続日）＝1記事。

- 日程・会場・時刻・公演名は scripts/live_data/<slug>.json の公式データだけから書く（終わった公演・未発表は作らない）
- 行き方・座席・持ち込み・当日の準備は会場データ scripts/venue_data/<key>.json と会場ガイドの図（assets/img/guide/<key>/）
- 近くの聖地: そのグループのメンバーが行った店を会場から近い順（3km、少なければ10km）。無ければ同じ都道府県のグループの店、
  それも無ければ会場の近くのほかの推しの店（_data/venue_nearby.json）
- 泊まる（じゃらん・楽天トラベル）を記事の上と「泊まる」の章に
- 値段・チケットの申し込み・セットリスト・体験談は書かない

live_data の形:
{
  "slug": "equal-love-vantelin-dome-nagoya-2026", "group": "equal_love",
  "tour": "公演名", "official_url": "https://…", "checked_at": "2026-10-26",
  "sources": [{"label": "…", "url": "…"}],
  "venue_key": "vantelin-dome-nagoya", "dates": ["2026-12-05"], "times": {"2026-12-05": "開場16:00／開演17:30"},
  "public_note": "（任意）記事に載せる公式の注意。調べたときのメモ（note）は記事に出さない"
}
使い方: python scripts/live_article.py <slug> [<slug> …] / --all（scripts/live_data の全部）
"""
import datetime
import glob
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tour_article as T  # noqa: E402

ROOT = T.ROOT
TODAY = datetime.date.today().isoformat()
NEAR_KM, FAR_KM, MAX_ROWS, MIN_ROWS, PREF_ROWS = 3.0, 10.0, 8, 3, 6
WEEK = '月火水木金土日'
NEWS = ('oricon.co.jp', 'mdpr.jp', 'thefirsttimes.jp', 'realsound.jp', 'natalie.mu', 'modelpress', 'billboard-japan', 'musicman', 'barks.jp', 'daily.co.jp', 'sponichi', 'nikkansports', 'hochi')
# 検索でよく使われる呼び名（題名とタグに足す）
AKA = {'equal_love': 'イコラブ', 'notme': 'ノイミー', 'neajoy': 'ニアジョイ', 'kismai': 'キスマイ', 'kingprince': 'キンプリ',
       'sixtones': 'ストーンズ', 'travisjapan': 'トラジャ', 'hihijets': 'ハイハイ',
       'kanjani': 'エイト', 'momoclo': 'ももクロ', 'ebichu': 'エビ中',
       'tokisen': '超とき宣', 'fruitszipper': 'ふるっぱー', 'bokuao': 'ぼくあお',
       'kpop_straykids': 'スキズ', 'kpop_seventeen': 'セブチ', 'kpop_lesserafim': 'ルセラ', 'kpop_andteam': 'エンティーム'}


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def dlabel(ds):
    """2026年12月5日（土）・6日（日） / 年をまたぐときは年を両方に"""
    ds = sorted(ds)
    out = []
    for i, d in enumerate(ds):
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        w = WEEK[datetime.date(y, m, dd).weekday()]
        if i == 0:
            out.append(f'{y}年{m}月{dd}日（{w}）')
        elif d[:7] == ds[i - 1][:7]:
            out.append(f'{dd}日（{w}）')
        elif d[:4] == ds[i - 1][:4]:
            out.append(f'{m}月{dd}日（{w}）')
        else:
            out.append(f'{y}年{m}月{dd}日（{w}）')
    return '・'.join(out)


def drange(ds):
    """題名用: 2026年12月5日 / 2026年11月26日〜29日 / 2026年12月31日〜2027年1月1日"""
    a, z = sorted(ds)[0], sorted(ds)[-1]
    f = lambda d: f'{int(d[5:7])}月{int(d[8:10])}日'
    if a == z:
        return f'{a[:4]}年{f(a)}'
    if a[:4] != z[:4]:
        return f'{a[:4]}年{f(a)}〜{z[:4]}年{f(z)}'
    if a[:7] == z[:7]:
        return f'{a[:4]}年{f(a)}〜{int(z[8:10])}日' if len(ds) > 2 else f'{a[:4]}年{f(a)}・{int(z[8:10])}日'
    return f'{a[:4]}年{f(a)}〜{f(z)}' if len(ds) > 2 else f'{a[:4]}年{f(a)}・{f(z)}'


def dshort(ds):
    ds = sorted(ds)
    return '・'.join(f'{int(d[5:7])}/{int(d[8:10])}' for d in ds)


def svg_size(p):
    t = open(os.path.join(ROOT, p), encoding='utf-8').read(600)
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', t)
    return (int(float(m.group(1))), int(float(m.group(2)))) if m else (600, 600)


def nobr(s):
    return re.sub(r'<br\s*/?>', '', s or '')


def guide_sources(key):
    """会場ガイドの front matter の sources（会場の公式ページ）"""
    p = os.path.join(ROOT, '_guides', f'{key}.html')
    if not os.path.exists(p):
        return []
    import yaml
    fm = yaml.safe_load(open(p, encoding='utf-8').read().split('---')[1])
    return [{'label': x['label'], 'url': x['url']} for x in (fm.get('sources') or [])]


def old_date(slug):
    """作り直すときは最初の公開日をそのまま使う（URLを変えない）"""
    old = sorted(glob.glob(os.path.join(ROOT, '_posts', f'*-{slug}.md')))
    return os.path.basename(old[0])[:10] if old else None


def stay_box(name, hk, hj, top=False):
    return (f'<div class="stay-in{" stay-in--top" if top else ""}">\n  <p class="stay-in__h"><span aria-hidden="true">🛏</span> {T.esc(name)}周辺に泊まる<small class="stay-in__pr">PR</small>'
            + ('<a class="stay-in__more" href="#stay">宿の選び方 ↓</a>' if top else '') + '</p>\n  <div class="btn-row">\n'
            f'    {{% include affiliate-link.html url="https://www.jalan.net/uw/uwp2011/uww2011init.do?keyword={hj}" label="じゃらんで探す" class="btn btn--accent" service="jalan" %}}\n'
            f'    {{% include affiliate-link.html url="https://kw.travel.rakuten.co.jp/keyword/Search.do?charset=utf-8&f_query={urllib.parse.quote(hk)}" label="楽天トラベルで探す" class="btn" service="rakuten" %}}\n'
            '  </div>\n</div>')


def build(slug, ctx):
    spec = J(f'scripts/live_data/{slug}.json')
    S, cards, gix, venues, vnear = ctx['S'], ctx['cards'], ctx['gix'], ctx['venues'], ctx['vnear']
    g = spec['group']
    gl, color = gix[g]['l'], gix[g]['c']
    key = spec['venue_key']
    v = venues[key]
    vd = J(f'scripts/venue_data/{key}.json')
    vname = v['name']
    lat, lng = v['lat'], v['lng']
    dates = sorted(spec['dates'])
    if dates[-1] < TODAY:
        print(slug, '終わった公演なので作らない')
        return None
    times = spec.get('times') or {}
    dl = dlabel(dates)
    ck = spec['checked_at']
    ckl = f'{ck[:4]}年{int(ck[5:7])}月{int(ck[8:10])}日'
    tour = spec['tour']
    # 公式ページが読めず報道で確かめた公演は、リンクの文言を「発表を伝える記事」に
    news = any(x in spec['official_url'] for x in NEWS)
    olink = '発表を伝える記事' if news else '公式の公演情報'
    hk, hj = vnear[key]['hk'], vnear[key]['hj']
    has_guide = os.path.exists(os.path.join(ROOT, '_guides', f'{key}.html'))
    vpref = spec.get('pref') or ''

    # 近くの聖地
    own = [s for s in S if g in (s.get('groups') or [s.get('group')]) and not s.get('closed')
           and s.get('lat') and s.get('lng') and s['id'] in cards and not s.get('location_unverified')]
    near = sorted(((T.km((lat, lng), (s['lat'], s['lng'])), s) for s in own), key=lambda x: x[0])
    rows = [(d, s) for d, s in near if d <= NEAR_KM]
    r = NEAR_KM
    if len(rows) < MIN_ROWS:
        rows = [(d, s) for d, s in near if d <= FAR_KM]
        r = FAR_KM
    rows = rows[:MAX_ROWS]
    if not vpref:
        vpref = next((x.get('pref') for x in [spec] if x.get('pref')), '') or vd.get('pref', '')
    pref_rows = []
    if not rows and vpref:
        pref_rows = [(d, s) for d, s in near if s.get('prefecture') == vpref][:PREF_ROWS]
    others = [x for x in vnear[key]['ids'] if x['id'] in cards and x['id'] not in {s['id'] for _, s in rows}][:4]
    ids = [s['id'] for _, s in rows + pref_rows]

    # 図（会場ガイドのもの）
    figs = {}
    for f in ('access', 'seats', 'rules', 'prepare'):
        p = f'assets/img/guide/{key}/{f}.svg'
        if os.path.exists(os.path.join(ROOT, p)):
            figs[f] = (p, *svg_size(p))

    st = vd.get('stations') or []
    st0 = st[0] if st else None
    rules = [nobr(x['label']) for x in (vd.get('rules') or {}).get('items', [])]
    prep = (vd.get('prepare') or {}).get('items', [])
    tiers = (vd.get('seats') or {}).get('tiers', [])

    gl_t = f'{gl}（{AKA[g]}）' if g in AKA else gl
    title = f'{gl_t} {vname}公演 参戦ガイド（{drange(dates)}）｜行き方・座席・持ち込み・泊まる・近くの聖地'
    tname = f'『{tour}』' if tour.startswith(gl) else f'{gl}『{tour}』'
    shrine = (f'会場から{r:.0f}km以内に{gl}のメンバーが行ったお店が{len(rows)}軒' if rows else
              (f'{vpref}にある{gl}の聖地{len(pref_rows)}軒' if pref_rows else '会場の近くのほかの推しの聖地'))
    desc = (f'{tname}の{vname}公演（{dl}）に行く人へ。最寄り駅と行き方、座席のつくり、持ち込めないもの、当日の準備、'
            f'会場の近くに泊まる宿の探し方、{shrine}をまとめました。日程は{ckl}時点の公式発表です。')
    summary = [f'{tname}の{vname}公演は{dl}（{ckl}時点の公式発表）']
    if st0:
        summary.append(f'最寄り駅は{st0["name"]}（{st0["exit"]}）' + (f'。{st[1]["name"]}からは{st[1]["exit"]}' if len(st) > 1 else ''))
    if rules:
        summary.append('会場のルールで持ち込めないもの: ' + '、'.join(rules[:4]) + '（公演ごとの案内も確かめる）')
    summary.append(shrine + ('。会場からの近さ順に載せています' if rows else ''))

    faq = [{'q': f'{gl}の{vname}公演はいつですか？',
            'a': f'{dl}です（{tour}）。' + ''.join(f'{int(d[5:7])}月{int(d[8:10])}日は{times[d]}。' for d in dates if times.get(d)) +
                 f'{ckl}時点の公式発表で、変わることがあります。最新は{gl}の公式サイトで確かめてください。'}]
    if st0:
        faq.append({'q': f'{vname}の最寄り駅はどこですか？',
                    'a': f'{st0["name"]}です（{st0["exit"]}）。' + ''.join(f'{x["name"]}からは{x["exit"]}。' for x in st[1:3])})
    if rules:
        faq.append({'q': f'{vname}に持ち込めないものは？',
                    'a': '会場のルールで、' + '、'.join(rules) + 'は持ち込めません。うちわ・ペンライト・双眼鏡などの扱いは公演ごとに主催者が決めるので、' + gl + 'の公式の案内で確かめてください。'})
    if rows:
        faq.append({'q': f'{vname}の近くに{gl}の聖地はありますか？',
                    'a': f'会場から{r:.0f}km以内に{len(rows)}軒あります。' + '、'.join(f'{s["name"]}（約{d:.1f}km）' for d, s in rows[:3]) + 'などです。距離は直線距離です。'})
    elif pref_rows:
        faq.append({'q': f'{vname}の近くに{gl}の聖地はありますか？',
                    'a': f'{ckl[:-3]}時点で会場から{FAR_KM:.0f}km以内にはありませんが、{vpref}には' + '、'.join(s['name'] for _, s in pref_rows[:3]) + 'などがあります。'})
    faq.append({'q': '会場の近くに泊まる宿はどう探せばいいですか？',
                'a': f'この記事の「{vname}周辺に泊まる」から、じゃらん・楽天トラベルで会場の近くの宿を検索できます。終演後の駅は混み合うので、移動の少ない宿を早めに探しておくと安心です。'})

    fm = {
        'layout': 'post', 'title': title, 'date': spec.get('date') or old_date(slug) or TODAY, 'last_modified_at': TODAY,
        'checked_at': ck, 'checked_label': '公演の日程と会場のルール', 'description': desc, 'group': g,
        'genre': 'ライブ', 'article_type': 'live', 'venue_key': key, 'live_dates': dates, 'live_end': dates[-1],
        'tags': [gl] + ([AKA[g]] if g in AKA else []) + [tour, vname, 'ライブ', '参戦', 'アクセス', '遠征', '聖地巡礼'],
        'sources': spec['sources'] + guide_sources(key)[:3],
        'shop_ids': ids, 'faq': faq, 'pr': True, 'summary': summary,
    }
    if has_guide:
        fm['thumbnail'] = f'/assets/img/guide/{key}.webp'
    import yaml
    fm_txt = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)

    b = [f'<div class="pf" style="--pc:{color}">', '']
    b.append(f'{{% if site.time | date: "%Y-%m-%d" > page.live_end %}}<p class="notice">この公演は終わりました。{gl}のこれからの公演は'
             f'<a href="{T.esc(spec["official_url"])}" target="_blank" rel="noopener">公式サイト</a>で確かめてください。</p>{{% endif %}}')
    b.append(f'<p><strong>{gl}</strong>『{T.esc(tour)}』の<strong>{T.esc(vname)}</strong>公演は、<strong>{dl}</strong>です'
             f'（<a href="{T.esc(spec["official_url"])}" target="_blank" rel="noopener">{olink}</a>・{ckl}時点）。'
             f'この記事では、{T.esc(vname)}への行き方・座席のつくり・持ち込めないもの・当日の準備と、会場の近くに泊まる宿の探し方、'
             f'{gl}のメンバーが番組やYouTubeで訪れたお店をまとめました。</p>')
    b.append(stay_box(vname, hk, hj, top=True))

    b.append('<h2 id="date">公演の日程</h2>')
    b.append('<ul class="live-dates">\n' + ''.join(
        f'  <li><b>{dlabel([d])}</b>{"<span>" + T.esc(times[d]) + "</span>" if times.get(d) else ""}</li>\n' for d in dates) + '</ul>')
    b.append(f'<p>会場：<strong>{T.esc(vname)}</strong>（{T.esc(vpref)}）。公演名：{T.esc(tour)}。</p>')
    if not any(times.get(d) for d in dates):
        b.append(f'<p class="note">開場・開演の時刻は、{ckl}時点ではまだ発表されていません。</p>')
    if spec.get('public_note'):
        b.append(f'<p class="note">{T.esc(spec["public_note"])}</p>')
    b.append(f'<p class="note">日程・時刻は{ckl}時点の<a href="{T.esc(spec["official_url"])}" target="_blank" rel="noopener">{"発表" if news else "公式発表"}</a>です。変わることがあるので、行く前に公式サイトで確かめてください。チケットの申し込みや値段はこの記事では扱いません。</p>')

    b.append('<h2 id="access">会場への行き方</h2>')
    if st:
        b.append('<ul>\n' + ''.join(f'  <li><strong>{T.esc(x["name"])}</strong>：{T.esc(x["exit"])}</li>\n' for x in st) + '</ul>')
    if 'access' in figs:
        p, w, h = figs['access']
        b.append(f'<figure class="fig"><img src="/{p}" alt="{T.esc(vname)}と最寄り駅の位置関係の図。' + '、'.join(f'{x["name"]}（{x["exit"]}）' for x in st) +
                 f'" width="{w}" height="{h}" loading="lazy" decoding="async"><figcaption>{T.esc(vname)}公式サイトのアクセス案内をもとに作図</figcaption></figure>')
    for n in vd.get('access_note') or []:
        b.append(f'<p class="note">{T.esc(n)}</p>')

    if tiers:
        b.append('<h2 id="seats">座席のつくり</h2>')
        if 'seats' in figs:
            p, w, h = figs['seats']
            b.append(f'<figure class="fig"><img src="/{p}" alt="{T.esc(vname)}の座席のつくりの図。' + '、'.join(x['label'] for x in tiers) +
                     f'" width="{w}" height="{h}" loading="lazy" decoding="async"><figcaption>会場の公式情報をもとに作図。ステージの位置や客席の並びは公演ごとに変わります</figcaption></figure>')
        b.append('<ul>\n' + ''.join(f'  <li><strong>{T.esc(x["label"])}</strong>：{T.esc(x.get("desc", ""))}</li>\n' for x in tiers) + '</ul>')
        b.append(f'<p class="note">{T.esc((vd.get("seats") or {}).get("note") or "席の並びは公演ごとに主催者が決めます")}。{gl}の公演の席は、チケットに書かれたゲート・席番号で確かめてください。</p>')

    if rules or prep:
        b.append('<h2 id="rules">持ち込めないもの・当日の準備</h2>')
        if rules:
            if 'rules' in figs:
                p, w, h = figs['rules']
                b.append(f'<figure class="fig"><img src="/{p}" alt="{T.esc(vname)}に持ち込めないものの図。' + '、'.join(rules) +
                         f'" width="{w}" height="{h}" loading="lazy" decoding="async"><figcaption>会場の公式サイトの案内より</figcaption></figure>')
            b.append('<p>会場のルールで持ち込めないもの：' + '、'.join(T.esc(x) for x in rules) + f'。グッズの扱い・撮影・うちわやペンライトの決まりは公演ごとに違うので、{gl}の公式の注意事項で確かめてください。</p>')
        if prep:
            b.append('<ul>\n' + ''.join(f'  <li><strong>{T.esc(x["title"])}</strong>：{T.esc("。".join(x.get("lines", [])))}</li>\n' for x in prep) + '</ul>')
            if (vd.get('prepare') or {}).get('source'):
                b.append(f'<p class="note">{T.esc(vd["prepare"]["source"])}</p>')
    if has_guide:
        b.append(f'<div class="btn-row"><a class="btn" href="/guide/{key}/">{T.esc(vname)}のライブ参戦ガイドをくわしく</a></div>')

    b.append(f'<h2 id="seichi">会場の近くの{gl}の聖地</h2>')
    if rows:
        b.append(f'<p>会場から{r:.0f}km以内にある、{gl}のメンバーが行ったお店を近い順に{len(rows)}軒。開演前や翌日に寄れる距離か、直線距離で確かめられます。</p>')
        lst = rows
    elif pref_rows:
        b.append(f'<p>{ckl[:-3]}時点で、会場から{FAR_KM:.0f}km以内に{gl}のメンバーが行ったお店は登録されていません。'
                 f'遠征のついでに寄れる、{T.esc(vpref)}の{gl}の聖地を会場から近い順に載せます。</p>')
        lst = pref_rows
    else:
        b.append(f'<p>{ckl[:-3]}時点で、{T.esc(vpref)}に{gl}のメンバーが行ったお店は登録されていません。</p>')
        lst = []
    if lst:
        b.append('<ul class="wrs">')
        for d, s in lst:
            b.append(f'  <li class="wr">{{% include wr-open.html id="{s["id"]}" %}}<span class="wr__k">{T.ym(s.get("visited_date"))}</span><b class="wr__name">{T.esc(s["name"])}</b>'
                     f'<span class="wr__t">{T.esc(T.row_text(s, d, g))}</span>{{% include wr-close.html id="{s["id"]}" %}}</li>')
        b.append('</ul>')
    if others:
        b.append(f'<p>会場の近くにある、ほかの推しの聖地も。</p>')
        b.append('<div class="ensei__shops">' + ''.join(f'{{% include mini.html id="{x["id"]}" m={x["m"]} from="会場から" %}}' for x in others) + '</div>')
    b.append(f'<div class="btn-row"><a class="btn" href="/shops/?near={lat},{lng}&amp;nl={urllib.parse.quote(vname)}">地図で会場の近くのお店</a>'
             f'<a class="btn" href="/shops/?g={g}&amp;view=map">地図で{gl}のお店を見る</a></div>')

    b.append('<h2 id="stay">泊まる</h2>')
    b.append(f'<p>終演後は最寄り駅が混み合います。{"夜の公演のあと" if any("17" in t or "18" in t for t in times.values()) else "公演のあと"}に遠くまで移動しなくていいように、'
             f'会場の近くや乗り換えの少ない駅の近くの宿を早めに探しておくと安心です。</p>')
    b.append(stay_box(vname, hk, hj))
    b.append('<ul>\n  <li><a href="/guide/live-ensei-checklist/">ライブ遠征の準備チェックリスト</a>：持ち物・宿・当日の動き方</li>\n'
             '  <li><a href="/guide/live-ensei-transport/">ライブ遠征の交通手段ガイド</a>：新幹線・飛行機・高速バスの使い分け</li>\n'
             '  <li><a href="/ensei/">ライブ遠征×聖地巡礼</a>：全国の会場の近くの聖地と宿</li>\n</ul>')

    b.append('<h2 id="more">あわせて読みたい</h2>')
    more = []
    if has_guide:
        more.append(f'<li><a href="/guide/{key}/">{T.esc(vname)} ライブ参戦ガイド</a>（基本情報・ゲート・お金と荷物）</li>')
    more.append(f'<li><a href="{{{{ site.data.group_ix.{g}.u }}}}">{gl}のお店一覧</a>（グループのページ）</li>')
    b.append('<ul>\n' + '\n'.join('  ' + x for x in more) + '\n</ul>')
    b.append(f'<p class="note">お店の情報は、各お店の出典（番組・YouTube・ファンのロケ地ブログ）をもとにしています。会場からの距離は直線距離で、歩く距離とは違います。'
             f'会場の情報は{T.esc(vname)}の公式サイトにもとづきます。</p>')
    b.append('</div>')

    for old in glob.glob(os.path.join(ROOT, '_posts', f'*-{slug}.md')):
        os.remove(old)
    out = os.path.join(ROOT, '_posts', f'{fm["date"]}-{slug}.md')
    open(out, 'w', encoding='utf-8').write('---\n' + fm_txt + '---\n' + '\n\n'.join(b) + '\n')
    print(out, f'近く{len(rows)} 県内{len(pref_rows)} ほか{len(others)}')
    return out


def main():
    args = sys.argv[1:]
    if args == ['--all']:
        args = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, 'scripts/live_data/*.json')))
    ctx = dict(S=J('data/shops.json'), cards=J('_data/shop_cards.json'), gix=J('_data/group_ix.json'),
               venues=J('_data/venues.json'), vnear=J('_data/venue_nearby.json'))
    for slug in args:
        build(slug, ctx)


if __name__ == '__main__':
    main()
