"""
member_article.py
メンバー別のまとめ記事（_posts/）を data/shops.json から作る。
「<メンバー>が行ったお店まとめ｜<出典>で訪れたグルメ<N>軒」
- そのメンバーが members に入っている店（閉店を除く）を、出典の種類（公式YouTube・冠番組・出演した番組・ドラマのロケ地・ほか）ごとに新しい順に並べる
- スタジオに料理が出ただけの店（studio_only）は「スタジオに料理が出たお店」の章に分ける（行った、とは書かない）
- 行の文は 回（番組・動画）／一緒に出た人／頼んだ物（場所）。店の評判・値段・営業時間は書かない
- 図は scripts/post_figures.py --only-genre（ジャンルと場所）をこのあと実行して作る
- メンバーが複数のグループにいるとき（二宮和也: よにのちゃんねる・嵐 など）は groups に複数を書く。front matter の group は店が最も多いグループ
使い方: python scripts/member_article.py <メンバー名> <group>[,<group>...] <slug>
"""
import collections
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = '2026-10-19'
KINDS = [('youtube', 'yt', '公式YouTube'), ('own_tv', 'tv', '冠番組'), ('guest_tv', 'guest', '出演した番組'),
         ('drama', 'drama', '出演したドラマのロケ地'), ('other', 'other', 'そのほかの出典')]


def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding='utf-8'))


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def ym(d):
    return f'{d[:4]}.{int(d[5:7])}' if d and len(d) >= 7 else (d[:4] if d else '')


def place(s):
    a = s.get('address') or ''
    m = re.match(r'(東京都|北海道|(?:京都|大阪)府|.{2,3}県)?(.+?[市区町村郡])(.*?)(?:\d|$)', a)
    if not m:
        return s.get('city') or s.get('prefecture') or ''
    town = re.sub(r'[一二三四五六七八九十０-９\d]+丁目.*$', '', m.group(3) or '').strip()
    return (m.group(2) or '') + (' ' + town if town else '')


def kind_of(s):
    k = s.get('visit_kind')
    if s.get('studio_only'):
        return 'studio'
    if k in ('youtube', 'own_tv', 'guest_tv', 'drama'):
        return k
    if s.get('youtube_id') and not s.get('program'):
        return 'youtube'
    return 'other'


def items_of(s):
    return [i for i in ((i.get('name', '') if isinstance(i, dict) else i) for i in (s.get('ordered_items') or [])) if i]


def row_text(s, name):
    bits = []
    prog = s.get('program') or ''
    title = s.get('source_video_title') or ''
    k = kind_of(s)
    if k == 'studio':
        bits.append(f'『{prog}』のスタジオに料理が出たお店' if prog else 'スタジオに料理が出たお店')
    elif k == 'drama':
        bits.append(f'ドラマ『{prog}』の撮影に使われたお店' if prog else 'ドラマの撮影に使われたお店')
    elif k == 'youtube' and title:
        bits.append(f'「{title[:42]}{"…" if len(title) > 42 else ""}」')
    elif prog:
        bits.append(f'『{prog}』')  # 番組の店の source_video_title はファンブログの記事名のことが多いので出さない
    others = [m for m in (s.get('members') or []) if m and m != name][:3]
    w = s.get('with')
    if isinstance(w, list):
        others += [x for x in w if x and x != name][:2]
    elif isinstance(w, str) and w and w != name:
        others.append(w[:30])
    if others and k not in ('studio', 'drama'):
        bits.append(name + '・' + '・'.join(dict.fromkeys(others)))
    elif k not in ('studio', 'drama'):
        bits.append(name)
    its = items_of(s)[:3]
    if its and k != 'studio':
        bits.append('・'.join(its))
    return '／'.join(bits) + f'（{place(s)}）'


