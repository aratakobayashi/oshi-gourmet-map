#!/usr/bin/env python3
"""
patch_kosodate_sixtones.py
kosodate-and.net 由来の SixTONES エントリに
visited_date と ordered_items を補完する。

使い方:
  python3 scripts/patch_kosodate_sixtones.py
  python3 scripts/patch_kosodate_sixtones.py --dry-run
"""

import argparse
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SLEEP = 1.5
MAX_RETRIES = 3

_EMBED_MARKERS = ('Instagram', 'この投稿をInstagram', 'pic.twitter.com', 'Twitterをフォロー')
_MENU_HEADER = re.compile(r'【[^】]+】|\d+[本皿杯品個品目皿]')


def fetch(url):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers={'User-Agent': UA}, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, 'html.parser')
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep((attempt + 1) * 3)
            else:
                raise


def extract_published_date(soup):
    """article:published_time メタタグから日付取得"""
    meta = soup.find('meta', property='article:published_time')
    if meta:
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', meta.get('content', ''))
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # フォールバック: 本文内の日付
    txt = soup.get_text()
    m = re.search(r'(\d{4})[年/](\d{1,2})[月/](\d{1,2})日?', txt)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ''


def extract_ordered_items(article):
    """メニューH3セクションから食べた品目リストを抽出"""
    items = []
    menu_h3 = None

    for h3 in article.find_all('h3'):
        txt = h3.get_text()
        if ('食べた' in txt or 'メニュー' in txt) and ('何' in txt or '？' in txt):
            menu_h3 = h3
            break

    if not menu_h3:
        return items

    for sib in menu_h3.next_siblings:
        if not hasattr(sib, 'name') or not sib.name:
            continue
        if sib.name in ('h2', 'h3'):
            break
        if sib.name in ('div', 'p', 'ul', 'ol'):
            raw = sib.get_text(separator=' ', strip=True)
            # embed スキップ
            if any(m in raw for m in _EMBED_MARKERS) or len(raw) > 400:
                continue
            # 【ヘッダー】と本数を削除
            cleaned = _MENU_HEADER.sub('', raw)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            # 空白区切りで品目に分割
            parts = [p.strip() for p in re.split(r'[\s　]+', cleaned) if p.strip()]
            # 1文字単語（タレ/塩など）と長すぎる説明文を除外
            parts = [p for p in parts if 2 <= len(p) <= 30
                     and not re.match(r'^(タレ|塩|醤油|味噌|スパイス|ソース)$', p)]
            items.extend(parts)

        # li タグ直接
        if sib.name in ('ul', 'ol'):
            for li in sib.find_all('li'):
                txt = li.get_text().strip()
                if 2 <= len(txt) <= 40:
                    items.append(txt)

    return list(dict.fromkeys(items))[:20]  # 重複除去・最大20品目


def patch_article(url):
    """1記事から (published_date, ordered_items) を返す"""
    try:
        soup = fetch(url)
    except Exception as e:
        print(f'    エラー: {e}', file=sys.stderr)
        return '', []

    article = soup.find('article') or soup.find('div', class_=re.compile(r'entry|post|content')) or soup
    date = extract_published_date(soup)
    items = extract_ordered_items(article)
    return date, items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--shops-json', default='data/shops.json')
    args = parser.parse_args()

    with open(args.shops_json, encoding='utf-8') as f:
        data = json.load(f)

    # 対象: sixtones & kosodate 由来
    targets = [
        s for s in data
        if 'sixtones' in s.get('groups', [])
        and 'kosodate' in s.get('source_url', '')
    ]
    print(f'対象: {len(targets)}件', file=sys.stderr)

    # URL単位でグループ化（同一記事の複数エントリを1回のフェッチで処理）
    url_to_entries = {}
    for s in targets:
        url = s['source_url']
        url_to_entries.setdefault(url, []).append(s)

    updated_date = 0
    updated_items = 0
    total_urls = len(url_to_entries)

    for i, (url, entries) in enumerate(url_to_entries.items(), 1):
        need_date  = any(not e.get('visited_date') for e in entries)
        need_items = any(not e.get('ordered_items') for e in entries)
        if not need_date and not need_items:
            continue

        print(f'[{i}/{total_urls}] {url}', file=sys.stderr)
        date, items = patch_article(url)
        print(f'    date={date or "なし"}, items={len(items)}品目', file=sys.stderr)

        for e in entries:
            if not e.get('visited_date') and date:
                e['visited_date'] = date
                updated_date += 1
            if not e.get('ordered_items') and items:
                e['ordered_items'] = items
                updated_items += 1

        time.sleep(SLEEP)

    print(f'\nvisited_date 更新: {updated_date}件', file=sys.stderr)
    print(f'ordered_items 更新: {updated_items}件', file=sys.stderr)

    if args.dry_run:
        print('（dry-run: 書き込みスキップ）', file=sys.stderr)
        return

    with open(args.shops_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'保存: {args.shops_json}', file=sys.stderr)


if __name__ == '__main__':
    main()
