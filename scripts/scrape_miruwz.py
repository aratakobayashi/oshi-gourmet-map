"""
scrape_miruwz.py
miruwz7.blog.jp から =LOVE / ≠ME / ≒JOY の飲食店データをスクレイピング

HTML構造（article-body-inner）:
  <iframe src="https://www.youtube.com/embed/{youtube_id}?..."> → youtube_id
  <h2>店名</h2>
  〒XXXXXXX 住所<br>
  <a href="tabelog or shop URL">...</a>
  ...（複数店舗は h2 が繰り返される）

article-footer タグ:
  #≒JOY / #≠ME / #＝LOVE → group
  #メンバー名               → members

使い方:
  python scripts/scrape_miruwz.py --output scripts/scraped_miruwz.json
"""

import re
import json
import time
import argparse
import urllib.request

BASE_URL = 'https://miruwz7.blog.jp'
CAT_URL  = BASE_URL + '/archives/cat_398470.html'

# チェーン店 / 飲食店以外の除外リスト（部分一致）
CHAIN_EXCLUDES = [
    'ガスト', 'ロイホ', 'ロイヤルホスト',
    '牛角', '焼肉ライク', '焼肉の和民',
    'マクドナルド', 'ケンタッキー', 'モスバーガー', 'バーガーキング',
    'スターバックス', 'ドトール', 'タリーズ', 'コメダ珈琲',
    'くら寿司', 'スシロー', 'はま寿司', '回転寿司',
    'サイゼリヤ', 'デニーズ', 'ジョナサン', 'ジョイフル',
    '松屋', '吉野家', 'すき家', '天丼てんや', 'なか卯',
    '警察署', '交番', '公園', '神社', '寺', '病院', 'クリニック',
    '駅前', 'アイクリニック', '眼鏡', 'アパレル', 'ショップ', 'GARDEN',
]

GROUP_TAG_MAP = {
    '＝LOVE': 'equal_love', 'イコラブ': 'equal_love', '=LOVE': 'equal_love',
    '≠ME':   'notme',
    '≒JOY':  'neajoy', 'ニアジョイ': 'neajoy',
}
GROUP_NAMES = set(GROUP_TAG_MAP.keys())

YT_EMBED_RE = re.compile(r'youtube\.com/embed/([A-Za-z0-9_-]{11})')
POSTAL_RE   = re.compile(r'〒\d{3}-?\d{4}\s*')
DATE_RE     = re.compile(r'(\d{4}-\d{2}-\d{2})')
ARTICLE_URL_RE = re.compile(r'https://miruwz7\.blog\.jp/archives/(\d+)\.html')


def fetch(url, delay=1.0):
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read().decode('utf-8')
    time.sleep(delay)
    return data


def is_chain_or_nonfood(name):
    return any(c in name for c in CHAIN_EXCLUDES)


def collect_article_urls(max_pages=40):
    """カテゴリページを辿って記事URLを全収集（regex版）"""
    seen = set()
    urls = []
    for page in range(1, max_pages + 1):
        url = CAT_URL if page == 1 else f'{CAT_URL}?p={page}'
        print(f'  カテゴリ p{page}: {url}')
        try:
            html = fetch(url, delay=1.5)
        except Exception as e:
            print(f'  エラー: {e}')
            break

        ids = ARTICLE_URL_RE.findall(html)
        if not ids:
            print('  → 記事なし（終了）')
            break

        new = 0
        for aid in dict.fromkeys(ids):  # dedupe while preserving order
            full = f'{BASE_URL}/archives/{aid}.html'
            if full not in seen:
                seen.add(full)
                urls.append(full)
                new += 1

        print(f'  → {new}件 新規（累計 {len(urls)}件）')
        if new == 0:
            break  # 同じ記事しか出なくなったら終了

    return urls


