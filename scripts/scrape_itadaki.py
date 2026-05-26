"""
scrape_itadaki.py
いただきハイジャンプ（Hey! Say! JUMP）グルメロケ地スクレイピング

ソース1: https://e-nini08.hatenadiary.jp/entry/2018/07/10/114437 (28店舗・住所あり)
ソース2: https://medax.hatenablog.com/entry/hijump (川越特集17店舗・食べログURL付き)
TMDB ポスター: いただきハイジャンプ (ID:197002) のポスターをthumbnail_urlに使用

使い方:
  export TMDB_API_KEY="your_key"
  python scripts/scrape_itadaki.py --output scripts/scraped_heysayjump.json
"""

import urllib.request
import json
import re
import os
import time
import argparse
from html.parser import HTMLParser

GROUP = 'heysayjump'
TMDB_SHOW_ID = 197002
TMDB_BASE_IMG = 'https://image.tmdb.org/t/p/w500'
SOURCE1 = 'https://e-nini08.hatenadiary.jp/entry/2018/07/10/114437'
SOURCE2 = 'https://medax.hatenablog.com/entry/hijump'

GENRE_MAP = [
    (['ラーメン', '麺', '汁いち', '爆裂石焼'], 'ラーメン'),
    (['焼肉', 'ステーキ', 'HERO'], '焼肉'),
    (['寿司', '鮨', '竜宮城'], '寿司'),
    (['カフェ', 'コーヒー', 'パン'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'たい焼き', '鯛焼き', '製菓', '菓子', '和菓子', '甘味'], 'スイーツ'),
    (['居酒屋', 'バー', 'ダーツ', 'Bee'], '居酒屋'),
    (['天ぷら', 'てんぷら', 'うなぎ', 'うな達', '和食', '割烹', '食堂', '茶寮', '定食'], '和食'),
    (['中華', '餃子', '蘭州', '楼蘭'], '食事'),
    (['漬物', '醤油', '味噌'], 'その他'),
]

SKIP_KEYWORDS = ['閉店', '光永ファーム', '新町の井戸', '向山', '共栄トンネル', '渓流の宿', '福水']

def detect_genre(name, desc=''):
    text = name + desc
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def parse_members(raw):
    raw = re.sub(r'（[^）]*）', '', raw)
    parts = re.split(r'[、,・/]', raw)
    return [m.strip() for m in parts if m.strip() and len(m.strip()) >= 2]


def fetch_html(url):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0 (compatible; oshi-gourmet-map/1.0)'}
    )
    return urllib.request.urlopen(req, timeout=15).read().decode('utf-8')


def fetch_tmdb_poster(api_key):
    if not api_key:
        return None
    url = f'https://api.themoviedb.org/3/tv/{TMDB_SHOW_ID}?api_key={api_key}&language=ja'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        poster = data.get('poster_path')
        return f'{TMDB_BASE_IMG}{poster}' if poster else None
    except Exception as e:
        print(f'TMDB取得エラー: {e}')
        return None


def _normalize_address(addr):
    """住所：プレフィックスを除去し、都道府県なしの場合は東京都を補完"""
    addr = re.sub(r'^住所[：:]\s*', '', addr).strip()
    pref = re.match(r'^(東京都|神奈川県|埼玉県|千葉県|茨城県|静岡県|福岡県|大阪府|京都府|北海道|.{2,3}県)', addr)
    if not pref:
        addr = '東京都' + addr
    return addr


