"""
scrape_kamaitachi_rascal.py
rascal8280.hatenablog.com/entry/2024/01/01/000000 から
かまいたち東京ロケ飲食店データをスクレイピングする

実際のHTML構造:
  <p>（飲食店）<br>
  ★店名（エリア）/<a href="youtube_url">- YouTube</a><br>
  ☆店名（エリア）/情報テキスト<br>
  ...
  </p><p>（その他）...
"""

import re
import json
import time
import argparse
import urllib.request

URL = 'https://rascal8280.hatenablog.com/entry/2024/01/01/000000'
GROUP = 'kamaitachi'
MEMBERS = ['山内健司', '濱家隆一']

AREA_MAP = {
    '丸の内':   ('東京都', '千代田区', '大手町駅'),
    '水道橋':   ('東京都', '文京区',   '水道橋駅'),
    '渋谷':     ('東京都', '渋谷区',   '渋谷駅'),
    '麻布十番': ('東京都', '港区',     '麻布十番駅'),
    '銀座':     ('東京都', '中央区',   '銀座駅'),
    '新宿':     ('東京都', '新宿区',   '新宿駅'),
    '池袋':     ('東京都', '豊島区',   '池袋駅'),
    '六本木':   ('東京都', '港区',     '六本木駅'),
    '恵比寿':   ('東京都', '渋谷区',   '恵比寿駅'),
    '神保町':   ('東京都', '千代田区', '神保町駅'),
    'お台場':   ('東京都', '江東区',   '台場駅'),
}

YT_ID_RE = re.compile(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})')
HATENA_KW = 'd.hatena.ne.jp/keyword'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8')


def extract_youtube_id(href):
    m = YT_ID_RE.search(href)
    return m.group(1) if m else None


def parse_page(html):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise SystemExit('beautifulsoup4 が必要です: pip install beautifulsoup4')

    soup = BeautifulSoup(html, 'html.parser')
    content = (soup.find('div', class_='entry-content hatenablog-entry')
               or soup.find('div', class_='entry-content'))
    if not content:
        raise SystemExit('entry-content が見つかりません')

    # （飲食店）を含む <p> を探す
    food_p = None
    for p in content.find_all('p'):
        if '飲食店' in p.get_text():
            food_p = p
            break
    if not food_p:
        raise SystemExit('（飲食店）セクションが見つかりません')

    # <br> で行に分割
    shops = []
    current = []
    segments = []

    for child in food_p.children:
        if getattr(child, 'name', None) == 'br':
            segments.append(current)
            current = []
        else:
            current.append(child)
    if current:
        segments.append(current)

    for seg in segments:
        # 行の全テキスト
        full_text = ''.join(
            n.get_text() if hasattr(n, 'get_text') else str(n)
            for n in seg
        ).strip()

        if not full_text or full_text[0] not in ('★', '☆'):
            continue

        # YouTube ID を取得（youtube キーワードリンクはスキップ）
        youtube_id = None
        for node in seg:
            targets = [node] + (node.find_all('a', href=True) if hasattr(node, 'find_all') else [])
            for t in targets:
                href = getattr(t, 'attrs', {}).get('href', '')
                if not href:
                    continue
                if 'youtube.com/watch' in href or 'youtu.be/' in href:
                    youtube_id = extract_youtube_id(href)
                    break
            if youtube_id:
                break

        # 店名テキストを組み立て
        # - YouTube へのリンクは除外
        # - hatena keyword リンクで「youtube」テキストのものは除外（それ以外は店名の一部）
        name_parts = []
        for node in seg:
            if hasattr(node, 'name') and node.name == 'a':
                href = node.get('href', '')
                txt  = node.get_text().strip()
                if 'youtube.com' in href or 'youtu.be' in href:
                    continue
                if txt.lower() in ('youtube', '- youtube'):
                    continue
                name_parts.append(txt)
            else:
                name_parts.append(str(node) if not hasattr(node, 'get_text') else node.get_text())

        name_text = ''.join(name_parts).strip()
        name_text = re.sub(r'^[★☆]', '', name_text).strip()
        name_text = name_text.split('/')[0].strip()

        area_m = re.search(r'（([^）]+)）', name_text)
        area   = area_m.group(1) if area_m else ''
        name   = re.sub(r'（[^）]+）', '', name_text).strip()

        if not name:
            continue

        pref, city, station = AREA_MAP.get(area, ('東京都', '', ''))
        if not area:
            for key, val in AREA_MAP.items():
                if key in name:
                    pref, city, station = val
                    break

        shop = {
            'name':               name,
            'genre':              '食事',
            'prefecture':         pref,
            'city':               city,
            'address':            '',
            'lat':                None,
            'lng':                None,
            'youtube_id':         youtube_id or '',
            'source_video_title': '',
            'source_video_url':   f'https://www.youtube.com/watch?v={youtube_id}' if youtube_id else '',
            'visited_date':       '',
            'members':            MEMBERS,
            'groups':             [GROUP],
            'group':              GROUP,
            'description':        '',
            'nearest_station':    station,
            'tags':               [],
            'affiliate_links':    [],
        }
        shops.append(shop)
        print(f'  {name} | area:{area or "不明"} | yt:{youtube_id or "なし"}')

    return shops


def make_id(name, index):
    slug = re.sub(r'[^\w]', '', name)[:20]
    return f'kamaitachi-{slug}-rascal-{index:03d}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kamaitachi_rascal.json')
    args = parser.parse_args()

    print(f'フェッチ: {URL}')
    html = fetch(URL)
    time.sleep(1)

    print('パース中...')
    shops = parse_page(html)

    for i, s in enumerate(shops):
        s['id'] = make_id(s['name'], i + 1)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n合計 {len(shops)}件 → {args.output} に保存しました')


if __name__ == '__main__':
    main()
