"""
scrape_hinatazaka.py
日向坂46グルメスポットのスクレイピング（複数ソース対応）

対応ソース:
  A. e宿.com / xn--e-3e2b.com
     せっかくグルメ銚子回など。h3+p形式、住所あり
  B. ひなたのまとめ (zakki10.blogspot.com)
     都道府県別聖地まとめ。h3+p形式、住所なし（店名でジオコーディング）

使い方:
  python scripts/scrape_hinatazaka.py --output scripts/scraped_hinatazaka.json
"""

import urllib.request
import urllib.parse
import json
import re
import time
import argparse
from bs4 import BeautifulSoup

GROUP = 'hinatazaka46'

# ソースA: e宿.com せっかくグルメ回
SEKKAKU_PAGES = [
    {
        'url': 'https://www.xn--e-3e2b.com/chiba/sekkaku200405_choshi/',
        'members': ['佐々木美玲', '丹生明里'],
        'program': 'バナナマンのせっかくグルメ',
        'visited_date': '2020-04-05',
        'prefecture': '千葉県',
    },
]

# ソースB: ひなたのまとめで確認済みの飲食店
# （スクレイピング済みデータから手動確認した飲食店のみ）
HINATA_CONFIRMED = [
    {'name': 'POPOCATE',              'city': '品川区', 'prefecture': '東京都', 'program': '日向坂で会いましょう', 'members': []},
    {'name': 'Boulangerie Sudo',      'city': '世田谷区', 'prefecture': '東京都', 'program': '日向坂で会いましょう', 'members': ['佐々木美玲']},
    {'name': 'ル・ポミエ',             'city': '世田谷区', 'prefecture': '東京都', 'program': '日向坂で会いましょう', 'members': []},
    {'name': 'ストロベリーマニア原宿店', 'city': '渋谷区',  'prefecture': '東京都', 'program': '日向の休日',          'members': ['東村芽依']},
    {'name': 'ザクリ珈琲',             'city': '杉並区',  'prefecture': '東京都', 'program': '日向の休日',          'members': ['宮田愛萌']},
    {'name': '鉄板焼き 玄 KURO',       'city': '新宿区',  'prefecture': '東京都', 'program': '自撮りTV',            'members': ['佐々木美玲']},
    {'name': 'CuBAR LOUNGE',          'city': '文京区',  'prefecture': '東京都', 'program': '自撮りTV',            'members': []},
    {'name': 'プラスヴィーガニック自由が丘', 'city': '目黒区', 'prefecture': '東京都', 'program': '自撮りTV',        'members': []},
    {'name': 'San Francisco Peaks',   'city': '渋谷区',  'prefecture': '東京都', 'program': 'あくびLetter',        'members': []},
    {'name': 'タナゴコロータス',         'city': '渋谷区',  'prefecture': '東京都', 'program': 'あくびLetter',        'members': []},
]

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん', '食堂'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', '鉄板', '和牛'], '焼肉'),
    (['寿司', '鮨', '海鮮', 'いけす', 'いけ'], '寿司'),
    (['カフェ', 'cafe', 'Cafe', 'CAFE', 'コーヒー', '珈琲', 'coffee'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'パティスリー', 'スイーツ',
      '今川焼', 'ベーカリー', 'パン', 'boulangerie', 'Boulangerie',
      'マニア', 'ストロベリー', 'ポミエ'], 'スイーツ'),
    (['居酒屋', 'バー', 'bar', 'Bar', 'LOUNGE', 'lounge'], '居酒屋'),
    (['中華', '餃子', '点心'], '中華'),
    (['ヴィーガン', 'vegan', 'VEGAN'], '食事'),
]


def make_tabelog_url(name):
    return 'https://tabelog.com/rstLst/?vs=1&sa=&sk=' + urllib.parse.quote(name)


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    return urllib.request.urlopen(req, timeout=20).read().decode('utf-8')


def extract_info_from_p(p_text):
    """「住所：〇〇\n電話番号：〇〇\n...」形式のpテキストから情報を抽出"""
    info = {}
    for line in p_text.split('\n'):
        line = line.strip()
        for key in ['住所', '電話番号', '営業時間', '定休日', 'URL']:
            if line.startswith(key + '：') or line.startswith(key + ':'):
                info[key] = re.sub(r'^' + key + r'[：:]', '', line).strip()
    return info


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


# ── ソースA: e宿.com スクレイパー ──

