"""
scrape_ginga.py
中丸雄一 銀河チャンネルのロケ地まとめブログからお店情報をスクレイピング

対応ソース:
  - 8888-info.hatenablog.com（ロケ地一覧ページ）
    h4（MM月DD日配信：エリア【店名】）+ h5(住所) + ValueCommerceアフィリリンク

使い方:
  python scripts/scrape_ginga.py \\
    --urls "https://8888-info.hatenablog.com/entry/%E3%83%AD%E3%82%B1%E5%9C%B0%E4%B8%80%E8%A6%A7" \\
    --year 2025 \\
    --output scripts/scraped_ginga.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
from bs4 import BeautifulSoup

GROUP = 'ginga'
MEMBER = '中丸雄一'

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', '肉', 'BBQ', 'バーベキュー', 'LIEBE', 'リーベ'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'すし'], '寿司'),
    (['カフェ', 'cafe', 'CAFE', 'コーヒー', '珈琲', 'ベーカリー', 'パン', 'トースト'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'パティスリー', 'チョコ', 'プリン'], 'スイーツ'),
    (['居酒屋', 'バー', '酒', 'ダイニング'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['カレー', 'インド', 'スパイス'], '食事'),
    (['ハンバーガー', 'バーガー'], '食事'),
    (['中華', 'チャイナ', '点心', '飲茶', '餃子'], '中華'),
    (['イタリアン', 'パスタ', 'ピザ'], '食事'),
    (['焼き鳥', '天ぷら', '和食', '割烹', '料亭'], '和食'),
]


def make_tabelog_url(name):
    return 'https://tabelog.com/rstLst/?vs=1&sa=&sk=' + urllib.parse.quote(name)


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def extract_vc_url(href):
    """ValueCommerceアフィリエイトリンクから実URLを取得"""
    m = re.search(r'vc_url=([^&"]+)', href)
    if m:
        return urllib.parse.unquote(m.group(1))
    return ''


def parse_h4(text):
    """
    '7月9日配信：新大久保【大久堂 OKUDO カフェ】' を解析
    → (month, day, shop_name, area)
    """
    date_m = re.search(r'(\d+)月(\d+)日', text)
    month = int(date_m.group(1)) if date_m else 0
    day   = int(date_m.group(2)) if date_m else 0

    name_m = re.search(r'[【\[](.+?)[】\]]', text)
    shop_name = name_m.group(1).strip() if name_m else ''

    # エリア: 「：」と「【」の間
    area_m = re.search(r'[：:]\s*(.+?)\s*[【\[]', text)
    area = area_m.group(1).strip() if area_m else ''

    return month, day, shop_name, area


def parse_address(td):
    """住所セル（h5住所 直後のテキスト/pノード）から住所文字列を取得"""
    h5 = td.find('h5')
    if not h5:
        return ''

    # h5以降のノードを走査し、iframeやciteが出たら止める
    lines = []
    for node in h5.next_siblings:
        # iframe・cite・図要素は住所と無関係なので終了
        if hasattr(node, 'name') and node.name in ('iframe', 'cite', 'figure'):
            break
        if hasattr(node, 'name') and node.name == 'p':
            # pタグの中にiframeがある場合はスキップ
            if node.find('iframe'):
                break
            lines.append(node.get_text(separator='\n', strip=True))
        elif hasattr(node, 'name') and node.name == 'br':
            continue
        elif hasattr(node, 'name') and node.name:
            lines.append(node.get_text(separator='\n', strip=True))
        else:
            # テキストノード
            text = str(node).strip()
            if text:
                lines.append(text)

    # 全行を結合して住所でないもの（〒/☎/✅/空）を除去
    address_lines = []
    for raw_line in '\n'.join(lines).split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('〒') or line.startswith('☎') or '✅' in line:
            continue
        # ドメイン名・URLっぽい文字列は除外
        if 'hatenablog' in line or 'http' in line or line.startswith('8888'):
            continue
        address_lines.append(line)
    return ''.join(address_lines)


def split_prefecture_city(address):
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
        if address.startswith(pref):
            rest = address[len(pref):]
            city_m = re.match(r'^([^\d\s（(【「]{1,10}[市区町村郡])', rest)
            city = city_m.group(1) if city_m else ''
            return pref, city
    return '', ''


def scrape_hatenablog(url, soup, year):
    shops = []
    tables = soup.find_all('table', style=lambda s: s and 'border' in s)

    for table in tables:
        # h4から店名・日付・エリアを取得
        h4 = table.find('h4')
        if not h4:
            continue
        raw_title = h4.get_text(strip=True)
        month, day, shop_name, area = parse_h4(raw_title)
        if not shop_name:
            continue

        visited_date = ''
        if month and day:
            visited_date = f'{year}-{month:02d}-{day:02d}'

        # 住所セル（h5 id="住所..." を含むtd）
        address = ''
        for td in table.find_all('td'):
            if td.find('h5'):
                address = parse_address(td)
                break

        if not address:
            continue  # 住所なし＝店舗ブロックでない可能性

        prefecture, city = split_prefecture_city(address)

        # ValueCommerceリンクからtabelog/hotpepper URL取得
        tabelog_url = ''
        hotpepper_url = ''
        for a in table.find_all('a', href=True):
            href = a.get('href', '')
            if 'valuecommerce' not in href and 'ck.jp.ap' not in href:
                continue
            actual_url = extract_vc_url(href)
            label = a.get_text(strip=True)
            if 'tabelog' in actual_url and not tabelog_url:
                tabelog_url = actual_url
            elif 'hotpepper' in actual_url and not hotpepper_url:
                hotpepper_url = actual_url

        if not tabelog_url:
            tabelog_url = make_tabelog_url(shop_name)

        genre = detect_genre(shop_name + area)

        affiliate_links = [{'label': '食べログで見る', 'url': tabelog_url}]
        if hotpepper_url:
            affiliate_links.append({'label': 'ホットペッパーで予約', 'url': hotpepper_url})

        shops.append({
            'name': shop_name,
            'genre': genre,
            'prefecture': prefecture,
            'city': city,
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': '銀河チャンネル',
            'source_video_url': '',
            'visited_date': visited_date,
            'members': [MEMBER],
            'groups': [GROUP],
            'group': GROUP,
            'description': '',
            'nearest_station': '',
            'price_range': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': hotpepper_url,
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': affiliate_links,
        })

    return shops


def scrape_page(url, year):
    print(f'取得中: {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    shops = scrape_hatenablog(url, soup, year)
    print(f'  → {len(shops)}件取得')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--year', type=int, default=2025, help='データの年（デフォルト: 2025）')
    parser.add_argument('--output', default='scripts/scraped_ginga.json')
    args = parser.parse_args()

    all_shops = []
    for url in args.urls:
        all_shops.extend(scrape_page(url, args.year))

    # 重複除去（店名）
    seen = set()
    unique = []
    for s in all_shops:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    no_addr = [s for s in unique if not s['address']]
    print(f'\n完了: {len(unique)}件（重複除去後）')
    print(f'→ {args.output} に保存しました')
    print(f'住所なし: {len(no_addr)}件')
    print('\n次のステップ:')
    print(f'  python scripts/geocode_shops.py --input {args.output} --output scripts/geocoded_ginga.json')
    print(f'  python scripts/merge_shops.py --input scripts/geocoded_ginga.json')


if __name__ == '__main__':
    main()
