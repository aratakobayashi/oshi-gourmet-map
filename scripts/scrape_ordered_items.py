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
    'snowman':   'https://8888-info.hatenablog.com/entry/%E3%81%94%E9%A3%AF',
    'yonino':    'https://8888-info.hatenablog.com/entry/%E6%9C%9D%E3%81%94%E3%81%AF%E3%82%93',
    'ginga':     'https://8888-info.hatenablog.com/entry/%E3%83%AD%E3%82%B1%E5%9C%B0%E4%B8%80%E8%A6%A7',
    'naniwa':    'https://8888-info.hatenablog.com/entry/%E3%81%AA%E3%81%AB%E3%82%8Ftube',
    'kamenashi': 'https://8888-info.hatenablog.com/entry/%E3%81%BE%E3%81%A8%E3%82%81',
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
    """記事からお店名を抽出"""
    # 方法1: h3/h1の『』「」【】で囲まれた店名
    for tag in soup.find_all(['h3', 'h1']):
        text = tag.get_text(strip=True)
        m = re.search(r'[『「【]([^』」】]{2,30})[』」】]', text)
        if m:
            candidate = m.group(1)
            candidate = re.sub(r'[（(][^）)]*[）)]', '', candidate).strip()  # フリガナ除去
            if candidate and len(candidate) > 1 and not re.search(r'(予約|場所|アクセス|方法|一覧|まとめ|情報|購入|価格|最安値)', candidate):
                return candidate

    # 方法2: h1タイトルの「ロケ地情報。[店名]の場所は」パターン
    for h1 in soup.find_all('h1'):
        text = h1.get_text(strip=True)
        m = re.search(r'[。．]([^。．]{2,30}?)(?:の場所|の店名|のお店|の予約)', text)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r'[（(][^）)]*[）)]', '', candidate).strip()
            if candidate and len(candidate) > 1:
                return candidate

    # 方法3: h3テキストから末尾ノイズ除去
    h3 = soup.find('h3')
    if h3:
        text = h3.get_text(strip=True)
        text = re.sub(r'(とは|について|の場所|のロケ地|＆アクセス.*).*$', '', text).strip()
        if text and text != 'お店' and len(text) > 1:
            return text
    return ''


def extract_ordered_items(soup: BeautifulSoup) -> list[str]:
    """h3「注文メニュー」以下のsibling divから注文品リストを抽出"""
    items = []
    current_member = ''

    # 「注文メニュー」h3を探す（「注文メニューリスト」「チョイスした料理」「メンバー別」なども対象）
    menu_h3 = None
    for h3 in soup.find_all('h3'):
        text = h3.get_text(strip=True)
        if ('注文' in text) or ('メンバー' in text and ('チョイス' in text or 'メニュー' in text or '料理' in text)):
            menu_h3 = h3
            break
    if not menu_h3:
        # フォールバック: ◎形式（亀梨など: <p>PersonName◎item1◎item2...</p>）
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if '◎' not in text:
                continue
            parts = text.split('◎')
            prefix = parts[0].strip()
            member = ''
            if prefix:
                cand = re.sub(r'(さん|くん|ちゃん)$', '', prefix).strip()
                if 2 <= len(cand) <= 8 and not re.search(r'(メニュー|まとめ|一覧|リスト|注文)', cand):
                    member = cand
            for part in parts[1:]:
                food = part.strip()
                food = re.sub(r'[（(]\s*\d[\d,，]*円[^）)]*[）)]', '', food).strip()
                food = re.sub(r'\s*\d[\d,，]*円.*$', '', food).strip()
                if food and len(food) > 1:
                    items.append(f'{food}（{member}）' if member else food)
        return items

    # h3の後の兄弟要素を走査（次のh3が来たら終了）
    for sibling in menu_h3.next_siblings:
        if not hasattr(sibling, 'name') or sibling.name is None:
            continue
        if sibling.name == 'h3':
            break

        text = sibling.get_text(strip=True)
        if not text:
            continue

        # メンバー名行の検出
        if '注文' in text or '頼' in text or 'オーダー' in text or ('チョイス' in text and 'メニュー' in text):
            # 「＊深澤辰哉さんが注文」「＊西畑大吾くん注文メニュー」「★岩本照さんが注文」形式
            m = re.search(r'[＊★☆▶◆*]?\s*([^\s　＊★☆▶◆*●]{2,8}?)(?:さん|くん)?(?:が|の)?(?:注文|頼|オーダー|チョイス)', text)
            if m:
                candidate = m.group(1).strip()
                if not re.search(r'(メニュー|まとめ|一覧|リスト)', candidate):
                    current_member = candidate
                    continue

        # ●を含む場合は注文品として解析
        if '●' in text:
            parts = text.split('●')
            for part in parts[1:]:  # 最初の空文字をスキップ
                part = part.strip()
                if not part:
                    continue

                # なにわ形式判定：「好きなメニュー・item1・item2」→ ・で分割
                sub_parts = part.split('・')
                first = sub_parts[0].strip()
                is_category = bool(re.search(r'メニュー$|^合計', first))

                food_parts = sub_parts[1:] if is_category and len(sub_parts) > 1 else [part]

                for food in food_parts:
                    food = food.strip()
                    if not food or food.startswith('合計'):
                        continue
                    # ※以降の注記・価格を除去
                    food = re.sub(r'※.*$', '', food).strip()
                    food = re.sub(r'[／/]\s*(?:\d[\d,，]*円|無料).*$', '', food).strip()
                    food = re.sub(r'\s*[\(（]\s*\d[\d,，]*円[^)）]*[\)）]', '', food).strip()
                    food = re.sub(r'\s*\d[\d,，]*円.*$', '', food).strip()
                    if food and len(food) > 1:
                        if current_member:
                            food = f'{food}（{current_member}）'
                        items.append(food)

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
