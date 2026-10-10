#!/usr/bin/env python3
"""
build_site_data.py
shops.json から、ページをビルド時に組み立てるための _data/ ファイルを作る（リニューアル「巡礼帳」用）。
JS でデータを読み込む前に、最初の一覧や「近くの聖地グルメ」を HTML に出しておくため（表示速度・SEO）。

出力
  _data/group_meta.json  グループ一覧（件数順）: id, label, color, kana, count, prefs, members[{name,count}]
  _data/shop_cards.json  店舗カード用の最小データ（id → {n,u,g,gr,st,w,v,t,r,m,p,src,hk,hj}）
  _data/group_ix.json    グループID → {l: 表示名, c: 色, n: 件数}（Liquid から引く用）
  _data/group_detail.json グループID → {ids: 新着24件, genres/prefs/stations: [[名前, 件数]], by_genre: {ジャンル: [ID]}}
  _data/nearby.json      店舗ID → 近い順の店舗ID（3km以内・最大6件）と距離m
  _data/venue_nearby.json 会場キー → {n: r km以内の件数, r: 3（少ない会場は10）, ids: 近い順8件}
  data/explore.json      /shops/ の絞り込み用（配列: id,name,slug,genre,groups,pref,city,station,walk,lat,lng,
                         youtube_id,thumb,reservable,members,source,visited_date,closed）
  _data/site_stats.json  件数・新着・よく出る駅・都道府県・ジャンル件数

使い方:
  python scripts/build_site_data.py
"""
import json
import math
import os
import re
import urllib.parse
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, '_data')

# グループ名の読み（絞り込みシートの五十音タブ・検索用）
READINGS = {
    'yonino': 'よにのちゃんねる', 'snowman': 'すのーまん', 'sixtones': 'すとーんず', 'equal_love': 'いこらぶ',
    'notme': 'のっといこーるみー', 'neajoy': 'にあじょい', 'naniwa': 'なにわだんし', 'kamenashi': 'かめなしかずや',
    'ginga': 'なかまるゆういち', 'kamaitachi': 'かまいたち', 'kodoku_no_gurume': 'こどくのぐるめ',
    'heysayjump': 'へいせいじゃんぷ', 'nogizaka46': 'のぎざか', 'hinatazaka46': 'ひなたざか', 'sakurazaka46': 'さくらざか',
    'timelesz': 'たいむれす', 'shiori': 'しおり', 'kingprince': 'きんぐあんどぷりんす', 'arashi': 'あらし',
    'kimura': 'きむらたくや', 'kpop_enhypen': 'えんはいぷん', 'kpop_seventeen': 'せぶんてぃーん', 'kpop_riize': 'らいず',
    'kpop_nct': 'えぬしーてぃー', 'west': 'うえすと', 'kinkikids': 'きんききっず', 'kanjani': 'かんじゃにえいと',
    'kattun': 'かとぅーん', 'v6': 'ぶいしっくす', 'smap': 'すまっぷ', 'numberi': 'なんばーあい',
    'travisjapan': 'とらびすじゃぱん', 'kismai': 'きすまいふっとつー', 'agroup': 'えーぇぐるーぷ',
    'kpop_bts': 'びーてぃーえす', 'kpop_twice': 'とぅわいす', 'kpop_blackpink': 'ぶらっくぴんく',
    'kpop_newjeans': 'にゅーじーんず', 'kpop_aespa': 'えすぱ', 'kpop_ive': 'あいぶ',
    'kpop_lesserafim': 'るせらふぃむ', 'kpop_straykids': 'すとれいきっず',
}


def jekyll_slug(name):
    """Jekyll の :name と同じ変換（英数字以外は - にまとめ、前後の - を除き小文字に）"""
    return re.sub(r'(?:[^\w]|_)+', '-', name).strip('-').lower()


def slug(shop_id):
    """店舗ページのURLの名前部分（_shop_pages のファイル名 → Jekyll の :name）"""
    return jekyll_slug(re.sub(r'-+$', '', shop_id.replace('_', '-')))


LINE_PREFIX = re.compile(r'^(JR|ＪＲ|東京メトロ|都営|東急|京王|小田急|西武|東武|京急|京成|相鉄|阪急|阪神|近鉄|南海|京阪|地下鉄|大阪メトロ|名鉄|りんかい線|ゆりかもめ)')


