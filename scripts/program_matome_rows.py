"""
program_matome_rows.py
番組グループ（町中華で飲ろうぜ・酒場放浪記など）のまとめ記事の「お店の行」を、店のデータから地域ごとに作る。
記事の本文の <!-- rows:start --> と <!-- rows:end --> のあいだを書き換え（区・地域ごとの閉じた <details>。行は開いたときに app.js が JSON から作る）、front matter の shop_ids を
グループの店（閉店を除く）全部にする。何度実行しても同じ結果。

使い方: python scripts/program_matome_rows.py <記事のslug> <group> [--prefix '町中華で飲ろうぜ']
"""
import argparse, glob, json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WARDS = [
    ('都心（千代田・中央・港・文京）', ['千代田区', '中央区', '港区', '文京区']),
    ('城東（台東・墨田・江東・荒川・足立・葛飾・江戸川）', ['台東区', '墨田区', '江東区', '荒川区', '足立区', '葛飾区', '江戸川区']),
    ('城西・城北（新宿・渋谷・中野・杉並・豊島・北・板橋・練馬）', ['新宿区', '渋谷区', '中野区', '杉並区', '豊島区', '北区', '板橋区', '練馬区']),
    ('城南（品川・目黒・大田・世田谷）', ['品川区', '目黒区', '大田区', '世田谷区']),
]
NEAR = ['神奈川県', '埼玉県', '千葉県']


def town(s):
    a = s.get('address') or ''
    rest = a.replace(s.get('prefecture') or '', '', 1).replace(s.get('city') or '', '', 1)
    t = re.split(r'[0-9０-９一二三四五六七八九十]+丁目|[0-9０-９]', rest)[0].strip()
    return t[:8]


def ep(s, prefix):
    t = s.get('source_video_title') or ''
    t = re.sub(r'（\d{4}-\d\d-\d\d[^）]*）$', '', t)
    t = t.replace(prefix, '', 1).strip().replace('　', ' ')
    t = t.replace(prefix, '').strip()
    return t or '放送回'


def esc(x):
    return (x or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def row(s, prefix, place, cards):
    """1軒分のデータ（app.js が開いたときに .wr の行にする）: [お店のページ, 年.月, 店名, 説明, 食べログ, ホットペッパー]"""
    d = s.get('visited_date') or ''
    k = f'{int(d[:4])}.{int(d[5:7])}' if len(d) >= 7 else ''
    mem = '・'.join(s.get('members') or [])
    t = f'{ep(s, prefix)}／{mem}（{place}）' if mem else f'{ep(s, prefix)}（{place}）'
    c = cards.get(s['id']) or {}
    return [c.get('u') or '', k, s['name'], t, c.get('tb') or '', c.get('hp') or '']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slug'); ap.add_argument('group'); ap.add_argument('--prefix', default='')
    a = ap.parse_args()
    path = glob.glob(os.path.join(ROOT, '_posts', f'*-{a.slug}.md'))[0]
    cards = json.load(open(os.path.join(ROOT, '_data/shop_cards.json'), encoding='utf-8'))
    shops = [s for s in json.load(open(os.path.join(ROOT, 'data/shops.json'), encoding='utf-8'))
             if a.group in (s.get('groups') or [s.get('group')]) and not s.get('closed')]
    shops.sort(key=lambda s: (s.get('visited_date') or '', s['id']))
    by = collections.defaultdict(list)
    for s in shops:
        by[(s.get('prefecture'), s.get('city'))].append(s)
    secs = []  # (見出し, [(小見出し, 行)])
    used = set()
    for title, wards in WARDS:
        sub = [(w, by[('東京都', w)]) for w in wards if by[('東京都', w)]]
        for w in wards: used.add(('東京都', w))
        if sub:
            secs.append(('東京23区 ' + title, sub))
    tama = [(c, l) for (p, c), l in sorted(by.items(), key=lambda x: -len(x[1])) if p == '東京都' and (p, c) not in used]
    for k in [('東京都', c) for c, _ in tama]: used.add(k)
    if tama:
        secs.append(('東京の市部・島', [('', [s for _, l in tama for s in l])]))
    for p in NEAR:
        l = [s for (pp, c), ll in by.items() if pp == p for s in ll]
        for k in [k for k in by if k[0] == p]: used.add(k)
        if l:
            secs.append((p, [('', sorted(l, key=lambda s: (s.get('visited_date') or '', s['id'])))]))
    rest = [s for k, l in by.items() if k not in used for s in l]
    if rest:
        secs.append(('そのほかの道府県', [('', sorted(rest, key=lambda s: (s.get('prefecture') or '', s.get('visited_date') or '')))]))

    out = []
    nav = []
    for n, (h, subs) in enumerate(secs, 1):
        cnt = sum(len(l) for _, l in subs)
        nav.append((f'area{n}', h, cnt))
        out.append(f'<h2 id="area{n}">{{% include chico.html kind="map" %}}{esc(h)}<small>（{cnt}軒）</small></h2>')
        for sh, l in subs:
            lab = f'{esc(sh)}（{len(l)}軒）' if sh else f'{esc(h)}の{len(l)}軒を見る'
            # 店が多いので、行は開いたときに app.js が作る（データは JSON で埋め込む）。店名だけは本文にも並べる（検索エンジン・ページ内検索のため）
            rows = []
            for s in l:
                if s.get('prefecture') == '東京都' and sh:
                    place = f'{sh} {town(s)}'.strip()
                elif s.get('prefecture') == '東京都':
                    place = f'{s.get("city")} {town(s)}'.strip()
                else:
                    place = f'{s.get("prefecture")}{s.get("city") or ""}'
                rows.append(row(s, a.prefix, place, cards))
            js = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
            out.append(f'<details class="wrd" data-lazy><summary>{lab}</summary><script type="application/json">{js}</script></details>')
            out.append('<p class="wrd__names">' + '・'.join(esc(s['name']) for s in l) + '</p>')
    navh = ('<div class="cnav">\n<p class="cnav__h">エリアで選ぶ</p>\n<div class="cnav__list">'
            + ''.join(f'<a href="#{i}">{{% include chico.html kind="map" %}}<span>{esc(h)}<small>{c}軒</small></span></a>' for i, h, c in nav)
            + '</div>\n</div>')
    t = open(path, encoding='utf-8').read()
    t = re.sub(r'<!-- nav:start -->.*?<!-- nav:end -->', lambda m: '<!-- nav:start -->\n' + navh + '\n<!-- nav:end -->', t, flags=re.S)
    t = re.sub(r'<!-- rows:start -->.*?<!-- rows:end -->', lambda m: '<!-- rows:start -->\n' + '\n'.join(out) + '\n<!-- rows:end -->', t, flags=re.S)
    _, fm, body = t.split('---', 2)
    ids = '\n'.join(f'  - "{s["id"]}"' for s in shops)
    fm = re.sub(r'\nshop_ids:\n(  - .*\n)*', '\nshop_ids:\n' + ids + '\n', fm)
    open(path, 'w', encoding='utf-8').write('---' + fm + '---' + body)
    print(path, len(shops), [(h, c) for _, h, c in nav])


if __name__ == '__main__':
    main()
