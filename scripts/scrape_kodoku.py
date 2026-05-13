"""
scrape_kodoku.py
孤独のグルメ 全シーズンのロケ地飲食店スクレイピング

ソース: hirofun.com/food/18753/（全シーズン一覧テーブル）
TMDB API: エピソードスチール画像をサムネイルとして取得

使い方:
  export TMDB_API_KEY="your_key_here"
  python scripts/scrape_kodoku.py --output scripts/scraped_kodoku.json

TMDBドラマID: 45753 (孤独のグルメ / Solitary Gourmet)
"""

import urllib.request
import json
import re
import os
import time
import argparse
from bs4 import BeautifulSoup

GROUP = 'kodoku_no_gurume'
SOURCE_URL = 'https://hirofun.com/food/18753/'
TMDB_SHOW_ID = 55582
TMDB_BASE_IMG = 'https://image.tmdb.org/t/p/w500'

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'ホルモン', '一人焼肉'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス'], 'スイーツ'),
    (['居酒屋', '酒場', 'バー', '炉端', '飲み屋'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['カレー'], '食事'),
    (['中華', '餃子', '麻婆', '担々麺', '四川', '点心'], '食事'),
    (['イタリアン', 'パスタ', 'ピザ', 'フレンチ', 'ナポリタン'], '食事'),
    (['定食', '和食', '割烹', '天ぷら', '鍋', 'とんかつ', '煮魚',
      'やきとり', '焼き鳥', '親子丼', 'しょうが焼', 'おでん'], '和食'),
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def fetch_html(url):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0 (compatible; oshi-gourmet-map/1.0)'}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    return resp.read().decode('utf-8')


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


def fetch_tmdb_episode_still(api_key, season_num, episode_num):
    if not api_key:
        return None
    url = (f'https://api.themoviedb.org/3/tv/{TMDB_SHOW_ID}'
           f'/season/{season_num}/episode/{episode_num}?api_key={api_key}&language=ja')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        still = data.get('still_path')
        return f'{TMDB_BASE_IMG}{still}' if still else None
    except Exception:
        return None


def scrape_all():
    print(f'取得中: {SOURCE_URL}')
    html = fetch_html(SOURCE_URL)
    soup = BeautifulSoup(html, 'html.parser')

    # 最初のtableが全シーズン一覧
    table = soup.find('table')
    if not table:
        print('テーブルが見つかりません')
        return []

    rows = table.find_all('tr')
    print(f'  テーブル行数: {len(rows)}')

    shops = []
    current_season_num = 0
    current_season_label = ''

    for row in rows:
        tds = row.find_all('td')

        # シーズンヘッダー行（列数=1, テキストが「シーズンX」）
        if len(tds) == 1:
            text = tds[0].get_text(strip=True)
            m = re.search(r'シーズン\s*(\d+)', text)
            if m:
                current_season_num = int(m.group(1))
                current_season_label = f'Season{current_season_num}'
                print(f'  {current_season_label}...')
            continue

        # エピソード行（列数=7）
        if len(tds) < 6 or not current_season_num:
            continue

        ep_text = tds[0].get_text(strip=True)
        ep_match = re.search(r'(\d+)', ep_text)
        if not ep_match:
            continue
        episode_num = int(ep_match.group(1))

        prefecture = tds[1].get_text(strip=True)
        city        = tds[2].get_text(strip=True)
        description = tds[3].get_text(strip=True)
        station     = tds[4].get_text(strip=True)

        name_cell  = tds[5]
        name_link  = name_cell.find('a')
        shop_name  = name_link.get_text(strip=True) if name_link else name_cell.get_text(strip=True)
        tabelog_url = name_link['href'] if name_link and name_link.get('href') else ''

        # 閉店はスキップ
        if '閉店' in shop_name:
            continue

        if not shop_name or len(shop_name) < 2:
            continue

        address = f'{prefecture}{city}' if prefecture else ''
        genre = detect_genre(description + shop_name)
        source_video_title = f'孤独のグルメ {current_season_label} 第{episode_num}話'

        shops.append({
            '_season_num':  current_season_num,
            '_episode_num': episode_num,
            'name':         shop_name,
            'genre':        genre,
            'group':        GROUP,
            'groups':       [GROUP],
            'members':      ['井之頭五郎'],
            'prefecture':   prefecture,
            'city':         city,
            'address':      address,
            'nearest_station': station,
            'lat':          None,
            'lng':          None,
            'youtube_id':   '',
            'thumbnail_url': '',
            'tmdb_id':      TMDB_SHOW_ID,
            'tmdb_type':    'tv',
            'source_type':  'drama',
            'source_video_title': source_video_title,
            'source_video_url':   '',
            'tabelog_url':  tabelog_url,
            'hotpepper_url': '',
            'description':  description,
            'tags':         ['孤独のグルメ', current_season_label, f'第{episode_num}話'],
            'affiliate_links': [],
        })

    print(f'  → 合計 {len(shops)}件（閉店除く）')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kodoku.json')
    args = parser.parse_args()

    api_key = os.environ.get('TMDB_API_KEY', '')
    if not api_key:
        print('警告: TMDB_API_KEY が未設定です。thumbnail_url は空になります。')
    else:
        print('TMDB APIキー確認: OK')

    poster_url = fetch_tmdb_poster(api_key)
    print(f'TMDB ポスター: {poster_url or "取得失敗"}')

    shops = scrape_all()

    # TMDBエピソードスチール取得
    print('\nTMDB エピソードスチール取得中...')
    for s in shops:
        sn = s.pop('_season_num')
        en = s.pop('_episode_num')
        if api_key:
            still = fetch_tmdb_episode_still(api_key, sn, en)
            s['thumbnail_url'] = still or poster_url or ''
            time.sleep(0.25)
        else:
            s['thumbnail_url'] = poster_url or ''

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 完了 ===')
    print(f'総件数: {len(shops)}件')
    print(f'住所あり: {sum(1 for s in shops if s["address"])}件')
    print(f'thumbnail_urlあり: {sum(1 for s in shops if s["thumbnail_url"])}件')
    print(f'→ {args.output}')


if __name__ == '__main__':
    main()
