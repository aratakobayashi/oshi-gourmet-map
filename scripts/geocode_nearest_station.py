#!/usr/bin/env python3
"""
geocode_nearest_station.py
nearest_stationが未設定の店舗に対してlat/lngからOverpass APIで最寄り駅を取得する。

使い方:
  python scripts/geocode_nearest_station.py --dry-run
  python scripts/geocode_nearest_station.py --apply
  python scripts/geocode_nearest_station.py --group yonino --apply
"""

import json
import math
import time
import urllib.request
import urllib.parse
import os
import argparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON  = os.path.join(SCRIPTS_DIR, '../data/shops.json')
CACHE_JSON  = os.path.join(SCRIPTS_DIR, 'nearest_station_cache.json')

OVERPASS_URL   = 'https://overpass-api.de/api/interpreter'
SEARCH_RADIUS  = 1200  # メートル（徒歩約15分圏内）
SLEEP          = 1.5   # 秒（Overpass APIへの負荷軽減）


def haversine(lat1, lng1, lat2, lng2):
    """2点間の直線距離をメートルで返す"""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def walking_minutes(dist_m):
    """直線距離→徒歩分数（道のり係数1.3、歩行速度80m/min）"""
    return max(1, round(dist_m * 1.3 / 80))


def find_nearest_station(lat, lng):
    """Overpass APIで半径SEARCH_RADIUS内の最寄り駅を検索し '○○駅 徒歩X分' を返す。なければNone。"""
    query = f'''[out:json][timeout:15];
(
  node["railway"="station"](around:{SEARCH_RADIUS},{lat},{lng});
  node["railway"="halt"](around:{SEARCH_RADIUS},{lat},{lng});
  node["railway"="tram_stop"](around:{SEARCH_RADIUS},{lat},{lng});
);
out body;'''

    data = urllib.parse.urlencode({'data': query}).encode()
    req  = urllib.request.Request(OVERPASS_URL, data=data, headers={
        'User-Agent': 'oshi-gourmet-map/1.0 (https://gourmet.oshikatsu-guide.com)'
    })
    with urllib.request.urlopen(req, timeout=20) as res:
        result = json.loads(res.read())

    elements = result.get('elements', [])
    if not elements:
        return None

    best_name = None
    best_dist = float('inf')
    for el in elements:
        elat = el.get('lat')
        elng = el.get('lon')
        if not elat or not elng:
            continue
        dist = haversine(lat, lng, elat, elng)
        if dist < best_dist:
            best_dist = dist
            tags = el.get('tags', {})
            # 日本語名を優先
            name = tags.get('name:ja') or tags.get('name', '')
            best_name = name

    if not best_name:
        return None

    if not best_name.endswith('駅'):
        best_name += '駅'

    mins = walking_minutes(best_dist)
    return f'{best_name} 徒歩{mins}分'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group',   default='', help='対象グループ（省略=全件）')
    parser.add_argument('--apply',   action='store_true', help='shops.jsonに反映')
    parser.add_argument('--dry-run', action='store_true', help='確認のみ（書き込みなし）')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    targets = [
        s for s in shops
        if not s.get('nearest_station')
        and s.get('lat') and s.get('lng')
        and (not args.group or s.get('group') == args.group)
    ]
    print(f'対象: {len(targets)}件（nearest_stationなし・lat/lngあり）\n')

    if args.dry_run:
        for s in targets[:20]:
            print(f'  [{s["group"]}] {s["name"]} ({s["lat"]}, {s["lng"]})')
        if len(targets) > 20:
            print(f'  ... 他{len(targets)-20}件')
        return

    # キャッシュ読み込み
    cache = {}
    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, encoding='utf-8') as f:
            cache = json.load(f)
        print(f'キャッシュ: {len(cache)}件')

    found = 0
    not_found = 0
    errors = 0

    for i, shop in enumerate(targets):
        shop_id = shop['id']
        print(f'[{i+1}/{len(targets)}] {shop["name"]}', end=' ', flush=True)

        if shop_id in cache:
            val = cache[shop_id]
            print(f'(キャッシュ: {val or "なし"})')
            continue

        try:
            result = find_nearest_station(shop['lat'], shop['lng'])
            cache[shop_id] = result or ''
            time.sleep(SLEEP)

            if result:
                print(f'→ {result}')
                found += 1
            else:
                print('→ 圏内に駅なし')
                not_found += 1

        except Exception as e:
            print(f'エラー: {e}')
            cache[shop_id] = ''
            errors += 1
            time.sleep(SLEEP)

        # 10件ごとにキャッシュ保存
        if (i + 1) % 10 == 0:
            with open(CACHE_JSON, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

    with open(CACHE_JSON, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f'\n完了: 取得 {found}件 / 圏外 {not_found}件 / エラー {errors}件')
    print(f'→ {CACHE_JSON}')

    if args.apply:
        apply_to_shops(shops, cache)


def apply_to_shops(shops, cache):
    updated = 0
    for shop in shops:
        val = cache.get(shop['id'])
        if val and not shop.get('nearest_station'):
            shop['nearest_station'] = val
            updated += 1

    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'shops.json 更新: {updated}店舗')


if __name__ == '__main__':
    main()
