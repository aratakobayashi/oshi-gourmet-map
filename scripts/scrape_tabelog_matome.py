"""
scrape_tabelog_matome.py
食べログまとめページから乃木坂46関連のお店情報をスクレイピング

各店舗の tabelog ページから JSON-LD で正確な座標取得。

使い方:
  python scripts/scrape_tabelog_matome.py \\
    --urls https://tabelog.com/matome/3277/ https://tabelog.com/matome/7804/ \\
    --output scripts/scraped_tabelog_matome.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
import time
from bs4 import BeautifulSoup

GROUP = 'nogizaka46'
UA_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
UA_BOT = 'oshi-gourmet-map/1.0'

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺'], 'ラーメン'),
    (['そば', 'うどん', '蕎麦'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', '焼き鳥'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'パン', 'ベーカリー'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', '甘味', '和菓子', '洋菓子'], 'スイーツ'),
    (['居酒屋', 'バー', '酒'], '居酒屋'),
    (['カレー', 'インド'], '食事'),
    (['中華', '餃子', '点心'], '中華'),
    (['イタリアン', 'パスタ', 'ピザ'], '食事'),
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def split_prefecture_city(area_text):
    prefectures = [
        '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
        '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
        '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
        '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
        '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
        '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
        '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
    ]
    for pref in prefectures:
        if area_text.startswith(pref):
            return pref, area_text[len(pref):].strip()
    return area_text, ''


def fetch_html(url, ua=UA_BROWSER):
    req = urllib.request.Request(url, headers={'User-Agent': ua})
    return urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')


def get_tabelog_data(tabelog_url):
    """tabelog ページから JSON-LD で name/address/lat/lng を取得"""
    try:
        html = fetch_html(tabelog_url)
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
                if isinstance(data, dict) and data.get('@type') in ('Restaurant', 'FoodEstablishment', 'LocalBusiness'):
                    addr = data.get('address', {})
                    geo = data.get('geo', {})
                    lat = float(geo.get('latitude', 0)) or None
                    lng = float(geo.get('longitude', 0)) or None
                    if lat and not (24 <= lat <= 46 and 122 <= lng <= 154):
                        lat = lng = None
                    full_addr = (
                        addr.get('addressRegion', '') +
                        addr.get('addressLocality', '') +
                        addr.get('streetAddress', '')
                    )
                    return {
                        'name': data.get('name', ''),
                        'address': full_addr,
                        'lat': lat,
                        'lng': lng,
                    }
            except Exception:
                pass
    except Exception as e:
        print(f'    tabelog取得エラー: {e}')
    return {}


def scrape_matome(url):
    print(f'取得中: {url}')
    html = fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    shops = []
    for rst in soup.find_all(class_='matome-rst'):
        name_el = rst.find(class_='matome-rst__name')
        addr_el = rst.find(class_='matome-rst__address')
        genre_el = rst.find(class_='matome-rst__areagenre')
        rst_id = rst.get('data-rst-id', '')

        if not name_el or not rst_id:
            continue

        name = name_el.get_text(strip=True)
        addr_raw = re.sub(r'\s+', '', addr_el.get_text()) if addr_el else ''
        genre_raw = genre_el.get_text(strip=True) if genre_el else ''

        # Find the tabelog URL by looking at the area prefix in the address element
        # Try to reconstruct from data-rst-id and known URL pattern
        tabelog_url = ''
        # Look for any href containing this rst_id in the whole soup
        links = soup.find_all('a', href=re.compile(rf'/{rst_id}'))
        for lk in links:
            href = lk.get('href', '')
            if re.search(r'/A\d+/A\d+/' + rst_id, href):
                tabelog_url = href.split('?')[0]
                if not tabelog_url.startswith('http'):
                    tabelog_url = 'https://tabelog.com' + tabelog_url
                break

        # Section heading = program/context
        prev_h = rst.find_previous(class_=re.compile('heading'))
        heading = prev_h.get_text(strip=True) if prev_h else ''
        # Strip bracketed info from heading to get clean program title
        program = re.sub(r'【.*?】', '', heading).strip()

        prefecture, city = split_prefecture_city(addr_raw)
        genre = detect_genre(name + genre_raw)

        shops.append({
            'name': name,
            'genre': genre,
            'prefecture': prefecture,
            'city': city,
            'address': addr_raw,
            'lat': None,
            'lng': None,
            'tabelog_url': tabelog_url,
            'source_video_title': heading,
            'program': program,
            'rst_id': rst_id,
        })

    print(f'  → {len(shops)}件')
    return shops


def enrich_from_tabelog(shops):
    """tabelog ページから正確な住所・座標を取得"""
    for i, shop in enumerate(shops):
        if shop.get('lat') and shop.get('lng'):
            continue
        tabelog_url = shop.get('tabelog_url', '')
        if not tabelog_url:
            print(f'  [{i+1}] {shop["name"]} tabelog_urlなし')
            continue

        print(f'  [{i+1}] {shop["name"]} → {tabelog_url}')
        data = get_tabelog_data(tabelog_url)
        if data.get('lat'):
            shop['lat'] = data['lat']
            shop['lng'] = data['lng']
            # Use tabelog's full name (display name in matome is often truncated)
            if data.get('name') and len(data['name']) > len(shop.get('name', '')):
                shop['name'] = data['name']
            # Use tabelog's full address
            if data.get('address') and len(data['address']) > len(shop.get('address', '')):
                pref, city = split_prefecture_city(data['address'])
                shop['address'] = data['address']
                if pref:
                    shop['prefecture'] = pref
                    shop['city'] = city
            print(f'    lat={data["lat"]:.4f}, lng={data["lng"]:.4f} name={shop["name"]}')
        else:
            print(f'    座標取得失敗')
        time.sleep(1)
    return shops


def to_shop_entry(shop):
    """shops.json フォーマットに変換"""
    name = shop['name']
    tabelog_url = shop.get('tabelog_url', '')
    return {
        'name': name,
        'genre': shop['genre'],
        'prefecture': shop['prefecture'],
        'city': shop['city'],
        'address': shop['address'],
        'lat': shop.get('lat'),
        'lng': shop.get('lng'),
        'youtube_id': '',
        'source_video_title': shop.get('source_video_title', ''),
        'source_video_url': '',
        'visited_date': '',
        'members': [],
        'groups': [GROUP],
        'group': GROUP,
        'description': '',
        'nearest_station': '',
        'price_range': '',
        'tabelog_url': tabelog_url,
        'hotpepper_url': '',
        'google_maps_url': '',
        'tags': [],
        'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}] if tabelog_url else [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--output', default='scripts/scraped_tabelog_matome.json')
    args = parser.parse_args()

    all_shops = []
    seen_ids = set()
    for url in args.urls:
        shops = scrape_matome(url)
        for s in shops:
            if s['rst_id'] not in seen_ids:
                seen_ids.add(s['rst_id'])
                all_shops.append(s)

    print(f'\n{len(all_shops)}件（重複除去後）。tabelog から座標取得中...')
    all_shops = enrich_from_tabelog(all_shops)

    output = [to_shop_entry(s) for s in all_shops]
    no_coord = [s for s in output if not s['lat']]

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(output)}件')
    print(f'座標なし: {len(no_coord)}件')
    print(f'→ {args.output} に保存しました')
    print('\n次のステップ:')
    print('  python scripts/merge_shops.py --input', args.output)


if __name__ == '__main__':
    main()
