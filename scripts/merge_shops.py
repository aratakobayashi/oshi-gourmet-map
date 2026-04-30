"""
merge_shops.py
新規お店データをshops.jsonにマージするスクリプト

使い方:
  python scripts/merge_shops.py --input scripts/geocoded_yonino.json --output data/shops.json
"""

import json
import re
import argparse


def make_id(group: str, name: str, visited_date: str) -> str:
    """ユニークIDを生成"""
    slug = re.sub(r'[^\w]', '', name.lower().replace(' ', '_'))[:20]
    date_slug = visited_date.replace('-', '')[:8]
    return f'{group}-{slug}-{date_slug}'


def extract_prefecture_city(address: str) -> tuple:
    """住所から都道府県・市区町村を抽出"""
    prefecture = ''
    city = ''
    if not address:
        return prefecture, city

    # 都道府県
    pref_m = re.match(r'^(東京都|北海道|(?:京都|大阪)府|.{2,3}県)', address)
    if pref_m:
        prefecture = pref_m.group(1)
        rest = address[len(prefecture):]
        # 市区町村
        city_m = re.match(r'^(.{2,6}?[市区町村])', rest)
        if city_m:
            city = city_m.group(1)

    return prefecture, city


def normalize_shop(raw: dict, existing_ids: set):
    """スクレイピングデータをshops.jsonのスキーマに変換"""
    # 座標なしは登録しない
    if not raw.get('lat') or not raw.get('lng'):
        return None

    name = raw.get('name', '').strip()
    if not name:
        return None

    group = raw.get('group', 'yonino')
    visited_date = raw.get('visited_date', '')
    address = raw.get('address', '')
    prefecture, city = extract_prefecture_city(address)

    shop_id = make_id(group, name, visited_date)
    # IDが重複したら連番を付与
    base_id = shop_id
    counter = 2
    while shop_id in existing_ids:
        shop_id = f'{base_id}-{counter}'
        counter += 1

    return {
        'id': shop_id,
        'name': name,
        'genre': raw.get('genre', 'その他'),
        'prefecture': prefecture,
        'city': city,
        'address': address,
        'lat': raw.get('lat'),
        'lng': raw.get('lng'),
        'youtube_id': raw.get('youtube_id', ''),
        'source_video_title': raw.get('source_video_title', ''),
        'visited_date': visited_date,
        'members': raw.get('members', []),
        'groups': raw.get('groups', [group]),
        'group': group,
        'nearest_station': raw.get('nearest_station', ''),
        'description': raw.get('description', ''),
        'tags': [],
        'affiliate_links': [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='新規データJSON')
    parser.add_argument('--dry-run', action='store_true', help='実際には書き込まず結果だけ表示')
    args = parser.parse_args()

    output = 'data/shops.json'

    with open(args.input, encoding='utf-8') as f:
        new_shops_raw = json.load(f)

    with open(output, encoding='utf-8') as f:
        existing = json.load(f)

    # 既存データのID・youtube_id・店名セット
    existing_ids = {s['id'] for s in existing}
    existing_youtube_ids = {s['youtube_id'] for s in existing if s.get('youtube_id')}
    existing_names = {s['name'] for s in existing}

    added = []
    skipped_no_coord = 0
    skipped_duplicate = 0

    for raw in new_shops_raw:
        shop = normalize_shop(raw, existing_ids)

        if shop is None:
            skipped_no_coord += 1
            continue

        # 飲食店以外を除外
        exclude_names = ['ダイソー', '西公園', 'IKEA', '島忠', 'マクドナルド']
        if any(ex in shop['name'] for ex in exclude_names):
            print(f'  除外スキップ: {shop["name"]}')
            skipped_duplicate += 1
            continue

        # 重複チェック（店名 or youtube_id）
        if shop['name'] in existing_names:
            print(f'  重複スキップ（店名）: {shop["name"]}')
            skipped_duplicate += 1
            continue

        added.append(shop)
        existing_ids.add(shop['id'])
        existing_names.add(shop['name'])

    print(f'\n=== マージ結果 ===')
    print(f'既存: {len(existing)}件')
    print(f'新規追加: {len(added)}件')
    print(f'スキップ（座標なし）: {skipped_no_coord}件')
    print(f'スキップ（重複）: {skipped_duplicate}件')
    print(f'マージ後合計: {len(existing) + len(added)}件')

    print(f'\n追加されるお店:')
    for s in added:
        print(f'  [{s["visited_date"]}] {s["name"]} ({s["prefecture"]} {s["city"]})')

    if args.dry_run:
        print('\n（dry-runモード: 書き込みをスキップしました）')
        return

    merged = existing + added
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f'\n→ {output} に保存しました')


if __name__ == '__main__':
    main()
