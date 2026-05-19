"""
add_hotpepper_urls.py
ホットペッパーグルメAPIで各店舗のURLを自動付与する

使い方:
  export HOTPEPPER_API_KEY="your_key"
  python scripts/add_hotpepper_urls.py           # 実行
  python scripts/add_hotpepper_urls.py --dry-run # 確認のみ
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
import argparse

HOTPEPPER_API = 'https://webservice.recruit.co.jp/hotpepper/gourmet/v1/'
SEARCH_RANGE = 5   # 1=300m 2=500m 3=1000m 4=2000m 5=3000m
SEARCH_COUNT = 5   # 候補件数
SLEEP_SEC = 0.5    # APIレート制限対策


def normalize(name):
    """店名を正規化して比較しやすくする"""
    name = re.sub(r'[\s　・\-－~〜（）()【】「」]', '', name)
    name = name.lower()
    # 全角→半角
    name = name.translate(str.maketrans(
        'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
        '０１２３４５６７８９',
        'abcdefghijklmnopqrstuvwxyz'
        'abcdefghijklmnopqrstuvwxyz'
        '0123456789'
    ))
    return name


def name_match_score(shop_name, candidate_name):
    """店名の一致スコア（0.0〜1.0）"""
    a = normalize(shop_name)
    b = normalize(candidate_name)
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.8
    # 共通文字数の割合
    common = sum(1 for c in a if c in b)
    return common / max(len(a), len(b), 1)


def search_hotpepper(api_key, name, lat, lng):
    """ホットペッパーAPIで店を検索し、最も名前が近いものを返す"""
    params = {
        'key': api_key,
        'keyword': name,
        'lat': lat,
        'lng': lng,
        'range': SEARCH_RANGE,
        'count': SEARCH_COUNT,
        'format': 'json',
    }
    url = HOTPEPPER_API + '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        candidates = data.get('results', {}).get('shop', [])
    except Exception as e:
        print(f'    APIエラー: {e}')
        return None, 0.0

    if not candidates:
        return None, 0.0

    # 名前スコアが最も高い候補を選ぶ
    best = max(candidates, key=lambda c: name_match_score(name, c['name']))
    score = name_match_score(name, best['name'])
    return best, score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='書き込まずに結果だけ表示')
    parser.add_argument('--min-score', type=float, default=0.6, help='採用する最低一致スコア（デフォルト0.6）')
    parser.add_argument('--overwrite', action='store_true', help='既存のhotpepper_urlも上書き')
    args = parser.parse_args()

    api_key = os.environ.get('HOTPEPPER_API_KEY', '')
    if not api_key:
        print('エラー: HOTPEPPER_API_KEY が未設定です')
        print('  export HOTPEPPER_API_KEY="your_key" を実行してください')
        return

    with open('data/shops.json', encoding='utf-8') as f:
        shops = json.load(f)

    # 対象: 緯度経度あり・hotpepper_urlなし（--overwriteなら全件）
    targets = [
        s for s in shops
        if s.get('lat') and s.get('lng')
        and (not s.get('hotpepper_url') or args.overwrite)
        and s.get('group') not in ('kodoku_no_gurume',)  # ドラマ系は除外
    ]

    print(f'対象: {len(targets)}件 / 全{len(shops)}件')
    print(f'最低一致スコア: {args.min_score}')
    print()

    matched = []
    skipped_score = 0
    skipped_no_result = 0

    for i, shop in enumerate(targets):
        name = shop['name']
        lat  = shop['lat']
        lng  = shop['lng']

        best, score = search_hotpepper(api_key, name, lat, lng)
        time.sleep(SLEEP_SEC)

        if best is None:
            skipped_no_result += 1
            continue

        if score < args.min_score:
            skipped_score += 1
            if score > 0.3:  # 惜しいものは表示
                print(f'  スコア低（{score:.2f}）: {name} ≠ {best["name"]}')
            continue

        hp_url = best['urls']['pc']
        matched.append((shop, best['name'], score, hp_url))
        print(f'  [{score:.2f}] {name} → {best["name"]}')

        if not args.dry_run:
            shop['hotpepper_url'] = hp_url
            # affiliate_linksにも追加
            links = shop.get('affiliate_links', [])
            if not any('ホットペッパー' in l.get('label', '') for l in links):
                links.append({'label': 'ホットペッパーで予約', 'url': hp_url})
                shop['affiliate_links'] = links

        if (i + 1) % 50 == 0:
            print(f'--- {i+1}/{len(targets)}件処理済み ---')

    print()
    print('=== 結果 ===')
    print(f'マッチ成功:       {len(matched)}件')
    print(f'スコア不足でスキップ: {skipped_score}件')
    print(f'検索結果なし:    {skipped_no_result}件')

    if not args.dry_run and matched:
        with open('data/shops.json', 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
        print(f'\n→ data/shops.json を更新しました')
    elif args.dry_run:
        print('\n（dry-runモード: 書き込みをスキップしました）')


if __name__ == '__main__':
    main()
