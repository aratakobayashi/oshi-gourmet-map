#!/usr/bin/env python3
"""
geocode_gsi.py
住所から座標を取り直す（国土地理院 アドレス検索API。無料・キー不要）。
地域の中心の座標が入っている店（ほかの店と座標がまったく同じ店）が多く、
地図のピン・「近くの聖地グルメ」がずれていたため。

更新するのは次のとき:
  - 結果が「番」「号」まで一致した（番地レベル）
  - 結果が「丁目」まで一致し、今の座標がほかの店と同じ（地域の中心の座標）だった
結果が今の座標から 30km 以上離れているものは、住所の誤りの可能性があるので更新しない。

使い方:
  python scripts/geocode_gsi.py            # 試算だけ（shops.json は書き換えない）
  python scripts/geocode_gsi.py --write    # shops.json を更新する
結果は scripts/.cache/gsi_geocode.json に保存し、2回目以降は問い合わせない。
"""
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOPS = os.path.join(ROOT, 'data', 'shops.json')
CACHE = os.path.join(ROOT, 'scripts', '.cache', 'gsi_geocode.json')
API = 'https://msearch.gsi.go.jp/address-search/AddressSearch?q='


def normalize(addr):
    """全角を半角に、数字の間のダッシュ類を - にそろえる"""
    a = unicodedata.normalize('NFKC', addr)
    return re.sub(r'(?<=\d)[ー−–—‐-]+(?=\d)', '-', a).strip()


def km(a, b):
    r = math.pi / 180
    h = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def lookup(addr, cache):
    if addr in cache:
        return cache[addr]
    req = urllib.request.Request(API + urllib.parse.quote(addr), headers={'User-Agent': 'oshi-gourmet-map geocoder'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception as e:
        print('  error', addr, e)
        return None
    res = None
    if data:
        lng, lat = data[0]['geometry']['coordinates']
        res = {'lat': lat, 'lng': lng, 'title': data[0]['properties']['title']}
    cache[addr] = res
    time.sleep(0.6)
    return res


def main():
    write = '--write' in sys.argv
    shops = json.load(open(SHOPS, encoding='utf-8'))
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}

    shared = Counter((round(s['lat'], 4), round(s['lng'], 4)) for s in shops if s.get('lat'))
    stats = Counter()
    moved = []
    for i, s in enumerate(shops):
        addr = s.get('address') or ''
        if not re.search(r'\d', unicodedata.normalize('NFKC', addr)):
            stats['住所に番地なし（対象外）'] += 1
            continue
        res = lookup(normalize(addr), cache)
        if i % 100 == 0:
            json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f'{i}/{len(shops)}', flush=True)
        if not res:
            stats['見つからない'] += 1
            continue
        t = res['title']
        exact = bool(re.search(r'[番号]$|番\S*号$|\d+$', t)) and ('番' in t or '号' in t)
        chome = t.endswith('丁目')
        was_shared = s.get('lat') and shared[(round(s['lat'], 4), round(s['lng'], 4))] >= 2
        if not (exact or (chome and (was_shared or not s.get('lat')))):
            stats['精度が足りない（更新しない）'] += 1
            continue
        if s.get('lat'):
            d = km((s['lat'], s['lng']), (res['lat'], res['lng']))
            if d > 30:
                stats['30km以上離れている（更新しない）'] += 1
                moved.append((s['id'], s['name'], addr, t, round(d, 1), 'skip'))
                continue
        else:
            d = None
        stats['番地レベルで更新' if exact else '丁目レベルで更新'] += 1
        if d is not None and d >= 0.2:
            moved.append((s['id'], s['name'], addr, t, round(d, 2), 'update'))
        s['lat'], s['lng'] = round(res['lat'], 6), round(res['lng'], 6)

    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    for k, v in stats.most_common():
        print(f'{k}: {v}')
    big = [m for m in moved if m[5] == 'update']
    print(f'200m以上動いた店: {len(big)}（1km以上 {sum(1 for m in big if m[4] >= 1)}）')
    for m in sorted(moved, key=lambda m: -m[4])[:15]:
        print('  ', m)
    if write:
        with open(SHOPS, 'w', encoding='utf-8') as f:
            f.write(json.dumps(shops, ensure_ascii=False, indent=2) + '\n')
        print('shops.json を更新しました')


if __name__ == '__main__':
    main()
