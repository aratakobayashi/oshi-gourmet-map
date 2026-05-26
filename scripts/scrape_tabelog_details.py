"""
scrape_tabelog_details.py
shops.jsonのtabelog_urlからスコア・価格帯・営業時間を取得する

使い方:
  python scripts/scrape_tabelog_details.py
  python scripts/scrape_tabelog_details.py --limit 10   # テスト用（10件のみ）
  python scripts/scrape_tabelog_details.py --apply      # 取得後にshops.jsonへ反映

出力: scripts/tabelog_details.json
"""

import urllib.request
import json
import re
import time
import argparse
import os
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DIRECT_URL_RE = re.compile(r'tabelog\.com/[a-z]+/A\d+/A\d+/\d+')
SLEEP_SEC = 2.5

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON   = os.path.join(SCRIPTS_DIR, '../data/shops.json')
OUTPUT_JSON  = os.path.join(SCRIPTS_DIR, 'tabelog_details.json')


def fetch_html(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'ja,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read().decode('utf-8', errors='replace')


def parse_shop(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    # スコア
    score_el = soup.select_one('.c-rating__val.rdheader-rating__score-val')
    if score_el:
        try:
            result['tabelog_score'] = float(score_el.text.strip())
        except ValueError:
            pass

    # 価格帯（ディナーを優先、なければランチ）
    budget_els = soup.select('.rdheader-budget__price-target')
    prices = [el.text.strip() for el in budget_els if el.text.strip()]
    if prices:
        result['price_range'] = prices[0]  # 最初がディナー

    # rstinfo-table から営業時間・最寄り駅
    table = soup.select_one('.rstinfo-table')
    if table:
        for row in table.select('tr'):
            th = row.select_one('th')
            td = row.select_one('td')
            if not th or not td:
                continue
            label = th.text.strip()
            value = td.text.strip()
            # 改行・余分なスペースを整理
            value = re.sub(r'\s+', ' ', value).strip()

            if '営業時間' in label and value:
                result['business_hours'] = value[:200]

            if '交通手段' in label and value and 'nearest_station' not in result:
                # 最初の行（駅名+徒歩X分）だけ抽出
                m = re.search(r'(.+?駅)\s*徒歩(\d+)分', value)
                if m:
                    result['nearest_station'] = f'{m.group(1)} 徒歩{m.group(2)}分'

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='取得件数上限（0=全件）')
    parser.add_argument('--apply', action='store_true', help='取得後にshops.jsonへ反映')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    targets = [s for s in shops if s.get('tabelog_url') and DIRECT_URL_RE.search(s['tabelog_url'])]
    print(f'対象: {len(targets)}件')

    if args.limit:
        targets = targets[:args.limit]
        print(f'→ {args.limit}件に制限')

    # 既存の結果があれば読み込んで差分だけ取得
    results = {}
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, encoding='utf-8') as f:
            results = json.load(f)
        print(f'既存結果: {len(results)}件 → 未取得分のみ実行')

    done = 0
    errors = 0
    for i, shop in enumerate(targets):
        if shop['id'] in results:
            continue

        url = shop['tabelog_url']
        print(f'[{i+1}/{len(targets)}] {shop["name"]} ...', end=' ', flush=True)
        try:
            html = fetch_html(url)
            data = parse_shop(html)
            results[shop['id']] = data
            parts = []
            if 'tabelog_score' in data: parts.append(f"スコア:{data['tabelog_score']}")
            if 'price_range'   in data: parts.append(f"価格:{data['price_range']}")
            if 'business_hours' in data: parts.append('営業時間あり')
            print(', '.join(parts) if parts else '取得できず')
            done += 1
        except Exception as e:
            print(f'エラー: {e}')
            results[shop['id']] = {}
            errors += 1

        # 定期的に中間保存
        if (i + 1) % 20 == 0:
            with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(SLEEP_SEC)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {done}件取得 / {errors}件エラー → {OUTPUT_JSON}')

    if args.apply:
        apply_to_shops(shops, results)


def apply_to_shops(shops, results):
    updated = 0
    for shop in shops:
        patch = results.get(shop['id'])
        if not patch:
            continue
        for key, val in patch.items():
            if val and not shop.get(key):
                shop[key] = val
                updated += 1

    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'shops.json 更新: {updated}フィールド反映')


if __name__ == '__main__':
    main()
