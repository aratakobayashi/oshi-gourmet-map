"""
scrape_mom_eat.py
mom-eat.com (スノオタLIFE) から Snow Man グルメロケ地をスクレイピング

- snowman-youtube-location-* などの記事からグルメ店を抽出
- ordered_items / seating_note も合わせて取得（新フィールド対応）
- 既存shops.jsonとの突合で新規／パッチ候補を分類

使い方:
  # 全記事スクレイピング
  python scripts/scrape_mom_eat.py --output scripts/scraped_mom_eat.json

  # 件数制限（動作確認）
  python scripts/scrape_mom_eat.py --limit 10 --output scripts/scraped_mom_eat.json
"""

import urllib.request
import json
import re
import time
import argparse
from bs4 import BeautifulSoup

GROUP = 'snowman'
SITEMAP_URL = 'https://mom-eat.com/wp-sitemap-posts-post-1.xml'

# 食事系でないと判断してスキップするURLキーワード
SKIP_FRAGMENTS = [
    'pilates', 'climbing', 'nazotoki', 'camera', 'dance', 'sauna',
    'cryosauna', 'zarigani', 'turigu', 'flystatio', 'suizokukan',
    'puro', 'tondemi', 'campgoods', 'bravepoi', 'helicopter',
    'shibuyatakkyu', 'treecross', 'shinagawasuizoku', 'ginzasauna',
    'drivegoods', 'customboot', 'toyosu', 'footgolf', 'dasshutsukichi',
    'escape', 'shibuyasky', 'ikushika', 'locationtour', 'tourlog',
    'matome', 'hanedaichiba',  # 複数店まとめ・市場系は除外
    'mv-', 'drama-', 'movie-', 'obakeyashiki', 'animalcafe',
    'ichigogari',  # いちご狩り（農業体験）
    'edogawakai',  # 江戸川花火大会
    'goldenonespoon',  # ゴールデンスプーン（非食事）
    'namidanoumiwo',  # MV関連
]

# 店名・タイトルに含まれる場合に非食事と判定するキーワード
NON_FOOD_KEYWORDS = [
    'ゴルフ', 'カントリークラブ', '脱出ゲーム', 'クライミング', 'ピラティス',
    'ボルダリング', 'サウナ', '釣り', 'アミューズメント', '水族館',
    'ジム', 'スポーツ', '映画', 'ライブ', '神社', '別院', '寺', '仏閣',
    '道の駅', 'ゲームセンター', '遊園地', 'ハイランド', '旅館', '神宮',
    'アドアーズ', 'スカイツリー', '空港', '稲荷', '公園', 'アトラクション',
    'クイズ', '劇場', '番組', 'スタジオ', 'ロケ地一覧', '一覧',
    '美術館', '博物館', 'ホテル', '温泉', '銭湯', '宿泊',
]

SNOWMAN_MEMBERS = [
    '岩本照', 'ラウール', '深澤辰哉', '宮舘涼太', '阿部亮平',
    '渡辺翔太', '向井康二', '目黒蓮', '佐久間大介', '山田涼介',
]

GENRE_MAP = [
    (['ラーメン', '油そば', 'つけ麺', 'らーめん', 'ちゃんぽん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'ホルモン', 'しゃぶ', 'すき焼き', 'BBQ'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'すし', 'シースー'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'パン', 'ベーカリー', 'ブランチ'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'パフェ', 'クレープ'], 'スイーツ'),
    (['居酒屋', '酒場', 'バー', '炉端', '焼き鳥', '鳥貴族', 'ガスト', 'ファミレス'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['フレンチ', 'イタリアン', 'パスタ', '洋食', 'ガレット', 'ピザ', 'ピッツァ'], '食事'),
    (['和食', '天ぷら', '薬膳', 'ちゃんこ', 'とんかつ', '定食', '蕎麦', 'そば', '割烹'], '和食'),
    (['うなぎ', 'ウナギ', '鰻'], '和食'),
    (['カレー'], '食事'),
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def fetch_html(url, delay=1.5):
    time.sleep(delay)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'oshi-gourmet-map-bot/1.0 (+https://gourmet.oshikatsu-guide.com)'
    })
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8')


def get_article_urls():
    """サイトマップからグルメ系記事URLを収集"""
    xml = fetch_html(SITEMAP_URL, delay=1.0)
    all_urls = re.findall(r'<loc>(https://mom-eat\.com/[^<]+)</loc>', xml)

    food_urls = []
    for url in all_urls:
        path = url.replace('https://mom-eat.com/', '').rstrip('/')
        if any(skip in path for skip in SKIP_FRAGMENTS):
            continue
        # Snow Man関連URLをすべて対象にする（コンテンツレベルの食事判定に委ねる）
        if any(prefix in path for prefix in [
            'snowman', 'soresuno', 'sunotube', 'snotube', 'suno-', 'snoman'
        ]):
            food_urls.append(url)

    return food_urls


def extract_youtube_id(soup):
    """YouTube IDを複数ソースから抽出"""
    # 1. iframeのsrc
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '') or iframe.get('data-src', '')
        m = re.search(r'youtube(?:-nocookie)?\.com/embed/([a-zA-Z0-9_-]{11})', src)
        if m:
            return m.group(1)

    # 2. YouTubeリンク（watch?v=）
    for a in soup.find_all('a', href=True):
        m = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})', a['href'])
        if m:
            return m.group(1)

    # 3. サムネ画像URL
    for img in soup.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '')
        m = re.search(r'img\.youtube\.com/vi/([a-zA-Z0-9_-]{11})/', src)
        if m:
            return m.group(1)

    # 4. ページ全体テキスト内のYouTube URL
    m = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})', soup.get_text())
    if m:
        return m.group(1)

    return ''


