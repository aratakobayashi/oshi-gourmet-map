"""
scrape_tsuredure.py
tsuredure-nogi-blog.com の乃木坂46ロケ地テーブルから食スポットをスクレイピング

使い方:
  python scripts/scrape_tsuredure.py --output scripts/scraped_tsuredure.json
"""

import urllib.request
import urllib.parse
import json
import re
import time
import argparse
from bs4 import BeautifulSoup

GROUP = 'nogizaka46'

MEMBERS = [
    '秋元真夏', '衛藤美彩', '新内眞衣', '齋藤飛鳥', '松村沙友理',
    '西野七瀬', '桜井玲香', '白石麻衣', '堀未央奈', '生田絵梨花',
    '星野みなみ', '松井玲奈', '橋本奈々未', '若月佑美', '高山一実',
    '川後陽菜', '斉藤優里', '伊藤万理華', '深川麻衣', '大和里菜',
    '中元日芽香', '能條愛未', '大園桃子', '与田祐希', '山下美月',
    '岩本蓮加', '阪口珠美', '北野日奈子', '佐藤楓', '梅澤美波',
    '遠藤さくら', '賀喜遥香', '筒井あやめ', '田村真佑', '矢久保美緒',
    '柴田柚菜', '金川紗耶', '池田瑛紗', '中西アルノ', '五百城茉央',
    '井上和', '一ノ瀬美空', '冨里奈央', '林瑠奈',
    '飛鳥', 'まいやん', 'いくちゃん', '西野', '桜井',
]

# 食スポットとして含めるキーワード（完全一致でなくis_food判定に使用）
FOOD_INCLUDE_KW = [
    '食堂', 'レストラン', 'カフェ', '喫茶', 'ラーメン', '蕎麦', '寿司', '鮨',
    '焼肉', '居酒屋', 'パン屋', 'パン工房', 'スイーツ', 'ケーキ', 'アイス',
    '和菓子', '洋菓子', 'ピザ', 'カレー', '中華', '定食', '弁当', '惣菜',
    'うどん', 'バー', '農場', 'ファーム', 'コーヒー', '珈琲', 'ベーカリー',
    'ラウンジ', 'ビストロ', 'バル', 'ダイニング', 'キッチン', '茶房',
    '牛乳', 'チーズ', 'ミルク', '醸造所', '酒蔵', '工房', '市場',
    '食品', 'ランチ', 'グルメ', 'フード', '海鮮', '魚介',
    '餃子', 'ハンバーグ', 'ハンバーガー', 'そうめん', 'うなぎ', '天ぷら',
    '焼き鳥', '串カツ', '豚骨', '味噌', 'つけ麺', '冷麺', '担々麺',
    'クレープ', 'ワッフル', 'ドーナツ', 'たい焼き', 'どら焼き',
    'アンテナショップ', 'おにぎり', 'おでん', '鍋', 'すき焼き',
    '菓子', '甘味', '甘い', 'わらびもち', '団子', '饅頭', '大福', '羊羹',
    '精肉', '肉屋', '魚屋', '鮮魚',
    # 英語キーワード
    'cafe', 'CAFE', 'coffee', 'COFFEE', 'bakery', 'BAKERY', 'bar', 'BAR',
    'restaurant', 'RESTAURANT', 'diner', 'DINER', 'kitchen', 'KITCHEN',
    'food', 'FOOD', 'grill', 'GRILL', 'bistro', 'BISTRO',
]

# 末尾が「店」「屋」で終わるもの（店舗を示す）
SHOP_SUFFIX = ['本店', '支店', '店舗', '売店', '販売店', '料理店', '専門店', '飲食店', '食事処']

