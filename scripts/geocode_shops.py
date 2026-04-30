"""
geocode_shops.py
住所から緯度・経度を取得するスクリプト（Nominatim / OpenStreetMap 無料API）

使い方:
  python scripts/geocode_shops.py --input scripts/matched_yonino.json --output scripts/geocoded_yonino.json
"""

import urllib.request
import urllib.parse
import json
import argparse
import time
import re

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'


def normalize(text: str) -> str:
    """全角英数字・記号を半角に変換"""
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:  # 全角！〜
            result.append(chr(code - 0xFEE0))
        elif ch == '　':  # 全角スペース
            result.append(' ')
        elif ch == '−':  # 全角マイナス
            result.append('-')
        else:
            result.append(ch)
    return ''.join(result)


def simplify_address(address: str) -> str:
    """住所を丁目・番地以降を除いた形に短縮する"""
    address = normalize(address)
    # 番地（数字-数字）以降を除去
    address = re.sub(r'\d+[-－]\d+.*$', '', address).strip()
    # ビル名・フロア情報を除去
    address = re.sub(r'\s*(B?\d+F|地下\d+階|[0-9]+階).*$', '', address).strip()
    return address


def geocode(address: str) -> tuple:
    """住所 → (lat, lng) を返す。失敗したら (None, None)"""
    query = simplify_address(address)
    params = urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'jp',
    })
    url = f'{NOMINATIM_URL}?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
        if results:
            return float(results[0]['lat']), float(results[0]['lon'])
    except Exception as e:
        print(f'    エラー: {e}')
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        shops = json.load(f)

    success = 0
    skip = 0

    for i, shop in enumerate(shops):
        address = shop.get('address', '').strip()

        if shop.get('lat') and shop.get('lng'):
            print(f'[{i+1}/{len(shops)}] スキップ（座標済み）: {shop["name"]}')
            skip += 1
            continue

        if not address:
            print(f'[{i+1}/{len(shops)}] スキップ（住所なし）: {shop["name"]}')
            skip += 1
            continue

        print(f'[{i+1}/{len(shops)}] {shop["name"]}')
        print(f'    住所: {address}')
        lat, lng = geocode(address)

        if lat and lng:
            shop['lat'] = lat
            shop['lng'] = lng
            print(f'    → lat: {lat}, lng: {lng}')
            success += 1
        else:
            print(f'    → 取得失敗')

        time.sleep(1)  # Nominatimの利用規約: 1秒以上間隔をあける

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n完了: 成功 {success}件 / スキップ {skip}件 / 失敗 {len(shops)-success-skip}件')
    print(f'→ {args.output} に保存しました')


if __name__ == '__main__':
    main()
