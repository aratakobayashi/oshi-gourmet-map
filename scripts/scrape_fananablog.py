#!/usr/bin/env python3
"""
scrape_fananablog.py
fananablog.com の SixTONES YouTube ロケ地まとめページをスクレイプ。

使い方:
  python3 scripts/scrape_fananablog.py --output scripts/scraped_sixtones.json
  python3 scripts/scrape_fananablog.py --dry-run
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

GROUP = 'sixtones'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SLEEP = 1.5

# 年別ページ URL
PAGE_URLS = [
    'https://fananablog.com/sixtones-seichi-youtube/',        # 2025
    'https://fananablog.com/sixtones-seichi-youtube-2024/',
    'https://fananablog.com/sixtones-seichi-youtube-2023/',
    'https://fananablog.com/sixtones-seichi-youtube-2022/',
    'https://fananablog.com/sixtones-seichi-youtube-2020/',
    'https://fananablog.com/sixtones-seichi-youtube-2019/',
    'https://fananablog.com/sixtones-seichi-youtube-2018/',
]

NONFOOD_KEYWORDS = [
    '大学', '専門学校', '高校', '中学', '小学', '博物館', '美術館', '水族館', '動物園',
    '植物園', '公園', '遊園地', 'テーマパーク', '映画館', '図書館', '体育館', 'スタジアム',
    '球場', 'ゴルフ', 'スキー', 'サーキット', 'ヨガ', 'スパ', 'ジム', 'アスレ',
    '脱出ゲーム', '謎解き', 'ゲームセンター', 'カラオケ', 'ボーリング', 'プール',
    'ポケモンセンター', 'アニメイト', 'トイザらス', 'ブックオフ', 'PLAZA',
    '家電', 'ノジマ', '無印良品', 'LOFT', 'ロフト', 'キデイランド', 'IKEA',
    '神社', 'お寺', '寺院', '城', '資料館', '記念館', '回向院',
    'ゴーカート', 'サバゲー', 'ペイント', 'アスレチック', 'サファリ',
    'キャンプ', '温泉', 'スタジオ', '劇場', '座',
    '駅', 'PA ', '牧場', '農場', '牧', 'ハンモック',
    '眼鏡', '古着', 'ヴィレッジ', '似顔絵', 'バッティング',
    '射的', 'FlyStation', 'アドベンチャー',
    '監獄', 'ゲーム体験',
    '食品サンプル', '中華街', '物産館', '観光物産', 'パーカッション', '楽器',
]

# グルメ確定キーワード（店名にあれば食事スポットと判定）
FOOD_KEYWORDS = [
    'ラーメン', 'らーめん', 'そば', 'うどん', 'パスタ', 'ピザ', 'ピッツァ',
    '餃子', '焼肉', '焼き肉', '焼き鳥', '焼鳥', '鉄板',
    '寿司', 'すし', '刺身', '海鮮', '魚', '魚介', '貝', 'うなぎ',
    'カフェ', 'cafe', 'coffee', 'コーヒー', '珈琲',
    'パン', 'ベーカリー', 'bakery', 'スイーツ', 'ケーキ', 'パフェ',
    '中華', '中国料理', '台湾', '韓国', 'もんじゃ', 'お好み焼き',
    'カレー', 'ハンバーグ', 'ハンバーガー', 'ステーキ',
    'イタリアン', 'フレンチ', '洋食', '和食', '定食', '食堂',
    'レストラン', 'ダイニング', '居酒屋', '酒場', 'バル', 'ビストロ',
    '食事処', '飯店', 'めし', '弁当',
    'チーズ', 'アイス', 'たこ焼き', 'クレープ', 'とんかつ',
    'お茶', '抹茶', 'タピオカ',
    '市場', '産直',
]


def fetch(url):
    r = requests.get(url, headers={'User-Agent': UA}, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')


def extract_address(text):
    # 〒XXX-XXXX 住所
    m = re.search(r'(〒\d{3}[-－]\d{4}\s*\n?\s*[^\n]{5,100})', text)
    if m:
        addr = re.sub(r'\s+', ' ', m.group(1)).strip()
        return addr[:120]
    # 都道府県パターン（番地あり）
    m = re.search(
        r'((?:東京都|大阪府|京都府|北海道|.{2,3}県)[^\n]{3,30}[市区町村][^\n]{2,40}(?:\d+[-－]\d+|\d+丁目))',
        text
    )
    if m:
        return m.group(1).strip()[:120]
    return ''


def extract_ordered_items(text):
    items = []
    # 「食べたもの」セクション以降の行を取得
    idx = text.find('食べたもの')
    if idx < 0:
        return items
    section = text[idx + len('食べたもの'):]
    for line in section.split('\n'):
        line = line.strip()
        if not line:
            continue
        # 次のセクション区切りで終了
        if re.match(r'^(住所|電話|アクセス|開始時間|定休日|営業|URL|https?://)', line):
            break
        if len(line) >= 2 and len(line) <= 60:
            items.append(line)
    return items[:15]


def extract_video_title(sibs):
    for sib in sibs:
        if sib.name == 'p':
            txt = sib.get_text().strip()
            if txt and len(txt) > 3:
                return txt[:120]
    return ''


def extract_visited_date(text):
    m = re.search(r'\((\d{4})[/．.](\d{1,2})[/．.](\d{1,2})配信', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ''


def extract_tabelog_url(sibs):
    for sib in sibs:
        # sibling自身がaタグの場合
        if getattr(sib, 'name', None) == 'a':
            href = sib.get('href', '')
            if 'tabelog.com' in href or 'vc_url' in href:
                return _resolve_tabelog(href)
        if not hasattr(sib, 'find_all'):
            continue
        for a in sib.find_all('a', href=True):
            href = a['href']
            if 'tabelog.com' in href or 'vc_url' in href:
                result = _resolve_tabelog(href)
                if result:
                    return result
    return ''


def _resolve_tabelog(href):
    if 'vc_url=' in href:
        m = re.search(r'vc_url=([^&]+)', href)
        if m:
            actual = urllib.parse.unquote(m.group(1))
            if 'tabelog.com' in actual:
                return actual
    elif re.search(r'tabelog\.com/.+/\d+', href):
        return href
    return ''


def make_id(name, visited_date):
    slug = re.sub(r'[^\w]', '_', name)[:20].lower()
    h = hashlib.md5(name.encode()).hexdigest()[:8]
    if visited_date:
        date_slug = visited_date.replace('-', '')
        return f"sixtones-{h}-{date_slug}"
    return f"sixtones-{h}-"


def scrape_page(url):
    print(f'  スクレイプ: {url}', file=sys.stderr)
    try:
        soup = fetch(url)
    except Exception as e:
        print(f'  エラー: {e}', file=sys.stderr)
        return []

    shops = []
    for h3 in soup.find_all('h3'):
        shop_name = h3.get_text().strip()
        if not shop_name:
            continue

        # 閉店施設はスキップ
        if '閉店' in shop_name:
            continue

        # 非グルメキーワードをスキップ
        if any(kw in shop_name for kw in NONFOOD_KEYWORDS):
            continue

        # siblings収集（次のh2/h3まで）
        sibs = []
        for sib in h3.next_siblings:
            if not hasattr(sib, 'name') or not sib.name:
                continue
            if sib.name in ('h2', 'h3'):
                break
            sibs.append(sib)

        if not sibs:
            continue

        full_text = '\n'.join(s.get_text(separator='\n', strip=True) for s in sibs if hasattr(s, 'get_text'))

        address = extract_address(full_text)
        if not address:
            continue

        # グルメ判定: 「食べたもの」セクションあり OR 店名にFOOD_KEYWORDS
        has_menu_section = '食べたもの' in full_text
        name_is_food = any(kw.lower() in shop_name.lower() for kw in FOOD_KEYWORDS)
        if not (has_menu_section or name_is_food):
            continue

        # 非グルメ施設チェック（full_textにも適用）
        if any(kw in full_text[:200] for kw in ['脱出ゲーム', '謎解き', 'ヨガ', 'スポーツ施設']):
            continue

        video_title = extract_video_title(sibs)
        visited_date = extract_visited_date(video_title + '\n' + full_text)
        ordered_items = extract_ordered_items(full_text)
        tabelog_url = extract_tabelog_url(sibs)

        shops.append({
            'name': shop_name,
            'group': GROUP,
            'groups': [GROUP],
            'members': ['ジェシー', '京本大我', '松村北斗', '髙地優吾', '田中樹', '森本慎太郎'],
            'address': address,
            'visited_date': visited_date,
            'source_url': url,
            'source_video_title': video_title,
            'tabelog_url': tabelog_url,
            'ordered_items': ordered_items,
            'genre': '',
            'description': '',
            'lat': None,
            'lng': None,
        })

    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_sixtones.json')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--existing-json', default='')
    args = parser.parse_args()

    existing_urls = set()
    if args.existing_json:
        try:
            with open(args.existing_json, encoding='utf-8') as f:
                existing = json.load(f)
            existing_urls = {s.get('source_url', '') for s in existing if s.get('group') == GROUP}
            print(f'既存ソースURL: {len(existing_urls)}件スキップ対象')
        except Exception:
            pass

    all_shops = []
    for url in PAGE_URLS:
        shops = scrape_page(url)
        # source_url が既存と重複するものはスキップ（ただし同一ページ内は許可）
        new_shops = []
        for s in shops:
            # 店名+住所で重複チェック
            key = s['name'] + '|' + s['address'][:30]
            if any(key == (e['name'] + '|' + e.get('address','')[:30]) for e in all_shops):
                continue
            new_shops.append(s)
        all_shops.extend(new_shops)
        print(f'  → {len(new_shops)}件取得 (累計 {len(all_shops)}件)', file=sys.stderr)
        time.sleep(SLEEP)

    # IDを付与
    for s in all_shops:
        s['id'] = make_id(s['name'], s.get('visited_date', ''))

    print(f'\n合計: {len(all_shops)}件', file=sys.stderr)

    if args.dry_run:
        for s in all_shops:
            print(f"  {s['name']} | {s.get('address','')[:50]} | {s.get('visited_date','')} | menu={len(s.get('ordered_items',[]))}件")
        return

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)
    print(f'保存: {args.output}', file=sys.stderr)


if __name__ == '__main__':
    main()