# 非食スポット除外キーワード（複合語・長めで誤マッチ防止）
FOOD_EXCLUDE_KW = [
    '公園', '神社', '寺院', '大学', '駅前広場', '記念館', '美術館', '博物館',
    '体育館', 'アリーナ', '球場', '競技場', '空港', '城跡', '湖', '海岸',
    '砂浜', '山頂', '展望台', '動物園', '水族館', '農業協同組合', '農協',
    '小学校', '中学校', '高等学校', '高校', '大学院', '図書館', '病院',
    '郵便局', '国会議事堂', '県庁', '役場', '市役所', '警察署', '消防署',
    '映画館', '撮影所', 'スタジオ', '劇場', 'スタジアム',
    '古墳', '神宮', '大社', '鳥居', '仏像', '石碑', '灯台', '港湾',
    '海水浴場', '滝', '温泉地', '観光地',
]


def is_food_spot(name):
    """店舗名から食スポットかどうかを判定"""
    if not name:
        return False
    # 除外キーワードチェック（長い複合語のみ）
    for kw in FOOD_EXCLUDE_KW:
        if kw in name:
            return False
    # 包含キーワードチェック
    for kw in FOOD_INCLUDE_KW:
        if kw in name:
            return True
    # 末尾が店/屋/や（平仮名）で終まる（ただし駅・停留所などを除く）
    if re.search(r'[店屋や]$', name):
        exclude_ends = ['駅', '停留所', '停車場', '海水浴場']
        if not any(name.endswith(e) for e in exclude_ends):
            return True
    # SHOP_SUFFIXチェック
    for s in SHOP_SUFFIX:
        if s in name:
            return True
    return False


GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', '蕎麦', 'うどん', 'そうめん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'ハンバーグ', 'ハンバーガー', 'BBQ'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'すし', '海鮮'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'ベーカリー', 'パン'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'チョコ', 'プリン', 'クレープ', 'ワッフル', 'ドーナツ', 'たい焼き', 'どら焼き', '和菓子', '洋菓子'], 'スイーツ'),
    (['居酒屋', 'バー', '酒場'], '居酒屋'),
    (['カレー', 'インド', 'スパイス'], '食事'),
    (['中華', '餃子', '点心', '飲茶', '担々麺'], '中華'),
    (['イタリアン', 'パスタ', 'ピザ', 'リゾット', 'ビストロ', 'バル'], '食事'),
    (['焼き鳥', '串カツ', '天ぷら', '和食', '定食', '食堂'], '和食'),
    (['喫茶', '茶房', '茶屋'], 'カフェ'),
    (['牛乳', 'チーズ', 'ミルク', 'ファーム', '農場'], 'その他'),
    (['市場', '惣菜', '弁当', '惣菜'], 'その他'),
]


def detect_genre(text):
    for kws, genre in GENRE_MAP:
        for kw in kws:
            if kw in text:
                return genre
    return 'その他'


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
            rest = address[len(pref):].strip()
            m = re.match(r'^(.{1,6}?[市区町村])', rest)
            city = m.group(1) if m else rest[:8]
            return pref, city
    return '', address[:10]


def extract_members(text):
    found = []
    for m in MEMBERS:
        if m in text and m not in found:
            found.append(m)
    return found