def extract_address_and_station(soup):
    """テーブルから住所・最寄り駅を抽出"""
    address = ''
    nearest_station = ''

    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)

            if not address and any(kw in label for kw in ['住所', 'アドレス']):
                address = value
            if not nearest_station and any(kw in label for kw in ['アクセス', '最寄', '駅']):
                nearest_station = value

    return address, nearest_station


def extract_members(soup):
    """記事内でのSnow Manメンバー言及を抽出"""
    text = soup.get_text()
    return [m for m in SNOWMAN_MEMBERS if m in text]


def extract_ordered_items(soup):
    """「食べたメニュー」系 h2/h3 の直後 ul/li からメニューを抽出"""
    items = []
    keywords = ['食べたメニュー', '注文した', '食べたもの', 'メニューは', '食べたご飯', 'メニュー']

    for tag in soup.find_all(['h2', 'h3']):
        if not any(kw in tag.get_text() for kw in keywords):
            continue
        sibling = tag.find_next_sibling()
        while sibling:
            if sibling.name == 'ul':
                for li in sibling.find_all('li'):
                    text = li.get_text(strip=True)
                    if text:
                        items.append(text)
                break
            elif sibling.name in ['h1', 'h2', 'h3']:
                break
            sibling = sibling.find_next_sibling()
        if items:
            break

    return items


def extract_seating_note(soup):
    """「座った席」系 h2/h3 の直後テキストを抽出"""
    keywords = ['座った席', '席は', '座席', 'どこに座', 'お席']

    for tag in soup.find_all(['h2', 'h3']):
        if not any(kw in tag.get_text() for kw in keywords):
            continue
        parts = []
        sibling = tag.find_next_sibling()
        while sibling:
            if sibling.name in ['h1', 'h2', 'h3']:
                break
            if sibling.name == 'p':
                text = sibling.get_text(strip=True)
                if text:
                    parts.append(text)
            sibling = sibling.find_next_sibling()
        if parts:
            return ' '.join(parts)

    return ''


def extract_shop_name(soup):
    """記事本文の最初のh2から店名を推定。"ロケ地は〇〇" や「店名」パターンを処理"""
    SECTION_NOISE = ['メニュー', '座った席', 'まとめ', 'PR', '広告', 'アクセス', '関連',
                     '？', 'どこ', 'いつ', 'なぜ', '何時', 'なに']
    NOISE_PREFIX_WORDS = ['ロケ地', 'どこ', 'その', 'この', 'あの', '場所']
    GENERIC_NAMES = [
        '場所', 'ロケ地', 'アクセス', '放送日', '行き方', '最寄り', '情報',
        'チャンネル', 'それスノ', '聖地巡礼', '全員', 'バスツアー', 'キャンプ場',
        '記録', '①', '②', '③',
    ]

    content = soup.find('div', class_='entry-content') or soup.find('article')
    if not content:
        return ''

    STRIP_LEAD = [
        'すのちゅーぶで訪れた', 'すの日常で訪れた', 'SnowManが訪れた',
        'Snow Manが訪れた', 'メンバーが訪れた', 'すのちゅーぶの',
    ]

    for h2 in content.find_all('h2'):
        raw = h2.get_text(strip=True)
        if any(kw in raw for kw in SECTION_NOISE):
            continue
        if not (3 < len(raw) < 80):
            continue

        text = raw
        for lead in STRIP_LEAD:
            if text.startswith(lead):
                text = text[len(lead):].strip()
                break

        # 「店名」パターン
        m = re.search(r'「(.{2,30}?)」', text)
        if m:
            return m.group(1)

        # "ロケ地は〇〇" パターン
        m = re.match(r'^ロケ地は(.+)', text)
        if m:
            return m.group(1).strip()

        # "ロケ地①店名（料理名）" パターン → 店名のみ抽出
        m = re.match(r'^(?:.*?ロケ地\s*[\①②③④⑤⑥⑦⑧⑨⑩\d]+\s*)(.+)', text)
        if m:
            shop_part = re.sub(r'[（(][^）)]{2,20}[）)]', '', m.group(1)).strip()
            shop_part = re.sub(r'^[\①②③④⑤⑥⑦⑧⑨⑩\d]+\s*', '', shop_part).strip()
            if shop_part and len(shop_part) >= 2:
                text = shop_part

        # 括弧内の料理名を除去（汎用）
        text_clean = re.sub(r'[（(][^）)]{2,20}[）)]', '', text).strip()
        if text_clean and len(text_clean) >= 2:
            text = text_clean

        # 汎用フレーズはスキップ
        if any(g in text for g in GENERIC_NAMES):
            continue

        # "△△は□□" → 最後のは以降を、直前の単語と組み合わせ
        if 'は' in text:
            ha_parts = text.rsplit('は', 1)
            after_ha = ha_parts[1].strip()
            before_ha = ha_parts[0]
            last_word = re.search(r'(\S{2,15})$', before_ha)
            if last_word:
                lw = last_word.group(1)
                if not any(kw in lw for kw in NOISE_PREFIX_WORDS):
                    return lw + ' ' + after_ha
                return after_ha

        # 直接店名の場合
        if not any(kw in text for kw in ['SnowMan', 'Snow Man', 'すの', '訪れ', 'ちゅーぶ', '日常']):
            return text

    return ''


