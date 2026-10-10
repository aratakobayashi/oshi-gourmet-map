"""
apply_shop_patch.py
店舗データの直し方の案（patch.json）を data/shops.json に反映する。
  [{"id","action":"set","fields":{...}} / {"id","action":"unset","fields":[...]} /
   {"id","action":"remove","keep":"<残すid or null>"} / {"id","action":"review",...}]
- remove した店の _shop_pages はURLを残したまま「転送ページ」（layout: redirect）にする。
  keep があればその店のページへ、なければグループのページへ転送し、noindex を付ける。
- review は何もしない（一覧を表示するだけ）。
使い方: python scripts/apply_shop_patch.py patch.json [patch2.json ...] [--dry-run]
反映したあとは bash scripts/build_pages.sh でページを作り直す。
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'shops.json')


def page_of(shop_id):
    for p in glob.glob(os.path.join(ROOT, '_shop_pages', '*.md')):
        t = open(p, encoding='utf-8').read()
        if re.search(r'^shop_id: "' + re.escape(shop_id) + r'"$', t, re.M):
            return p
    return None


def main():
    files = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    raw = open(PATH, encoding='utf-8').read()
    shops = json.loads(raw)
    by = {s['id']: s for s in shops}
    groups = json.load(open(os.path.join(ROOT, '_data', 'group_ix.json'), encoding='utf-8'))
    cards = json.load(open(os.path.join(ROOT, '_data', 'shop_cards.json'), encoding='utf-8'))
    ops = [o for f in files for o in json.load(open(f, encoding='utf-8'))]
    n = {'set': 0, 'unset': 0, 'remove': 0, 'review': 0, 'skip': 0}
    removed = []
    for o in ops:
        s = by.get(o['id'])
        a = o['action']
        if a == 'review':
            n['review'] += 1
            print('確認:', o['id'], '|', o.get('note', ''))
            continue
        if not s:
            n['skip'] += 1
            print('見つからない:', o['id'])
            continue
        if a == 'set':
            s.update(o['fields'])
        elif a == 'unset':
            for k in o['fields']:
                s.pop(k, None)
        elif a == 'remove':
            keep = o.get('keep')
            if keep and keep in by:
                k = by[keep]
                for m in s.get('members') or []:
                    if m not in (k.get('members') or []):
                        k.setdefault('members', []).append(m)
            removed.append((s, keep))
            del by[o['id']]
        n[a] += 1
    shops = [s for s in shops if s['id'] in by]
    print(n)
    if dry:
        return
    indent = 2 if raw.startswith('[\n  {') else None
    open(PATH, 'w', encoding='utf-8').write(json.dumps(shops, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else ''))
    for s, keep in removed:
        p = page_of(s['id'])
        if not p:
            continue
        if keep and keep in cards:
            to, label = cards[keep]['u'], by[keep]['name'] + 'のページ'
        else:
            g = groups.get(s.get('group'), {})
            to, label = g.get('u', '/shops/'), (g.get('l', '') + 'のお店一覧') if g else 'お店を探す'
        open(p, 'w', encoding='utf-8').write(
            f'---\nlayout: redirect\nshop_id: "{s["id"]}"\nredirect_to: "{to}"\nredirect_label: "{label}"\nsitemap: false\n---\n')
        print('転送ページ:', os.path.basename(p), '→', to)


if __name__ == '__main__':
    main()
