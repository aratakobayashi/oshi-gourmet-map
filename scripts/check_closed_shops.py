#!/usr/bin/env python3
"""
check_closed_shops.py
食べログページのタイトルを確認して閉店フラグ(closed: true)を付ける。

使い方:
  python scripts/check_closed_shops.py --dry-run    # 対象一覧のみ表示
  python scripts/check_closed_shops.py              # キャッシュに結果保存
  python scripts/check_closed_shops.py --apply      # shops.jsonに反映
  python scripts/check_closed_shops.py --group yonino --apply
"""

import json
import time
import urllib.request
import os
import argparse
import re

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON  = os.path.join(SCRIPTS_DIR, '../data/shops.json')
CACHE_JSON  = os.path.join(SCRIPTS_DIR, 'closed_shops_cache.json')

DIRECT_URL_RE = re.compile(r'tabelog\.com/[a-z]+/A\d+/A\d+/\d+')
SLEEP = 2.0
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def is_closed_page(html: str) -> bool:
    """食べログページが閉店かどうか判定"""
    # タイトルに（閉店）が含まれる
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
    if title_match:
        title = title_match.group(1)
        if '閉店' in title:
            return True

    # OGタイトルに閉店が含まれる
    og_match = re.search(r'og:title[^>]+content="([^"]+)"', html)
    if og_match and '閉店' in og_match.group(1):
        return True

    # 店舗ページ固有の閉店バナー
    if 'rstdtl-top-diffinfo' in html and '閉店' in html:
        # 報告リンクではなく実際の閉店表示か確認
        banner_match = re.search(r'rstdtl-top-diffinfo[^>]*>.*?閉店.*?</div>', html, re.DOTALL)
        if banner_match:
            return True

    return False


def fetch_title(url: str) -> tuple[bool, str]:
    """URLをフェッチして (閉店かどうか, タイトル) を返す"""
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'ja,en;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=12) as res:
        # タイトルだけ取れれば十分なので先頭4KBだけ読む
        chunk = res.read(4096).decode('utf-8', errors='replace')

    title_match = re.search(r'<title[^>]*>([^<]+)</title>', chunk)
    title = title_match.group(1).strip() if title_match else ''

    # 先頭4KBでタイトルが取れなければ全体を読む
    if not title:
        with urllib.request.urlopen(urllib.request.Request(url, headers={
            'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.9'
        }), timeout=12) as res:
            html = res.read().decode('utf-8', errors='replace')
        return is_closed_page(html), ''

    closed = '閉店' in title
    return closed, title


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group',   default='', help='対象グループ（省略=全件）')
    parser.add_argument('--apply',   action='store_true', help='shops.jsonに反映')
    parser.add_argument('--dry-run', action='store_true', help='対象一覧のみ表示')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    # 直接URLを持つ店舗のみ対象
    targets = [
        s for s in shops
        if s.get('tabelog_url') and DIRECT_URL_RE.search(s.get('tabelog_url', ''))
        and not s.get('closed')
        and (not args.group or s.get('group') == args.group)
    ]
    print(f'対象: {len(targets)}件（直接tabelog_url保有・未チェック）\n')

    if args.dry_run:
        for s in targets[:20]:
            print(f'  [{s["group"]}] {s["name"]}')
        if len(targets) > 20:
            print(f'  ... 他{len(targets)-20}件')
        return

    # キャッシュ読み込み
    cache = {}
    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, encoding='utf-8') as f:
            cache = json.load(f)
        print(f'キャッシュ: {len(cache)}件')

    closed_found = 0
    errors = 0

    for i, shop in enumerate(targets):
        shop_id = shop['id']
        print(f'[{i+1}/{len(targets)}] {shop["name"]}', end=' ', flush=True)

        if shop_id in cache:
            status = cache[shop_id]
            print(f'(キャッシュ: {"閉店" if status else "営業中"})')
            if status:
                closed_found += 1
            continue

        try:
            closed, title = fetch_title(shop['tabelog_url'])
            cache[shop_id] = closed
            time.sleep(SLEEP)

            if closed:
                print(f'→ 【閉店】{title[:50]}')
                closed_found += 1
            else:
                print(f'→ 営業中')

        except Exception as e:
            print(f'エラー: {e}')
            cache[shop_id] = None
            errors += 1
            time.sleep(SLEEP)

        if (i + 1) % 20 == 0:
            with open(CACHE_JSON, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

    with open(CACHE_JSON, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f'\n完了: 閉店 {closed_found}件 / エラー {errors}件 / 計{len(targets)}件')

    if args.apply:
        apply_to_shops(shops, cache)


def apply_to_shops(shops, cache):
    updated = 0
    for shop in shops:
        if cache.get(shop['id']) is True:
            shop['closed'] = True
            updated += 1

    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'shops.json 更新: {updated}店舗に closed: true を付与')


if __name__ == '__main__':
    main()