def extract_visited_date(soup):
    """og:article:published_time から訪問日を推定"""
    pub = soup.find('meta', property='article:published_time')
    if pub:
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', pub.get('content', ''))
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return ''


def scrape_article(url):
    """1記事をスクレイピング。食事関連でなければ None を返す。"""
    html = fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    ordered_items = extract_ordered_items(soup)
    seating_note = extract_seating_note(soup)
    address, nearest_station = extract_address_and_station(soup)

    name = extract_shop_name(soup)
    if not name:
        return None

    # 非食事系の店名はスキップ
    if any(kw in name for kw in NON_FOOD_KEYWORDS):
        return None

    # 食事関連の証拠が何もなければスキップ
    if not ordered_items and not seating_note and not address:
        return None

    youtube_id = extract_youtube_id(soup)

    members = extract_members(soup)
    visited_date = extract_visited_date(soup)

    og_title = soup.find('meta', property='og:title')
    source_title = og_title.get('content', '') if og_title else ''

    genre = detect_genre(name + ' ' + ' '.join(ordered_items))

    slug = url.rstrip('/').split('/')[-1]
    shop_id = f'snowman-momeeat-{slug[:36]}'
    # youtube_idなし → 既存店補完専用（新規登録は不可）
    can_add_new = bool(youtube_id)

    return {
        'id': shop_id,
        'name': name,
        'genre': genre,
        'group': GROUP,
        'groups': [GROUP],
        'address': address,
        'nearest_station': nearest_station,
        'prefecture': '東京都' if '東京' in address else '',
        'city': '',
        'youtube_id': youtube_id,
        'source_video_title': source_title,
        'source_video_url': f'https://www.youtube.com/watch?v={youtube_id}',
        'visited_date': visited_date,
        'members': members,
        'ordered_items': ordered_items,
        'seating_note': seating_note,
        'description': '',
        'tags': [],
        'affiliate_links': [],
        '_source_url': url,
        '_can_add_new': can_add_new,  # False=既存店補完専用
    }


def main():
    parser = argparse.ArgumentParser(description='mom-eat.com Snow Manグルメスクレイパー')
    parser.add_argument('--output', default='scripts/scraped_mom_eat.json')
    parser.add_argument('--limit', type=int, default=0, help='記事数上限（0=全件）')
    args = parser.parse_args()

    print('サイトマップ取得中...')
    urls = get_article_urls()
    print(f'{len(urls)} 件のグルメ系記事URLを検出')

    if args.limit:
        urls = urls[:args.limit]
        print(f'（--limit {args.limit} で先頭{args.limit}件のみ処理）')

    results = []
    skipped = 0

    for i, url in enumerate(urls, 1):
        print(f'[{i}/{len(urls)}] {url}')
        try:
            shop = scrape_article(url)
            if shop:
                results.append(shop)
                print(f'  → ✓ {shop["name"]}  メニュー{len(shop["ordered_items"])}件  席:{bool(shop["seating_note"])}')
            else:
                skipped += 1
                print(f'  → スキップ（食事関連なし or youtube_idなし）')
        except Exception as e:
            print(f'  → エラー: {e}')
            skipped += 1

    print(f'\n完了: {len(results)} 件取得 / {skipped} 件スキップ')

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'{args.output} に保存しました')

    # 既存shops.jsonとの突合サマリ
    try:
        with open('data/shops.json', encoding='utf-8') as f:
            existing = json.load(f)
        existing_yt = {s['youtube_id'] for s in existing if s.get('youtube_id')}
        existing_names = {s['name'] for s in existing}

        enrich = [s for s in results if s['youtube_id'] in existing_yt or s['name'] in existing_names]
        new_ok = [s for s in results if s.get('_can_add_new') and s['youtube_id'] not in existing_yt and s['name'] not in existing_names]
        enrich_only = [s for s in results if not s.get('_can_add_new') and s['name'] not in existing_names]

        print(f'\n突合結果:')
        print(f'  新規登録候補 (youtube_idあり): {len(new_ok)} 件 → merge_shops.py で追加可能')
        print(f'  既存店の補完候補: {len(enrich)} 件 → ordered_items/seating_note を追記可能')
        print(f'  youtube_idなし・未登録: {len(enrich_only)} 件 → 補完専用（新規登録は不可）')
    except Exception:
        pass


if __name__ == '__main__':
    main()
