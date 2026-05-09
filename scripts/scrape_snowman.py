"""
scrape_snowman.py
Snow Man グルメロケ地スクレイピング

対応ソース:
  - snowman-information.com : div+p構造、youtube_id・食べログURL・住所・動画タイトル・日付
  - 8888-info.hatenablog.com: table構造、食べログURL・ホットペッパーURL（補完用）

使い方:
  python scripts/scrape_snowman.py --output scripts/scraped_snowman.json

ソースURL:
  PRIMARY : https://snowman-information.com/youtube-roke/
  SECONDARY: https://8888-info.hatenablog.com/entry/%E3%81%94%E9%A3%AF
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
from bs4 import BeautifulSoup

GROUP = 'snowman'
PRIMARY_URL = 'https://snowman-information.com/youtube-roke/'
SECONDARY_URL = 'https://8888-info.hatenablog.com/entry/%E3%81%94%E9%A3%AF'

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん', 'そうめん', 'らーめん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'BBQ', 'バーベキュー', 'ホルモン', 'しゃぶ'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'シースー', 'すし'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'ベーカリー', 'パン', 'トースト'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'パティスリー'], 'スイーツ'),
    (['居酒屋', '酒', '炉端', '炉ばた', 'バー'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['フレンチ', 'フランス', 'イタリアン', 'パスタ', '洋食'], '食事'),
    (['割烹', '和食', '天ぷら', '鍋', 'とろろ', '薬膳'], '和食'),
]


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def make_tabelog_url(name):
    return 'https://tabelog.com/rstLst/?vs=1&sa=&sk=' + urllib.parse.quote(name)


def extract_vc_url(href):
    m = re.search(r'vc_url=([^&]+)', href)
    return urllib.parse.unquote(m.group(1)) if m else ''


def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    return urllib.request.urlopen(req, timeout=15).read().decode('utf-8')


def scrape_primary(url):
    """snowman-information.com: div=店名, p=日付/サムネ/住所/タイトル の繰り返し"""
    print(f'取得中（primary）: {url}')
    soup = BeautifulSoup(fetch_html(url), 'html.parser')
    content = soup.find('div', class_='entry-content')
    children = [c for c in content.children if hasattr(c, 'name') and c.name]

    shops = []
    i = 0
    while i < len(children):
        el = children[i]

        # 店名ブロック（divタグ）
        if el.name != 'div' or not el.get_text(strip=True):
            i += 1
            continue

        shop_name = el.get_text(strip=True)
        # 広告・ナビ系のdivを除外
        if any(kw in shop_name for kw in ['広告', 'Snow Man', 'すのちゅーぶ', 'お知らせ', 'PR']):
            i += 1
            continue

        # 次のdivまでの要素を収集
        block = []
        j = i + 1
        while j < len(children):
            if children[j].name == 'div':
                break
            block.append(children[j])
            j += 1

        # --- 日付 ---
        visited_date = ''
        for el2 in block:
            m = re.search(r'(\d{4})/(\d{2})/(\d{2})', el2.get_text())
            if m:
                visited_date = f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
                break
        if not visited_date:
            i = j
            continue

        # --- YouTube ID（サムネ画像 or 動画リンク）---
        youtube_id = ''
        for el2 in block:
            # サムネ画像から取得
            img = el2.find('img', src=re.compile(r'img\.youtube\.com'))
            if not img:
                img = el2.find('img', attrs={'data-src': re.compile(r'img\.youtube\.com')})
            if img:
                src = img.get('data-src') or img.get('src', '')
                m = re.search(r'youtube\.com/vi/([a-zA-Z0-9_-]{11})/', src)
                if m:
                    youtube_id = m.group(1)
                    break
        # サムネから取れなければ動画リンクから
        if not youtube_id:
            for el2 in block:
                a = el2.find('a', href=re.compile(r'youtube\.com/watch'))
                if a:
                    m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', a['href'])
                    if m:
                        youtube_id = m.group(1)
                        break

        # --- 食べログURL ---
        tabelog_url = ''
        for el2 in block:
            a = el2.find('a', href=re.compile(r'tabelog\.com'))
            if a and 'tabelog.com' in a.get('href', ''):
                tabelog_url = a['href'].split('?')[0]
                break
        if not tabelog_url:
            tabelog_url = make_tabelog_url(shop_name)

        # --- 住所・最寄り駅 ---
        address = ''
        nearest_station = ''
        for el2 in block:
            text = el2.get_text(strip=True)
            if text.startswith('■住所'):
                address = text.replace('■住所', '').split('■')[0].strip()
                break
            if re.match(r'^(東京都|大阪府|京都府|北海道|.{2,3}県)', text):
                address = text.split('定休日')[0].strip()
                break
            if '最寄り駅' in text:
                m = re.search(r'最寄り駅[：:]\s*(.+?)(?:定休日|$)', text)
                if m:
                    nearest_station = m.group(1).strip()
                break

        # --- 動画タイトル ---
        source_video_title = ''
        source_video_url = ''
        for el2 in block:
            a = el2.find('a', href=re.compile(r'youtube\.com/watch'))
            if a:
                source_video_title = el2.get_text(strip=True)
                source_video_url = f'https://www.youtube.com/watch?v={youtube_id}' if youtube_id else ''
                break

        genre = detect_genre(shop_name + source_video_title)
        affiliate_links = [{'label': '食べログで見る', 'url': tabelog_url}]

        shops.append({
            'name': shop_name,
            'visited_date': visited_date,
            'description': '',
            'genre': genre,
            'group': GROUP,
            'groups': [GROUP],
            'members': [],
            'address': address,
            'nearest_station': nearest_station,
            'lat': None,
            'lng': None,
            'youtube_id': youtube_id,
            'source_video_title': source_video_title,
            'source_video_url': source_video_url,
            'tabelog_url': tabelog_url,
            'hotpepper_url': '',
            'affiliate_links': affiliate_links,
        })

        i = j

    print(f'  → {len(shops)}件取得')
    return shops


def scrape_secondary(url):
    """hatenablog: table構造、ホットペッパーURLを補完用に取得"""
    print(f'取得中（secondary）: {url}')
    soup = BeautifulSoup(fetch_html(url), 'html.parser')
    tables = soup.find_all('table')

    # h3から年マップ
    year_map = {}
    for h3 in soup.find_all('h3'):
        y_m = re.search(r'(\d{4})年', h3.get_text())
        if y_m:
            year = y_m.group(1)
            for sib in h3.next_siblings:
                if not hasattr(sib, 'name') or not sib.name:
                    continue
                if sib.name == 'h3':
                    break
                if sib.name == 'table':
                    year_map[id(sib)] = year

    result = {}  # 店名 → {hotpepper_url, tabelog_url}
    for table in tables:
        # 店名はh4（日付説明）の次の行テキスト
        h4 = table.find('h4')
        if not h4:
            continue
        # テーブル内のテキスト行をリスト化して店名を取得
        lines = [l.strip() for l in table.get_text(separator='\n').split('\n') if l.strip()]
        # h4テキストの次の行が店名
        h4_text = h4.get_text(strip=True)
        try:
            h4_idx = lines.index(h4_text)
            shop_name = lines[h4_idx + 1] if h4_idx + 1 < len(lines) else ''
        except ValueError:
            continue
        if not shop_name or shop_name in ('PR', '➡'):
            continue

        tabelog_url = ''
        hotpepper_url = ''
        for a in table.find_all('a'):
            label = a.get_text(strip=True)
            actual = extract_vc_url(a.get('href', ''))
            if '食べログ' in label and actual:
                tabelog_url = actual
            elif 'ホットペッパー' in label and actual:
                hotpepper_url = actual

        if hotpepper_url or tabelog_url:
            result[shop_name] = {
                'hotpepper_url': hotpepper_url,
                'tabelog_url': tabelog_url,
            }

    print(f'  → {len(result)}件取得（補完用）')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_snowman.json')
    args = parser.parse_args()

    # primary スクレイピング
    shops = scrape_primary(PRIMARY_URL)

    # secondary でホットペッパーURL補完
    supplement = scrape_secondary(SECONDARY_URL)
    補完 = 0
    for s in shops:
        sup = supplement.get(s['name'])
        if sup:
            if sup['hotpepper_url']:
                s['hotpepper_url'] = sup['hotpepper_url']
                s['affiliate_links'].append({'label': 'ホットペッパーで予約', 'url': sup['hotpepper_url']})
                補完 += 1
            # tabelog_urlも直URLで上書き（secondaryが直URL）
            if sup['tabelog_url'] and 'rstLst' in s.get('tabelog_url', ''):
                s['tabelog_url'] = sup['tabelog_url']
                s['affiliate_links'][0]['url'] = sup['tabelog_url']

    print(f'\nホットペッパーURL補完: {補完}件')

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 完了 ===')
    print(f'総件数: {len(shops)}件')
    print(f'youtube_idあり: {len([s for s in shops if s["youtube_id"]])}件')
    print(f'住所あり: {len([s for s in shops if s["address"]])}件')
    print(f'ホットペッパーあり: {len([s for s in shops if s["hotpepper_url"]])}件')
    print(f'→ {args.output}')


if __name__ == '__main__':
    main()
