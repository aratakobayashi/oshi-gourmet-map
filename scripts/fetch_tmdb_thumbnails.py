"""
fetch_tmdb_thumbnails.py
tmdb_id を持つ店舗に TMDB ポスター画像を thumbnail_url として補完する

使い方:
  python scripts/fetch_tmdb_thumbnails.py
  python scripts/fetch_tmdb_thumbnails.py --dry-run   # 変更せず件数だけ確認
"""

import json
import os
import time
import urllib.request
import argparse

TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '4573ec6c37323f6f89002cb24c690875')
TMDB_BASE_IMG = 'https://image.tmdb.org/t/p/w500'
SHOPS_PATH = 'data/shops.json'


def fetch_poster(tmdb_id, cache):
    if tmdb_id in cache:
        return cache[tmdb_id]
    url = f'https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&language=ja'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        poster = data.get('poster_path')
        result = f'{TMDB_BASE_IMG}{poster}' if poster else None
        print(f'  TMDB {tmdb_id} → {data.get("name","?")} : {result}')
    except Exception as e:
        print(f'  TMDB {tmdb_id} 取得エラー: {e}')
        result = None
    cache[tmdb_id] = result
    time.sleep(0.25)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with open(SHOPS_PATH) as f:
        shops = json.load(f)

    targets = [
        s for s in shops
        if s.get('tmdb_id') and not s.get('youtube_id') and not s.get('thumbnail_url')
    ]
    print(f'対象: {len(targets)}件 / 全{len(shops)}件')

    if args.dry_run:
        from collections import Counter
        ids = Counter(s['tmdb_id'] for s in targets)
        print('tmdb_id 別件数:')
        for tid, cnt in ids.most_common():
            print(f'  {tid}: {cnt}件')
        return

    cache = {}
    updated = 0
    for shop in shops:
        if not shop.get('tmdb_id') or shop.get('youtube_id') or shop.get('thumbnail_url'):
            continue
        poster_url = fetch_poster(shop['tmdb_id'], cache)
        if poster_url:
            shop['thumbnail_url'] = poster_url
            updated += 1

    print(f'\n更新: {updated}件')
    with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'→ {SHOPS_PATH} に保存しました')


if __name__ == '__main__':
    main()