def scrape_source1(thumbnail_url):
    """hatenadiary: ◎店名 / 住所：... 形式"""
    print(f'取得中: {SOURCE1}')
    html = fetch_html(SOURCE1)

    # entry-content を正規表現で抽出（bs4不要）
    m = re.search(r'<div class="entry-content">(.*?)</div>\s*(?:<div class="hatena-|<footer)', html, re.DOTALL)
    if not m:
        print('  本文が見つかりません')
        return []

    content = m.group(1)
    text = re.sub(r'<[^>]+>', '', content)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    shops = []
    current_episode = ''
    current_members = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # エピソード行（日付パターン）
        if re.search(r'20\d\d\.\d\d\.\d\d', line):
            current_episode = line
            current_members = parse_members(line)
            i += 1
            continue

        # ◎で始まる行が店名
        if line.startswith('◎'):
            name = line[1:].strip()
            if any(kw in name for kw in SKIP_KEYWORDS) or len(name) < 2:
                i += 1
                continue

            # 後続行から「住所：」を探す（最大3行先まで）
            address = ''
            for j in range(i + 1, min(i + 4, len(lines))):
                if re.match(r'^住所[：:]', lines[j]) or re.match(
                    r'^(東京都|神奈川県|埼玉県|千葉県|茨城県|静岡県|福岡県|大阪府|京都府|北海道)',
                    lines[j]
                ):
                    address = _normalize_address(lines[j])
                    break

            if not address:
                i += 1
                continue

            pref_m = re.match(r'^(東京都|神奈川県|埼玉県|千葉県|茨城県|静岡県|福岡県|大阪府|京都府|北海道)', address)
            prefecture = pref_m.group(1) if pref_m else '東京都'

            shops.append({
                'name': name,
                'address': address,
                'prefecture': prefecture,
                'members': current_members,
                'episode_info': current_episode,
                'genre': detect_genre(name),
                'thumbnail_url': thumbnail_url or '',
            })

        i += 1

    print(f'  → {len(shops)}件')
    return shops


def _scrape_source1_table(soup, thumbnail_url):
    """テーブル形式のフォールバック"""
    shops = []
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            name = cells[0].get_text(strip=True)
            address = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            member_text = cells[2].get_text(strip=True) if len(cells) > 2 else ''
            ep = cells[3].get_text(strip=True) if len(cells) > 3 else ''

            if any(kw in name for kw in SKIP_KEYWORDS):
                continue
            if not name or len(name) < 2:
                continue

            pref_match = re.match(r'(東京都|神奈川県|埼玉県|千葉県|茨城県|静岡県|福岡県)', address)
            shops.append({
                'name': name,
                'address': address,
                'prefecture': pref_match.group(1) if pref_match else '',
                'members': parse_members(member_text),
                'episode_info': ep,
                'genre': detect_genre(name),
                'thumbnail_url': thumbnail_url or '',
            })
    return shops


def scrape_source2(thumbnail_url):
    """medax hatenablog: 川越特集17店舗・tabelog URLあり"""
    from bs4 import BeautifulSoup
    print(f'取得中: {SOURCE2}')
    html = fetch_html(SOURCE2)
    soup = BeautifulSoup(html, 'html.parser')

    shops = []
    body = soup.find('div', class_='entry-content') or soup.find('article')
    if not body:
        print('  本文が見つかりません')
        return shops

    current_ep = ''
    current_members = []

    for elem in body.find_all(['p', 'h2', 'h3', 'li']):
        text = elem.get_text(strip=True)
        if not text:
            continue

        # エピソード行
        if re.search(r'20\d\d\.\d\d\.\d\d', text):
            current_ep = text
            current_members = parse_members(text)
            continue

        # メンバー行（例: 伊野尾慧・髙木雄也）
        member_only = re.match(r'^([ぁ-ん一-鿿]{2,5}[・、]{1}[ぁ-ん一-鿿]{2,5})', text)
        if member_only:
            current_members = parse_members(text)
            continue

        # 食べログリンクと店名
        link = elem.find('a', href=re.compile(r'tabelog\.com'))
        if link:
            name = link.get_text(strip=True)
            tabelog_url = link.get('href', '')
            if any(kw in name for kw in SKIP_KEYWORDS):
                continue
            if len(name) < 2:
                continue

            shops.append({
                'name': name,
                'address': '埼玉県川越市',
                'prefecture': '埼玉県',
                'members': list(current_members),
                'episode_info': current_ep,
                'genre': detect_genre(name),
                'thumbnail_url': thumbnail_url or '',
                'tabelog_url': tabelog_url,
            })

    print(f'  → {len(shops)}件')
    return shops


