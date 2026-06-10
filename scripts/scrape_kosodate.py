#!/usr/bin/env python3
"""
scrape_kosodate.py
kosodate-and.net の各グループカテゴリをスクレイプする汎用スクレイパー。

使い方:
  python3 scripts/scrape_kosodate.py --group kingprince --output scripts/scraped_kingprince.json
  python3 scripts/scrape_kosodate.py --group kattun --output scripts/scraped_kattun.json
  python3 scripts/scrape_kosodate.py --group numberi --output scripts/scraped_numberi.json
  python3 scripts/scrape_kosodate.py --group agroup --output scripts/scraped_agroup.json
  python3 scripts/scrape_kosodate.py --group smap --output scripts/scraped_smap.json
  python3 scripts/scrape_kosodate.py --dry-run --group kingprince
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://kosodate-and.net'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SLEEP = 2.0
MAX_RETRIES = 3

GROUP_CONFIG = {
    'kingprince': {
        'group': 'kingprince',
        'category': 'johnnys/king-and-prince',
        'members': ['永瀬廉', '髙橋海人', '岸優太', '神宮寺勇太'],
        'color': '#5a67d8',
        'max_pages': 55,
    },
    'kattun': {
        'group': 'kattun',
        'category': 'johnnys/kat-tun',
        'members': ['亀梨和也', '中丸雄一', '上田竜也'],
        'color': '#d53f8c',
        'max_pages': 10,
    },
    'numberi': {
        'group': 'numberi',
        'category': 'tobe/number-i',
        'members': ['平野紫耀', '神宮寺勇太', '岸優太'],
        'color': '#2d3748',
        'max_pages': 10,
    },
    'agroup': {
        'group': 'agroup',
        'category': 'johnnys/agroup',
        'members': ['正門良規', '草間リチャード敬太', '末澤誠也', '小島健', '福本大晴', '佐野晶哉'],
        'color': '#e53e3e',
        'max_pages': 10,
    },
    'smap': {
        'group': 'smap',
        'category': 'johnnys/smap',
        'members': ['木村拓哉', '中居正広', '香取慎吾', '草彅剛', '稲垣吾郎'],
        'color': '#38a169',
        'max_pages': 20,
    },
}

NONFOOD_KEYWORDS = [
    '神社', '寺院', 'お寺', 'ペットショップ', 'ペット', '美術館', '博物館', '水族館',
    '動物園', '植物園', '公園', '遊園地', 'テーマパーク', '映画館', '劇場',
    '牧場', '農場', 'ゴルフ', 'スキー', 'スタジアム', '球場', '資料館',
    'ジム', 'スパ', '温泉', '大学', '高校', '中学', '小学', '専門学校',
    'LOFT', 'ロフト', '無印良品', 'IKEA', '古着', '眼鏡',
    'ゲームセンター', 'カラオケ', 'ボーリング', '脱出ゲーム', '謎解き',
    '城', '記念館', 'スクール', '教室', '体験施設',
    'アニメイト', 'PLAZA', '家電', 'キデイランド',
    '商店街', 'トイザらス', '保育園', '幼稚園', '科学館', 'プラネタリウム',
    '雑貨', '服飾', 'ヨガ', 'ピラティス', 'アートリンク', 'スケートリンク',
    '文化園', 'アミューズメント', 'WEGO', 'ゲーセン', 'プール',
    '式場', '会場', '広場', '庭園', 'ビーチ', '海水浴場',
]

NONFOOD_URL_KEYWORDS = [
    '-mv', 'mv-', '-wego', '-yoga-', '-pool', 'tondemi', '-golf',
    '-gym-', '-school', '-university', '-sample', '-furugi',
    '-sneaker', '-shoes', '-coat-', '-jacket', '-dressing',
    '-supermarket', '-driving-school', '-sandal',
    'toysrus', '-toys-', '-planetarium', '-library',
    '-vs-park', '-amusement-park', '-onigokko',
    'zakka', 'hoikuen', 'muji-',
]

EMBED_MARKERS = ('Instagram', 'Twitterをフォロー', 'この投稿をInstagram', 'pic.twitter.com')
SENTENCE_ENDS = re.compile(r'(?:です|ます|した|でした|ください|います)[。！。\s]?$')
BRACKET_NAME = re.compile(r'[「『]([^」』]{2,30})[」』]')
SQUARE_NAME = re.compile(r'【([^【】]{2,30})】')
SKIP_BRACKETS = {'住所', 'アクセス', '営業', '定休', '電話', '予約', '席', '注意', '備考'}


def fetch(url):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers={'User-Agent': UA}, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, 'html.parser')
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 3
                print(f'    リトライ {attempt + 1}/{MAX_RETRIES - 1} ({wait}s待機): {e}', file=sys.stderr)
                time.sleep(wait)
            else:
                raise


def get_all_article_urls(category, max_pages):
    cat_url = f'{BASE_URL}/category/{category}/'
    urls = set()
    for page in range(1, max_pages + 1):
        page_url = cat_url if page == 1 else f'{cat_url}page/{page}/'
        print(f'  カテゴリ p{page}: {page_url}', file=sys.stderr)
        try:
            soup = fetch(page_url)
        except Exception as e:
            print(f'  エラー: {e}', file=sys.stderr)
            break

        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href'].rstrip('/')
            if not href.startswith(BASE_URL):
                continue
            path = href[len(BASE_URL):]
            if re.search(r'/(category|tag|author|page|profile|sitemap|feed|privacy|contact|mail|unei)', path):
                continue
            segments = [s for s in path.split('/') if s]
            if len(segments) == 1 and href not in urls:
                urls.add(href)
                found += 1

        print(f'    → {found}件追加 (累計 {len(urls)}件)', file=sys.stderr)

        has_next = any(f'page/{page + 1}/' in a.get('href', '') for a in soup.find_all('a', href=True))
        if not has_next:
            break
        time.sleep(SLEEP)

    return list(urls)


def _resolve_tabelog(href):
    if 'vc_url=' in href:
        m = re.search(r'vc_url=([^&]+)', href)
        if m:
            actual = urllib.parse.unquote(m.group(1))
            if 'tabelog.com' in actual:
                return actual
    if re.search(r'tabelog\.com/.+/\d', href):
        return href
    return ''


def _find_tabelog_in_elements(elements):
    for el in elements:
        if getattr(el, 'name', None) == 'a':
            href = el.get('href', '')
            if 'tabelog.com' in href:
                result = _resolve_tabelog(href)
                if result:
                    return result
        if not hasattr(el, 'find_all'):
            continue
        for a in el.find_all('a', href=True):
            result = _resolve_tabelog(a['href'])
            if result:
                return result
    return ''


def extract_store_name_before(node):
    candidates = []
    for sib in node.previous_siblings:
        if not hasattr(sib, 'name') or not sib.name:
            continue
        if sib.name in ('h2', 'h3'):
            break
        if sib.name == 'h4':
            txt = sib.get_text().strip()
            if txt and len(txt) <= 50 and '？' not in txt and 'どこ' not in txt:
                candidates.insert(0, txt[:50])
            break
        if sib.name in ('p', 'div'):
            raw = sib.get_text(separator=' ', strip=True)
            if any(m in raw for m in EMBED_MARKERS) or len(raw) > 150:
                continue
            if not raw:
                continue

            strong = sib.find('strong')
            if strong:
                txt = strong.get_text().strip()
                if txt and 2 <= len(txt) <= 50:
                    candidates.insert(0, txt[:50])
                    continue

            a_tag = sib.find('a')
            if a_tag:
                txt = a_tag.get_text().strip()
                if txt and 2 <= len(txt) <= 50 and 'http' not in txt:
                    candidates.insert(0, txt[:50])
                    continue

            if SENTENCE_ENDS.search(raw):
                m = BRACKET_NAME.search(raw)
                if m:
                    candidates.insert(0, m.group(1))
                continue

            normalized = re.sub(r'\s+', ' ', raw).strip()
            if 2 <= len(normalized) <= 50 and '？' not in normalized:
                m = SQUARE_NAME.search(normalized)
                if m and m.group(1) not in SKIP_BRACKETS:
                    candidates.insert(0, m.group(1))
                else:
                    candidates.insert(0, normalized[:50])

    return candidates[-1] if candidates else ''


def extract_visited_date(text):
    m = re.search(r'(\d{4})[年/](\d{1,2})[月/](\d{1,2})日?', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ''


def scrape_article(url):
    url_path = url.split('kosodate-and.net')[-1]
    if any(kw in url_path for kw in NONFOOD_URL_KEYWORDS):
        return []

    try:
        soup = fetch(url)
    except Exception as e:
        print(f'    エラー: {e}', file=sys.stderr)
        return []

    article = soup.find('article') or soup.find('div', class_=re.compile(r'entry|post|content')) or soup
    if not article:
        return []

    shops = []
    video_title = ''
    h2 = article.find('h2')
    if h2:
        video_title = h2.get_text().strip()[:120]

    page_text = article.get_text()
    visited_date = extract_visited_date(page_text)

    for node in article.find_all(string=re.compile(r'【住所】')):
        parent = node.parent
        if not parent or not hasattr(parent, 'name'):
            continue

        addr_text = ''
        parent_text = parent.get_text().strip()
        if parent_text != '【住所】' and len(parent_text) > 4:
            addr_text = parent_text.replace('【住所】', '').strip()
        else:
            next_sib = parent.find_next_sibling()
            if next_sib:
                addr_text = next_sib.get_text(separator=' ', strip=True)

        if not addr_text:
            continue
        addr_text = re.sub(r'\s+', ' ', addr_text).strip()[:120]

        if not re.search(r'(?:都|道|府|県|市|区|町|村|\d+[-－]\d+)', addr_text):
            continue

        store_name = extract_store_name_before(parent)
        if not store_name:
            continue

        if any(kw in store_name for kw in NONFOOD_KEYWORDS):
            continue

        context = list(parent.previous_siblings)[:15] + list(parent.next_siblings)[:15]
        tabelog_url = _find_tabelog_in_elements(context)

        if any(s['name'] == store_name and s['address'][:20] == addr_text[:20] for s in shops):
            continue

        shops.append({
            'name': store_name,
            'address': addr_text,
            'tabelog_url': tabelog_url,
            'visited_date': visited_date,
            'source_url': url,
            'source_video_title': video_title,
        })

    # テーブルパターン
    for table in article.find_all('table'):
        headers = []
        header_row = table.find('tr')
        if header_row:
            headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]

        name_col = next((i for i, h in enumerate(headers) if '店名' in h or '名前' in h), -1)
        addr_col = next((i for i, h in enumerate(headers) if '住所' in h or 'アドレス' in h), -1)
        tab_col = next((i for i, h in enumerate(headers) if '食べログ' in h or 'tabelog' in h.lower()), -1)

        if name_col < 0 or addr_col < 0:
            continue

        for row in table.find_all('tr')[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) <= max(name_col, addr_col):
                continue
            store_name = cells[name_col].get_text().strip()[:50]
            addr_text = cells[addr_col].get_text(separator=' ', strip=True)[:120]

            if not store_name or not addr_text:
                continue
            if any(kw in store_name for kw in NONFOOD_KEYWORDS):
                continue
            if not re.search(r'(?:都|道|府|県|市|区|町|村|\d+[-－]\d+)', addr_text):
                continue

            tabelog_url = ''
            if tab_col >= 0 and len(cells) > tab_col:
                a_tag = cells[tab_col].find('a', href=True)
                if a_tag:
                    tabelog_url = _resolve_tabelog(a_tag['href'])

            if any(s['name'] == store_name for s in shops):
                continue

            shops.append({
                'name': store_name,
                'address': re.sub(r'\s+', ' ', addr_text).strip(),
                'tabelog_url': tabelog_url,
                'visited_date': visited_date,
                'source_url': url,
                'source_video_title': video_title,
            })

    return shops


def make_id(group, name, visited_date):
    h = hashlib.md5(name.encode()).hexdigest()[:8]
    if visited_date:
        return f"{group}-{h}-{visited_date.replace('-', '')}"
    return f"{group}-{h}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', required=True, choices=list(GROUP_CONFIG.keys()),
                        help='グループID')
    parser.add_argument('--output', default='')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max-pages', type=int, default=0)
    args = parser.parse_args()

    cfg = GROUP_CONFIG[args.group]
    group_id = cfg['group']
    members = cfg['members']

    if not args.output:
        args.output = f'scripts/scraped_{args.group}.json'

    max_pages = args.max_pages or cfg['max_pages']

    print(f'=== {args.group} スクレイピング開始 ===', file=sys.stderr)
    print(f'カテゴリ: /category/{cfg["category"]}/', file=sys.stderr)

    article_urls = get_all_article_urls(cfg['category'], max_pages)
    print(f'\n記事URL合計: {len(article_urls)}件\n', file=sys.stderr)

    # 既存DB読み込み（重複除外）
    existing_names = set()
    try:
        with open('data/shops.json', encoding='utf-8') as f:
            existing = json.load(f)
        existing_names = {s['name'] for s in existing if s.get('group') == group_id}
        print(f'既存DB: {len(existing_names)}件スキップ対象', file=sys.stderr)
    except Exception:
        pass

    all_shops = []
    for i, url in enumerate(sorted(article_urls), 1):
        shops = scrape_article(url)
        if shops:
            print(f'[{i}/{len(article_urls)}] {url.split("/")[-2]} → {len(shops)}件', file=sys.stderr)
        for s in shops:
            if s['name'] in existing_names:
                continue
            key = s['name'] + '|' + s['address'][:20]
            if any((e['name'] + '|' + e['address'][:20]) == key for e in all_shops):
                continue
            all_shops.append(s)
        time.sleep(SLEEP)

    # フィールド補完
    for s in all_shops:
        s['group'] = group_id
        s['groups'] = [group_id]
        s['members'] = members
        s['genre'] = ''
        s['description'] = ''
        s['ordered_items'] = []
        s['lat'] = None
        s['lng'] = None
        s['prefecture'] = ''
        s['city'] = ''
        s['nearest_station'] = ''
        s['tags'] = []
        s['affiliate_links'] = [{'label': '食べログで見る', 'url': s['tabelog_url']}] if s.get('tabelog_url') else []
        s['id'] = make_id(group_id, s['name'], s.get('visited_date', ''))

    print(f'\n合計: {len(all_shops)}件', file=sys.stderr)

    if args.dry_run:
        for s in all_shops:
            print(f"  {s['name']} | {s.get('address', '')[:50]}")
        return

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)
    print(f'保存: {args.output}', file=sys.stderr)


if __name__ == '__main__':
    main()
