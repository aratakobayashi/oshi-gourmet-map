#!/usr/bin/env python3
"""
scrape_kpop_oshito.py
oshito.online の聖地巡礼記事からK-popグループの訪問飲食店を収集する。

使い方:
  python scripts/scrape_kpop_oshito.py --dry-run   # 記事URLのみ表示
  python scripts/scrape_kpop_oshito.py --output scripts/scraped_kpop.json
"""

import json
import re
import time
import hashlib
import argparse
import urllib.request
from bs4 import BeautifulSoup

BASE_URL   = 'https://oshito.online'
SLEEP      = 1.5
USER_AGENT = 'Mozilla/5.0 (compatible; oshi-gourmet-map/1.0; +https://gourmet.oshikatsu-guide.com)'

# グループ名 → group_id マッピング（タイトルに含まれるキーワード順に判定）
GROUP_MAP = [
    ('ENHYPEN',       'enhypen',    'ENHYPEN'),
    ('エンハイプン',   'enhypen',    'ENHYPEN'),
    ('SEVENTEEN',     'seventeen',  'SEVENTEEN'),
    ('セブチ',        'seventeen',  'SEVENTEEN'),
    ('aespa',         'aespa',      'aespa'),
    ('エスパ',        'aespa',      'aespa'),
    ('Stray Kids',    'straykids',  'Stray Kids'),
    ('ストレイキッズ', 'straykids',  'Stray Kids'),
    ('NewJeans',      'newjeans',   'NewJeans'),
    ('ニュージーンズ', 'newjeans',   'NewJeans'),
    ('IVE',           'ive',        'IVE'),
    ('アイヴ',        'ive',        'IVE'),
    ('RIIZE',         'riize',      'RIIZE'),
    ('ライズ',        'riize',      'RIIZE'),
    ('&TEAM',         'andteam',    '&TEAM'),
    ('アンドチーム',  'andteam',    '&TEAM'),
    ('LE SSERAFIM',   'lesserafim', 'LE SSERAFIM'),
    ('ルセラフィム',   'lesserafim', 'LE SSERAFIM'),
    ('NCT',           'nct',        'NCT'),
    ('TWICE',         'twice',      'TWICE'),
    ('トワイス',      'twice',      'TWICE'),
    ('BTS',           'bts',        'BTS'),
    ('防弾少年団',    'bts',        'BTS'),
    ('BLACKPINK',     'blackpink',  'BLACKPINK'),
    ('ブラックピンク', 'blackpink',  'BLACKPINK'),
    ('EXO',           'exo',        'EXO'),
    ('MONSTA X',      'monstax',    'MONSTA X'),
    ('GOT7',          'got7',       'GOT7'),
    ('ASTRO',         'astro',      'ASTRO'),
]


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': USER_AGENT,
                'Accept-Language': 'ja,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
            })
            with urllib.request.urlopen(req, timeout=15) as res:
                return res.read().decode('utf-8', errors='replace')
        except Exception as e:
            if i < retries - 1:
                time.sleep(SLEEP * 2)
            else:
                raise e


def detect_group(title):
    for keyword, gid, glabel in GROUP_MAP:
        if keyword in title:
            return gid, glabel
    return None, None


def clean_name(raw):
    """店名から番号・絵文字・余分な空白を除去する。"""
    name = re.sub(r'^\d+[\.\．、．]\s*', '', raw).strip()
    name = re.sub(r'[\U00010000-\U0010ffff]', '', name)  # 絵文字除去
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def collect_article_urls(max_pages=15):
    """サイトマップから全記事URLを取得。"""
    urls = []
    for sitemap in ['post-sitemap.xml', 'post-sitemap2.xml']:
        url = f'{BASE_URL}/{sitemap}'
        print(f'  サイトマップ: {url}', flush=True)
        try:
            html = fetch(url)
            soup = BeautifulSoup(html, 'xml')
            found = [loc.text for loc in soup.find_all('loc') if '/news/' in loc.text]
            urls.extend(found)
            print(f'  → {len(found)}件')
            time.sleep(SLEEP)
        except Exception as e:
            print(f'  エラー: {e}')
    return sorted(set(urls))


SHOP_PAT = re.compile(r'^\d+[\.\．、]')
ADDR_PAT = re.compile(r'[都道府県].*[市区町村]')
JP_PREFS  = ('東京都','大阪府','京都府','北海道','神奈川','愛知','福岡','埼玉','千葉',
             '兵庫','静岡','茨城','広島','宮城','栃木','群馬','岡山','新潟','長野',
             '福島','岐阜','三重','滋賀','鹿児島','熊本','沖縄','山口','愛媛','長崎',
             '奈良','青森','岩手','大分','石川','山形','富山','秋田','香川','和歌山',
             '山梨','佐賀','福井','徳島','高知','島根','宮崎','鳥取')


def is_japan_address(addr):
    return any(p in addr for p in JP_PREFS)


