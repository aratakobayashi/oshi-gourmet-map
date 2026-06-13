#!/usr/bin/env python3
"""
Retry tabelog search for arashi shops with cleaned names.
"""
import json, re, time, urllib.request, urllib.parse, os, sys
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DIRECT_URL_RE = re.compile(r'tabelog\.com/[a-z]+/A\d+/A\d+/\d+')
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON  = os.path.join(SCRIPTS_DIR, '../data/shops.json')
CACHE_JSON  = os.path.join(SCRIPTS_DIR, 'tabelog_thumbnails_cache.json')

PREF_TO_PATH = {
    '東京都': 'tokyo', '神奈川県': 'kanagawa', '大阪府': 'osaka', '京都府': 'kyoto',
    '愛知県': 'aichi', '福岡県': 'fukuoka', '北海道': 'hokkaido', '宮城県': 'miyagi',
    '埼玉県': 'saitama', '千葉県': 'chiba', '兵庫県': 'hyogo', '広島県': 'hiroshima',
    '静岡県': 'shizuoka', '大分県': 'oita',
}

# Manually specify cleaned search names and tabelog URL hints
RETRY_MAP = {
    'arashi-dolala-20200718':        ('Dolala 目黒', '東京都'),
    'arashi-6d3e8582-20200523':      ('肉じるや 港区', '東京都'),
    'arashi-c420c615-20200523':      ('三軒茶屋 ザ サン リブズ ヒア', '東京都'),
    'arashi-f31a35ee-20200516':      ('白ねぎ醤油 大分', '大分県'),
    'arashi-patisserie_le_333-20200404': ('パティスリー ル トワ 港区', '東京都'),
    'arashi-b2f06b81-20191214':      ('カシヤマ ダイカンヤマ', '東京都'),
    'arashi-d60f15cc-20190525':      ('ダイゴミ バーガー 横浜', '神奈川県'),
    'arashi-7f824860-20190406':      ('チーズ ミートバンク 渋谷', '東京都'),
    'arashi-1799745c-20190309':      ('ダンプリングタイム 渋谷', '東京都'),
    'arashi-6073e95a-20190126':      ('クルアナムプリック 目黒', '東京都'),
    'arashi-65ce3bcf-20190101':      ('利尻ラーメン 味楽', '北海道'),
    'arashi-466393aa-20180929':      ('ラ ミニョネット 中央区', '東京都'),
}

def fetch_html(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read().decode('utf-8', errors='replace')

def resolve_tabelog_url(search_name, prefecture='東京都'):
    area_path = PREF_TO_PATH.get(prefecture, 'tokyo')
    search_url = f'https://tabelog.com/{area_path}/rstLst/?vs=1&sw=' + urllib.parse.quote(search_name)
    print(f'  GET {search_url}')
    html = fetch_html(search_url)
    soup = BeautifulSoup(html, 'html.parser')
    el = soup.select_one('.list-rst__rst-name a')
    if el and el.get('href'):
        href = el['href']
        if DIRECT_URL_RE.search(href):
            result_name = el.get_text(strip=True)
            print(f'  → found: {result_name}  {href}')
            return href.split('?')[0].rstrip('/') + '/'
    print('  → not found')
    return None

def parse_shop_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img and og_img.get('content'):
        img_url = og_img['content']
        if 'noimage' not in img_url and 'default' not in img_url and 'tblg.k-img.com' in img_url:
            result['thumbnail_url'] = img_url
    score_el = soup.select_one('.c-rating__val.rdheader-rating__score-val')
    if score_el:
        try:
            result['tabelog_score'] = float(score_el.text.strip())
        except ValueError:
            pass
    # price_range
    for el in soup.select('.rdheader-budget__price-target'):
        txt = el.get_text(strip=True)
        if txt and txt != '-':
            result.setdefault('price_range', txt)
            break
    # tabelog_url from canonical
    canon = soup.select_one('link[rel="canonical"]')
    if canon and canon.get('href'):
        result['tabelog_url'] = canon['href'].rstrip('/') + '/'
    return result

def main():
    with open(CACHE_JSON) as f:
        cache = json.load(f)
    with open(SHOPS_JSON) as f:
        shops = json.load(f)

    updated = 0
    for shop_id, (search_name, pref) in RETRY_MAP.items():
        print(f'\n[{shop_id}] searching: {search_name}')
        tabelog_url = resolve_tabelog_url(search_name, pref)
        time.sleep(3)
        if not tabelog_url:
            cache[shop_id] = {}
            print('  → cached as empty')
            continue
        html = fetch_html(tabelog_url)
        time.sleep(2.5)
        data = parse_shop_page(html)
        if not data.get('thumbnail_url'):
            print(f'  → no thumbnail at {tabelog_url}')
            cache[shop_id] = {}
            continue
        data['tabelog_url'] = tabelog_url
        cache[shop_id] = data
        print(f'  → OK: {data.get("thumbnail_url","")[:60]}')
        updated += 1

    with open(CACHE_JSON, 'w') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    # Apply to shops.json
    patched = 0
    for shop in shops:
        sid = shop['id']
        if sid not in RETRY_MAP:
            continue
        patch = cache.get(sid)
        if not patch:
            continue
        for key in ['thumbnail_url', 'tabelog_url', 'tabelog_score', 'price_range']:
            if patch.get(key):
                shop[key] = patch[key]
                patched += 1

    with open(SHOPS_JSON, 'w') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 結果 ===')
    print(f'tabelog検索成功: {updated}件')
    print(f'shops.jsonパッチ: {patched}フィールド')

if __name__ == '__main__':
    main()
