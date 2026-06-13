#!/usr/bin/env python3
"""
pipeline_naniwa.py
なにわ男子グルメデータの自動収集・マージ・サイト生成・Gitプッシュを一括実行

使い方:
  python scripts/pipeline_naniwa.py           # 通常実行
  python scripts/pipeline_naniwa.py --dry-run  # 書き込み・pushなし
  python scripts/pipeline_naniwa.py --no-push  # commitはするがpushしない
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
SHOPS_JSON  = REPO_ROOT / 'data' / 'shops.json'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'

PREF_KEYWORDS = [
    '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県',
    '茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
    '新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県',
    '静岡県','愛知県','三重県','滋賀県','京都府','大阪府','兵庫県',
    '奈良県','和歌山県','鳥取県','島根県','岡山県','広島県','山口県',
    '徳島県','香川県','愛媛県','高知県','福岡県','佐賀県','長崎県',
    '熊本県','大分県','宮崎県','鹿児島県','沖縄県',
]

PREF_BBOX = {
    '北海道':   (41.0, 45.7, 139.5, 145.9),
    '東京都':   (35.5, 35.9, 138.9, 139.9),
    '大阪府':   (34.4, 34.9, 135.1, 135.8),
    '愛知県':   (34.5, 35.4, 136.5, 137.6),
    '神奈川県': (35.1, 35.7, 139.0, 139.8),
    '京都府':   (34.7, 35.8, 135.0, 136.1),
    '福岡県':   (33.0, 34.2, 129.7, 131.3),
    '三重県':   (33.7, 35.3, 135.7, 136.9),
    '埼玉県':   (35.7, 36.3, 138.7, 139.9),
    '千葉県':   (35.0, 36.1, 139.7, 140.9),
    '静岡県':   (34.5, 35.5, 137.5, 139.2),
}

JAPAN_BBOX = (24.0, 46.0, 122.0, 154.0)


def log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')


def run(cmd: list, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO_ROOT)


def make_id(group: str, name: str, visited_date: str) -> str:
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '_', ascii_name.lower().strip())[:20].strip('_')
    if len(slug) < 2:
        slug = hashlib.md5(name.encode()).hexdigest()[:8]
    date_slug = visited_date.replace('-', '')[:8]
    return f'{group}-{slug}-{date_slug}'


def extract_prefecture_city(address: str):
    prefecture = ''
    city = ''
    if not address:
        return prefecture, city
    address = re.sub(r'^〒\d{3}[-－]\d{4}\s*', '', address).strip()
    pref_m = re.match(r'^(東京都|北海道|(?:京都|大阪)府|.{2,3}県)', address)
    if pref_m:
        prefecture = pref_m.group(1)
        rest = address[len(prefecture):]
        city_m = re.match(r'^(.{1,6}?[市区町村])', rest)
        if city_m:
            city = city_m.group(1)
    return prefecture, city


def normalize_addr(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif ch == '　':
            result.append(' ')
        elif ch == '−':
            result.append('-')
        else:
            result.append(ch)
    return ''.join(result)


def simplify_address(address: str) -> str:
    address = normalize_addr(address)
    address = re.sub(r'^〒\d{3}[-－]\d{4}\s*', '', address).strip()
    address = re.sub(r'\s*[※\*].+$', '', address).strip()
    address = re.sub(r'\d+[-－]\d+.*$', '', address).strip()
    address = re.sub(r'(\d+丁目)\d+.*$', r'\1', address).strip()
    address = re.sub(r'\s*(B?\d+F|地下\d+階|[0-9]+階).*$', '', address).strip()
    return address


def geocode_query(query: str):
    params = urllib.parse.urlencode({
        'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'jp',
    })
    url = f'{NOMINATIM_URL}?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
        if results:
            return float(results[0]['lat']), float(results[0]['lon'])
    except Exception as e:
        log(f'  Nominatimエラー: {e}')
    return None, None


def geocode_shop(shop: dict):
    address = shop.get('address', '').strip()
    name    = shop.get('name', '')
    pref    = shop.get('prefecture', '')
    city    = shop.get('city', '')

    lat, lng = None, None

    if address:
        lat, lng = geocode_query(simplify_address(address))
        time.sleep(1)

    if not lat:
        lat, lng = geocode_query(name)
        time.sleep(1)
    if not lat:
        lat, lng = geocode_query(f'{name} 日本')
        time.sleep(1)
    if not lat and (pref or city):
        lat, lng = geocode_query(f'{pref}{city} {name}')
        time.sleep(1)

    return lat, lng


def validate_coords(lat, lng, prefecture: str) -> bool:
    if not lat or not lng:
        return False
    if not (JAPAN_BBOX[0] <= lat <= JAPAN_BBOX[1] and JAPAN_BBOX[2] <= lng <= JAPAN_BBOX[3]):
        return False
    bbox = PREF_BBOX.get(prefecture)
    if bbox:
        lat_min, lat_max, lng_min, lng_max = bbox
        if not (lat_min <= lat <= lat_max and lng_min <= lng <= lng_max):
            log(f'    ⚠️  座標が{prefecture}の範囲外: ({lat:.3f}, {lng:.3f})')
            return False
    return True


def fetch_tabelog_thumbnail(tabelog_url: str) -> dict:
    if not tabelog_url or 'tabelog.com' not in tabelog_url:
        return {}
    try:
        req = urllib.request.Request(
            tabelog_url,
            headers={'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode('utf-8', errors='replace')
        og_image = ''
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m:
            og_image = m.group(1)
        score = ''
        sm = re.search(r'"ratingValue"\s*:\s*"([0-9.]+)"', html)
        if sm:
            score = sm.group(1)
        return {'thumbnail_url': og_image, 'tabelog_score': score}
    except Exception as e:
        log(f'    tabelog取得エラー: {e}')
        return {}


def load_shops() -> list:
    with open(SHOPS_JSON, encoding='utf-8') as f:
        return json.load(f)


def save_shops(shops: list):
    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)


def normalize_shop(raw, existing_ids):
    if not raw.get('lat') or not raw.get('lng'):
        return None
    name = raw.get('name', '').strip()
    if not name:
        return None
    group = raw.get('group', 'naniwa')
    visited_date = raw.get('visited_date', '')
    address = raw.get('address', '')
    prefecture, city = extract_prefecture_city(address)
    if not prefecture:
        prefecture = raw.get('prefecture', '')

    shop_id = make_id(group, name, visited_date)
    base_id = shop_id
    counter = 2
    while shop_id in existing_ids:
        shop_id = f'{base_id}-{counter}'
        counter += 1

    return {
        'id':                 shop_id,
        'name':               name,
        'genre':              raw.get('genre', 'その他'),
        'prefecture':         prefecture,
        'city':               city,
        'address':            address,
        'lat':                raw.get('lat'),
        'lng':                raw.get('lng'),
        'youtube_id':         raw.get('youtube_id', ''),
        'source_video_title': raw.get('source_video_title', ''),
        'source_url':         raw.get('source_url', ''),
        'visited_date':       visited_date,
        'members':            raw.get('members', []),
        'groups':             raw.get('groups', [group]),
        'group':              group,
        'nearest_station':    raw.get('nearest_station', ''),
        'description':        raw.get('description', ''),
        'tags':               [],
        'tabelog_url':        raw.get('tabelog_url', ''),
        'hotpepper_url':      raw.get('hotpepper_url', ''),
        'affiliate_links':    raw.get('affiliate_links', []),
        'thumbnail_url':      raw.get('thumbnail_url', ''),
        'source_type':        raw.get('source_type', ''),
        'tmdb_id':            raw.get('tmdb_id', None),
        'tmdb_type':          raw.get('tmdb_type', ''),
        'ordered_items':      raw.get('ordered_items', []),
    }


def run_scraper(dry_run: bool) -> list:
    out_file = SCRIPTS_DIR / 'scraped_pipeline_naniwa_tmp.json'
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'scrape_chiicrane.py'),
        '--auto-discover',
        '--output', str(out_file),
        '--existing-json', str(SHOPS_JSON),
    ]
    log('chiicrane-life.fun 自動巡回スクレイプ中...')
    result = run(cmd)
    if result.returncode != 0:
        log(f'スクレイパーエラー:\n{result.stderr}')
        return []
    print(result.stdout)

    if not out_file.exists():
        return []
    with open(out_file, encoding='utf-8') as f:
        shops = json.load(f)
    if not dry_run:
        out_file.unlink(missing_ok=True)
    return shops


def load_manual_inputs() -> list:
    """scripts/input_naniwa_manual.json から手動追加データを読み込む

    スキーマ例:
    [
      {
        "name": "店舗名",
        "group": "naniwa",
        "address": "〒xxx-xxxx 都道府県...",
        "members": ["大西流星"],
        "visited_date": "2025-01-01",
        "source_url": "https://...",
        "source_video_title": "なにわ男子のどっち派",
        "genre": "カフェ",
        "ordered_items": ["メニュー名"],
        "tabelog_url": "https://tabelog.com/..."
      }
    ]
    """
    manual_file = SCRIPTS_DIR / 'input_naniwa_manual.json'
    if not manual_file.exists():
        return []
    try:
        with open(manual_file, encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            return []
        log(f'手動追加データ: {len(data)}件')
        for item in data:
            if 'group' not in item:
                item['group'] = 'naniwa'
            if 'groups' not in item:
                item['groups'] = ['naniwa']
        return data
    except Exception as e:
        log(f'manual input読み込みエラー: {e}')
        return []


def reset_manual_input(dry_run: bool):
    manual_file = SCRIPTS_DIR / 'input_naniwa_manual.json'
    if not manual_file.exists():
        return
    if not dry_run:
        with open(manual_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
        log(f'{manual_file.name} をリセット')


def run_generate():
    log('generate_lite.py...')
    r = run([sys.executable, str(SCRIPTS_DIR / 'generate_lite.py')])
    if r.stdout:
        print(r.stdout[:500])
    log('generate_shop_pages.py...')
    r = run([sys.executable, str(SCRIPTS_DIR / 'generate_shop_pages.py')])
    if r.stdout:
        print(r.stdout[:500])


def git_commit_push(added_shops: list, dry_run: bool, no_push: bool):
    names = ', '.join(s['name'] for s in added_shops[:5])
    if len(added_shops) > 5:
        names += f' 他{len(added_shops)-5}件'

    run(['git', 'add',
         'data/shops.json',
         'data/shops-lite.json',
         'data/shops-lite/naniwa.json'])
    run(['git', 'add', '_shop_pages/naniwa-*.md'])

    msg = (
        f'naniwa +{len(added_shops)}件追加（自動パイプライン）\n\n'
        f'{names}\n\n'
        'Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>'
    )

    if dry_run:
        log(f'[dry-run] commit スキップ: "{msg[:60]}..."')
        return

    r = run(['git', 'commit', '-m', msg])
    if r.returncode != 0:
        log(f'commit失敗: {r.stderr}')
        return
    log(f'commit完了: {r.stdout.strip()}')

    if not no_push:
        r = run(['git', 'push'])
        if r.returncode != 0:
            log(f'push失敗: {r.stderr}')
        else:
            log('push完了')


def main():
    parser = argparse.ArgumentParser(description='なにわ男子グルメ自動収集パイプライン')
    parser.add_argument('--dry-run', action='store_true', help='書き込み・commitなし')
    parser.add_argument('--no-push', action='store_true', help='commitはするがpushしない')
    args = parser.parse_args()

    log('=== なにわ男子グルメ自動パイプライン 開始 ===')

    existing_shops = load_shops()
    existing_ids   = {s['id'] for s in existing_shops}
    existing_names = {s['name'] for s in existing_shops}
    log(f'既存: {len(existing_shops)}件')

    scraped = run_scraper(args.dry_run)
    manual  = load_manual_inputs()
    all_raw = scraped + manual
    log(f'スクレイプ: {len(scraped)}件 + 手動: {len(manual)}件')

    if not all_raw:
        log('新規データなし。終了。')
        return

    candidates = [s for s in all_raw if s['name'] not in existing_names]
    log(f'名前重複除外後: {len(candidates)}件')

    if not candidates:
        log('追加対象なし。終了。')
        return

    log('ジオコーディング中...')
    geocoded = []
    for i, shop in enumerate(candidates):
        log(f'  [{i+1}/{len(candidates)}] {shop["name"]}')
        if shop.get('lat') and shop.get('lng'):
            log('    座標済みスキップ')
            geocoded.append(shop)
            continue
        lat, lng = geocode_shop(shop)
        if lat and lng:
            shop['lat'] = lat
            shop['lng'] = lng
            log(f'    → ({lat:.4f}, {lng:.4f})')
            geocoded.append(shop)
        else:
            log('    → 座標取得失敗: スキップ')

    log(f'ジオコーディング成功: {len(geocoded)}/{len(candidates)}件')

    valid = []
    for shop in geocoded:
        pref = shop.get('prefecture', '')
        if not pref:
            addr = shop.get('address', '')
            for pk in PREF_KEYWORDS:
                if pk in addr:
                    pref = pk
                    shop['prefecture'] = pref
                    break
        if validate_coords(shop.get('lat'), shop.get('lng'), pref):
            valid.append(shop)
        else:
            log(f'  ⚠️  座標無効のためスキップ: {shop["name"]}')

    log(f'座標バリデーション通過: {len(valid)}/{len(geocoded)}件')

    if not valid:
        log('追加対象なし。終了。')
        return

    log('shops.json にマージ中...')
    added_shops = []
    for raw in valid:
        shop = normalize_shop(raw, existing_ids)
        if shop is None:
            continue
        if shop['name'] in existing_names:
            log(f'  重複スキップ: {shop["name"]}')
            continue
        added_shops.append(shop)
        existing_ids.add(shop['id'])
        existing_names.add(shop['name'])
        log(f'  追加: {shop["name"]} ({shop["prefecture"]} {shop.get("city","")}) [{shop.get("visited_date","")}]')

    log(f'追加件数: {len(added_shops)}件')

    if not added_shops:
        log('追加対象なし。終了。')
        return

    log('tabelog サムネイル取得中...')
    for shop in added_shops:
        if shop.get('tabelog_url') and not shop.get('thumbnail_url'):
            result = fetch_tabelog_thumbnail(shop['tabelog_url'])
            if result.get('thumbnail_url'):
                shop['thumbnail_url'] = result['thumbnail_url']
                shop['tabelog_score'] = result.get('tabelog_score', '')
                log(f'  {shop["name"]}: サムネ取得完了')
            time.sleep(1.5)

    merged = existing_shops + added_shops
    if not args.dry_run:
        save_shops(merged)
        log(f'shops.json 保存: {len(merged)}件')
    else:
        log(f'[dry-run] shops.json 保存スキップ ({len(merged)}件になるはず)')

    if not args.dry_run:
        run_generate()
    else:
        log('[dry-run] generate スキップ')

    if manual:
        reset_manual_input(args.dry_run)

    git_commit_push(added_shops, args.dry_run, args.no_push)

    log(f'=== 完了: {len(added_shops)}件追加 ===')
    for s in added_shops:
        log(f'  {s["name"]} ({s["prefecture"]} {s.get("city","")}) [{s.get("visited_date","")}]')


if __name__ == '__main__':
    main()