def clean_address(addr):
    """住所を整形"""
    if not addr:
        return ''
    addr = re.sub(r'〒\d{3}[-－]\d{4}\s*', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    # 座標文字列を除去
    addr = re.sub(r'\d+\.\d+[,、]\s*\d+\.\d+', '', addr).strip()
    return addr


def fetch_page(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0 (nogizaka46 research)'})
    html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8')
    return BeautifulSoup(html, 'html.parser')


def scrape_rokechi_page(url):
    """各都道府県ロケ地ページをスクレイプしてテーブルデータを抽出"""
    soup = fetch_page(url)
    full_text = soup.get_text(separator=' ', strip=True)
    shops = []

    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        if not rows:
            continue
        # ヘッダー行を確認（ロケ地/住所/メディア形式か）
        headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
        if len(headers) < 2:
            continue

        # カラムインデックスを推定
        name_idx, addr_idx, media_idx = 0, 1, 2
        for i, h in enumerate(headers):
            if 'ロケ' in h or '名前' in h or '施設' in h or '店' in h:
                name_idx = i
            elif '住所' in h or '座標' in h or '場所' in h:
                addr_idx = i
            elif 'メディア' in h or '番組' in h or '出典' in h or '出演' in h:
                media_idx = i

        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            name = cells[name_idx].get_text(strip=True) if name_idx < len(cells) else ''
            addr_raw = cells[addr_idx].get_text(strip=True) if addr_idx < len(cells) else ''
            media = cells[media_idx].get_text(strip=True) if media_idx < len(cells) else ''

            name = re.sub(r'\s+', ' ', name).strip()
            address = clean_address(addr_raw)

            if not name or not address:
                continue
            if not is_food_spot(name):
                continue
            # 住所が実際の住所っぽくなければスキップ
            if not any(c in address for c in ['市', '区', '町', '村', '丁目', '番']):
                if not re.search(r'\d', address):
                    continue

            prefecture, city = split_prefecture_city(address)
            # 都道府県が取れなければURLから推定
            if not prefecture:
                pref_map = {
                    'hokkaidou': '北海道', 'hokkaido': '北海道',
                    'tohoku': '宮城県', 'aomori': '青森県', 'iwate': '岩手県',
                    'miyagi': '宮城県', 'akita': '秋田県', 'yamagata': '山形県',
                    'fukushima': '福島県', 'ibaragi': '茨城県', 'tochigi': '栃木県',
                    'gunma': '群馬県', 'saitama': '埼玉県', 'chiba': '千葉県',
                    'tokyo': '東京都', 'kanagawa': '神奈川県', 'niigata': '新潟県',
                    'toyama': '富山県', 'ishikawa': '石川県', 'fukui': '福井県',
                    'yamanashi': '山梨県', 'nagano': '長野県', 'gifu': '岐阜県',
                    'shizuoka': '静岡県', 'aichi': '愛知県', 'mie': '三重県',
                    'shiga': '滋賀県', 'kyoto': '京都府', 'osaka': '大阪府',
                    'hyogo': '兵庫県', 'nara': '奈良県', 'wakayama': '和歌山県',
                    'tottori': '鳥取県', 'shimane': '島根県', 'okayama': '岡山県',
                    'hiroshima': '広島県', 'yamaguchi': '山口県', 'tokushima': '徳島県',
                    'kagawa': '香川県', 'ehime': '愛媛県', 'kochi': '高知県',
                    'fukuoka': '福岡県', 'saga': '佐賀県', 'nagasaki': '長崎県',
                    'kumamoto': '熊本県', 'oita': '大分県', 'miyazaki': '宮崎県',
                    'kagoshima': '鹿児島県', 'okinawa': '沖縄県',
                    'kansai': '大阪府', 'kyusyu': '福岡県', 'shikoku': '香川県',
                    'tyugoku': '広島県', 'hokuriku': '石川県',
                }
                for key, pref in pref_map.items():
                    if key in url:
                        prefecture = pref
                        break

            members = extract_members(full_text)
            genre = detect_genre(name + media)

            shops.append({
                'name': name,
                'genre': genre,
                'prefecture': prefecture,
                'city': city,
                'address': address,
                'lat': None,
                'lng': None,
                'youtube_id': '',
                'source_video_title': media[:50] if media else '乃木坂46',
                'source_video_url': '',
                'visited_date': '',
                'members': [],
                'groups': [GROUP],
                'group': GROUP,
                'description': f'出典: {media[:40]}',
                'nearest_station': '',
                'price_range': '',
                'tags': [],
            })

    return shops


ALL_PAGES = [
    'https://tsuredure-nogi-blog.com/rokechi-hokkaidou',
    'https://tsuredure-nogi-blog.com/rokechi-tohoku',
    'https://tsuredure-nogi-blog.com/rokechi-tochigi-2',
    'https://tsuredure-nogi-blog.com/rokechi-tochigi-ashikaga',
    'https://tsuredure-nogi-blog.com/rokechi-ibaragi',
    'https://tsuredure-nogi-blog.com/rokechi-gunma',
    'https://tsuredure-nogi-blog.com/rokechi-saitama',
    'https://tsuredure-nogi-blog.com/rokechi-saitama-east',
    'https://tsuredure-nogi-blog.com/rokechi-chiba-1',
    'https://tsuredure-nogi-blog.com/rokechi-chiba-2',
    'https://tsuredure-nogi-blog.com/rokechi-chiba-5',
    'https://tsuredure-nogi-blog.com/rokechi-minatoku-nogizaka-omotesanndou',
    'https://tsuredure-nogi-blog.com/rokechi-minatoku-akasaka',
    'https://tsuredure-nogi-blog.com/rokechi-minatoku-azabu',
    'https://tsuredure-nogi-blog.com/rokechi-kanagawa-kamakura/',
    'https://tsuredure-nogi-blog.com/rokechi-kanagawa-enoshima',
    'https://tsuredure-nogi-blog.com/rokechi-kanagawa-yokohama',
    'https://tsuredure-nogi-blog.com/rokechi-yamanashi',
    'https://tsuredure-nogi-blog.com/rokechi-nagano/',
    'https://tsuredure-nogi-blog.com/rokechi-hokuriku',
    'https://tsuredure-nogi-blog.com/rokechi-shizuoka/',
    'https://tsuredure-nogi-blog.com/rokechi-shizuoka-2/',
    'https://tsuredure-nogi-blog.com/rokechi-aichi',
    'https://tsuredure-nogi-blog.com/rokechi-gihu/',
    'https://tsuredure-nogi-blog.com/rokechi-kansai',
    'https://tsuredure-nogi-blog.com/rokechi-kyoto',
    'https://tsuredure-nogi-blog.com/rokechi-kyoto/',
    'https://tsuredure-nogi-blog.com/rokechi-osaka',
    'https://tsuredure-nogi-blog.com/rokechi-tyugoku-region',
    'https://tsuredure-nogi-blog.com/rokechi-shikoku',
    'https://tsuredure-nogi-blog.com/rokechi-kyusyu',
    'https://tsuredure-nogi-blog.com/rokechi-kyusyu-2-oita-hukuoka-saga',
    'https://tsuredure-nogi-blog.com/rokechi-okinawa',
    # 東京都の各区ページ
    'https://tsuredure-nogi-blog.com/rokechi-endosakura',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_tsuredure.json')
    parser.add_argument('--pages', nargs='+', help='特定ページのみ処理')
    args = parser.parse_args()

    pages = args.pages if args.pages else ALL_PAGES
    all_shops = []
    seen_names = set()

    for url in pages:
        print(f'取得中: {url.split("/")[-1] or url.split("/")[-2]}')
        try:
            shops = scrape_rokechi_page(url)
            new = [s for s in shops if s['name'] not in seen_names]
            seen_names.update(s['name'] for s in new)
            all_shops.extend(new)
            print(f'  → {len(new)}件 (食スポット)')
            time.sleep(1)
        except Exception as e:
            print(f'  エラー: {e}')
            time.sleep(2)

    # 既存DBと重複チェック
    try:
        with open('data/shops.json', encoding='utf-8') as f:
            existing = {s['name'] for s in json.load(f)}
        before = len(all_shops)
        all_shops = [s for s in all_shops if s['name'] not in existing]
        print(f'\n既存DBと照合: {before - len(all_shops)}件重複除去')
    except Exception:
        pass

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)

    print(f'\n合計: {len(all_shops)}件 → {args.output}')
    no_addr = sum(1 for s in all_shops if not s.get('address'))
    print(f'住所なし: {no_addr}件')


if __name__ == '__main__':
    main()
