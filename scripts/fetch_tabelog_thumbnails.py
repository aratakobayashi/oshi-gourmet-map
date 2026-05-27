#!/usr/bin/env python3
"""
fetch_tabelog_thumbnails.py
食べログ検索URLしか持っていない店舗について:
  1. 食べログ検索で直接URLを解決
  2. 店舗ページからOG画像・スコア・価格帯・営業時間・最寄駅を取得
  3. shops.json に反映

使い方:
  python scripts/fetch_tabelog_thumbnails.py --group naniwa --dry-run
  python scripts/fetch_tabelog_thumbnails.py --group naniwa --apply
  python scripts/fetch_tabelog_thumbnails.py --apply   # 全グループ対象
"""

import urllib.request
import urllib.parse
import json
import re
import time
import argparse
import os
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DIRECT_URL_RE = re.compile(r'tabelog\.com/[a-z]+/A\d+/A\d+/\d+')
SEARCH_SLEEP = 3.0   # 検索ページ
DETAIL_SLEEP = 2.5   # 詳細ページ

PREF_TO_PATH = {
    '東京都': 'tokyo', '神奈川県': 'kanagawa', '大阪府': 'osaka', '京都府': 'kyoto',
    '愛知県': 'aichi', '福岡県': 'fukuoka', '北海道': 'hokkaido', '宮城県': 'miyagi',
    '埼玉県': 'saitama', '千葉県': 'chiba', '兵庫県': 'hyogo', '広島県': 'hiroshima',
    '静岡県': 'shizuoka', '茨城県': 'ibaraki', '栃木県': 'tochigi', '群馬県': 'gunma',
    '新潟県': 'niigata', '長野県': 'nagano', '岐阜県': 'gifu', '三重県': 'mie',
    '滋賀県': 'shiga', '奈良県': 'nara', '和歌山県': 'wakayama', '岡山県': 'okayama',
    '山口県': 'yamaguchi', '香川県': 'kagawa', '愛媛県': 'ehime', '高知県': 'kochi',
    '徳島県': 'tokushima', '福島県': 'fukushima', '秋田県': 'akita', '山形県': 'yamagata',
    '岩手県': 'iwate', '青森県': 'aomori', '富山県': 'toyama', '石川県': 'ishikawa',
    '福井県': 'fukui', '山梨県': 'yamanashi', '長野県': 'nagano',
    '鳥取県': 'tottori', '島根県': 'shimane', '佐賀県': 'saga', '長崎県': 'nagasaki',
    '熊本県': 'kumamoto', '大分県': 'oita', '宮崎県': 'miyazaki', '鹿児島県': 'kagoshima',
    '沖縄県': 'okinawa',
}

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON  = os.path.join(SCRIPTS_DIR, '../data/shops.json')
CACHE_JSON  = os.path.join(SCRIPTS_DIR, 'tabelog_thumbnails_cache.json')


