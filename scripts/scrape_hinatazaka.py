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

# ソースD: zakki10.blogspot.com 都道府県別聖地まとめ（9ページ）
ZAKKI10_PAGES = [
    {'url': 'https://zakki10.blogspot.com/2022/04/hinatazaka46-seichi-hokkaido-tohoku.html',
     'regions': ['北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県']},
    {'url': 'https://zakki10.blogspot.com/2022/05/hinatazaka46-seichi-kitakanto.html',
     'regions': ['茨城県', '栃木県', '群馬県', '埼玉県']},
    {'url': 'https://zakki10.blogspot.com/2022/05/hinatazaka46-seichi-tokyo.html',
     'regions': ['東京都']},
    {'url': 'https://zakki10.blogspot.com/2022/05/hinatazaka46-seichi-chiba.html',
     'regions': ['千葉県']},
    {'url': 'https://zakki10.blogspot.com/2022/05/hinatazaka46-seichi-kanagawa.html',
     'regions': ['神奈川県']},
    {'url': 'https://zakki10.blogspot.com/2022/04/hinatazaka46-seichi-chubu.html',
     'regions': ['新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県', '静岡県', '愛知県']},
    {'url': 'https://zakki10.blogspot.com/2022/04/hinatazaka46-seichi-kansai.html',
     'regions': ['三重県', '滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県']},
    {'url': 'https://zakki10.blogspot.com/2022/04/hinatazaka46-seichi-chugoku-shikoku.html',
     'regions': ['鳥取県', '島根県', '岡山県', '広島県', '山口県', '徳島県', '香川県', '愛媛県', '高知県']},
    {'url': 'https://zakki10.blogspot.com/2022/04/hinatazaka46-seichi-kyushu-okinawa.html',
     'regions': ['福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県']},
]

FOOD_KEYWORDS = [
    'カフェ', 'cafe', 'Cafe', 'CAFE', 'ラーメン', '食堂', '定食', '居酒屋',
    '寿司', '鮨', '焼肉', '焼き肉', 'ステーキ', '鉄板', 'パン', 'ベーカリー',
    'スイーツ', 'ケーキ', 'アイス', 'かき氷', '今川焼', 'コーヒー', '珈琲',
    'そば', 'うどん', 'つけ麺', '冷麺', '餃子', '中華', '海鮮', '天ぷら',
    'とんかつ', '豚カツ', 'とんき', 'バー', 'bar', 'Bar', 'ビストロ', 'レストラン',
    'restaurant', 'Restaurant', 'イタリアン', 'フレンチ', '和食', '洋食',
    '韓国', 'タイ', 'インド', 'カレー', '餅', 'もち', '串', '丼', '鍋',
    '牛タン', 'ホルモン', 'やきとり', '焼き鳥', 'すき焼き', 'しゃぶ',
    'パスタ', 'ピザ', 'ヴィーガン', 'vegan', 'ハンバーグ', 'ハンバーガー',
    'バーガー', 'ランチ', 'ビュッフェ', '食事', '飯', '麺', '肉',
    'いけす', '炉端', '炭火', 'おでん', '甘味', '和菓子', '洋菓子',
    'pudding', 'プリン', 'タルト', 'ガレット', 'クレープ', 'ドーナツ',
    'チーズ', '抹茶', 'わらび', '白玉', 'みたらし', '大福',
    'boulangerie', 'Boulangerie', 'patisserie', 'Patisserie',
    'lounge', 'Lounge', 'LOUNGE', 'dining', 'Dining', 'DINING',
    'キッチン', 'kitchen', 'Kitchen',
]

