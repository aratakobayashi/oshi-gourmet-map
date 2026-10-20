"""
group_matome.py
グループのまとめ記事（巡礼帳）を data/shops.json から作る。
「<グループ>の聖地巡礼・ロケ地まとめ｜<主な出典>で行った<主な地域>のご飯ほか<N>軒」
- そのグループの店（閉店を除く）を、出典の種類（公式YouTube → 冠番組 → 出演した番組 → ドラマのロケ地 → ほか → スタジオ）ごとに新しい順に並べる
- 冒頭の「出典で選ぶ」・メンバーで選ぶ・はじめての3軒（写真と回がはっきりしている店）・半日で巡るなら（同じ市区町村で近い3軒。front matter の courses → course_stops.py）・編集部メモ（店のデータから分かる事実だけ）
- 図: post_figures.py --only-genre（ジャンルと場所）、東京23区の店が5軒以上なら ward_tilemap.py も
- 店の評判・値段・営業時間は書かない。行の文は 回／メンバー／頼んだ物（場所）
使い方: python scripts/group_matome.py <group> [slug]   → そのあと build_pages.sh（enrich_rows などは build_pages.sh が実行）
"""
import collections
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = '2026-10-20'
KINDS = [('youtube', 'yt', '公式YouTube'), ('own_tv', 'tv', '冠番組'), ('guest_tv', 'guest', '出演した番組'),
         ('drama', 'drama', '出演したドラマのロケ地'), ('other', 'other', 'そのほかの出典')]


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def ym(d):
    return f'{d[:4]}.{int(d[5:7])}' if d and len(d) >= 7 else (d[:4] if d else '')


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def place(s):
    a = s.get('address') or ''
    m = re.match(r'(東京都|北海道|(?:京都|大阪)府|.{2,3}県)?(.+?[市区町村郡])(.*?)(?:\d|$)', a)
    if not m:
        return s.get('city') or s.get('prefecture') or ''
    town = re.sub(r'[一二三四五六七八九十０-９\d]+丁目.*$', '', m.group(3) or '').strip()
    return (m.group(2) or '') + (' ' + town if town else '')


def kind_of(s):
    if s.get('studio_only'):
        return 'studio'
    k = s.get('visit_kind')
    if k in ('youtube', 'own_tv', 'guest_tv', 'drama'):
        return k
    if s.get('youtube_id') and not s.get('program'):
        return 'youtube'
    return 'other'


def items_of(s):
    return [i for i in ((i.get('name', '') if isinstance(i, dict) else i) for i in (s.get('ordered_items') or [])) if i]


def row_text(s, own):
    bits = []
    prog = s.get('program') or ''
    title = s.get('source_video_title') or ''
    k = kind_of(s)
    if k == 'studio':
        bits.append(f'『{prog}』のスタジオに料理が出たお店' if prog else 'スタジオに料理が出たお店')
    elif k == 'drama':
        bits.append(f'ドラマ『{prog}』の撮影に使われたお店' if prog else 'ドラマの撮影に使われたお店')
    elif k == 'youtube' and title:
        bits.append(f'「{title[:44]}{"…" if len(title) > 44 else ""}」')
    elif prog:
        bits.append(f'『{prog}』')
    mem = [m for m in (s.get('members') or []) if m in own][:4]
    if mem and k not in ('studio', 'drama'):
        bits.append('・'.join(mem) + ('ほか' if len([m for m in (s.get('members') or []) if m in own]) > 4 else ''))
    its = items_of(s)[:3]
    if its and k != 'studio':
        bits.append('・'.join(its))
    return '／'.join(bits) + f'（{place(s)}）'


