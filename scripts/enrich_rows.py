"""
enrich_rows.py
まとめ記事の「お店の行」（.wrs の li.wr）に、店のデータの「頼んだ物」（ordered_items）と「座った席」（seating_note）を書き足す。
- 行の文（.wr__t）にすでに出ている品は足さない。足すのは最大3品
- スタジオに料理が出ただけの店（studio_only）には足さない
- ほかのグループが主の店の品・席は、その店に行った回が別のことがあるので足さない（記事の group と店の group が同じとき、
  または group のない記事で店が1グループだけのときだけ）
- 足した部分は <span class="wr__more">…</span>。実行するたびに作り直す（何度実行しても同じ）
使い方: python scripts/enrich_rows.py [記事のslug ...]（省略すると全記事）
"""
import glob
import html
import json
import os
import re
import sys
import unicodedata

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_ITEMS = 3


def norm(s):
    return re.sub(r'[\s　・、,（）()「」『』]', '', unicodedata.normalize('NFKC', s or '')).lower()


def item_name(i):
    return i.get('name', '') if isinstance(i, dict) else (i or '')


ROW = re.compile(r'(<li class="wr[^"]*">\{% include wr-open\.html id="([^"]+)"[^%]*%\}.*?<span class="wr__t">(.*?)</span>)'
                 r'(<span class="wr__more">.*?</span></span>)?(\{% include wr-close\.html)', re.S)


def more(shop, row_text):
    t = norm(re.sub(r'<[^>]+>', '', row_text))
    items = [item_name(i) for i in shop.get('ordered_items') or []]
    items = [i for i in dict.fromkeys(items) if i and norm(i) not in t][:MAX_ITEMS]
    seat = (shop.get('seating_note') or '').strip()
    if seat and norm(seat) in t:
        seat = ''
    parts = []
    if items:
        parts.append(f'<span class="wr__oi">頼んだ物：{html.escape("・".join(items))}</span>')
    if seat:
        parts.append(f'<span class="wr__seat">席：{html.escape(seat)}</span>')
    return f'<span class="wr__more">{"".join(parts)}</span>' if parts else ''


def main():
    shops = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'data/shops.json'), encoding='utf-8'))}
    slugs = sys.argv[1:]
    paths = [p for p in sorted(glob.glob(os.path.join(ROOT, '_posts', '*.md')))
             if not slugs or any(p.endswith(f'-{s}.md') for s in slugs)]
    total = 0
    for p in paths:
        t = open(p, encoding='utf-8').read()
        if 'wr-open.html' not in t:
            continue
        fm = yaml.safe_load(t.split('---')[1]) or {}
        g = fm.get('group')
        n = 0

        def rep(m):
            nonlocal n
            head, sid, row_text, _old, close = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            s = shops.get(sid)
            add = ''
            if s and not s.get('studio_only'):
                gs = s.get('groups') or [s.get('group')]
                if (g and s.get('group') == g) or (not g and len(gs) == 1):
                    add = more(s, row_text)
            if add:
                n += 1
            return head + add + close

        t2 = ROW.sub(rep, t)
        if t2 != t:
            open(p, 'w', encoding='utf-8').write(t2)
        if n:
            print(os.path.basename(p), n)
        total += n
    print('行に足した店', total)


if __name__ == '__main__':
    main()