def scrape_sekkaku_page(page_info):
    """e宿.com 形式: h3（店舗見出し）+ 最後のp（住所・電話など）"""
    url = page_info['url']
    print(f'取得中: {url}')
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f'  エラー: {e}')
        return []

    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', class_='entry-content') or soup.find('article') or soup.body
    if not content:
        return []

    shops = []
    h3_tags = content.find_all('h3')

    for h3 in h3_tags:
        # h3から次のh3までのp要素を収集
        p_tags = []
        for sib in h3.next_siblings:
            if not hasattr(sib, 'name') or not sib.name:
                continue
            if sib.name == 'h3':
                break
            if sib.name == 'p':
                p_tags.append(sib)

        if not p_tags:
            continue

        # 店名: strong タグのテキスト、またはh3テキストから「」内
        shop_name = ''
        for p in p_tags:
            strong = p.find('strong')
            if strong:
                candidate = strong.get_text(strip=True)
                # メニュー名（価格つき）は除外
                if '円' not in candidate and len(candidate) < 30:
                    shop_name = candidate
                    break

        if not shop_name:
            # h3テキストから「〇〇」を抽出
            h3_text = h3.get_text(strip=True)
            m = re.search(r'「(.+?)」', h3_text)
            shop_name = m.group(1) if m else h3_text.strip()

        # 住所が含まれる最後のpを探す
        info = {}
        for p in reversed(p_tags):
            p_text = p.get_text(separator='\n', strip=True)
            if '住所' in p_text:
                info = extract_info_from_p(p_text)
                break

        address = info.get('住所', '')
        if not address:
            continue

        prefecture, city = split_prefecture_city(address)
        if not prefecture:
            prefecture = page_info.get('prefecture', '')

        genre = detect_genre(shop_name)
        tabelog_url = make_tabelog_url(shop_name)

        shops.append({
            'name': shop_name,
            'genre': genre,
            'prefecture': prefecture,
            'city': city,
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': page_info.get('program', ''),
            'source_video_url': '',
            'visited_date': page_info.get('visited_date', ''),
            'members': page_info.get('members', []),
            'groups': [GROUP],
            'group': GROUP,
            'description': '',
            'nearest_station': '',
            'price_range': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': '',
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}],
        })

    print(f'  → {len(shops)}件取得')
    return shops


# ── ソースB: せっかくグルメ銚子回（住所確認済み・直接定義） ──

SEKKAKU_CHOSHI = [
    {
        'name': '一山いけす',
        'address': '千葉県銚子市黒生町7387-5',
        'genre': '寿司',
        'members': ['佐々木美玲', '丹生明里'],
        'program': 'バナナマンのせっかくグルメ',
        'visited_date': '2020-04-05',
    },
    {
        'name': '元祖今川焼 さのや',
        'address': '千葉県銚子市飯沼町6-7',
        'genre': 'スイーツ',
        'members': ['佐々木美玲', '丹生明里'],
        'program': 'バナナマンのせっかくグルメ',
        'visited_date': '2020-04-05',
    },
    {
        'name': 'お食事処ゆうなぎ',
        'address': '千葉県銚子市川口町2-6528-2',
        'genre': 'ラーメン',
        'members': ['佐々木美玲', '丹生明里'],
        'program': 'バナナマンのせっかくグルメ',
        'visited_date': '2020-04-05',
    },
]

def build_sekkaku_choshi():
    shops = []
    for item in SEKKAKU_CHOSHI:
        address = item['address']
        prefecture, city = split_prefecture_city(address)
        tabelog_url = make_tabelog_url(item['name'])
        shops.append({
            'name': item['name'],
            'genre': item['genre'],
            'prefecture': prefecture,
            'city': city,
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': item['program'],
            'source_video_url': '',
            'visited_date': item['visited_date'],
            'members': item['members'],
            'groups': [GROUP],
            'group': GROUP,
            'description': '',
            'nearest_station': '',
            'price_range': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': '',
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}],
        })
    return shops


# ── ソースC: ひなたのまとめ確定10件 ──

def build_hinata_confirmed():
    """住所なし・店名ジオコーディング用の確定飲食店リスト"""
    shops = []
    for item in HINATA_CONFIRMED:
        name = item['name']
        genre = detect_genre(name)
        tabelog_url = make_tabelog_url(name)
        shops.append({
            'name': name,
            'genre': genre,
            'prefecture': item['prefecture'],
            'city': item['city'],
            'address': '',  # 住所なし → 店名でジオコーディング
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': item.get('program', ''),
            'source_video_url': '',
            'visited_date': '',
            'members': item.get('members', []),
            'groups': [GROUP],
            'group': GROUP,
            'description': '',
            'nearest_station': '',
            'price_range': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': '',
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}],
        })
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_hinatazaka.json')
    args = parser.parse_args()

    all_shops = []

    # ソースA: e宿.com
    for page in SEKKAKU_PAGES:
        all_shops.extend(scrape_sekkaku_page(page))
        time.sleep(1)

    # ソースB: せっかくグルメ銚子回（住所確認済み）
    choshi = build_sekkaku_choshi()
    print(f'せっかくグルメ銚子回: {len(choshi)}件')
    all_shops.extend(choshi)

    # ソースC: ひなたのまとめ確定リスト
    hinata = build_hinata_confirmed()
    print(f'ひなたのまとめ確定リスト: {len(hinata)}件')
    all_shops.extend(hinata)

    # 重複除去（店名）
    seen = set()
    unique = []
    for s in all_shops:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    addr_ok  = [s for s in unique if s['address']]
    addr_ng  = [s for s in unique if not s['address']]
    print(f'\n完了: {len(unique)}件')
    print(f'  住所あり: {len(addr_ok)}件（直接ジオコーディング）')
    print(f'  住所なし: {len(addr_ng)}件（店名+エリアでジオコーディング）')
    print(f'→ {args.output} に保存しました')
    print('\n次のステップ:')
    print(f'  python scripts/geocode_shops.py --input {args.output} --output scripts/geocoded_hinatazaka.json')
    print(f'  python scripts/merge_shops.py --input scripts/geocoded_hinatazaka.json')


if __name__ == '__main__':
    main()
