"""
check_articles.py
特集記事（_posts/）の店舗IDを data/shops.json と照合する。

- 記事の front matter の shop_ids と、本文の inline-shop-card / inline-shop-grid に書かれたIDを調べる
- shops.json にないID（掲載をやめた店・書き間違い）を一覧にする
- --fix を付けると、REMAP にあるIDは置き換え、それ以外のないIDは外し、
  shop_ids を「front matter の順 → 本文に出てくる順」の和集合にそろえる
  （shop_ids は店舗ページの「この店が載っている記事」と、記事末尾の「この記事のお店」に使う）

使い方:
  python scripts/check_articles.py          # 確認だけ
  python scripts/check_articles.py --fix    # 直して保存
"""

import argparse
import glob
import json
import re

SHOPS_PATH = 'data/shops.json'

# 記事に書かれていたが shops.json では別IDになっている店（店名で確認済み）
REMAP = {
    'sixtones-minmin-hachioji': 'sixtones-7c39702f-',          # みんみんラーメン 本店
    'sixtones-ushioidochu-nagoya': 'sixtones-e6599dc3-',       # 牛追道中
    'snowman-yoshidaya-tachiaigawa': 'snowman-07838f1d-20250505',  # 立会川 吉田家
    'kodoku_no_gurume-a9a7c2c5-': 'snowman-a9a7c2c5-202502',   # 伊勢屋食堂（孤独のグルメにも登場）
    'neajoy-78570ead-202408': 'neajoy-0ccad40f-202408',        # 徳造丸 海鮮家 箱根湯本店
}

INLINE = re.compile(r'(\{%-?\s*include\s+inline-shop-(card|grid)\.html\s+(?:shop_id|ids)=")([^"]*)("\s*-?%\})')


def split_post(text):
    _, fm, body = text.split('---', 2)
    return fm, body


def fm_ids(fm):
    m = re.search(r'^shop_ids:\n((?:  - .*\n)+)', fm, re.M)
    return [x.strip().strip('"\'') for x in re.findall(r'^  - (.*)$', m.group(1), re.M)] if m else []


def set_fm_ids(fm, ids):
    block = 'shop_ids:\n' + ''.join(f'  - {i}\n' for i in ids)
    if re.search(r'^shop_ids:\n((?:  - .*\n)+)', fm, re.M):
        return re.sub(r'^shop_ids:\n((?:  - .*\n)+)', block, fm, count=1, flags=re.M)
    if re.search(r'^shop_ids:\s*(\[\])?\s*$', fm, re.M):
        return re.sub(r'^shop_ids:.*\n', block, fm, count=1, flags=re.M)
    return fm.rstrip('\n') + '\n' + block


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix', action='store_true')
    args = ap.parse_args()
    known = {s['id'] for s in json.load(open(SHOPS_PATH, encoding='utf-8'))}

    def fix_id(i):
        i = REMAP.get(i, i)
        return i if i in known else None

    problems = 0
    for path in sorted(glob.glob('_posts/*.md')):
        text = open(path, encoding='utf-8').read()
        fm, body = split_post(text)
        before = fm_ids(fm)
        inline = []
        for m in INLINE.finditer(body):
            inline += [x.strip() for x in m.group(3).split(',') if x.strip()]
        bad = sorted({i for i in before + inline if i not in known})
        if bad:
            problems += len(bad)
            print(f'{path}: shops.json にないID {len(bad)}件: {", ".join(bad)}')
        if not args.fix:
            continue

        def repl(m):
            ids = [x for x in (fix_id(x.strip()) for x in m.group(3).split(',') if x.strip()) if x]
            ids = list(dict.fromkeys(ids))
            if not ids:
                return '\x00'  # 消した印。前後の空行ごと詰める
            kind = 'card' if len(ids) == 1 and m.group(2) == 'card' else 'grid'
            key = 'shop_id' if kind == 'card' else 'ids'
            return f'{{% include inline-shop-{kind}.html {key}="{",".join(ids)}" %}}'

        body2 = re.sub(r'\n*\x00\n*', '\n\n', INLINE.sub(repl, body))
        inline2 = []
        for m in INLINE.finditer(body2):
            inline2 += [x.strip() for x in m.group(3).split(',') if x.strip()]
        ids = list(dict.fromkeys([x for x in (fix_id(i) for i in before) if x] + inline2))
        fm2 = set_fm_ids(fm, ids) if ids != before else fm
        if fm2 != fm or body2 != body:
            open(path, 'w', encoding='utf-8').write('---' + fm2 + '---' + body2)
            print(f'  → 修正: shop_ids {len(before)} → {len(ids)}')
    if not args.fix:
        print(f'shops.json にないID: 計{problems}件' + ('（--fix で直せます）' if problems else ''))


if __name__ == '__main__':
    main()
