#!/usr/bin/env python3
"""
scrape_ordered_items.py
8888-info.hatenablog.com から注文メニューをスクレイピングして
shops.json の ordered_items を補完する。

使い方:
  python scripts/scrape_ordered_items.py --group snowman --dry-run
  python scripts/scrape_ordered_items.py --group snowman --apply
  python scripts/scrape_ordered_items.py --group yonino --dry-run
"""

import json, re, time, argparse, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import requests
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent
SHOPS_JSON  = SCRIPTS_DIR / '../data/shops.json'

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; research-bot/1.0)'}

# グループごとのまとめページURL
INDEX_URLS = {
    'snowman': 'https://8888-info.hatenablog.com/entry/%E3%81%94%E9%A3%AF',
    'yonino':  'https://8888-info.hatenablog.com/entry/%E6%9C%9D%E3%81%94%E3%81%AF%E3%82%93',
}


def normalize(text: str) -> str:
    """照合用の正規化（全角→半角・スペース除去・記号除去）"""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\s　　]+', '', text)
    text = re.sub(r'[【】「」『』（）()・\-ー〜~]', '', text)
    return text.lower()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    # apparent_encoding often misdetects; content-type is utf-8, parse bytes directly
    return BeautifulSoup(resp.content, 'html.parser', from_encoding='utf-8')


def get_article_urls(index_url: str) -> list[str]:
    """まとめページから個別記事URLを収集"""
    soup = fetch(index_url)
    base = 'https://8888-info.hatenablog.com'
    urls = []
    for a in soup.select('a[href]'):
        href = a['href']
        if not href:
            continue
        # 絶対URLに変換
        if href.startswith('http'):
            url = href
        elif href.startswith('/'):
            url = base + href
        else:
            continue
        # 同ブログの /entry/ URLのみ（はてなブックマーク等を除外）
        if not url.startswith(base + '/entry/'):
            continue
        # インデックスページ自身を除外
        if url == index_url or url.rstrip('/') == index_url.rstrip('/'):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def extract_shop_name(soup: BeautifulSoup) -> str:
    """記事からお店名を抽出（最初のh3の『』内、またはh3テキスト末尾の「とは」を除去）"""
    h3 = soup.find('h3')
    if not h3:
        return ''
    text = h3.get_text(strip=True)
    # 『キッチン南国』とは → キッチン南国
    m = re.search(r'[『「]([^』」]+)[』」]', text)
    if m:
        return m.group(1)
    # 末尾の「とは」「について」などを除去
    text = re.sub(r'(とは|について|の場所|のロケ地).*$', '', text).strip()
    return text


def extract_ordered_items(soup: BeautifulSoup) -> list[str]:
    """h3「注文メニュー」以下のsibling divから注文品リストを抽出"""
    items = []
    current_member = ''

    # 「注文メニュー」h3を探す（「注文メニューリスト」「注文したもの」なども対象）
    menu_h3 = None
    for h3 in soup.find_all('h3'):
        text = h3.get_text(strip=True)
        if '注文' in text:
            menu_h3 = h3
            break
    if not menu_h3:
        return []

    # h3の後の兄弟要素を走査（次のh3が来たら終了）
    for sibling in menu_h3.next_siblings:
        if not hasattr(sibling, 'name') or sibling.name is None:
            continue
        if sibling.name == 'h3':
            break

        text = sibling.get_text(strip=True)
        if not text:
            continue

        # メンバー名行の検出（＊/★/☆/▶ + 「注文」を含む行）
        if '注文' in text or '頼' in text or 'オーダー' in text:
            # 「＊深澤辰哉さんが注文したメニュー」「★岩本照さんが注文」形式
            m = re.search(r'[＊★☆▶◆*]?\s*([^\s　＊★☆▶◆*●]{2,8}?)(?:さん)?(?:が|の)(?:注文|頼|オーダー)', text)
            if m:
                current_member = m.group(1).strip()
                continue

        # ●を含む場合は注文品として解析
        if '●' in text:
            parts = text.split('●')
            for part in parts[1:]:  # 最初の空文字をスキップ
                part = part.strip()
                if not part:
                    continue
                # ※以降の注記・価格を除去
                part = re.sub(r'※.*$', '', part).strip()
                # ／300円 / (300円) / 1380円(税込) 形式の価格除去
                part = re.sub(r'[／/]\s*\d[\d,，]*円.*$', '', part).strip()
                part = re.sub(r'\s*[\(（]\s*\d[\d,，]*円[^)）]*[\)）]', '', part).strip()
                part = re.sub(r'\s*\d[\d,，]*円.*$', '', part).strip()
                if part and len(part) > 1:
                    if current_member:
                        part = f'{part}（{current_member}）'
                    items.append(part)

    return items


def match_shop(name: str, candidates: list, threshold: float = 0.6):
    """店名でshops.jsonの店舗をファジーマッチ"""
    best = None
    best_score = 0.0
    for shop in candidates:
        score = similarity(name, shop['name'])
        if score > best_score:
            best_score = score
            best = shop
    if best_score >= threshold:
        return best, best_score
    return None, 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', required=True, choices=list(INDEX_URLS.keys()))
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--threshold', type=float, default=0.6, help='マッチ閾値（デフォルト0.6）')
    args = parser.parse_args()

    if args.apply:
        args.dry_run = False

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    # 対象グループの店舗のみ（既にordered_itemsがないもの）
    candidates = [s for s in shops if s.get('group') == args.group]
    empty_candidates = [s for s in candidates if not s.get('ordered_items')]
    print(f'{args.group}: 全{len(candidates)}件 / ordered_itemsなし{len(empty_candidates)}件\n')

    article_urls = get_article_urls(INDEX_URLS[args.group])
    print(f'記事URL: {len(article_urls)}件取得\n')

    updates = {}  # shop_id -> ordered_items

    for url in article_urls:
        time.sleep(1)
        try:
            soup = fetch(url)
        except Exception as e:
            print(f'  取得失敗: {url} ({e})')
            continue

        shop_name = extract_shop_name(soup)
        if not shop_name:
            continue

        ordered = extract_ordered_items(soup)
        if not ordered:
            continue

        matched, score = match_shop(shop_name, empty_candidates, args.threshold)
        if not matched:
            print(f'  [未マッチ] 「{shop_name}」（スコア不足）')
            continue

        print(f'  [マッチ] 「{shop_name}」→「{matched["name"]}」（score={score:.2f}）')
        print(f'    注文品({len(ordered)}件): {ordered[:3]}{"..." if len(ordered) > 3 else ""}')

        updates[matched['id']] = ordered

    print(f'\n--- 結果: {len(updates)}件マッチ ---')

    if args.dry_run:
        print('（--apply を付けると shops.json に書き込みます）')
        return

    # shops.json に書き込み
    updated = 0
    for shop in shops:
        if shop['id'] in updates:
            shop['ordered_items'] = updates[shop['id']]
            updated += 1

    with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'shops.json 更新: {updated}件')


if __name__ == '__main__':
    main()
