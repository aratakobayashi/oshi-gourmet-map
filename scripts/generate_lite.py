#!/usr/bin/env python3
"""
generate_lite.py
shops.json からカード表示・フィルター・マップに必要な最小フィールドだけを抽出し
data/shops-lite.json を生成する。

【削除するフィールド（詳細ページのみ必要）】
  business_hours, description, affiliate_links, tabelog_url, hotpepper_url,
  ordered_items, price_range, source_url, tabelog_score, address,
  tmdb_id, tmdb_type, seating_note, google_maps_url, source_video_url

【残すフィールド（一覧・マップ・検索で必要）】
  id, name, genre, prefecture, city, nearest_station,
  lat, lng, group, groups,
  thumbnail_url, youtube_id,
  members, visited_date,
  source_video_title, source_type,
  tags, closed

パイプライン上の位置:
  merge_shops.py → fetch_tabelog_thumbnails.py → generate_lite.py → generate_shop_pages.py

使い方:
  python scripts/generate_lite.py
"""

import json, os, gzip

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC       = os.path.join(ROOT, 'data', 'shops.json')
DST       = os.path.join(ROOT, 'data', 'shops-lite.json')

KEEP = {
    'id', 'name', 'genre', 'prefecture', 'city', 'nearest_station',
    'lat', 'lng', 'group', 'groups',
    'thumbnail_url', 'youtube_id',
    'members', 'visited_date',
    'source_video_title', 'source_type',
    'tags', 'closed',
}

with open(SRC, encoding='utf-8') as f:
    shops = json.load(f)

lite = [{k: v for k, v in s.items() if k in KEEP} for s in shops]

# インデントなし（compact）で出力 → ファイルサイズ最小化
with open(DST, 'w', encoding='utf-8') as f:
    json.dump(lite, f, ensure_ascii=False, separators=(',', ':'))

src_size  = os.path.getsize(SRC)
dst_size  = os.path.getsize(DST)
dst_gzip  = len(gzip.compress(open(DST, 'rb').read()))
src_gzip  = len(gzip.compress(open(SRC, 'rb').read()))

print(f"shops.json      : {src_size/1024:.0f} KB  (gzip {src_gzip/1024:.0f} KB)")
print(f"shops-lite.json : {dst_size/1024:.0f} KB  (gzip {dst_gzip/1024:.0f} KB)")
print(f"削減率          : {(1 - dst_size/src_size)*100:.0f}% raw / {(1 - dst_gzip/src_gzip)*100:.0f}% gzip")
print(f"件数            : {len(lite)} 件")