NONFOOD_KEYWORDS = [
    '公園', '神社', '寺', '城', '橋', '駅', '空港', '港', '山', '川', '湖', '海',
    '博物館', '美術館', '図書館', '病院', '学校', '大学', '高校',
    '映画館', 'シネマ', '劇場', 'ライブ', 'ホール', 'スタジアム', '球場',
    '温泉', '銭湯', '旅館', 'ホテル',
    'ショッピング', 'モール', '百貨店', 'デパート', 'スーパー',
    'コンビニ', 'ドラッグ', 'サロン', '美容', 'スポーツ', 'ジム',
    '撮影地', 'ロケ地', '展望台', '遊園地', '水族館', '動物園',
    'おもちゃ', 'ゲーム', 'アニメ', '漫画', '書店', '雑貨',
    '花', '植物園', '農園', '牧場',
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


# ── ソースD: zakki10.blogspot.com 都道府県別聖地まとめ ──

def _is_food(name):
    if any(kw in name for kw in NONFOOD_KEYWORDS):
        return False
    if any(kw in name for kw in FOOD_KEYWORDS):
        return True
    return False


def _parse_prefecture_from_h3(h3_text, page_regions):
    """h3テキストから都道府県を推定する"""
    for pref in page_regions:
        if pref in h3_text:
            return pref
    # 区・市・町・村・郡が含まれる場合はそのまま使えないが都道府県を返せない
    return ''


def scrape_zakki10_hinatazaka():
    """zakki10.blogspot.com の9ページ全てをスクレイピングして飲食店のみ返す"""
    all_shops = []
    seen_names = set()

    for page_info in ZAKKI10_PAGES:
        url = page_info['url']
        print(f'取得中: {url}')
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f'  エラー: {e}')
            time.sleep(2)
            continue
        time.sleep(1.5)

        soup = BeautifulSoup(html, 'html.parser')
        content = soup.find('div', class_='post-body') or \
                  soup.find('div', class_='entry-content') or \
                  soup.find('article') or soup.body
        if not content:
            print('  コンテンツ要素が見つかりません')
            continue

        current_pref = page_info['regions'][0] if page_info['regions'] else ''
        current_city = ''

        page_shops = []

        # h3, ul を順番に走査
        for tag in content.find_all(['h3', 'ul', 'h2']):
            if tag.name in ('h2', 'h3'):
                h3_text = tag.get_text(strip=True)
                # 都道府県の切り替えを検出
                detected = _parse_prefecture_from_h3(h3_text, page_info['regions'])
                if detected:
                    current_pref = detected
                    current_city = ''
                else:
                    # 市区町村レベルの見出しの可能性
                    city_m = re.search(r'([^\s（(【「]{1,12}[市区町村郡])', h3_text)
                    if city_m:
                        current_city = city_m.group(1)
                continue

            # ul > li をパース
            for li in tag.find_all('li', recursive=False):
                li_text = li.get_text(strip=True)

                # 「・店名（番組名）」形式 → 先頭の・を除去
                li_text = li_text.lstrip('・').strip()
                if not li_text:
                    continue

                # 番組名は（）内に入っている場合が多い
                m = re.match(r'^(.+?)(?:[（(](.+?)[)）])?$', li_text)
                if not m:
                    continue
                shop_name = m.group(1).strip()
                program = m.group(2).strip() if m.group(2) else ''

                # 空・短すぎるものはスキップ
                if not shop_name or len(shop_name) < 2:
                    continue

                # tabelog リンクがあれば取得
                tabelog_url_found = ''
                for a in li.find_all('a', href=True):
                    href = a['href']
                    if 'tabelog.com' in href:
                        tabelog_url_found = href
                        break

                # 飲食店フィルター: 名前ベース + プログラム名ベース
                food_prog_keywords = ['グルメ', 'せっかく', '食べ', '飯', 'ランチ', 'グルメ']
                is_food_prog = any(kw in program for kw in food_prog_keywords)

                if not _is_food(shop_name) and not is_food_prog:
                    continue

                # 重複スキップ
                if shop_name in seen_names:
                    continue
                seen_names.add(shop_name)

                genre = detect_genre(shop_name)
                tabelog_url = tabelog_url_found or make_tabelog_url(shop_name)
                aff = [{'label': '食べログで見る', 'url': tabelog_url}]

                page_shops.append({
                    'name': shop_name,
                    'genre': genre,
                    'prefecture': current_pref,
                    'city': current_city,
                    'address': '',
                    'lat': None,
                    'lng': None,
                    'youtube_id': '',
                    'source_video_title': program,
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
                    'affiliate_links': aff,
                })

        print(f'  → 飲食店 {len(page_shops)}件取得')
        all_shops.extend(page_shops)

    print(f'zakki10 合計: {len(all_shops)}件')
    return all_shops


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

    # ソースD: zakki10.blogspot.com 9ページ
    zakki = scrape_zakki10_hinatazaka()
    print(f'zakki10 聖地まとめ: {len(zakki)}件')
    all_shops.extend(zakki)

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
