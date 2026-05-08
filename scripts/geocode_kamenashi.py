"""
geocode_kamenashi.py
亀梨データ専用ジオコーディング
- 店名に地域情報（原宿, 銀座 etc.）が含まれる場合はそれを使って検索
- 海外店舗はcountrycodes制限を外す
- Overpass API（OSM）でも補完

使い方:
  python scripts/geocode_kamenashi.py --input scripts/scraped_kamenashi.json --output scripts/geocoded_kamenashi.json

【注意】Nominatimのsearch結果に含まれるdisplay_nameを住所フィールドに使ってはいけない。
display_nameはOSMのラベル文字列であり、正確な日本語住所ではない。
また、店名検索では全く別の場所に誤マッチすることがある（例：「日生家」→沖縄の神殿）。
このスクリプトはlat/lngのみ取得し、addressフィールドは更新しない設計にしている。
"""

import urllib.request
import urllib.parse
import json
import argparse
import time
import re

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
OVERPASS_URL = 'https://overpass-api.de/api/interpreter'

# 店名に含まれる地域キーワード → 検索用エリア名
AREA_MAP = {
    '銀座': '銀座 東京',
    'GINZA': '銀座 東京',
    '原宿': '原宿 東京',
    '新宿': '新宿 東京',
    '渋谷': '渋谷 東京',
    '恵比寿': '恵比寿 東京',
    '六本木': '六本木 東京',
    '池袋': '池袋 東京',
    '浅草': '浅草 東京',
    'みなとみらい': 'みなとみらい 横浜',
    '横浜': '横浜',
    '鳥取': '鳥取市',
    '京都': '京都市',
    '大阪': '大阪市',
    '福岡': '福岡市',
    '博多': '博多 福岡',
    '名古屋': '名古屋市',
    '札幌': '札幌市',
}

# 既知の海外店舗（店名 → (lat, lng)）
OVERSEAS_COORDS = {
    'ALES SHOP': (47.5553, 7.5905),      # Basel, Switzerland
    'Beschle': (47.5596, 7.5886),         # Basel, Switzerland
    'Le Rhin Bleu': (47.5573, 7.5913),    # Basel, Rhine area
}


def nominatim_search(query: str, countrycodes: str = 'jp') -> tuple:
    params = {'q': query, 'format': 'json', 'limit': 1}
    if countrycodes:
        params['countrycodes'] = countrycodes
    url = f'{NOMINATIM_URL}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
        if results:
            return float(results[0]['lat']), float(results[0]['lon'])
    except Exception as e:
        print(f'      Nominatimエラー: {e}')
    return None, None


def overpass_search(name: str) -> tuple:
    """Overpass APIで店名を検索"""
    escaped = name.replace('"', '\\"')
    query = f'[out:json][timeout:15];node["name"="{escaped}"]["amenity"];out body 1;'
    data = urllib.parse.urlencode({'data': query}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=data, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            result = json.loads(r.read())
        elements = result.get('elements', [])
        if elements:
            return float(elements[0]['lat']), float(elements[0]['lon'])
    except Exception as e:
        print(f'      Overpassエラー: {e}')
    return None, None


def extract_area(name: str) -> str:
    """店名から地域キーワードを抽出"""
    for keyword, area in AREA_MAP.items():
        if keyword in name:
            return area
    return ''


def simplify_name(name: str) -> str:
    """「〇〇 原宿店」→「〇〇 原宿」のように末尾の「店」を除去"""
    return re.sub(r'店$', '', name.strip())


def geocode_shop(shop: dict) -> tuple:
    name = shop.get('name', '')
    address = shop.get('address', '').strip()

    # 1. 住所があればNominatimで検索
    if address:
        lat, lng = nominatim_search(address)
        time.sleep(1)
        if lat and lng:
            return lat, lng

    # 2. 海外既知座標
    if name in OVERSEAS_COORDS:
        return OVERSEAS_COORDS[name]

    # 3. 店名でOverpass検索（OSMに登録されている有名店）
    lat, lng = overpass_search(name)
    time.sleep(1)
    if lat and lng:
        return lat, lng

    # 4. 店名を簡略化してOverpass検索
    simple = simplify_name(name)
    if simple != name:
        lat, lng = overpass_search(simple)
        time.sleep(1)
        if lat and lng:
            return lat, lng

    # 5. 地域ヒント付きでNominatim検索
    area = extract_area(name)
    if area:
        chain = re.split(r'[\s　]', name)[0]  # 店名の最初の単語（チェーン名）
        lat, lng = nominatim_search(f'{chain} {area}')
        time.sleep(1)
        if lat and lng:
            return lat, lng
        # チェーン名だけでも試す
        lat, lng = nominatim_search(area)
        time.sleep(1)
        if lat and lng:
            return lat, lng

    # 6. 店名のみ（国制限なし）で最後の試行
    lat, lng = nominatim_search(name, countrycodes='')
    time.sleep(1)
    return lat, lng


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        shops = json.load(f)

    success = 0
    skip = 0
    fail = 0

    for i, shop in enumerate(shops):
        if shop.get('lat') and shop.get('lng'):
            print(f'[{i+1}/{len(shops)}] スキップ（座標済み）: {shop["name"]}')
            skip += 1
            continue

        print(f'[{i+1}/{len(shops)}] {shop["name"]}')
        lat, lng = geocode_shop(shop)

        if lat and lng:
            shop['lat'] = lat
            shop['lng'] = lng
            print(f'    → {lat:.4f}, {lng:.4f}')
            success += 1
        else:
            print(f'    → 取得失敗')
            fail += 1

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n完了: 成功 {success}件 / スキップ {skip}件 / 失敗 {fail}件')
    print(f'→ {args.output} に保存しました')


if __name__ == '__main__':
    main()
