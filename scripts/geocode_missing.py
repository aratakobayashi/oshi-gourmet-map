#!/usr/bin/env python3
"""
geocode_missing.py
shops.json 内の lat/lng が null のアイテムを一括ジオコーディング

優先順位:
  1. tabelog_url がある場合 → tabelog JSON-LD から精確な座標取得
  2. 住所がある場合 → Nominatim API（1秒間隔）

使い方:
  python3 scripts/geocode_missing.py
  python3 scripts/geocode_missing.py --group kingprince --limit 50
  python3 scripts/geocode_missing.py --dry-run
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request

SHOPS_JSON = 'data/shops.json'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'


def normalize(text):
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif ch == '　':
            result.append(' ')
        elif ch in ('−', '－'):
            result.append('-')
        else:
            result.append(ch)
    return ''.join(result)


def simplify_address(address):
    address = normalize(address)
    address = re.sub(r'^〒\d{3}[-－]\d{4}\s*', '', address).strip()
    address = re.sub(r'\s*[※\*].+$', '', address).strip()
    address = re.sub(r'\d+[-－]\d+.*$', '', address).strip()
    address = re.sub(r'(\d+丁目)\d+.*$', r'\1', address).strip()
    address = re.sub(r'\s*(B?\d+F|地下\d+階|\d+階).*$', '', address).strip()
    return address


def geocode_query(query):
    params = urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'jp',
    })
    req = urllib.request.Request(
        f'{NOMINATIM_URL}?{params}',
        headers={'User-Agent': 'oshi-gourmet-map/1.0 (+https://gourmet.oshikatsu-guide.com)'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
        if results:
            lat, lng = float(results[0]['lat']), float(results[0]['lon'])
            if 24 <= lat <= 46 and 122 <= lng <= 154:
                return lat, lng
    except Exception as e:
        print(f'    Nominatimエラー: {e}')
    return None, None


def geocode_from_tabelog(url):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='replace')
        m = re.search(r'"latitude"\s*:\s*([\d.]+)[^}]*"longitude"\s*:\s*([\d.]+)', html)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if 24 <= lat <= 46 and 122 <= lng <= 154:
                return lat, lng
    except Exception as e:
        print(f'    tabelog取得エラー: {e}')
    return None, None


def geocode_shop(shop):
    name = shop.get('name', '')
    address = shop.get('address', '')
    tabelog_url = shop.get('tabelog_url', '')

    # 1. tabelog URL → JSON-LD
    if tabelog_url and 'tabelog.com' in tabelog_url:
        print(f'    [tabelog] {tabelog_url[:60]}')
        lat, lng = geocode_from_tabelog(tabelog_url)
        time.sleep(1)
        if lat and lng:
            return lat, lng

    # 2. 住所 → Nominatim
    if address:
        simplified = simplify_address(address)
        if simplified:
            print(f'    [住所] {simplified[:50]}')
            lat, lng = geocode_query(simplified)
            time.sleep(1)
            if lat and lng:
                return lat, lng

            # リトライ: 丁目変換
            converted = re.sub(r'(\d+)-(\d+)', r'\1丁目\2番', simplified)
            if converted != simplified:
                print(f'    [住所リトライ] {converted[:50]}')
                lat, lng = geocode_query(converted)
                time.sleep(1)
                if lat and lng:
                    return lat, lng

    # 3. 店名 + 都道府県 → Nominatim
    if name and address:
        pref_m = re.match(r'(東京都|北海道|(?:京都|大阪)府|\S+?[都道府県])', address)
        if pref_m:
            query = f'{pref_m.group(1)} {name}'
            print(f'    [店名+都道府県] {query}')
            lat, lng = geocode_query(query)
            time.sleep(1)
            if lat and lng:
                return lat, lng

    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', help='特定グループのみ対象')
    parser.add_argument('--limit', type=int, default=0, help='処理件数上限（0=全件）')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    # 座標なしアイテムを抽出
    targets = [s for s in shops if not s.get('lat') or not s.get('lng')]
    if args.group:
        targets = [s for s in targets if s.get('group') == args.group]

    print(f'座標なし: {len(targets)}件')
    if args.group:
        print(f'（グループ: {args.group}）')

    if args.limit:
        targets = targets[:args.limit]
        print(f'（--limit {args.limit} で先頭{args.limit}件のみ処理）')

    if args.dry_run:
        for s in targets[:20]:
            print(f'  {s["name"]} | {s.get("address","")[:50]} | tabelog={bool(s.get("tabelog_url"))}')
        print(f'  ...(合計 {len(targets)}件)')
        return

    # ジオコーディング実行
    success = 0
    failed = 0
    shop_by_id = {s['id']: s for s in shops}

    for i, target in enumerate(targets, 1):
        print(f'[{i}/{len(targets)}] {target["name"]}')
        lat, lng = geocode_shop(target)
        if lat and lng:
            shop_by_id[target['id']]['lat'] = lat
            shop_by_id[target['id']]['lng'] = lng
            print(f'    → ✓ ({lat:.4f}, {lng:.4f})')
            success += 1
        else:
            print(f'    → 失敗')
            failed += 1

    print(f'\n完了: 成功 {success}件 / 失敗 {failed}件')

    updated = list(shop_by_id.values())
    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)
    print(f'{SHOPS_JSON} を更新しました')


if __name__ == '__main__':
    main()
