"""
scrape_kimura.py
8888-info.hatenablog.com の木村拓哉カテゴリから店舗データ＋注文メニューを抽出し
Nominatim でジオコーディングして scraped_kimura.json を出力する。

使い方:
  python scripts/scrape_kimura.py
  python scripts/scrape_kimura.py --output scripts/scraped_kimura.json

出力後:
  python scripts/merge_shops.py --input scripts/scraped_kimura.json --output data/shops.json
"""

import json, re, time, argparse, unicodedata
from pathlib import Path
import requests
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent
CATEGORY_URL = 'https://8888-info.hatenablog.com/archive/category/%E6%9C%A8%E6%9D%91%E6%8B%93%E5%93%89'
BASE_URL = 'https://8888-info.hatenablog.com'

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; oshi-gourmet-map/1.0)'}
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'

# 飲食店でないと判断するキーワード（shop名またはh1に含まれる）
NON_FOOD_KEYWORDS = [
    'キャンプ', 'ゴルフ', 'チョコレート', 'チョコ', 'スイーツのお取り寄せ',
    'タピオカ', '占い', '足ツボ', '中華街', '神社', '博物館',
    'ショッピング', 'ウィンドウショッピング', '美容', '理髪',
    'ホテル', '旅館', '温泉', '銭湯', '足湯', 'ヴィレッジ',
    'ラーメン博物館',
]

# 店名として不正なキーワード（extract_shop_nameの除外に追加）
INVALID_SHOP_NAMES = {'通販', 'お取り寄せ', 'まとめ', '場所', 'ロケ地', 'ウォーキング', 'シーズン'}

# 交通・アクセス情報と判断するキーワード（p要素を除外）
TRANSIT_KEYWORDS = [
    '最寄駅', '徒歩', '乗り換え', '乗車', '下車', '電車', 'バス停',
    '羽田空港', '成田空港', '新幹線', 'アクセス情報', 'シェアサイクル',
    'navitime', 'maps.app', 'goo.gl',
]


def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    return BeautifulSoup(resp.content, 'html.parser', from_encoding='utf-8')


def get_article_urls(category_url: str) -> list[str]:
    soup = fetch(category_url)
    urls = []
    for a in soup.select('a[href]'):
        href = a['href']
        if not href:
            continue
        if href.startswith('http'):
            url = href
        elif href.startswith('/'):
            url = BASE_URL + href
        else:
            continue
        if not url.startswith(BASE_URL + '/entry/'):
            continue
        if url == category_url or url.rstrip('/') == category_url.rstrip('/'):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def extract_shop_name(soup: BeautifulSoup) -> str:
    """h3/h1 の『』「」【】から店名を抽出"""
    for tag in soup.find_all(['h3', 'h1']):
        text = tag.get_text(strip=True)
        # 全マッチを試して最適なものを選ぶ
        for m in re.finditer(r'[『「【]([^』」】]{2,30})[』」】]', text):
            candidate = m.group(1)
            candidate = re.sub(r'[（(][^）)]*[）)]', '', candidate).strip()
            if not candidate or len(candidate) <= 1:
                continue
            if re.search(r'(予約|場所|アクセス|方法|一覧|まとめ|情報|購入|価格|最安値|通販)', candidate):
                continue
            if any(iv in candidate for iv in INVALID_SHOP_NAMES):
                continue
            return candidate
    return ''


def is_food_article(soup: BeautifulSoup, shop_name: str) -> bool:
    h1 = soup.find('h1')
    title = h1.get_text(strip=True) if h1 else ''
    text = shop_name + title
    for kw in NON_FOOD_KEYWORDS:
        if kw in text:
            return False
    return True


def extract_ordered_items(soup: BeautifulSoup) -> list[str]:
    """●マーカーを持つ<p>から注文品を抽出（交通情報は除外）"""
    items = []
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if '●' not in text:
            continue
        # 交通・アクセス情報を除外
        if any(kw in text for kw in TRANSIT_KEYWORDS):
            continue
        # セクションに分割（"---"区切り）
        sections = re.split(r'-{3,}', text)
        for section in sections:
            # 同行者マーカー（▼◆★など + 説明文）を除去
            section = re.sub(r'[▼◆★☆].*?(?=●|$)', '', section).strip()
            if '●' not in section:
                continue
            parts = section.split('●')
            for part in parts[1:]:
                food = part.strip()
                # ※以降の注記を除去
                food = re.sub(r'※.*$', '', food).strip()
                # 価格（…1650円 や (税込) 形式）を除去
                food = re.sub(r'[…・]\s*\d[\d,，]*円[（(税込\-）)]*', '', food).strip()
                food = re.sub(r'\s*[（(]\s*税込[）)]', '', food).strip()
                food = re.sub(r'\s*\d[\d,，]*円.*$', '', food).strip()
                # ×数量（×2など）は保持
                if food and len(food) > 1 and len(food) < 50:
                    items.append(food)
    return items