def main():
    name, groups, slug = sys.argv[1], sys.argv[2].split(','), sys.argv[3]
    S = J('data/shops.json')
    cards = J('_data/shop_cards.json')
    gix = J('_data/group_ix.json')
    genres = J('_data/genres.json')
    gname = {g['key']: g['label'] for g in genres} if isinstance(genres, list) else {k: v.get('label', k) for k, v in genres.items()}
    mine = [s for s in S if name in (s.get('members') or []) and s.get('group') in groups and not s.get('closed') and s['id'] in cards]
    if not mine:
        raise SystemExit('店がありません')
    gcount = collections.Counter(s['group'] for s in mine)
    g = gcount.most_common(1)[0][0]
    color = gix[g]['c']
    glabels = '・'.join(gix[x]['l'] for x, _ in gcount.most_common())
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
        src_names.append('YouTube')
    if bykind.get('own_tv') or bykind.get('guest_tv'):
        src_names.append('番組')
    if bykind.get('drama'):
        src_names.append('ドラマ')
    src = '・'.join(src_names) or '出典'
    top_pref = [p for p, _ in pref.most_common(3) if p]
    title = f'{name}（{glabels}）が行ったお店まとめ｜{src}で訪れた{top_pref[0] if top_pref else ""}のグルメほか{len(visited)}軒'
    kind_counts = '、'.join(f'{lab}{len(bykind[k])}軒' for k, _, lab in KINDS if bykind.get(k))
    desc = (f'{glabels}の{name}が{src}で行ったお店{len(visited)}軒をまとめました（{kind_counts}）。'
            f'お店ごとに、どの回で誰と行ったか・頼んだ物・場所が分かります。'
            + (f'場所は{"・".join(f"{p}{pref[p]}軒" for p in top_pref)}など。' if top_pref else '')
            + (f'頼んだ物が分かるお店は{n_items}軒。' if n_items else '') + '地図でまとめて巡れます。')

    # はじめての3軒: 頼んだ物と写真があり、行った店。東京を優先
    def pick_score(s):
        c = cards[s['id']]
        return (kind_of(s) in ('youtube', 'own_tv', 'guest_tv'), bool(items_of(s)), bool(c.get('v') or (c.get('t') and c.get('sp') != 1)), s.get('prefecture') == '東京都', s.get('visited_date') or '')
    picks = sorted(visited, key=pick_score, reverse=True)[:3]
    cover = [s['id'] for s in picks if cards[s['id']].get('v') or (cards[s['id']].get('t') and cards[s['id']].get('sp') != 1)]
    if len(cover) < 3:
        cover += [s['id'] for s in visited if s['id'] not in cover and (cards[s['id']].get('v') or (cards[s['id']].get('t') and cards[s['id']].get('sp') != 1))][:3 - len(cover)]
    vid = next((s['youtube_id'] for s in picks + visited if s.get('youtube_id')), '')

    faq = [{'q': f'{name}が行ったお店はどこですか？',
            'a': f'{glabels}の{src}で訪れたお店が{len(visited)}軒あります（{kind_counts}）。' +
                 ('新しい回では、' + '、'.join(f'{s["name"]}（{ym(s.get("visited_date"))}・{place(s)}）' for s in visited[:0] or sorted(visited, key=lambda s: s.get("visited_date") or "", reverse=True)[:3]) + 'などです。')}]
    if top_pref:
        faq.append({'q': f'{name}の聖地が多い場所はどこですか？',
                    'a': '、'.join(f'{p}{pref[p]}軒' for p in top_pref) + 'です。' +
                         ('市区町村では' + '、'.join(f'{c.split(" ", 1)[1]}{n}軒' for c, n in city.most_common(3)) + 'が多いです。' if city else '')})
    if n_items:
        ex = [s for s in visited if items_of(s)][:3]
        faq.append({'q': f'{name}が頼んだ物が分かるお店はありますか？',
                    'a': f'{n_items}軒で分かります。' + '、'.join(f'{s["name"]}の{"・".join(items_of(s)[:2])}' for s in ex) + 'などです。出典の番組・動画・ファンのロケ地ブログに書かれている物だけを載せています。'})
    if progs:
        faq.append({'q': f'{name}が番組で行ったお店はどの番組ですか？',
                    'a': '、'.join(f'『{p}』{n}軒' for p, n in progs.most_common(5)) + 'などです。'})
    faq.append({'q': f'{name}のお店をまとめて地図で見られますか？',
                'a': f'「お店を探す」で{gix[g]["l"]}を選び、メンバーで{name}を選ぶと、この記事のお店を地図で見られます。'})

    fm = {'layout': 'post', 'title': title, 'date': TODAY, 'last_modified_at': TODAY, 'description': desc, 'group': g,
          'genre': 'まとめ', 'article_type': 'member', 'member': name,
          'tags': [name] + [gix[x]['l'] for x in gcount] + [p for p, _ in progs.most_common(4)] + ['聖地巡礼', 'ロケ地', 'グルメ', 'まとめ'] + top_pref,
          'shop_ids': ids, 'faq': faq, 'pr': True}
    if vid:
        fm['thumbnail_video_id'] = vid
    if len(cover) >= 3:
        fm.update(techo=True, cover_ids=','.join(cover[:3]), cover_title=f'{name} 聖地巡礼帳', cover_sub=f'{src}で訪れた{len(visited)}軒')
    fm['summary'] = [f'{glabels}の{name}が{src}で行ったお店{len(visited)}軒（{kind_counts}）' + (f'。ほかにスタジオに料理が出たお店{len(bykind["studio"])}軒' if bykind.get('studio') else ''),
                     ('場所は' + '、'.join(f'{p}{pref[p]}軒' for p in top_pref) + ('、市区町村では' + '・'.join(c.split(' ', 1)[1] for c, _ in city.most_common(3)) + 'が多い' if city else '')) if top_pref else '場所はお店ごとに載せています',
                     f'頼んだ物が分かるお店は{n_items}軒。お店ごとに回・一緒に出た人・頼んだ物を載せ、地図でまとめて巡れる']
    if dates:
        fm['summary'].append(f'回の時期は{dates[0][:4]}年から{dates[-1][:4]}年まで')
    fm_txt = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)

    b = [f'<div class="pf{" pf--techo" if fm.get("techo") else ""}" style="--pc:{color}">', '']
    b.append(f'<p><strong>{glabels}の{name}</strong>が{src}で行ったお店を、<strong>{len(visited)}軒</strong>まとめました。'
             f'{kind_counts}。' + (f'ほかに、スタジオに料理が出ただけのお店が{len(bykind["studio"])}軒あります（行ったお店とは分けて載せています）。' if bykind.get('studio') else '') + '</p>')
    b.append('<p>お店ごとに、どの回で誰と行ったか・頼んだ物（出典に書かれている物だけ）・場所を載せています。'
             + (f'場所は{"・".join(f"{p}{pref[p]}軒" for p in top_pref)}' + (f'で、市区町村では{"・".join(c.split(" ", 1)[1] for c, _ in city.most_common(3))}が多いです。' if city else 'です。') if top_pref else '')
             + '行きたいお店は保存して、地図でまとめて巡れます。</p>')
    nav = [(f'#src-{k}', ico, lab, len(bykind[k])) for k, ico, lab in KINDS if bykind.get(k)]
    if bykind.get('studio'):
        nav.append(('#src-studio', 'studio', 'スタジオに料理が出たお店', len(bykind['studio'])))
    b.append('<div class="cnav">\n<p class="cnav__h">出典で選ぶ</p>\n<div class="cnav__list">' +
             ''.join(f'<a href="{h}">{{% include chico.html kind="{ico}" %}}<span>{lab}<small>{n}軒</small></span></a>' for h, ico, lab, n in nav) + '</div>\n</div>')
    b.append(f'{{% include matome-members.html group="{g}" %}}')
    b.append('<h2>はじめての3軒：編集部が選ぶならここから</h2>')
    b.append(f'<p>{len(visited)}軒のなかから、どの回で行ったか・頼んだ物がはっきりしているお店を3つ選びました。</p>\n<div class="picks">')
    for i, s in enumerate(picks):
        why = row_text(s, name).rsplit('（', 1)
        b.append(f'{{% include pick.html id="{s["id"]}" no="{["其の一", "其の二", "其の三"][i]}" why="{esc(why[0] + "。お店は" + place(s) + "です。")}" %}}')
    b.append('</div>')
    b.append('<h2>ジャンルと場所で見る</h2>')
    b.append(f'<figure class="fig"><img src="/assets/img/posts/{slug}/genre.svg" alt="お店のジャンルと場所：' +
             '、'.join(f'{gname.get(k, k)}{n}軒' for k, n in gen.most_common()) + '。' + '、'.join(f'{p}{n}軒' for p, n in pref.most_common(5) if p) +
             f'" width="420" height="500" loading="lazy" decoding="async"><figcaption>この記事の{len(ids)}軒を数えました（ジャンルはお店のデータの分類）</figcaption></figure>')
    for k, ico, lab in KINDS + [('studio', 'studio', 'スタジオに料理が出たお店')]:
        rows = bykind.get(k)
        if not rows:
            continue
        b.append(f'<h2 id="src-{k}">{{% include chico.html kind="{ico}" %}}{lab}{"" if k == "studio" else "で行ったお店"}（{len(rows)}軒）</h2>')
        if k == 'studio':
            b.append(f'<p>番組のスタジオに料理が出たお店です。{name}がお店に行った回ではありません。</p>')
        elif k == 'drama':
            b.append(f'<p>{name}が出演したドラマの撮影に使われたお店です。食べに行ったお店ではなく、場面に使われたお店です。</p>')
        else:
            b.append('<p>新しい回から順に並べています。日付はYouTubeの回は動画の公開年月、番組は放送年月です。</p>')
        b.append('<ul class="wrs">')
        for s in rows:
            b.append(f'  <li class="wr">{{% include wr-open.html id="{s["id"]}" %}}<span class="wr__k">{ym(s.get("visited_date"))}</span><b class="wr__name">{esc(s["name"])}</b>'
                     f'<span class="wr__t">{esc(row_text(s, name))}</span>{{% include wr-close.html id="{s["id"]}" %}}</li>')
        b.append('</ul>')
    if city:
        b.append('<h2>エリアで巡る</h2>\n<ul>')
        for c, n in city.most_common(8):
            p, ci = c.split(' ', 1)
            names = [s['name'] for s in visited if (s.get('prefecture') or '') == p and s.get('city') == ci][:4]
            b.append(f'  <li><strong>{esc(ci)}</strong>（{p}・{n}軒）：{esc("、".join(names))}{"ほか" if n > 4 else ""}</li>')
        b.append('</ul>')
    b.append(f'<div class="pf-cta">\n  <p>{name}のお店を、地図でぜんぶ見る</p>\n  <span>この記事の{len(visited)}軒を地図で探せます。行きたいお店は保存して、巡礼の計画に。</span>\n'
             f'  <a class="btn" href="/shops/?g={g}&amp;m={g}:{name}&amp;view=map">地図で{name}のお店を見る</a>\n</div>')
    b.append('<p>' + '、'.join(f'<a href="{{{{ site.data.group_ix.{x}.u }}}}">{gix[x]["l"]}のお店一覧</a>' for x in gcount) + 'もどうぞ。</p>')
    b.append('<p class="note">お店の情報は、各お店の出典（番組・YouTube・ファンのロケ地ブログ）をもとにしています。頼んだ物は出典に書かれている物だけで、番組の紹介メニューや推測は入れていません。営業日・営業時間は各お店の公式情報で確かめてください。</p>')
    b.append('</div>')
    out = os.path.join(ROOT, '_posts', f'{TODAY}-{slug}.md')
    open(out, 'w', encoding='utf-8').write('---\n' + fm_txt + '---\n' + '\n\n'.join(b) + '\n')
    print(out, len(visited), '軒', dict(gcount))


if __name__ == '__main__':
    main()
