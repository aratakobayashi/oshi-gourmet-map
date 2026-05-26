"""
scrape_kinpri.py
King & Prince「当たり前レストラン」（King&Princeる。）ファンブログスクレイピング

対応ソース:
  - tsuzuki-fam.com: h2=店名、p=住所・予約リンク形式

使い方:
  python scripts/scrape_kinpri.py --output scripts/scraped_kinpri.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
import time
from bs4 import BeautifulSoup, Tag


def extract_tabelog_url(href):
    """ValueCommerce経由リンクからtabelog URLを抽出"""
    if 'vc_url=' in href:
        vc = href.split('vc_url=')[1].split('&')[0]
        decoded = urllib.parse.unquote(vc)
        if 'tabelog.com' in decoded:
            return decoded.split('?')[0]
    if 'tabelog.com' in href and 'valuecommerce' not in href:
        return href.split('?')[0]
    return ''


def get_tabelog_data(tabelog_url):
    """tabelogページのJSON-LDからname/address/lat/lngを取得"""
    try:
        req = urllib.request.Request(tabelog_url, headers={'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36'})
        html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
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
                    return {'name': data.get('name', ''), 'address': full_addr, 'lat': lat, 'lng': lng}
            except Exception:
                pass
    except Exception as e:
        print(f'    tabelog取得エラー: {e}')
    return {}

GROUP = 'kingprince'
PROGRAM = 'King&Princeる。当たり前レストラン'

MEMBERS = [
    '平野紫耀', '神宮寺勇太', '岸優太', '髙橋海人', '永瀬廉',
    '高橋海人',  # 表記ゆれ
]

EPISODE_URLS = [
    ('2022-08-13', 'https://tsuzuki-fam.com/kpr-atarimae0813/'),
    ('2022-09-03', 'https://tsuzuki-fam.com/atarimae0903/'),
    ('2022-09-10', 'https://tsuzuki-fam.com/atarimae0910/'),
    ('2022-10-15', 'https://tsuzuki-fam.com/atarimae1015/'),
    ('2022-10-22', 'https://tsuzuki-fam.com/atarimae-1022/'),
    ('2022-12-03', 'https://tsuzuki-fam.com/atarimae-1203/'),
    ('2022-12-10', 'https://tsuzuki-fam.com/atarimae1210/'),
    ('2023-05-20', 'https://tsuzuki-fam.com/atarimae-final/'),
]

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'シュラスコ', 'プルコギ', 'サムギョプサル'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン', 'ブーランジェリー', 'クレープリー'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'チョコ', 'タルト', 'クロワッサン', 'カヌレ', 'ショコラ', 'パティスリー', 'ミルフィーユ', 'クレーム', 'トルテ'], 'スイーツ'),
    (['居酒屋', 'バー', '酒'], '居酒屋'),
    (['お好み焼き', 'もんじゃ'], 'もんじゃ'),
    (['カレー', 'インド', 'タイ', 'アジア', 'ビリヤニ'], '食事'),
    (['中華', '四川', '飲茶', '点心', '餃子'], '中華'),
    (['フレンチ', 'フランス', 'ビストロ', 'ガストロノミー', 'ロブション', 'ボキューズ'], '食事'),
    (['イタリアン', 'パスタ', 'ピザ', 'ピッツェリア'], '食事'),
    (['海鮮', '寿司', 'まぐろ', '海老', '魚'], '食事'),
]

PREFECTURES = [
    '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
    '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
    '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
    '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
    '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
    '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
    '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def split_prefecture_city(address):
    for pref in PREFECTURES:
        if address.startswith(pref):
            rest = address[len(pref):]
            city_m = re.match(r'^(.{1,6}?[市区町村])', rest)
            city = city_m.group(1) if city_m else ''
            return pref, city
    return '', ''


def extract_members(text):
    found = []
    for m in MEMBERS:
        if m in text and m not in found:
            # 髙橋 → 髙橋海人 に正規化
            canonical = '髙橋海人' if m == '高橋海人' else m
            if canonical not in found:
                found.append(canonical)
    return found


def normalize_address(addr):
    """全角数字・記号を半角に、〒郵便番号を除去"""
    addr = re.sub(r'〒\d{3}[-－]\d{4}\s*', '', addr)
    result = []
    for ch in addr:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif ch == '　':
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result).strip()


def scrape_episode(visited_date, url):
    print(f'取得中: {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36'})
    html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    content = soup.find('article') or soup.find('div', class_='entry-content') or soup.find('main')
    if not content:
        print('  コンテンツ領域が見つかりません')
        return []

    shops = []
    h2_tags = content.find_all('h2')

    for h2 in h2_tags:
        shop_name = h2.get_text(strip=True)
        # ナビ系・記事タイトル系のh2を除外
        if any(skip in shop_name for skip in ['まとめ', '目次', 'スポンサー', 'プロフィール', 'コメント']):
            continue
        # @東京・渋谷 などの位置情報を除去
        shop_name = re.sub(r'[　\s]*[@＠].+$', '', shop_name).strip()
        # 読み仮名（ひらがな）括弧除去
        shop_name = re.sub(r'[\s　]*[（(][ぁ-ん\s]+[）)]', '', shop_name).strip()
        if len(shop_name) < 2 or len(shop_name) > 40:
            continue

        # h2以降、次のh2までの要素を収集
        block_texts = []
        block_links = {}  # label -> url
        for sib in h2.next_siblings:
            if not isinstance(sib, Tag):
                continue
            if sib.name == 'h2':
                break
            text = sib.get_text(separator=' ', strip=True)
            block_texts.append(text)
            for a in sib.find_all('a', href=True):
                href = a['href']
                label = a.get_text(strip=True)
                if 'hotpepper.jp' in href or 'ikyu.com' in href:
                    block_links[label] = href
                else:
                    tb = extract_tabelog_url(href)
                    if tb:
                        block_links[label] = tb

        full_text = ' '.join(block_texts)

        # 住所を抽出（〒から始まる行）
        address = ''
        for text in block_texts:
            m = re.search(r'〒\d{3}[-－]\d{4}\s*(.+?)(?:\s|$)', text)
            if m:
                address = normalize_address('〒' + text[m.start()+1:].strip().split('\n')[0])
                break
            # 都道府県から始まる場合も
            for pref in PREFECTURES:
                if text.startswith(pref):
                    address = normalize_address(text.split('\n')[0])
                    break
            if address:
                break

        # 住所なしはtabelog URLから取得を試みる
        tabelog_url_from_link = next((v for k, v in block_links.items() if 'tabelog.com' in v), '')
        lat, lng = None, None
        if not address and tabelog_url_from_link:
            print(f'  tabelog補完中: {shop_name}')
            tb_data = get_tabelog_data(tabelog_url_from_link)
            time.sleep(1)
            if tb_data.get('lat'):
                address = tb_data.get('address', '')
                lat = tb_data['lat']
                lng = tb_data['lng']
                if tb_data.get('name') and len(tb_data['name']) > len(shop_name):
                    shop_name = tb_data['name']

        if not address:
            print(f'  住所なし: {shop_name}')
            continue

        prefecture, city = split_prefecture_city(address)
        members = extract_members(full_text)
        genre = detect_genre(shop_name + full_text)

        # 予約リンク
        hotpepper_url = next((v for k, v in block_links.items() if 'hotpepper' in v), '')
        tabelog_url = next((v for k, v in block_links.items() if 'tabelog.com' in v), '')
        ikyu_url = next((v for k, v in block_links.items() if 'ikyu.com' in v), '')

        # 注文アイテム（答えは〇〇、正解は〇〇パターン）
        ordered_items = []
        for m in re.finditer(r'(?:答えは|正解は|出題は)(.{2,20}?)(?:[。、．\s]|$)', full_text):
            item = m.group(1).strip('「」『』【】')
            if item and len(item) < 20:
                ordered_items.append(item)

        description = ''
        for text in block_texts[:2]:
            if len(text) > 20 and '問目は' in text or 'から' in text:
                description = re.sub(r'\s+', ' ', text).strip()[:200]
                break

        affiliate_links = []
        if hotpepper_url:
            affiliate_links.append({'label': 'ホットペッパーで予約', 'url': hotpepper_url})
        if tabelog_url:
            affiliate_links.append({'label': '食べログで見る', 'url': tabelog_url})
        if not affiliate_links and ikyu_url:
            affiliate_links.append({'label': '一休で予約', 'url': ikyu_url})

        shops.append({
            'name': shop_name,
            'genre': genre,
            'prefecture': prefecture,
            'city': city,
            'address': address,
            'lat': lat,
            'lng': lng,
            'youtube_id': '',
            'source_video_title': PROGRAM,
            'source_video_url': '',
            'visited_date': visited_date,
            'members': members if members else ['平野紫耀', '神宮寺勇太', '岸優太', '髙橋海人', '永瀬廉'],
            'groups': [GROUP],
            'group': GROUP,
            'description': description,
            'nearest_station': '',
            'price_range': '',
            'ordered_items': ordered_items,
            'tabelog_url': tabelog_url,
            'hotpepper_url': hotpepper_url,
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': affiliate_links,
        })

    print(f'  → {len(shops)}件')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kinpri.json')
    args = parser.parse_args()

    all_shops = []
    seen_names = set()

    for visited_date, url in EPISODE_URLS:
        shops = scrape_episode(visited_date, url)
        for s in shops:
            if s['name'] not in seen_names:
                seen_names.add(s['name'])
                all_shops.append(s)
        time.sleep(1)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)

    no_addr = [s for s in all_shops if not s['address']]
    print(f'\n完了: {len(all_shops)}件（住所なし: {len(no_addr)}件）')
    print(f'→ {args.output} に保存しました')
    print('\n次のステップ:')
    print(f'  python scripts/geocode_shops.py --input {args.output} --output scripts/geocoded_kinpri.json')
    print(f'  python scripts/merge_shops.py --input scripts/geocoded_kinpri.json')


if __name__ == '__main__':
    main()
