#!/usr/bin/env python3
"""
clean_orphan_pages.py
data/shops.json に存在しない店舗の _shop_pages/*.md（孤立ページ）から、
掲載しない方針のフィールドを取り除く。URL を変えないためページ自体は残す。

generate_shop_pages.py は shops.json にある店舗のページしか再生成しないため、
孤立ページはこのスクリプトで個別に整える。

使い方:
  python scripts/clean_orphan_pages.py --list            # 孤立ページの一覧だけ表示
  python scripts/clean_orphan_pages.py --drop tabelog_score price_range
"""
import argparse
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def orphan_pages():
    with open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8') as f:
        ids = {s['id'] for s in json.load(f)}
    for path in sorted(glob.glob(os.path.join(ROOT, '_shop_pages', '*.md'))):
        text = open(path, encoding='utf-8').read()
        m = re.search(r'^shop_id: "(.*?)"$', text, re.M)
        if m and m.group(1) not in ids:
            yield path, text


def drop_keys(text, keys):
    """front matter からトップレベルのキー（とその下のインデント行）を削除"""
    out, skipping = [], False
    for line in text.split('\n'):
        top = re.match(r'^([A-Za-z_]+):', line)
        if top:
            skipping = top.group(1) in keys
        elif line and not line.startswith(' '):
            skipping = False
        if not skipping:
            out.append(line)
    return '\n'.join(out)


def clean_description(text):
    def fix(m):
        v = re.sub(r'食べログ\d\.\d+点(?:以上|超)?[、。]?', '', m.group(2))
        v = re.sub(r'￥[\d,]*～(?:￥[\d,]+)?[、。]?', '', v)
        return m.group(1) + v
    return re.sub(r'^(description: ")(.*)$', fix, text, flags=re.M)


def drop_affiliate_duplicates(text):
    """affiliate_links から食べログ・ホットペッパーを削除（tabelog_url / hotpepper_url を正とする）"""
    m = re.search(r'^affiliate_links:\n((?:  .*\n)+)', text, re.M)
    if not m:
        return text
    items = re.findall(r'  - label: (.*)\n    url: (.*)\n', m.group(1))
    kept = [(l, u) for l, u in items if 'tabelog.com' not in u and 'hotpepper.jp' not in u]
    block = ''.join(f'  - label: {l}\n    url: {u}\n' for l, u in kept)
    return text.replace(m.group(0), ('affiliate_links:\n' + block) if kept else '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--drop', nargs='*', default=[])
    args = ap.parse_args()

    changed = 0
    for path, text in orphan_pages():
        if args.list:
            print(os.path.relpath(path, ROOT))
            continue
        new = drop_affiliate_duplicates(clean_description(drop_keys(text, set(args.drop))))
        if new != text:
            open(path, 'w', encoding='utf-8').write(new)
            changed += 1
    if not args.list:
        print(f'更新した孤立ページ: {changed}件')


if __name__ == '__main__':
    main()