def parse_article(url):
    """1記事から店舗リストを抽出して返す。"""
    html = fetch(url)
    soup = BeautifulSoup(html, 'html.parser')

    # タイトル: <title> タグ or <h2>
    title = ''
    if soup.title:
        title = re.sub(r'\s*[-–|].*$', '', soup.title.string or '').strip()
    if not title:
        h2 = soup.find('h2')
        title = h2.get_text(strip=True) if h2 else ''

    group_id, group_label = detect_group(title)
    if not group_id:
        return None, title

    # ドキュメント順で shop / addr / station イベントを収集
    events = []
    for tag in soup.find_all(True):
        t = tag.get_text(strip=True)
        if not t:
            continue

        # 店舗名: <strong> or <h3> で "N. 店名" パターン
        if tag.name in ('strong', 'h3') and SHOP_PAT.match(t) and '🚃' not in t and 2 < len(t) < 65:
            name = clean_name(t)
            if name:
                events.append(('shop', id(tag), name))

        # 住所: <span> or <p>（spanなしのp）で "住所：" を含む
        elif tag.name in ('span', 'p') and '住所' in t and 10 < len(t) < 150:
            # p の場合、子 span に住所 span があれば p 側をスキップ（重複防止）
            if tag.name == 'p' and tag.find('span', string=re.compile('住所')):
                continue
            addr = re.sub(r'^住所[：:\s〒]*', '', t)
            addr = re.sub(r'^\d{3}-\d{4}\s*', '', addr).strip()
            if addr and is_japan_address(addr):
                events.append(('addr', id(tag), addr))

        # 最寄り駅: 🚃 を含む span
        elif tag.name == 'span' and '🚃' in t:
            sta = re.sub(r'🚃\s*', '', t).strip()
            sta = re.sub(r'\d+[\.\．、].*$', '', sta).strip()
            if sta:
                events.append(('station', id(tag), sta))

        # メンバー: 「XXが訪れた」
        elif tag.name in ('p', 'span') and ('が訪れ' in t or 'が来日' in t):
            members = re.findall(r'([ァ-ヶーa-zA-Z]{2,12})(?:が訪れ|が来日)', t)
            if members:
                events.append(('members', id(tag), members))

    # 重複イベント除去（同じ id は1回）
    seen_ids = set()
    uniq_events = []
    for kind, eid, val in events:
        if eid not in seen_ids:
            seen_ids.add(eid)
            uniq_events.append((kind, val))

    # shop → 後続 addr を対応付け（shop が更新されるまで addr は直前の shop に帰属）
    shops = []
    current_name = None
    current_station = ''
    current_members = []

    for kind, val in uniq_events:
        if kind == 'shop':
            # 同名の重複は最後の出現を採用するため上書き
            current_name = val
            current_station = ''
            current_members = []
        elif kind == 'station' and current_station == '':
            current_station = val
        elif kind == 'members':
            current_members.extend(val)
        elif kind == 'addr' and current_name:
            h = hashlib.md5(f'kpop_{group_id}:{current_name}'.encode()).hexdigest()[:8]
            shops.append({
                'id': f'kpop_{group_id}-{h}',
                'name': current_name,
                'group': f'kpop_{group_id}',
                'groups': [f'kpop_{group_id}'],
                'source_video_title': group_label,
                'source_url': url,
                'address': val,
                'nearest_station': current_station,
                'members': list(dict.fromkeys(current_members)),
                'tags': ['K-pop', group_label],
                'lat': None,
                'lng': None,
            })
            current_name = None
            current_station = ''
            current_members = []

    return shops, title


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--output', default='scripts/scraped_kpop.json')
    parser.add_argument('--max-pages', type=int, default=15)
    args = parser.parse_args()

    print('=== oshito.online 記事一覧収集 ===')
    all_urls = collect_article_urls(max_pages=args.max_pages)
    print(f'総記事数: {len(all_urls)}件\n')

    print('=== 記事スクレイピング ===')
    all_shops = []
    skipped = 0
    errors = 0

    for i, url in enumerate(all_urls):
        print(f'[{i+1}/{len(all_urls)}] {url}', end=' ... ', flush=True)
        try:
            shops, title = parse_article(url)
            time.sleep(SLEEP)
            if shops is None:
                print(f'グループ不明: {title[:40]}')
                skipped += 1
            elif len(shops) == 0:
                print(f'店舗なし: {title[:40]}')
                skipped += 1
            else:
                print(f'{len(shops)}件: {title[:40]}')
                all_shops.extend(shops)
        except Exception as e:
            print(f'エラー: {e}')
            errors += 1
            time.sleep(SLEEP)

    # 重複排除
    seen = set()
    unique = []
    for s in all_shops:
        if s['id'] not in seen:
            seen.add(s['id'])
            unique.append(s)

    print(f'\n=== 結果 ===')
    print(f'取得: {len(unique)}件 / スキップ: {skipped}件 / エラー: {errors}件')
    from collections import Counter
    for g, n in Counter(s['group'] for s in unique).most_common():
        print(f'  {g}: {n}件')

    if args.dry_run:
        print('\nサンプル:')
        for s in unique[:10]:
            print(f'  [{s["group"]}] {s["name"]} / {s["address"][:50]}')
        return

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f'\n→ {args.output} に保存')


if __name__ == '__main__':
    main()
