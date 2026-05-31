#!/usr/bin/env python3
"""
generate_lite.py
shops.json からカード表示・フィルター・マップに必要な最小フィールドだけを抽出し
data/shops-lite.json（全件）および data/shops-lite-{group}.json（グループ別）を生成する。

【削除するフィールド（詳細ページのみ必要）】
  business_hours, description, affiliate_links, tabelog_url, hotpepper_url,
  ordered_items, source_url, address, tmdb_id, tmdb_type, seating_note,
  google_maps_url, source_video_url

【残すフィールド（一覧・マップ・検索で必要）】
  id, name, genre, prefecture, city, nearest_station,
  lat, lng, group, groups,
  thumbnail_url, youtube_id,
  members, visited_date,
  source_video_title, source_type,
  tags, closed, tabelog_score, price_range

パイプライン上の位置:
  merge_shops.py → fetch_tabelog_thumbnails.py → generate_lite.py → generate_shop_pages.py

使い方:
  python scripts/generate_lite.py
"""

import json, os, gzip
from collections import defaultdict

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC      = os.path.join(ROOT, 'data', 'shops.json')
DST_ALL  = os.path.join(ROOT, 'data', 'shops-lite.json')
DST_DIR  = os.path.join(ROOT, 'data', 'shops-lite')

KEEP = {
    'id', 'name', 'genre', 'prefecture', 'city', 'nearest_station',
    'lat', 'lng', 'group', 'groups',
    'thumbnail_url', 'youtube_id',
    'members', 'visited_date',
    'source_video_title', 'source_type',
    'tags', 'closed', 'tabelog_score', 'price_range',
}

def slim(shop):
    return {k: v for k, v in shop.items() if k in KEEP}

def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

def gzip_size(path):
    return len(gzip.compress(open(path, 'rb').read()))

# --- メイン ---
with open(SRC, encoding='utf-8') as f:
    shops = json.load(f)

# 全件 lite
lite_all = [slim(s) for s in shops]
write_json(DST_ALL, lite_all)

src_gz  = gzip_size(SRC)
all_gz  = gzip_size(DST_ALL)
src_kb  = os.path.getsize(SRC) / 1024
all_kb  = os.path.getsize(DST_ALL) / 1024
print(f"shops.json      : {src_kb:.0f} KB  (gzip {src_gz/1024:.0f} KB)")
print(f"shops-lite.json : {all_kb:.0f} KB  (gzip {all_gz/1024:.0f} KB)")
print(f"削減率          : {(1-all_kb*1024/os.path.getsize(SRC))*100:.0f}% raw / {(1-all_gz/src_gz)*100:.0f}% gzip\n")

# グループ別 lite
os.makedirs(DST_DIR, exist_ok=True)
by_group = defaultdict(list)
for s in shops:
    by_group[s['group']].append(slim(s))

print(f"{'グループ':20} {'件数':>5}  {'KB':>6}  {'gzip KB':>8}")
print("-" * 45)
for group, gshops in sorted(by_group.items(), key=lambda x: -len(x[1])):
    path = os.path.join(DST_DIR, f'{group}.json')
    write_json(path, gshops)
    kb = os.path.getsize(path) / 1024
    gz = gzip_size(path) / 1024
    print(f"  {group:18} {len(gshops):5}  {kb:6.1f}  {gz:8.1f}")

print(f"\n合計 {len(shops)} 件 → shops-lite.json + {len(by_group)} グループ別ファイル生成完了")
