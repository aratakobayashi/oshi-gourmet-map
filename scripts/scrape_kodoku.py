"""
scrape_kodoku.py
孤独のグルメ 全シーズンのロケ地飲食店スクレイピング

ソース: goro-tablog.com（孤独のグルメ公式ロケ地まとめファンサイト）
TMDB API: ドラマのポスター画像をサムネイルとして取得

使い方:
  export TMDB_API_KEY="your_key_here"
  python scripts/scrape_kodoku.py --output scripts/scraped_kodoku.json

TMDBドラマID: 45753 (孤独のグルメ / Solitary Gourmet)
"""

import urllib.request
import urllib.parse
import json
import re
import os
import time
import argparse
from bs4 import BeautifulSoup

GROUP = 'kodoku_no_gurume'
TMDB_SHOW_ID = 45753
TMDB_BASE_IMG = 'https://image.tmdb.org/t/p/w500'

# goro-tablog.com のシーズン別URL
SEASON_URLS = [
    ('Season1', 'https://goro-tablog.com/season1/'),
    ('Season2', 'https://goro-tablog.com/season2/'),
    ('Season3', 'https://goro-tablog.com/season3/'),
    ('Season4', 'https://goro-tablog.com/season4/'),
    ('Season5', 'https://goro-tablog.com/season5/'),
    ('Season6', 'https://goro-tablog.com/season6/'),
    ('Season7', 'https://goro-tablog.com/season7/'),
    ('Season8', 'https://goro-tablog.com/season8/'),
    ('Season9', 'https://goro-tablog.com/season9/'),
    ('Season10', 'https://goro-tablog.com/season10/'),
]

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'ホルモン', 'BBQ'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス'], 'スイーツ'),
    (['居酒屋', '酒', 'バー', '炉端'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['カレー'], '食事'),
    (['中華', '餃子', '麻婆', '点心'], '食事'),
    (['イタリアン', 'パスタ', 'ピザ', 'フレンチ'], '食事'),
    (['定食', '和食', '割烹', '天ぷら', '鍋', 'とんかつ'], '和食'),
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    return resp.read().decode('utf-8')


def fetch_tmdb_poster(api_key):
    """TMDBから孤独のグルメのポスター画像URLを取得"""
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
    """TMDBからエピソードスチール画像URLを取得"""
    if not api_key:
        return None
    url = f'https://api.themoviedb.org/3/tv/{TMDB_SHOW_ID}/season/{season_num}/episode/{episode_num}?api_key={api_key}&language=ja'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        still = data.get('still_path')
        return f'{TMDB_BASE_IMG}{still}' if still else None
    except Exception:
        return None


def scrape_season(season_label, url):
    """各シーズンページから店舗情報を取得"""
    print(f'取得中: {season_label} ({url})')
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f'  エラー: {e}')
        return []

    soup = BeautifulSoup(html, 'html.parser')
    shops = []

    # シーズン番号を抽出
    season_num = re.search(r'Season(\d+)', season_label)
    season_num = int(season_num.group(1)) if season_num else 0

    # 各話エントリを探す（h2/h3タグまたはli要素）
    entries = soup.find_all(['h2', 'h3'])
    ep_num = 0

    for entry in entries:
        text = entry.get_text(strip=True)

        # 「第X話」パターンを検出
        ep_match = re.search(r'第\s*(\d+)\s*話', text)
        if not ep_match:
            continue
        ep_num = int(ep_match.group(1))

        # 店名（h2/h3テキストから「第X話」を除いた部分）
        shop_name = re.sub(r'第\s*\d+\s*話\s*[「『【]?', '', text).strip()
        shop_name = re.sub(r'[」』】].*$', '', shop_name).strip()
        if not shop_name or len(shop_name) < 2:
            continue

        # 次の兄弟要素から住所・詳細を収集
        address = ''
        description = ''
        sib = entry.find_next_sibling()
        for _ in range(10):
            if not sib:
                break
            if sib.name in ['h2', 'h3']:
                break
            sib_text = sib.get_text(separator=' ', strip=True)
            if re.match(r'^(東京都|大阪府|京都府|北海道|.{2,3}県|.{2,3}市)', sib_text):
                address = sib_text.split('　')[0].split(' ')[0].strip()
            if not description and len(sib_text) > 20:
                description = sib_text[:120]
            sib = sib.find_next_sibling()

        genre = detect_genre(shop_name + description)
        source_video_title = f'孤独のグルメ {season_label} 第{ep_num}話'

        shops.append({
            'name': shop_name,
            'season': season_label,
            'episode': ep_num,
            'season_num': season_num,
            'episode_num': ep_num,
            'genre': genre,
            'group': GROUP,
            'groups': [GROUP],
            'members': ['井之頭五郎'],
            'address': address,
            'nearest_station': '',
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'thumbnail_url': '',
            'tmdb_id': TMDB_SHOW_ID,
            'tmdb_type': 'tv',
            'source_type': 'drama',
            'source_video_title': source_video_title,
            'source_video_url': '',
            'tabelog_url': f'https://tabelog.com/rstLst/?vs=1&sa=&sk={urllib.parse.quote(shop_name)}',
            'hotpepper_url': '',
            'description': description,
            'tags': ['孤独のグルメ', season_label, f'第{ep_num}話'],
            'affiliate_links': [],
        })

    print(f'  → {len(shops)}件取得')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kodoku.json')
    args = parser.parse_args()

    api_key = os.environ.get('TMDB_API_KEY', '')
    if not api_key:
        print('警告: TMDB_API_KEY が未設定です。thumbnail_url は空になります。')
    else:
        print(f'TMDB APIキー確認: OK')

    # TMDBポスター取得（全店舗共通のフォールバック）
    poster_url = fetch_tmdb_poster(api_key)
    print(f'TMDB ポスター: {poster_url or "取得失敗"}')

    all_shops = []
    for season_label, url in SEASON_URLS:
        shops = scrape_season(season_label, url)
        # エピソードスチール画像をTMDBから取得
        for s in shops:
            if api_key and s['season_num'] and s['episode_num']:
                still = fetch_tmdb_episode_still(api_key, s['season_num'], s['episode_num'])
                s['thumbnail_url'] = still or poster_url or ''
                time.sleep(0.3)
            else:
                s['thumbnail_url'] = poster_url or ''
        all_shops.extend(shops)
        time.sleep(1)

    # season_num / episode_num は内部用なので出力から除外
    for s in all_shops:
        s.pop('season_num', None)
        s.pop('episode_num', None)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 完了 ===')
    print(f'総件数: {len(all_shops)}件')
    print(f'住所あり: {sum(1 for s in all_shops if s["address"])}件')
    print(f'thumbnail_urlあり: {sum(1 for s in all_shops if s["thumbnail_url"])}件')
    print(f'→ {args.output}')


if __name__ == '__main__':
    main()
