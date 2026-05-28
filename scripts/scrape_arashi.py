"""
scrape_arashi.py
activitv.com から「嵐にしやがれ」グルメロケ地をスクレイピング

使い方:
  python scripts/scrape_arashi.py --output scripts/scraped_arashi.json
  python scripts/scrape_arashi.py --dry-run   # URL一覧だけ確認
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
import time
from bs4 import BeautifulSoup

BASE_URL = 'https://www.activitv.com'
CATEGORY_URL = f'{BASE_URL}/entry/category/tv/arashinishiyagare/'

GROUP = 'arashi'
PROGRAM = '嵐にしやがれ'
MEMBERS_ALL = ['大野智', '櫻井翔', '相葉雅紀', '二宮和也', '松本潤']

PREFECTURES = [
    '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
    '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
    '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
    '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
    '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
    '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
    '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん', '麺'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'シュラスコ', 'プルコギ', 'サムギョプサル'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'すし'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン', 'ブーランジェリー', 'クレープリー'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'チョコ', 'タルト', 'クロワッサン', 'カヌレ', 'ショコラ', 'パティスリー', 'パンケーキ'], 'スイーツ'),
    (['居酒屋', 'バー', '酒場'], '居酒屋'),
    (['お好み焼き', 'もんじゃ', '焼き鳥', '串', '炭火'], '食事'),
    (['カレー', 'インド', 'タイ', 'アジア', 'ベトナム', 'フォー'], '食事'),
    (['中華', '四川', '飲茶', '点心', '餃子', '担々麺'], '中華'),
    (['フレンチ', 'フランス', 'ビストロ', 'ガストロノミー'], '食事'),
    (['イタリアン', 'パスタ', 'ピザ', 'ピッツェリア', 'リストランテ'], '食事'),
    (['海鮮', 'まぐろ', '刺身', '天ぷら', '和食', '割烹', '料亭', '懐石', 'おでん'], '食事'),
    (['オムライス', '洋食', 'ハンバーグ', 'ビーフ', 'とんかつ', '肉'], '食事'),
]


def fetch_html(url, delay=1.0):
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    )
    html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
    time.sleep(delay)
    return html


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def split_prefecture_city(address):
    for pref in PREFECTURES:
        if address.startswith(pref):
            rest = address[len(pref):]
            m = re.match(r'^(.{1,6}?[市区町村])', rest)
            city = m.group(1) if m else ''
            return pref, city
    return '', ''


def normalize_address(addr):
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


def extract_date_from_url(url):
    """URL から YYMMDD を抽出して YYYY-MM-DD に変換"""
    m = re.search(r'arashinishiyagare_(\d{6})', url)
    if not m:
        return ''
    s = m.group(1)
    yy, mm, dd = s[:2], s[2:4], s[4:6]
    year = '20' + yy
    return f'{year}-{mm}-{dd}'


def extract_shop_name_from_title(title):
    """タイトルから『店名』を抽出"""
    # 『店名（読み）』 or 『店名』
    matches = re.findall(r'[『「]([^』」]{2,40}?)[』」]', title)
    if matches:
        # 番組名・コーナー名を除く
        skip_patterns = ['明石家', 'NiziU', '出川', 'デスマッチ', '大好物', 'グルメ', 'ブレイク',
                         '嵐にしやがれ', 'コーナー', 'SP', '最終回']
        for m in matches:
            if not any(sk in m for sk in skip_patterns):
                # 読み仮名の括弧除去
                name = re.sub(r'[（(][ぁ-んァ-ヶ\s]+[）)]', '', m).strip()
                if len(name) >= 2:
                    return name
    return ''


def get_tabelog_data(tabelog_url):
    """食べログJSON-LDから name/address/lat/lng を取得"""
    try:
        req = urllib.request.Request(
            tabelog_url,
            headers={'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36'}
        )
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


def scrape_article(url):
    """個別記事ページから店舗情報を取得"""
    print(f'  取得: {url}')
    try:
        html = fetch_html(url, delay=1.5)
    except Exception as e:
        print(f'    取得エラー: {e}')
        return None

    soup = BeautifulSoup(html, 'html.parser')

    # タイトルから店名抽出: h1 → h2 の順で試す
    heading = soup.find('h1') or soup.find('h2', class_=re.compile(r'entry-title|post-title|article-title', re.I))
    if not heading:
        # class なしの最初の h2
        heading = soup.find('h2')
    title = heading.get_text(strip=True) if heading else (soup.find('title') or type('', (), {'get_text': lambda *a, **k: ''})()).get_text(strip=True)
    # <title> タグ fallback
    if not title:
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''

    shop_name = extract_shop_name_from_title(title)
    if not shop_name:
        print(f'    店名抽出失敗: {title[:60]}')
        return None

    # 本文
    content = (
        soup.find('article') or
        soup.find('div', class_='entry-content') or
        soup.find('main')
    )
    if not content:
        return None

    full_text = content.get_text(separator='\n', strip=True)

    # 住所: full_text から「住所」の次の行を抽出
    address = ''
    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        # 「住所: 東京都...」 or 「住所」の次行が都道府県
        if line == '住所' or line.startswith('住所：') or line.startswith('住所:'):
            addr_raw = re.sub(r'^住所[：:]\s*', '', line).strip()
            # 「住所」単独行 or 剥ぎ取り後が空 → 次行
            if (not addr_raw or addr_raw == '住所') and i + 1 < len(lines):
                addr_raw = lines[i + 1]
            if addr_raw and addr_raw != '住所':
                address = normalize_address(addr_raw)
            break
        # 都道府県で始まる行で直前行に「住所」がある
        for pref in PREFECTURES:
            if line.startswith(pref) and len(line) > len(pref) + 2:
                if i > 0 and '住所' in lines[i - 1]:
                    address = normalize_address(line)
                    break
        if address:
            break

    # フォールバック: 本文中の最初の都道府県+市区町村パターン
    if not address:
        for pref in PREFECTURES:
            idx = full_text.find(pref)
            if idx >= 0:
                candidate = full_text[idx:idx+50].split('\n')[0].strip()
                if len(candidate) > len(pref) + 2:
                    address = normalize_address(candidate)
                    break

    # ジャンル: li パターン → dl パターン
    genre_raw = ''
    for li in content.find_all('li'):
        text = li.get_text(strip=True)
        if text.startswith('ジャンル'):
            genre_raw = re.sub(r'^ジャンル[：:]\s*', '', text)
            break
    if not genre_raw:
        for dl in content.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for i, dt in enumerate(dts):
                if 'ジャンル' in dt.get_text():
                    if i < len(dds):
                        genre_raw = dds[i].get_text(strip=True)
                        break
            if genre_raw:
                break
    genre = detect_genre(genre_raw) if genre_raw else detect_genre(shop_name + title)

    # 放送日: URLから
    visited_date = extract_date_from_url(url)

    # tabelog URL (直接 or ValueCommerce経由)
    tabelog_url = ''
    for a in content.find_all('a', href=True):
        href = a['href']
        if not href.startswith('http'):
            href = 'https:' + href if href.startswith('//') else BASE_URL + href
        if 'tabelog.com' in href and ('tabelog.com/tokyo' in href or '/rst/' in href or '/A' in href):
            tabelog_url = href.split('?')[0]
            break
        if 'valuecommerce' in href and 'tabelog' in href:
            m = re.search(r'vc_url=([^&]+)', href)
            if m:
                decoded = urllib.parse.unquote(m.group(1))
                if 'tabelog.com' in decoded:
                    tabelog_url = decoded.split('?')[0]
                    break

    # tabelog から座標・住所補完
    lat, lng = None, None
    if tabelog_url and not address:
        print(f'    tabelog補完: {shop_name}')
        tb = get_tabelog_data(tabelog_url)
        time.sleep(1)
        if tb.get('address'):
            address = tb['address']
        if tb.get('lat'):
            lat, lng = tb['lat'], tb['lng']
        if tb.get('name') and len(tb['name']) > len(shop_name):
            shop_name = tb['name']

    if not address:
        print(f'    住所なし: {shop_name}')
        return None

    prefecture, city = split_prefecture_city(address)

    # メンバー検出（URLに名前のヒントがある場合もある）
    members = []
    url_lower = url.lower()
    name_hints = {
        'ohno': '大野智', 'nino': '二宮和也', 'sakurai': '櫻井翔',
        'aiba': '相葉雅紀', 'matsu': '松本潤',
    }
    for hint, member in name_hints.items():
        if hint in url_lower:
            members.append(member)
    # 本文中のメンバー名検出
    for m in MEMBERS_ALL:
        if m in full_text and m not in members:
            members.append(m)
    if not members:
        members = MEMBERS_ALL[:]

    # description: 最初の意味のある文から
    description = ''
    for para in content.find_all('p'):
        text = para.get_text(strip=True)
        if len(text) > 30 and shop_name not in text[:5]:
            description = re.sub(r'\s+', ' ', text)[:200]
            break

    return {
        'name': shop_name,
        'genre': genre,
        'prefecture': prefecture,
        'city': city,
        'address': address,
        'lat': lat,
        'lng': lng,
        'youtube_id': '',
        'source_video_title': PROGRAM,
        'source_video_url': url,
        'visited_date': visited_date,
        'members': members,
        'groups': [GROUP],
        'group': GROUP,
        'description': description,
        'nearest_station': '',
        'price_range': '',
        'ordered_items': [],
        'tabelog_url': tabelog_url,
        'hotpepper_url': '',
        'google_maps_url': '',
        'tags': ['嵐にしやがれ'],
        'affiliate_links': ([{'label': '食べログで見る', 'url': tabelog_url}] if tabelog_url else []),
    }


def collect_article_urls():
    """カテゴリーページを巡回して記事URLを収集"""
    urls = []
    page = 1
    while True:
        cat_url = CATEGORY_URL if page == 1 else f'{CATEGORY_URL}page/{page}/'
        print(f'カテゴリー {page}ページ目: {cat_url}')
        try:
            html = fetch_html(cat_url, delay=1.0)
        except Exception as e:
            print(f'  取得エラー: {e}')
            break

        soup = BeautifulSoup(html, 'html.parser')
        found = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if re.search(r'/entry/arashinishiyagare_\d{6}', href):
                full = href if href.startswith('http') else BASE_URL + href
                if full not in urls and full not in found:
                    found.append(full)

        if not found:
            break
        urls.extend(found)
        print(f'  {len(found)}件のURL取得')

        # 次ページ確認
        next_link = soup.find('a', string=re.compile(r'次|›|»|Next|\d+'))
        has_next = soup.find('a', href=re.compile(rf'page/{page+1}/'))
        if not has_next:
            break
        page += 1
        if page > 50:
            break

    return list(dict.fromkeys(urls))  # 重複除去・順序保持


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_arashi.json')
    parser.add_argument('--dry-run', action='store_true', help='URL一覧確認のみ')
    args = parser.parse_args()

    print('=== 嵐にしやがれ スクレイピング開始 ===')
    article_urls = collect_article_urls()
    print(f'\n合計 {len(article_urls)} 件のURL収集')

    if args.dry_run:
        for u in article_urls:
            print(f'  {u}')
        return

    all_shops = []
    seen_names = set()
    failed = []

    for url in article_urls:
        shop = scrape_article(url)
        if shop is None:
            failed.append(url)
            continue
        key = shop['name']
        if key in seen_names:
            print(f'    重複スキップ: {key}')
            continue
        seen_names.add(key)
        all_shops.append(shop)
        print(f'    ✓ {shop["name"]} ({shop["address"][:20]})')

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 完了 ===')
    print(f'取得成功: {len(all_shops)}件')
    print(f'失敗/住所なし: {len(failed)}件')
    if failed:
        for u in failed:
            print(f'  {u}')
    print(f'→ {args.output} に保存')
    print('\n次のステップ:')
    print(f'  python scripts/geocode_shops.py --input {args.output} --output scripts/geocoded_arashi.json')
    print(f'  python scripts/merge_shops.py --input scripts/geocoded_arashi.json')


if __name__ == '__main__':
    main()
