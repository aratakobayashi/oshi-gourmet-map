"""
matome_rows.py
グループのまとめ記事（_posts/）を「お店の行」の形にそろえる。何度実行しても同じ結果。
- .pf-works（回・メンバー・食べた物の文字の一覧）と、そのあとの inline-shop-grid（同じ店の写真カード）を、
  1つの .wrs（写真＋店名＋回・メンバー・食べた物。押すとお店のページ。予約・食べログのボタン）にまとめる
- 出典の章（公式YouTube・冠番組・出演番組・ドラマのロケ地・スタジオ）に id とアイコンを付け、
  冒頭に「出典で選ぶ」「メンバーで選ぶ」を置く
- 年表とジャンルの図の章は、お店の章のあと（「はじめて見るなら」「エリアで巡るなら」の前）へ移す
- 「エリアで巡るなら」の先頭に東京の聖地マップ（scripts/post_map.py の map.svg）を入れる
使い方: python scripts/matome_rows.py <記事のslug> [--color '#7c3aed']
"""
import json
import os
import re
import subprocess
import sys
import unicodedata

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    s = re.sub(r'[（(][^）)]*[）)]?', '', s)  # 読みがな・地名のかっこを外す
    return re.sub(r'[\s　・\-－~〜（）()【】「」『』&;amp]', '', unicodedata.normalize('NFKC', s)).lower()


def kind_of(h):
    if 'YouTube' in h or 'チャンネル' in h or 'CHANNEL' in h:
        return 'yt'
    if 'ドラマ' in h or 'ロケ地' in h:
        return 'drama'
    if 'スタジオ' in h:
        return 'studio'
    if '冠番組' in h:
        return 'tv'
    if '出演' in h or '番組' in h:
        return 'guest'
    return 'other'