def main():
    g = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else f'{g.replace("_", "")}-gourmet-matome'
    S = J('data/shops.json')
    cards = J('_data/shop_cards.json')
    gix = J('_data/group_ix.json')
    gl, color = gix[g]['l'], gix[g]['c']
    genres = J('_data/genres.json')
    gname = {x['key']: x['label'] for x in genres} if isinstance(genres, list) else {k: v.get('label', k) for k, v in genres.items()}
    mine = [s for s in S if g in (s.get('groups') or [s.get('group')]) and not s.get('closed') and s['id'] in cards]
    own = collections.Counter(m for s in mine if s.get('group') == g for m in (s.get('members') or []) if m)
    bykind = collections.defaultdict(list)
    for s in mine:
        bykind[kind_of(s)].append(s)
    for k in bykind:
        bykind[k].sort(key=lambda s: s.get('visited_date') or '', reverse=True)
    visited = [s for s in mine if kind_of(s) != 'studio']
    ids = [s['id'] for k, _, _ in KINDS for s in bykind.get(k, [])] + [s['id'] for s in bykind.get('studio', [])]
    pref = collections.Counter(s.get('prefecture') or '' for s in visited)
    city = collections.Counter((s.get('prefecture') or '') + ' ' + (s.get('city') or '') for s in visited if s.get('city'))
    gen = collections.Counter(s.get('genre') or 'others' for s in visited)
    progs = collections.Counter(s.get('program') for s in visited if s.get('program'))
    n_items = sum(1 for s in visited if items_of(s))
    dates = sorted(s['visited_date'] for s in visited if s.get('visited_date'))
    src_names = []
    if bykind.get('youtube'):
        src_names.append('公式YouTube')
    if bykind.get('own_tv') or bykind.get('guest_tv'):
        src_names.append('番組')
    if bykind.get('drama'):
        src_names.append('ドラマ')
    src = '・'.join(src_names) or '出典'
    top_pref = [p for p, _ in pref.most_common(3) if p]
    top_city = [c for c, _ in city.most_common(3)]
    area_word = {'東京都': '東京', '大阪府': '大阪', '神奈川県': '横浜・神奈川', '愛知県': '名古屋', '福岡県': '福岡', '北海道': '札幌', '京都府': '京都', '兵庫県': '神戸'}.get(top_pref[0], top_pref[0]) if top_pref else ''
    title = f'{gl}の聖地巡礼・ロケ地まとめ｜{src}で行った{area_word}のご飯ほか{len(visited)}軒'
    kind_counts = '、'.join(f'{lab}{len(bykind[k])}軒' for k, _, lab in KINDS if bykind.get(k))
    main_src = '、'.join(f'『{p}』' for p, _ in progs.most_common(3)) if progs else ''
    desc = (f'{gl}の聖地巡礼・ロケ地{len(visited)}軒のまとめ。{kind_counts}を出典ごとに分けて紹介します。'
            + (f'出典は{main_src}など。' if main_src else '') + (f'場所は{"・".join(f"{p}{pref[p]}軒" for p in top_pref)}。' if top_pref else '')
            + 'お店ごとに回・出たメンバー・頼んだ物を載せ、地図でまとめて巡れます。')

    def has_photo(s):
        c = cards[s['id']]
        return bool(c.get('v') or (c.get('t') and c.get('sp') != 1))

    def pick_score(s):
        return (kind_of(s) in ('youtube', 'own_tv', 'guest_tv'), has_photo(s), bool(items_of(s)), bool([m for m in (s.get('members') or []) if m in own]), s.get('visited_date') or '')
    picks = sorted(visited, key=pick_score, reverse=True)[:3]
    cover = [s['id'] for s in picks if has_photo(s)]
    if len(cover) < 3:
        cover += [s['id'] for s in visited if s['id'] not in cover and has_photo(s)][:3 - len(cover)]
    vid = next((s['youtube_id'] for s in picks + visited if s.get('youtube_id')), '')

    # 半日コース: 店が最も多い市区町村の中で、互いに近い3軒（座標あり・場所が確かな店）
    course = None
    for c, _ in city.most_common(3):
        p, ci = c.split(' ', 1)
        cand = [s for s in visited if (s.get('prefecture') or '') == p and s.get('city') == ci and s.get('lat') and s.get('lng') and not s.get('location_unverified')]
        if len(cand) >= 3:
            best = None
            for a in cand:
                near = [a]
                for b in sorted(cand, key=lambda b: km((a['lat'], a['lng']), (b['lat'], b['lng']))):
                    if all(km((b['lat'], b['lng']), (c['lat'], c['lng'])) >= 0.15 for c in near):  # 同じ座標の店（住所が町名までの店）は使わない
                        near.append(b)
                    if len(near) == 3:
                        break
                if len(near) < 3:
                    continue
                d = sum(km((near[i]['lat'], near[i]['lng']), (near[i + 1]['lat'], near[i + 1]['lng'])) for i in range(2))
                if d < 6 and (best is None or d < best[0]):
                    best = (d, near)
            if best:
                course = (ci, best[1])
                break

    faq = [{'q': f'{gl}の聖地巡礼・ロケ地のお店はどこにありますか？',
            'a': f'{len(visited)}軒のうち、' + '、'.join(f'{p}{pref[p]}軒' for p in top_pref) + 'です。' + ('市区町村では' + '、'.join(f'{c.split(" ", 1)[1]}{n}軒' for c, n in city.most_common(3)) + 'が多いです。' if city else '')}]
    if progs:
        faq.append({'q': f'{gl}が行ったお店はどの番組やYouTubeの回ですか？',
                    'a': '、'.join(f'『{p}』{n}軒' for p, n in progs.most_common(5)) + ('、公式YouTubeの回が' + str(len(bykind['youtube'])) + '軒' if bykind.get('youtube') else '') + 'です。お店ごとに回と出たメンバーを載せています。'})
    if n_items:
        ex = [s for s in visited if items_of(s)][:3]
        faq.append({'q': 'メンバーが頼んだ物は分かりますか？',
                    'a': f'{n_items}軒で分かります。' + '、'.join(f'{s["name"]}の{"・".join(items_of(s)[:2])}' for s in ex) + 'などです。出典の番組・動画・ファンのロケ地ブログに書かれている物だけを載せています。'})
    if own:
        faq.append({'q': f'{gl}のメンバー別にお店を探せますか？',
                    'a': '記事の冒頭の「メンバーで選ぶ」から、メンバーごとに地図と一覧で見られます。お店の数が多いのは' + '、'.join(f'{m}（{n}軒）' for m, n in own.most_common(3)) + 'です。'})
    faq.append({'q': f'{gl}のお店をまとめて地図で見られますか？',
                'a': f'「お店を探す」で{gl}を選ぶと、この記事の{len(visited)}軒を地図で見られます。'})

    fm = {'layout': 'post', 'title': title, 'date': TODAY, 'last_modified_at': TODAY, 'checked_at': TODAY, 'description': desc,
          'group': g, 'genre': 'まとめ', 'article_type': 'matome', 'prefecture': top_pref[0] if top_pref else None,
          'tags': [gl] + [p for p, _ in progs.most_common(4)] + [m for m, _ in own.most_common(6)] + ['聖地巡礼', 'ロケ地', 'グルメ', 'まとめ'] + ([area_word] if area_word else []),
          'shop_ids': ids, 'faq': faq, 'pr': True}
    fm = {k: v for k, v in fm.items() if v is not None}
    if vid:
        fm['thumbnail_video_id'] = vid
    if len(cover) >= 3:
        fm.update(techo=True, cover_ids=','.join(cover[:3]), cover_title=f'{gl} 聖地巡礼帳', cover_sub=f'{src}で行った{len(visited)}軒')
    if course:
        ci, cs = course
        fm['courses'] = [{'title': f'{ci}の{len(cs)}軒を歩く', 'stops': [s['id'] for s in cs], 'labels': [s['name'][:14] for s in cs], 'legs': ['', '']}]
        fm['stay_area'] = ci
        fm['stay_note'] = f'{ci}の{len(cs)}軒を歩くコースは、{cs[0]["name"]}から始めます。遠征で来るなら、{ci}の近くに泊まると朝から回りやすくなります。'
        fm['stay_inline'] = True
    fm['summary'] = [f'{gl}の聖地{len(visited)}軒。{kind_counts}' + (f'。ほかにスタジオに料理が出たお店{len(bykind["studio"])}軒' if bykind.get('studio') else ''),
                     ('場所は' + '、'.join(f'{p}{pref[p]}軒' for p in top_pref) + ('、市区町村では' + '・'.join(c.split(' ', 1)[1] for c in top_city) + 'が多い' if city else '')) if top_pref else '場所はお店ごとに載せています',
                     f'頼んだ物が分かるお店は{n_items}軒。お店ごとに回・出たメンバー・頼んだ物を載せ、地図でまとめて巡れる']
    if dates:
        fm['summary'].append(f'回の時期は{dates[0][:4]}年から{dates[-1][:4]}年まで')
    fm_txt = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)

    b = [f'<div class="pf{" pf--techo" if fm.get("techo") else ""}" style="--pc:{color}">', '']
    mem_line = '・'.join(m for m, _ in own.most_common(12))
    b.append(f'<p><strong>{gl}</strong>' + (f'（{esc(mem_line)}）' if mem_line else '') + f'の聖地巡礼・ロケ地を、<strong>{len(visited)}軒</strong>まとめました。{kind_counts}。'
             + (f'ほかに、スタジオに料理が出ただけのお店が{len(bykind["studio"])}軒あります（行ったお店とは分けて載せています）。' if bykind.get('studio') else '') + '</p>')
    b.append('<p>' + (f'出典で多いのは{main_src}です。' if main_src else '') + 'お店ごとに、どの回で誰が行ったか・頼んだ物（出典に書かれている物だけ）・場所を載せています。'
             + (f'場所は{"・".join(f"{p}{pref[p]}軒" for p in top_pref)}' + (f'で、市区町村では{"・".join(c.split(" ", 1)[1] for c in top_city)}が多いです。' if city else 'です。') if top_pref else '')
             + '行きたいお店は保存して、地図でまとめて巡れます。</p>')
    nav = [(f'#src-{k}', ico, lab, len(bykind[k])) for k, ico, lab in KINDS if bykind.get(k)]
    if bykind.get('studio'):
        nav.append(('#src-studio', 'studio', 'スタジオに料理が出たお店', len(bykind['studio'])))
    b.append('<div class="cnav">\n<p class="cnav__h">出典で選ぶ</p>\n<div class="cnav__list">' +
             ''.join(f'<a href="{h}">{{% include chico.html kind="{ico}" %}}<span>{lab}<small>{n}軒</small></span></a>' for h, ico, lab, n in nav) + '</div>\n</div>')
    b.append(f'{{% include matome-members.html group="{g}" %}}')
    b.append('<h2>はじめての3軒：編集部が選ぶならここから</h2>')
    b.append(f'<p>{len(visited)}軒のなかから、どの回で行ったか・頼んだ物がはっきりしていて、写真のあるお店を3つ選びました。</p>\n<div class="picks">')
    for i, s in enumerate(picks):
        why = row_text(s, own).rsplit('（', 1)
        b.append(f'{{% include pick.html id="{s["id"]}" no="{["其の一", "其の二", "其の三"][i]}" why="{esc(why[0] + "。お店は" + place(s) + "です。")}" %}}')
    b.append('</div>')
    if course:
        ci, cs = course
        b.append(f'<h2>半日で巡るなら：{esc(ci)}の{len(cs)}軒を歩く</h2>')
        b.append(f'<p>{esc(ci)}にある{len(cs)}軒は、互いに歩ける距離にあります。' + '、'.join(esc(s['name']) for s in cs) + 'の順に回れます。</p>')
        b.append('<!-- stops:1 -->\n<ol class="stops">\n</ol>\n<!-- /stops -->')
        b.append('{% include stay-inline.html %}')
    memo = (f'{len(visited)}軒のうち、' + '、'.join(f'{lab}が{len(bykind[k])}軒' for k, _, lab in KINDS if bykind.get(k)) + '。'
            + (f'回の時期は{dates[0][:4]}年から{dates[-1][:4]}年までで、' if dates else '') + (f'場所は{top_pref[0]}が{pref[top_pref[0]]}軒と最も多く' + (f'、{top_pref[1]}が{pref[top_pref[1]]}軒' if len(top_pref) > 1 else '') + 'です。' if top_pref else '')
            + (f'メンバーでは{"・".join(m for m, _ in own.most_common(3))}の回が多く、' if own else '') + f'頼んだ物まで分かるお店は{n_items}軒です。')
    b.append(f'<div class="pf-quote"><p>{esc(memo)}</p><footer>— 推しグルメ巡礼MAP 編集部</footer></div>')
    b.append('<h2>ジャンルと場所で見る</h2>')
    b.append(f'<figure class="fig"><img src="/assets/img/posts/{slug}/genre.svg" alt="お店のジャンルと場所：' +
             '、'.join(f'{gname.get(k, k)}{n}軒' for k, n in gen.most_common()) + '。' + '、'.join(f'{p}{n}軒' for p, n in pref.most_common(5) if p) +
             f'" width="420" height="500" loading="lazy" decoding="async"><figcaption>この記事の{len(ids)}軒を数えました（ジャンルはお店のデータの分類）</figcaption></figure>')
    n23 = sum(1 for s in visited if s.get('prefecture') == '東京都' and (s.get('city') or '').endswith('区'))
    if n23 >= 5:
        b.append(f'<figure class="fig"><img src="/assets/img/posts/{slug}/wards.svg" alt="お店の場所の図（東京23区のタイル地図）" width="420" height="400" loading="lazy" decoding="async"><figcaption>東京23区は1区＝1マス。色が濃いほどお店が多い</figcaption></figure>')
    for k, ico, lab in KINDS + [('studio', 'studio', 'スタジオに料理が出たお店')]:
        rows = bykind.get(k)
        if not rows:
            continue
        b.append(f'<h2 id="src-{k}">{{% include chico.html kind="{ico}" %}}{lab}{"" if k == "studio" else "で行ったお店"}（{len(rows)}軒）</h2>')
        if k == 'studio':
            b.append(f'<p>番組のスタジオに料理が出たお店です。{gl}のメンバーがお店に行った回ではありません。</p>')
        elif k == 'drama':
            b.append('<p>メンバーが出演したドラマの撮影に使われたお店です。食べに行ったお店ではなく、場面に使われたお店です。</p>')
        elif k == 'youtube':
            b.append('<p>公式YouTubeの回です。新しい回から順に並べ、日付は動画の公開年月です。</p>')
        else:
            b.append('<p>新しい回から順に並べています。日付は放送年月です。</p>')
        b.append('<ul class="wrs">')
        for s in rows:
            b.append(f'  <li class="wr">{{% include wr-open.html id="{s["id"]}" %}}<span class="wr__k">{ym(s.get("visited_date"))}</span><b class="wr__name">{esc(s["name"])}</b>'
                     f'<span class="wr__t">{esc(row_text(s, own))}</span>{{% include wr-close.html id="{s["id"]}" %}}</li>')
        b.append('</ul>')
    if city:
        b.append('<h2>エリアで巡る</h2>\n<ul>')
        for c, n in city.most_common(8):
            p, ci = c.split(' ', 1)
            names = [s['name'] for s in visited if (s.get('prefecture') or '') == p and s.get('city') == ci][:4]
            b.append(f'  <li><strong>{esc(ci)}</strong>（{p}・{n}軒）：{esc("、".join(names))}{"ほか" if n > 4 else ""}</li>')
        b.append('</ul>')
    b.append(f'<div class="pf-cta">\n  <p>{gl}のお店を、地図でぜんぶ見る</p>\n  <span>この記事の{len(visited)}軒を地図で探せます。行きたいお店は保存して、巡礼の計画に。</span>\n'
             f'  <a class="btn" href="/shops/?g={g}&amp;view=map">地図で{gl}のお店を見る</a>\n</div>')
    b.append(f'<p><a href="{{{{ site.data.group_ix.{g}.u }}}}">{gl}のお店一覧（グループのページ）</a>もどうぞ。</p>')
    b.append('<p class="note">お店の情報は、各お店の出典（番組・YouTube・番組公式サイト・ファンのロケ地ブログ）をもとにしています。頼んだ物は出典に書かれている物だけで、番組の紹介メニューや推測は入れていません。営業日・営業時間は各お店の公式情報で確かめてください。</p>')
    b.append('</div>')
    out = os.path.join(ROOT, '_posts', f'{TODAY}-{slug}.md')
    open(out, 'w', encoding='utf-8').write('---\n' + fm_txt + '---\n' + '\n\n'.join(b) + '\n')
    print(out, len(visited), '軒')
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/post_figures.py'), slug, '--color', color, '--only-genre'], check=True)
    if n23 >= 5:
        subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/ward_tilemap.py'), slug, '--color', color, '--title', f'{gl}の聖地の場所'], check=True)
    if course:
        subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/course_stops.py'), slug], check=True)


if __name__ == '__main__':
    main()