def parse_article(html):
    """記事HTMLから店舗リストを返す"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # YouTube ID（iframe から）
    youtube_id = ''
    iframe = soup.find('iframe', src=YT_EMBED_RE)
    if iframe:
        m = YT_EMBED_RE.search(iframe.get('src', ''))
        if m:
            youtube_id = m.group(1)

    # 投稿日（article-date か time タグから）
    visited_date = ''
    time_el = soup.find('time')
    if time_el:
        m = DATE_RE.search(time_el.get('datetime', '') + time_el.get_text())
        if m:
            visited_date = m.group(1)

    # グループ・メンバー（記事タグ）
    group   = ''
    members = []
    for a in soup.select('dl.article-tags a, li.article-tags-wrap a'):
        raw = a.get_text(strip=True).lstrip('#')
        if raw in GROUP_TAG_MAP:
            group = GROUP_TAG_MAP[raw]
        elif raw and raw not in GROUP_NAMES and len(raw) >= 2:
            members.append(raw)

    # 記事本文
    body = soup.find('div', class_='article-body-inner')
    if not body:
        return []

    shops = []
    h2_tags = body.find_all('h2')

    for h2 in h2_tags:
        name = h2.get_text(strip=True)
        if not name or is_chain_or_nonfood(name):
            continue

        # h2 直後のノードから 〒+住所を取得
        address = ''
        tabelog_url = ''
        for sib in h2.next_siblings:
            sib_name = getattr(sib, 'name', None)
            if sib_name == 'h2':
                break
            sib_text = (sib.get_text(separator=' ', strip=True)
                        if hasattr(sib, 'get_text') else str(sib).strip())
            # 住所検出
            if not address and POSTAL_RE.search(sib_text):
                raw = POSTAL_RE.sub('', sib_text).strip()
                # 改行・&nbsp; で切り取り
                address = re.split(r'\xa0{2,}|\n{2,}|https?://', raw)[0].strip()
                address = re.sub(r'\s+', ' ', address).strip()
            # 食べログURL
            if sib_name == 'a':
                href = sib.get('href', '')
                if 'tabelog.com' in href and not tabelog_url:
                    tabelog_url = href

        if not address:
            continue  # 住所なしはスキップ

        # 都道府県・市区町村を分離
        pref, city = '', ''
        m = re.match(
            r'(東京都|北海道|(?:大阪|京都|神奈川|埼玉|千葉|兵庫|愛知|福岡|静岡|茨城|栃木|群馬|'
            r'新潟|富山|石川|福井|山梨|長野|岐阜|三重|滋賀|奈良|和歌山|鳥取|島根|岡山|広島|'
            r'山口|徳島|香川|愛媛|高知|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄|青森|岩手|'
            r'宮城|秋田|山形|福島)府|.+?県)(\S+?[都道府県市区町村])',
            address
        )
        if m:
            pref = m.group(1)
            city = m.group(2)

        affiliate = []
        if tabelog_url:
            affiliate.append({'label': '食べログで見る', 'url': tabelog_url})

        shop = {
            'name':               name,
            'genre':              '食事',
            'prefecture':         pref,
            'city':               city,
            'address':            address,
            'lat':                None,
            'lng':                None,
            'youtube_id':         youtube_id,
            'source_video_title': '',
            'source_video_url':   f'https://www.youtube.com/watch?v={youtube_id}' if youtube_id else '',
            'visited_date':       visited_date,
            'members':            members,
            'groups':             [group] if group else [],
            'group':              group,
            'description':        '',
            'nearest_station':    '',
            'tags':               [],
            'affiliate_links':    affiliate,
        }
        shops.append(shop)
        addr_disp = address[:30] + '...' if len(address) > 30 else address
        print(f'    ✓ {name} | {pref}{city} | yt:{youtube_id or "なし"} | {addr_disp}')

    return shops


def make_id(name, index):
    slug = re.sub(r'[^\w]', '', name)[:20]
    return f'miruwz-{slug}-{index:03d}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',    default='scripts/scraped_miruwz.json')
    parser.add_argument('--max-pages', type=int, default=40)
    args = parser.parse_args()

    print('=== 記事URL収集 ===')
    article_urls = collect_article_urls(args.max_pages)
    print(f'合計 {len(article_urls)} 記事')

    print('\n=== 記事パース ===')
    all_shops   = []
    seen_names  = set()

    for i, url in enumerate(article_urls):
        print(f'[{i+1}/{len(article_urls)}] {url}')
        try:
            html  = fetch(url, delay=1.2)
            shops = parse_article(html)
            for s in shops:
                if s['name'] not in seen_names:
                    seen_names.add(s['name'])
                    all_shops.append(s)
        except Exception as e:
            print(f'  エラー: {e}')

    for i, s in enumerate(all_shops):
        s['id'] = make_id(s['name'], i + 1)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)

    from collections import Counter
    print(f'\n=== 完了 ===')
    print(f'総件数: {len(all_shops)}件 → {args.output}')
    for g, c in Counter(s['group'] for s in all_shops).most_common():
        print(f'  {g or "(不明)"}: {c}件')


if __name__ == '__main__':
    main()