def station_of(s):
    """'JR「飯田橋駅」徒歩5分' → ('飯田橋駅', '徒歩5分')"""
    st = re.sub(r'[「」『』"]', '', (s.get('nearest_station') or '').strip())
    m = re.search(r'([^\s、,・/／（()）]+?駅)', st)
    if not m:
        return '', ''
    name = LINE_PREFIX.sub('', m.group(1))
    name = re.sub(r'^.*線', '', name)
    if len(name) < 2:
        return '', ''
    w = re.search(r'徒歩\s*(\d+)\s*分', st)
    return name, ('徒歩' + w.group(1) + '分') if w else ''


def hotel_keyword(s, st):
    """「周辺に泊まる」の検索語: 駅名（駅を除く）→ 市区町村 → 都道府県。国内のみ"""
    pref = s.get('prefecture') or ''
    if not re.search(r'[都道府県]$', pref):
        return ''
    if st:
        return re.sub(r'駅$', '', st)
    return s.get('city') or pref


def km(a, b):
    r = math.pi / 180
    dlat, dlng = (b[0] - a[0]) * r, (b[1] - a[1]) * r
    h = math.sin(dlat / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin(dlng / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def front_matter(path):
    t = open(path, encoding='utf-8').read()
    if not t.startswith('---'):
        return {}
    import yaml
    return yaml.safe_load(t.split('---', 2)[1]) or {}


def build_article_rel(shops, venues, venue_nearby, by_id):
    """記事（_posts）とガイド（_guides）ごとに、関連する記事・ガイドを並べる。
    キーは 'p:<記事のslug>' / 'g:<ガイドのslug>'。値は {'posts': [...], 'guides': [...]}（各要素は表示用のカード）"""
    docs = {}
    for f in sorted(os.listdir(os.path.join(ROOT, '_posts'))):
        if not f.endswith('.md'):
            continue
        fm = front_matter(os.path.join(ROOT, '_posts', f))
        y, mo, d, name = f[:4], f[5:7], f[8:10], f[11:-3]
        thumb = ''
        if fm.get('thumbnail_video_id'):
            thumb = f"https://i.ytimg.com/vi_webp/{fm['thumbnail_video_id']}/mqdefault.webp"
        elif fm.get('thumbnail'):
            thumb = fm['thumbnail']
        ids = [i for i in (fm.get('shop_ids') or []) if i in by_id]
        docs['p:' + name] = {'u': f'/articles/{y}/{mo}/{d}/{name}/', 't': fm.get('title', ''), 'img': thumb,
                             'cat': fm.get('article_type') or '', 'group': fm.get('group') or '', 'ids': ids,
                             'date': f'{y}-{mo}-{d}', 'kind': 'post'}
    for f in sorted(os.listdir(os.path.join(ROOT, '_guides'))):
        if not f.endswith('.html'):
            continue
        fm = front_matter(os.path.join(ROOT, '_guides', f))
        name = f[:-5]
        th = fm.get('thumbnail') or ''
        if th.startswith('/') and th.endswith('.webp'):
            th = th[:-5] + '_600.webp'
        docs['g:' + name] = {'u': f'/guide/{jekyll_slug(name)}/', 't': fm.get('title', ''), 'img': th,
                             'cat': fm.get('guide_category') or '', 'group': '', 'ids': [], 'kind': 'guide',
                             'new': 1 if fm.get('checked_at') else 0}

    def card(k, meta=''):
        d = docs[k]
        return {'u': d['u'], 't': d['t'], 'img': d['img'], 'cat': d['cat'], 'kind': d['kind'], 'meta': meta}

    venue_shops = {k: set(v.get('all', [])) for k, v in venue_nearby.items()}
    venue_shops3 = {k: set(v.get('all3', [])) for k, v in venue_nearby.items()}  # 記事→会場は3km以内だけ
    rel = {}
    for k, d in docs.items():
        posts, guides = [], []
        if d['kind'] == 'post':
            mine = set(d['ids'])
            score = []
            for k2, d2 in docs.items():
                if k2 == k or d2['kind'] != 'post':
                    continue
                s = (3 if d['group'] and d2['group'] == d['group'] else 0) + len(mine & set(d2['ids'])) + (1 if d2['cat'] == d['cat'] else 0)
                score.append((-s, d2['date'] and -int(d2['date'].replace('-', '')), k2))
            posts = [card(k2, f"{len(docs[k2]['ids'])}軒" if docs[k2]['ids'] else '') for _, _, k2 in sorted(score)[:6]]
            # 記事のお店の近くにある会場のガイド（近くのお店が多い順）
            vs = sorted(((len(mine & venue_shops3.get(vk, set())), vk) for vk in venues if 'g:' + vk in docs), reverse=True)
            guides = [card('g:' + vk, f'この記事のお店{c}軒が近く') for c, vk in vs if c > 0][:3]
        else:
            slug = k[2:]
            if slug in venues:
                v0 = venues[slug]
                near = sorted((km((v0['lat'], v0['lng']), (v['lat'], v['lng'])), vk) for vk, v in venues.items() if vk != slug and 'g:' + vk in docs)
                guides = [card('g:' + vk, f'ここから{dk:.0f}km' if dk >= 1 else f'ここから{dk * 1000:.0f}m') for dk, vk in near[:6]]
                mine = venue_shops.get(slug, set())
                ps = sorted(((len(mine & set(docs[pk]['ids'])), pk) for pk in docs if pk.startswith('p:')), reverse=True)
                posts = [card(pk, f'会場の近くのお店{c}軒') for c, pk in ps if c > 0][:4]
            else:
                same = [k2 for k2, d2 in docs.items() if d2['kind'] == 'guide' and k2 != k and d2['cat'] == d['cat']]
                guides = [card(k2) for k2 in same[:6]]
                newv = sorted((k2 for k2, d2 in docs.items() if d2['kind'] == 'guide' and d2.get('new') and d2['cat'] == 'venue'),
                              key=lambda k2: -venue_nearby.get(k2[2:], {}).get('n', 0))
                posts = [card(k2, f"周辺の聖地{venue_nearby.get(k2[2:], {}).get('n', 0)}軒") for k2 in newv[:4]]
        rel[k] = {'posts': posts, 'guides': guides}
    return rel


def main():
    shops = json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8'))
    labels = json.load(open(os.path.join(DATA, 'groups.json'), encoding='utf-8'))

    # グループ色は _group_pages の group_color が正
    colors, colors2, gurls = {}, {}, {}
    for f in os.listdir(os.path.join(ROOT, '_group_pages')):
        t = open(os.path.join(ROOT, '_group_pages', f), encoding='utf-8').read()
        k = re.search(r'^group_key: "(.*?)"', t, re.M)
        c = re.search(r'^group_color: "(.*?)"', t, re.M)
        c2 = re.search(r'^group_color2: "(.*?)"', t, re.M)
        if k and c:
            colors[k.group(1)] = c.group(1)
        if k and c2:
            colors2[k.group(1)] = c2.group(1)
        if k:
            gurls[k.group(1)] = '/groups/' + jekyll_slug(f[:-3]) + '/'

    # --- 店舗カード ---
    cards = {}
    for s in shops:
        st, walk = station_of(s)
        # 予約可 = ネット予約できるリンクがある（ホットペッパー・一休など）。食べログは予約できない店もあるので含めない
        reservable = bool(s.get('hotpepper_url') or
                          any('予約' in (l.get('label') or '') for l in s.get('affiliate_links') or []))
        cards[s['id']] = {
            'n': s['name'], 'u': '/shops/' + slug(s['id']) + '/', 'g': s.get('genre', ''),
            'gr': s.get('group', ''), 'st': st, 'w': walk, 'v': s.get('youtube_id') or '',
            't': s.get('hotpepper_photo') or s.get('thumbnail_url') or '', 'r': 1 if reservable else 0,
            'm': (s.get('members') or [])[:2], 'p': s.get('prefecture', ''),
            'src': (s.get('source_video_title') or '')[:40],
        }
        hk = hotel_keyword(s, st)
        if hk:
            # じゃらんの検索は Shift_JIS のため、ここでエンコードしておく
            cards[s['id']]['hk'] = hk
            cards[s['id']]['hj'] = urllib.parse.quote(hk, encoding='cp932', errors='ignore')

    # --- グループ ---
    by_group = defaultdict(list)
    for s in shops:
        for g in s.get('groups') or [s.get('group')]:
            if g:
                by_group[g].append(s)
    meta = []
    for g, items in by_group.items():
        # メンバーは、そのグループが主の店（group が一致）だけから数える（複数グループの店で他グループのメンバーが混ざらないように）
        mem = Counter(m for s in items if (s.get('group') or g) == g for m in (s.get('members') or []) if m and len(m) < 15)
        meta.append({
            'id': g, 'label': labels.get(g, g), 'color': colors.get(g, '#9a8f80'), 'url': gurls.get(g, '/groups/'),
            'kana': READINGS.get(g, ''), 'count': len(items),
            'prefs': len({s.get('prefecture') for s in items if s.get('prefecture')}),
            'members': [{'name': n, 'count': c} for n, c in mem.most_common(12) if c >= 2],
        })
    meta.sort(key=lambda x: -x['count'])

    # グループページ用: 新着20件・よく行くジャンル／エリア／駅
    def recent_key(s):
        return (s.get('visited_date') or '', 1 if s.get('youtube_id') else 0)
    detail = {}
    for g, items in by_group.items():
        live = [s for s in items if not s.get('closed')]
        detail[g] = {
            'ids': [s['id'] for s in sorted(live, key=recent_key, reverse=True)[:24]],
            'genres': Counter(s.get('genre') for s in items if s.get('genre')).most_common(),
            'prefs': Counter(s.get('prefecture') for s in items if s.get('prefecture')).most_common(6),
            'stations': Counter(st for st in (station_of(s)[0] for s in items) if st).most_common(6),
            # グループ×ジャンル一覧（/list/）用: ジャンル → 店舗ID（閉店は最後・新着順）
            'by_genre': {},
        }
        for s in sorted(items, key=lambda s: (0 if s.get('closed') else 1,) + recent_key(s), reverse=True):
            detail[g]['by_genre'].setdefault(s.get('genre') or 'others', []).append(s['id'])

    # --- 近くの聖地グルメ（3km以内・最大6件） ---
    by_id = {s['id']: s for s in shops}
    pts = [(s['id'], (s['lat'], s['lng'])) for s in shops if s.get('lat') and s.get('lng') and not s.get('closed')]
    # 「近くの店」に出してよい店: 住所が番地まであり、座標がほかの店と重なっていないもの。
    # 住所が「東京都文京区」までの店は区役所あたりの座標になっていて、実際の場所と離れているため
    same_xy = Counter((round(q[0], 5), round(q[1], 5)) for _, q in pts)
    addr = {s['id']: s.get('address') or '' for s in shops}
    unverified = {s['id'] for s in shops if s.get('location_unverified')}  # 場所の確認待ち（shops.json で付ける）
    pts_near = [(oid, q) for oid, q in pts
                if re.search(r'[0-9０-９]', addr[oid]) and same_xy[(round(q[0], 5), round(q[1], 5))] < 3
                and oid not in unverified]
    nearby = {}
    for sid, p in pts:
        cand = []
        for oid, q in pts_near:
            if oid == sid or abs(q[0] - p[0]) > 0.03 or abs(q[1] - p[1]) > 0.04:
                continue
            d = km(p, q)
            if d <= 3:
                cand.append((d, oid))
        cand.sort()
        nearby[sid] = [{'id': oid, 'm': int(round(d * 1000, -1))} for d, oid in cand[:6]]

    # --- 会場ガイド: 会場から3km以内の店（近い順・最大8件）と件数 ---
    venues = json.load(open(os.path.join(DATA, 'venues.json'), encoding='utf-8'))
    venue_nearby = {}
    for key, v in venues.items():
        p = (v['lat'], v['lng'])
        cand = sorted((km(p, q), oid) for oid, q in pts_near
                      if abs(q[0] - p[0]) < 0.03 and abs(q[1] - p[1]) < 0.04 and km(p, q) <= 3)
        radius = 3
        within3 = [oid for _, oid in cand]
        if len(cand) < 3:
            # 3km以内に少ない会場は10kmまで広げて近い順に出す（件数 n も10km以内の数）
            cand = sorted((km(p, q), oid) for oid, q in pts_near
                          if abs(q[0] - p[0]) < 0.1 and abs(q[1] - p[1]) < 0.12 and km(p, q) <= 10)
            radius = 10
        gc = Counter(g for _, oid in cand for g in (by_id[oid].get('groups') or [by_id[oid].get('group')]) if g)
        venue_nearby[key] = {'n': len(cand), 'r': radius, 'ids': [{'id': oid, 'm': int(round(d * 1000, -1))} for d, oid in cand[:8]],
                             'all': [oid for _, oid in cand], 'all3': within3,
                             'gc': [[g, c] for g, c in gc.most_common(6)], 'lat': v['lat'], 'lng': v['lng'],
                             'hk': v['name'], 'hj': urllib.parse.quote(v['name'], encoding='cp932', errors='ignore')}

    # --- 記事どうしの関連（サムネイルつきの「あわせて読みたい」用）---
    article_rel = build_article_rel(shops, venues, venue_nearby, by_id)
    for v in venue_nearby.values():
        v.pop('all', None)
        v.pop('all3', None)

    # --- サイト全体の数字 ---
    latest = [s['id'] for s in sorted(shops, key=recent_key, reverse=True) if not s.get('closed')][:20]
    stations = Counter(station_of(s)[0] for s in shops if station_of(s)[0])
    prefs = Counter(s.get('prefecture') for s in shops if s.get('prefecture'))
    genres = Counter(s.get('genre') for s in shops if s.get('genre'))
    stats = {
        'shops': len(shops), 'groups': len(meta), 'prefs': len(prefs),
        'hp_photos': sum(1 for s in shops if s.get('hotpepper_photo')),  # 1件以上でフッターにクレジット
        'latest': latest,
        'latest_video': [s['id'] for s in sorted(shops, key=recent_key, reverse=True) if not s.get('closed') and s.get('youtube_id')][:6],
        'stations': [{'name': n, 'count': c} for n, c in stations.most_common(12)],
        'prefectures': [{'name': n, 'count': c} for n, c in prefs.most_common(10)],
        'genres': dict(genres),
    }

    # --- お店を探す（/shops/）用の軽量データ（data/explore.json。表示後に読み込む） ---
    explore = []
    for sh in shops:
        cd = cards[sh['id']]
        t = cd['t'] if cd['t'] and 'youtube.com' not in cd['t'] and 'ytimg' not in cd['t'] else ''
        explore.append([
            sh['id'], cd['n'], cd['u'][len('/shops/'):-1], cd['g'],
            [g for g in (sh.get('groups') or [sh.get('group')]) if g],
            cd['p'], sh.get('city') or '', cd['st'], cd['w'],
            round(sh['lat'], 5) if sh.get('lat') else 0, round(sh['lng'], 5) if sh.get('lng') else 0,
            cd['v'], t, cd['r'], [m for m in (sh.get('members') or []) if m and len(m) < 15],
            cd['src'], sh.get('visited_date') or '', 1 if sh.get('closed') else 0,
        ])
    with open(os.path.join(ROOT, 'data', 'explore.json'), 'w', encoding='utf-8') as f:
        json.dump(explore, f, ensure_ascii=False, separators=(',', ':'))

    def dump(name, obj):
        with open(os.path.join(DATA, name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))

    dump('shop_cards.json', cards)
    dump('group_meta.json', meta)
    dump('group_ix.json', {g['id']: {'l': g['label'], 'c': g['color'], 'c2': colors2.get(g['id'], g['color']), 'n': g['count'], 'u': g['url'],
                                  'ph': 1 if os.path.exists(os.path.join(ROOT, 'assets', 'images', 'groups', g['id'] + '_120.webp')) else 0}
                            for g in meta})
    dump('nearby.json', nearby)
    dump('group_detail.json', detail)
    dump('venue_nearby.json', venue_nearby)
    dump('article_rel.json', article_rel)
    dump('site_stats.json', stats)
    print(f'cards {len(cards)} / groups {len(meta)} / nearby {sum(1 for v in nearby.values() if v)}件に近くの店あり')


if __name__ == '__main__':
    main()