def main():
    slug = sys.argv[1]
    color = sys.argv[sys.argv.index('--color') + 1] if '--color' in sys.argv else '#e2553f'
    path = next(os.path.join(ROOT, '_posts', f) for f in os.listdir(os.path.join(ROOT, '_posts')) if f.endswith(slug + '.md'))
    text = open(path, encoding='utf-8').read()
    _, fm, body = text.split('---', 2)
    meta = yaml.safe_load(fm)
    group = meta.get('group')
    ids = [str(i) for i in meta.get('shop_ids') or []]
    cards = json.load(open(os.path.join(ROOT, '_data', 'shop_cards.json'), encoding='utf-8'))
    gname = json.load(open(os.path.join(ROOT, '_data', 'groups.json'), encoding='utf-8')).get(group, group)

    if 'class="wrs"' not in body:
        # --- 1) pf-works ＋ grid → wrs ---
        used = set()
        def find_id(name, pool):
            n = norm(name)
            for cand in (pool, ids):
                for i in cand:
                    if i in used or i not in cards:
                        continue
                    c = norm(cards[i]['n'])
                    if c == n:
                        return i
                for i in cand:
                    if i in used or i not in cards:
                        continue
                    c = norm(cards[i]['n'])
                    if n and c and (n in c or c in n or n[:6] == c[:6]):
                        return i
            return None

        out = []
        pos = 0
        works_re = re.compile(r'<ul class="pf-works">(.*?)</ul>', re.S)
        grid_re = re.compile(r'\{%\s*include inline-shop-grid\.html ids="([^"]*)"\s*%\}')
        for m in works_re.finditer(body):
            # この一覧のあと、次の見出し・一覧までにある grid
            nxt = re.search(r'<h[23]|<ul class="pf-works">', body[m.end():])
            seg_end = m.end() + (nxt.start() if nxt else len(body) - m.end())
            seg = body[m.end():seg_end]
            pool = [i for g in grid_re.findall(seg) for i in g.split(',') if i]
            rows = []
            for li in re.findall(r'<li>(.*?)</li>', m.group(1), re.S):
                k = re.search(r'<span class="k">(.*?)</span>', li, re.S)
                b = re.search(r'<b>(.*?)</b>', li, re.S)
                rest = li
                if b:
                    rest = li[b.end():]
                t = re.search(r'<span>(.*)</span>', rest, re.S)
                name = b.group(1) if b else ''
                sid = find_id(name, pool)
                if sid:
                    used.add(sid)
                kk = k.group(1) if k else ''
                tt = t.group(1) if t else re.sub(r'<[^>]+>', '', rest).strip()
                inner = (f'<span class="wr__k">{kk}</span>' if kk else '') + f'<b class="wr__name">{name}</b>' + (f'<span class="wr__t">{tt}</span>' if tt else '')
                if sid:
                    rows.append(f'  <li class="wr">{{% include wr-open.html id="{sid}" %}}{inner}{{% include wr-close.html id="{sid}" %}}</li>')
                else:
                    rows.append(f'  <li class="wr"><span class="wr__link wr__link--none"><span class="wr__body">{inner}</span></span></li>')
            if not pool and not any('include wr-open' in r for r in rows):
                continue  # 店ではない一覧（メンバーごとの注文など）はそのまま
            left = [i for i in pool if i not in used]
            new_seg = grid_re.sub('', seg)
            if left:
                new_seg = '\n{% include inline-shop-grid.html ids="' + ','.join(left) + '" %}' + new_seg
            out.append(body[pos:m.start()])
            out.append('<ul class="wrs">\n' + '\n'.join(rows) + '\n</ul>')
            out.append(new_seg)
            pos = seg_end
        out.append(body[pos:])
        body = ''.join(out)
        body = re.sub(r'\n{3,}', '\n\n', body)

    # --- 2) 章を分ける ---
    parts = re.split(r'(?=<h2[ >])', body)
    head, secs = parts[0], parts[1:]
    def title(s):
        return re.sub(r'<[^>]+>', '', re.match(r'<h2[^>]*>(.*?)</h2>', s, re.S).group(1)).strip()
    def idx(word):
        return next((i for i, s in enumerate(secs) if word in title(s)), None)
    tl, gn = idx('年表'), idx('ジャンルと場所')
    moved = [secs[i] for i in (tl, gn) if i is not None]
    secs = [s for i, s in enumerate(secs) if i not in (tl, gn)]
    land = idx('はじめて見るなら')
    if land is None:
        land = idx('エリアで巡る')
    if land is None:
        land = len(secs)
    first_src = 1 if secs and 'ひと目で' in title(secs[0]) else 0
    # 出典の章: ひと目で〜 のあと、はじめて見るなら／エリア の前
    nav = []
    no = 0  # 章の番号は出典の章だけで数える（何度実行しても同じ id になるように）
    for i in range(first_src, land):
        s = secs[i]
        h = title(s)
        if any(w in h for w in ('メンバーで選ぶ', 'はじめての', '半日で', 'ひと目で')):
            continue
        h = re.sub(r'\{% include chico\.html kind="\w+" %\}', '', h).strip()
        kd = kind_of(h)
        no += 1
        cid = f'src{no}'
        n = s.count('class="wr"') + sum(len(g.split(',')) for g in re.findall(r'inline-shop-grid\.html ids="([^"]*)"', s))
        label = re.sub(r'で(行った|紹介された)お店.*$|（\d+軒）', '', h).strip()
        hm = re.match(r'<h2([^>]*)>(.*?)</h2>', s, re.S)
        inner = re.sub(r'\{% include chico\.html kind="\w+" %\}', '', hm.group(2))
        attrs = re.sub(r'\s*id="[^"]*"', '', hm.group(1))
        secs[i] = f'<h2 id="{cid}"{attrs}>{{% include chico.html kind="{kd}" %}}{inner}</h2>' + s[hm.end():]
        nav.append((cid, kd, label, n))
    secs = secs[:land] + moved + secs[land:]
    # エリアの章に地図
    ai = idx('エリアで巡る')
    if ai is not None and 'map.svg' not in secs[ai]:
        hm = re.match(r'<h2[^>]*>.*?</h2>\n?', secs[ai], re.S)
        fig = (f'<figure class="fig"><img src="/assets/img/posts/{slug}/map.svg" alt="{gname}が行った東京のお店を、山手線の輪を目印にした地図のイラストに点で打った図" '
               f'width="420" height="542" loading="lazy" decoding="async"><figcaption>推しグルメ巡礼MAPのお店の座標から作ったイラスト（目安）。地図の外の店は数だけ</figcaption></figure>\n')
        secs[ai] = secs[ai][:hm.end()] + fig + secs[ai][hm.end():]
    body = head + ''.join(secs)

    # --- 3) 冒頭の「出典で選ぶ」「メンバーで選ぶ」 ---
    cnav_re = r'<div class="cnav">.*?</div>\n</div>\n(\{% include matome-members\.html group="\w+" %\}\n)?\n?'
    old = re.search(cnav_re, body, re.S)
    body = re.sub(cnav_re, '', body, flags=re.S)
    items = ''.join(f'<a href="#{c}">{{% include chico.html kind="{k}" %}}<span>{l}<small>{n}軒</small></span></a>' for c, k, l, n in nav if n)
    block = (f'<div class="cnav">\n<p class="cnav__h">出典で選ぶ</p>\n<div class="cnav__list">{items}</div>\n</div>\n'
             f'{{% include matome-members.html group="{group}" %}}\n')
    first_h2 = body.find('<h2 id="src')
    # 「ひと目で」の章の前に置く
    hi = old.start() if old else body.find('<h2>ひと目で')
    if hi < 0:
        hi = first_h2
    body = body[:hi] + block + '\n' + body[hi:]

    if not re.search(r'^pr:', fm, re.M):
        fm = fm.rstrip('\n') + '\npr: true\n'
    open(path, 'w', encoding='utf-8').write('---' + fm + '---' + body)
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'post_figures.py'), slug, '--color', color, '--only-genre'], check=False, capture_output=True)
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'post_map.py'), slug, '--color', color, '--title', f'{gname}の東京の聖地マップ'], check=True)
    print(slug, 'rows', body.count('class="wr"'), 'nav', len(nav))


if __name__ == '__main__':
    main()