def fetch_html(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'ja,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read().decode('utf-8', errors='replace')


def resolve_tabelog_url(shop_name, prefecture=''):
    """
    店名と都道府県で食べログを検索して直接URLを返す。
    URL形式: https://tabelog.com/{area}/rstLst/?vs=1&sw={name}
    失敗時はNone。
    """
    area_path = PREF_TO_PATH.get(prefecture, 'tokyo')
    search_url = f'https://tabelog.com/{area_path}/rstLst/?vs=1&sw=' + urllib.parse.quote(shop_name)
    html = fetch_html(search_url)
    soup = BeautifulSoup(html, 'html.parser')

    el = soup.select_one('.list-rst__rst-name a')
    if el and el.get('href'):
        href = el['href']
        if DIRECT_URL_RE.search(href):
            return href.split('?')[0].rstrip('/') + '/'
    return None


def parse_shop_page(html):
    """食べログ店舗ページからOG画像・スコア・価格帯・営業時間・最寄駅を抽出"""
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    # OG画像
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img and og_img.get('content'):
        img_url = og_img['content']
        # 食べログのno-imageやデフォルト画像は除外
        if 'noimage' not in img_url and 'default' not in img_url and 'tblg.k-img.com' in img_url:
            result['thumbnail_url'] = img_url

    # スコア
    score_el = soup.select_one('.c-rating__val.rdheader-rating__score-val')
    if score_el:
        try:
            result['tabelog_score'] = float(score_el.text.strip())
        except ValueError:
            pass

    # 価格帯（ディナー優先）
    budget_els = soup.select('.rdheader-budget__price-target')
    prices = [el.text.strip() for el in budget_els if el.text.strip()]
    if prices:
        result['price_range'] = prices[0]

    # rstinfo-table から営業時間・最寄駅
    table = soup.select_one('.rstinfo-table')
    if table:
        for row in table.select('tr'):
            th = row.select_one('th')
            td = row.select_one('td')
            if not th or not td:
                continue
            label = th.text.strip()
            value = re.sub(r'\s+', ' ', td.text.strip())

            if '営業時間' in label and value:
                result['business_hours'] = value[:200]

            if '交通手段' in label and value and 'nearest_station' not in result:
                m = re.search(r'(.+?駅)\s*徒歩(\d+)分', value)
                if m:
                    result['nearest_station'] = f'{m.group(1)} 徒歩{m.group(2)}分'

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', default='', help='対象グループ（省略=全件）')
    parser.add_argument('--apply', action='store_true', help='結果をshops.jsonに反映')
    parser.add_argument('--dry-run', action='store_true', help='書き込みなしで確認')
    parser.add_argument('--no-url', action='store_true', help='tabelog_urlが未設定の店舗も対象にする')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    def is_target(s):
        if args.group and s.get('group') != args.group:
            return False
        url = s.get('tabelog_url', '')
        # 検索URLしか持っていない店舗（既存の対象）
        if url and not DIRECT_URL_RE.search(url):
            return True
        # --no-url 指定時: URLが未設定の店舗も対象
        if args.no_url and not url:
            return True
        return False

    targets = [s for s in shops if is_target(s)]
    label = 'tabelog_urlなし含む' if args.no_url else '検索URL保有'
    print(f'対象（{label}）: {len(targets)}件')
    if args.dry_run:
        for s in targets:
            print(f'  [{s["group"]}] {s["name"]}')
        return

    # キャッシュ読み込み
    cache = {}
    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, encoding='utf-8') as f:
            cache = json.load(f)
        print(f'キャッシュ: {len(cache)}件')

    resolved = 0
    got_thumb = 0
    errors = 0

    for i, shop in enumerate(targets):
        shop_id = shop['id']
        print(f'[{i+1}/{len(targets)}] {shop["name"]}', end=' ', flush=True)

        if shop_id in cache:
            print('(キャッシュ済み)')
            continue

        try:
            # Step 1: 店名+都道府県で食べログ直接URLを解決
            prefecture = shop.get('prefecture', '東京都')
            direct_url = resolve_tabelog_url(shop['name'], prefecture)
            time.sleep(SEARCH_SLEEP)

            if not direct_url:
                print('→ 直接URL取得失敗')
                cache[shop_id] = {}
                errors += 1
                continue

            print(f'→ {direct_url}', end=' ', flush=True)
            resolved += 1

            # Step 2: 店舗詳細ページをスクレイピング
            detail_html = fetch_html(direct_url)
            data = parse_shop_page(detail_html)
            data['tabelog_url'] = direct_url
            cache[shop_id] = data
            time.sleep(DETAIL_SLEEP)

            parts = []
            if 'thumbnail_url' in data: parts.append('画像あり')
            if 'tabelog_score' in data: parts.append(f"スコア:{data['tabelog_score']}")
            if 'price_range'   in data: parts.append(f"価格:{data['price_range']}")
            print(', '.join(parts) if parts else '詳細なし')
            if 'thumbnail_url' in data:
                got_thumb += 1

        except Exception as e:
            print(f'エラー: {e}')
            cache[shop_id] = {}
            errors += 1
            time.sleep(SEARCH_SLEEP)

        # 定期保存
        if (i + 1) % 10 == 0:
            with open(CACHE_JSON, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

    with open(CACHE_JSON, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f'\n完了: URL解決 {resolved}件 / 画像取得 {got_thumb}件 / エラー {errors}件')
    print(f'→ {CACHE_JSON}')

    if args.apply:
        apply_to_shops(shops, cache)


def apply_to_shops(shops, cache):
    updated_fields = 0
    updated_shops = 0
    for shop in shops:
        patch = cache.get(shop['id'])
        if not patch:
            continue
        changed = False
        for key, val in patch.items():
            if val and not shop.get(key):
                shop[key] = val
                updated_fields += 1
                changed = True
            # tabelog_url は常に上書き（検索URLを直接URLに更新）
            elif key == 'tabelog_url' and val:
                if shop.get('tabelog_url') != val:
                    shop['tabelog_url'] = val
                    updated_fields += 1
                    changed = True
        if changed:
            updated_shops += 1

    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'shops.json 更新: {updated_shops}店舗 / {updated_fields}フィールド')


if __name__ == '__main__':
    main()