def extract_visited_date(soup: BeautifulSoup) -> str:
    """記事テキストから配信日・訪問日を抽出 (YYYY-MM-DD)"""
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return ''


def extract_address_hint(soup: BeautifulSoup) -> str:
    """記事テキストから住所ヒントを抽出（都道府県+市区町村、または最寄駅）"""
    pref_pattern = r'(東京都|北海道|(?:京都|大阪)府|[^\d\s、。]{2,3}県)'
    # 都道府県+市区町村を優先
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        m = re.search(pref_pattern + r'.{0,20}?([市区町村])', text)
        if m:
            return m.group(0)[:25]
    # フォールバック: 最寄駅名
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        m = re.search(r'最寄駅は[『「]([^』」]{1,10}駅)[』」]', text)
        if m:
            return m.group(1)
    return ''


def geocode(shop_name: str, address_hint: str) -> tuple:
    """Nominatim で lat/lng を取得。住所ヒント優先で誤マッチを避ける"""
    # 試みる順序: 住所ヒント+店名 → 住所ヒントのみ → 店名のみ
    queries = []
    if address_hint:
        queries.append(f'{shop_name} {address_hint}')
        queries.append(address_hint)  # 住所だけでも試す（エリア近似座標）
    queries.append(shop_name)

    for q in queries:
        try:
            params = {
                'q': q,
                'format': 'json',
                'limit': 1,
                'accept-language': 'ja',
                'countrycodes': 'jp',
            }
            resp = requests.get(NOMINATIM_URL, params=params,
                                headers={**HEADERS, 'Referer': 'https://gourmet.oshikatsu-guide.com'},
                                timeout=10)
            results = resp.json()
            if results:
                lat, lng = float(results[0]['lat']), float(results[0]['lon'])
                # 日本の範囲チェック（24-46°N, 123-146°E）
                if 24 <= lat <= 46 and 123 <= lng <= 146:
                    return lat, lng
        except Exception:
            pass
        time.sleep(1.1)
    return None, None


def scrape_article(url: str):
    soup = fetch(url)
    shop_name = extract_shop_name(soup)
    if not shop_name:
        print(f'  [店名なし] {url}')
        return None

    if not is_food_article(soup, shop_name):
        print(f'  [非飲食] 「{shop_name}」をスキップ')
        return None

    ordered_items = extract_ordered_items(soup)
    address_hint = extract_address_hint(soup)
    visited_date = extract_visited_date(soup)

    print(f'  「{shop_name}」 ({len(ordered_items)}品) {address_hint} {visited_date}')
    if ordered_items:
        print(f'    → {ordered_items[:3]}{"..." if len(ordered_items) > 3 else ""}')

    return {
        'name': shop_name,
        'group': 'kimura',
        'groups': ['kimura'],
        'members': ['木村拓哉'],
        'genre': '食事',
        'address': address_hint,
        'visited_date': visited_date,
        'source_url': url,
        'source_video_title': '',
        'source_video_url': '',
        'youtube_id': '',
        'ordered_items': ordered_items,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kimura.json')
    parser.add_argument('--no-geocode', action='store_true', help='ジオコーディングをスキップ')
    args = parser.parse_args()

    print(f'カテゴリページから記事URL収集中...')
    urls = get_article_urls(CATEGORY_URL)
    print(f'{len(urls)}件の記事URL取得\n')

    shops = []
    for url in urls:
        time.sleep(1)
        result = scrape_article(url)
        if result:
            shops.append(result)

    print(f'\n=== {len(shops)}件の飲食店を抽出 ===\n')

    if not args.no_geocode:
        print('ジオコーディング中...')
        for shop in shops:
            lat, lng = geocode(shop['name'], shop.get('address', ''))
            shop['lat'] = lat
            shop['lng'] = lng
            status = f'({lat:.4f}, {lng:.4f})' if lat else '失敗'
            print(f'  {shop["name"]}: {status}')
            time.sleep(1.1)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n→ {args.output} に保存しました')
    print('\n次のステップ:')
    print(f'  python scripts/merge_shops.py --input {args.output} --output data/shops.json')


if __name__ == '__main__':
    main()