def build_shop_entry(raw, thumbnail_url):
    name = raw['name']
    address = raw.get('address', '')
    prefecture = raw.get('prefecture', '')
    if not prefecture and address:
        m = re.match(r'(東京都|神奈川県|埼玉県|千葉県|茨城県|静岡県|福岡県|大阪府|京都府)', address)
        if m:
            prefecture = m.group(1)

    members = raw.get('members', [])
    ep_info = raw.get('episode_info', '')
    genre = raw.get('genre', '食事')
    tabelog_url = raw.get('tabelog_url', '')

    # IDは店名から生成
    slug = re.sub(r'[^\w]', '', name)
    slug = re.sub(r'[a-zA-Z]', lambda m: m.group().lower(), slug)
    shop_id = f'heysayjump-{slug[:20]}'

    # 訪問日（episode_infoから最初の日付）
    date_match = re.search(r'(20\d\d)\.(\d\d)\.(\d\d)', ep_info)
    visited_date = f'{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}' if date_match else ''

    affiliate = []
    if tabelog_url:
        affiliate.append({'label': '食べログで見る', 'url': tabelog_url})

    return {
        'id': shop_id,
        'name': name,
        'genre': genre,
        'prefecture': prefecture,
        'city': '',
        'address': address,
        'lat': None,
        'lng': None,
        'youtube_id': '',
        'thumbnail_url': thumbnail_url or '',
        'source_type': 'tv',
        'tmdb_id': TMDB_SHOW_ID,
        'tmdb_type': 'tv',
        'source_video_title': ep_info,
        'source_video_url': '',
        'visited_date': visited_date,
        'members': members,
        'groups': [GROUP],
        'group': GROUP,
        'description': ep_info,
        'nearest_station': '',
        'price_range': '',
        'tabelog_url': tabelog_url,
        'hotpepper_url': '',
        'google_maps_url': '',
        'tags': ['いただきハイジャンプ', 'HeySayJUMP'],
        'affiliate_links': affiliate,
    }


def dedup(shops):
    seen = set()
    result = []
    for s in shops:
        key = s['name'] + s.get('address', '')[:10]
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_heysayjump.json')
    parser.add_argument('--skip-source2', action='store_true', help='川越特集をスキップ')
    args = parser.parse_args()

    api_key = os.environ.get('TMDB_API_KEY', '')
    if not api_key:
        print('警告: TMDB_API_KEY が未設定。thumbnail_url は固定値を使用します。')
        thumbnail_url = f'{TMDB_BASE_IMG}/fHu3eQ9wF9NiVUXYBMV5e9VbOob.jpg'
    else:
        print('TMDB APIキー確認: OK')
        thumbnail_url = fetch_tmdb_poster(api_key)
        if not thumbnail_url:
            thumbnail_url = f'{TMDB_BASE_IMG}/fHu3eQ9wF9NiVUXYBMV5e9VbOob.jpg'
        print(f'TMDB ポスター: {thumbnail_url}')

    try:
        raw1 = scrape_source1(thumbnail_url)
    except Exception as e:
        print(f'SOURCE1 取得エラー: {e}')
        raw1 = []

    raw2 = []
    if not args.skip_source2:
        try:
            time.sleep(1)
            raw2 = scrape_source2(thumbnail_url)
        except Exception as e:
            print(f'SOURCE2 取得エラー: {e}')

    all_raw = raw1 + raw2
    shops = [build_shop_entry(r, thumbnail_url) for r in all_raw]
    shops = dedup(shops)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 完了 ===')
    print(f'総件数: {len(shops)}件')
    print(f'住所あり: {sum(1 for s in shops if s["address"])}件')
    print(f'thumbnail_urlあり: {sum(1 for s in shops if s["thumbnail_url"])}件')
    print(f'→ {args.output}')
    if shops:
        print('\n最初の5件:')
        for s in shops[:5]:
            print(f'  [{s["genre"]}] {s["name"]} / {s["address"]}')


if __name__ == '__main__':
    main()
