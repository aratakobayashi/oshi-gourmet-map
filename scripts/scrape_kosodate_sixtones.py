#!/usr/bin/env python3
"""
scrape_kosodate_sixtones.py
kosodate-and.net の SixTONES カテゴリをスクレイプ。

使い方:
  python3 scripts/scrape_kosodate_sixtones.py --output scripts/scraped_kosodate_sixtones.json
  python3 scripts/scrape_kosodate_sixtones.py --dry-run
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
CATEGORY_URL = 'https://kosodate-and.net/category/johnnys/sixtones/'
BASE_URL = 'https://kosodate-and.net'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SLEEP = 2.0
MAX_RETRIES = 3

NONFOOD_KEYWORDS = [
    '神社', '寺院', 'お寺', 'ペットショップ', 'ペット', '美術館', '博物館', '水族館',
    '動物園', '植物園', '公園', '遊園地', 'テーマパーク', '映画館', '劇場',
    '駅', '牧場', '農場', 'ゴルフ', 'スキー', 'スタジアム', '球場', '資料館',
    'ジム', 'スパ', '温泉', '大学', '高校', '中学', '小学', '専門学校',
    'LOFT', 'ロフト', '無印良品', 'IKEA', '古着', '眼鏡',
    'ゲームセンター', 'カラオケ', 'ボーリング', '脱出ゲーム', '謎解き',
    '城', '記念館', 'スクール', '教室', '体験施設',
    'アニメイト', 'PLAZA', '家電', 'キデイランド',
    '商店街', 'トイザらス', '保育園', '幼稚園', '科学館', 'プラネタリウム',
    '動物公園', '動物園', '遊園地', 'テーマパーク', '雑貨', '服飾',
    'ヨガ', 'ピラティス', 'アートリンク', 'スケートリンク',
    '食品サンプル', '文化園', 'アミューズメント',
    'Reebok', 'WEGO', 'ゲーセン',
    '大学', '高校', '中学', '小学', '学校法人',
    '住友ビル', 'プール',
]

NONFOOD_URL_KEYWORDS = [
    'driving-school', 'pajyama', 'pajama', '-sandal', 'rohto',
    'mbs-cbc', '-adidas', '-dressing', '-supermarket', '-yakiniku-tare',
    '-coat-', '-jacket-', '-sneaker-', '-shoes-', '-nino-supermarket',
    '-arashi-yakiniku-tare', '-juri-dressing', '-hokuto-sandal',
    '-rebellion-roof',  # MV撮影地
    'taiga-adidas', '6sixtones-mbs',
    '-golf', 'golf-cap',
    'toysrus', '-toys-',
    '-kokkara-mv', '-gong-mv', '-mv',   # MV撮影地（末尾も含む）
    '-piasu', 'reebok-', '-reebok', '-library',
    '-vs-park', '-amusement-park',
    '-onigokko', '-gym-',
    '-kye-piasu',
    'ensemble-wdate',
    'bokurano-jidai',
    'tobuzoo', '5cm-movie', '-planetarium',
    '-zakka',           # 雑貨店
    '-hoikuen',         # 保育園
    '-muji-',           # 無印良品
    '-sano-sa',
    '-wego',            # WEGO古着屋
    '-yoga-', 'yoga-',  # ヨガスタジオ
    '-artrink',         # アートリンク
    '-pool',            # プール
    'tondemi',          # トンデミ（体験型施設）
    '-school',          # 学校/ドラマロケ
    '-sample',          # 食品サンプル展示店
    '-furugi',          # 古着屋
    '-university',      # 大学
    '-ansemu-university',
]


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


def get_all_article_urls(max_pages=25):
    """カテゴリ全ページから記事URLを収集"""
    urls = set()
    for page in range(1, max_pages + 1):
        if page == 1:
            cat_url = CATEGORY_URL
        else:
            cat_url = f'{CATEGORY_URL}page/{page}/'

        print(f'  カテゴリ p{page}: {cat_url}', file=sys.stderr)
        try:
            soup = fetch(cat_url)
        except Exception as e:
            print(f'  エラー: {e}', file=sys.stderr)
            break

        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href'].rstrip('/')
            if not href.startswith(BASE_URL):
                continue
            path = href[len(BASE_URL):]
            # カテゴリ・タグ・著者・固定ページは除外
            if re.search(r'/(category|tag|author|page|profile|sitemap|feed|privacy|contact)', path):
                continue
            # 記事っぽいURLのみ（スラッグが1セグメント）
            segments = [s for s in path.split('/') if s]
            if len(segments) == 1 and href not in urls:
                urls.add(href)
                found += 1

        print(f'    → {found}件追加 (累計 {len(urls)}件)', file=sys.stderr)

        # 次ページがなければ終了
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


_EMBED_MARKERS = ('Instagram', 'Twitterをフォロー', 'この投稿をInstagram', 'pic.twitter.com')
_SENTENCE_ENDS = re.compile(r'(?:です|ます|した|でした|ください|います)[。！。\s]?$')
_BRACKET_NAME = re.compile(r'[「『]([^」』]{2,30})[」』]')
_SQUARE_NAME = re.compile(r'【([^【】]{2,30})】')
_SKIP_BRACKETS = {'住所', 'アクセス', '営業', '定休', '電話', '予約', '席', '注意', '備考'}


def extract_store_name_before(node):
    """【住所】ノードの前から店名を抽出（div/p/h4対応、説明文フィルタあり）"""
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
            # Instagram/Twitterエンベッドをスキップ
            if any(m in raw for m in _EMBED_MARKERS) or len(raw) > 150:
                continue
            if not raw:
                continue

            # <strong> 優先
            strong = sib.find('strong')
            if strong:
                txt = strong.get_text().strip()
                if txt and 2 <= len(txt) <= 50:
                    candidates.insert(0, txt[:50])
                    continue

            # <a> 優先（URLではないリンクテキスト）
            a_tag = sib.find('a')
            if a_tag:
                txt = a_tag.get_text().strip()
                if txt and 2 <= len(txt) <= 50 and 'http' not in txt:
                    candidates.insert(0, txt[:50])
                    continue

            # 説明文フィルタ（です/ます で終わる文は店名でない）
            if _SENTENCE_ENDS.search(raw):
                # 「」 or 『』 内の店名を拾う
                m = _BRACKET_NAME.search(raw)
                if m:
                    candidates.insert(0, m.group(1))
                continue

            # 空白正規化後の長さチェック
            normalized = re.sub(r'\s+', ' ', raw).strip()
            if 2 <= len(normalized) <= 50 and '？' not in normalized:
                # 【store】形式なら中身を抽出
                m = _SQUARE_NAME.search(normalized)
                if m and m.group(1) not in _SKIP_BRACKETS:
                    candidates.insert(0, m.group(1))
                else:
                    candidates.insert(0, normalized[:50])

    # 住所に最も近い候補（最後に挿入されたもの）を返す
    return candidates[-1] if candidates else ''


def extract_visited_date(text):
    m = re.search(r'(\d{4})[年/](\d{1,2})[月/](\d{1,2})日?', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ''


def scrape_article(url):
    """1記事から食事スポット情報を抽出"""
    # URLベース非グルメフィルタ
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

    # H2からビデオタイトルと日付を取得
    video_title = ''
    h2 = article.find('h2')
    if h2:
        video_title = h2.get_text().strip()[:120]

    page_text = article.get_text()
    visited_date = extract_visited_date(page_text)

    # パターン1: <p>【住所】</p> + 次の <p> が住所
    for node in article.find_all(string=re.compile(r'【住所】')):
        parent = node.parent
        if not parent or not hasattr(parent, 'name'):
            continue

        # 住所の抽出: 同じpタグ内にある場合 OR 次のp
        addr_text = ''
        parent_text = parent.get_text().strip()
        if parent_text != '【住所】' and len(parent_text) > 4:
            # 【住所】の後ろに住所がある
            addr_text = parent_text.replace('【住所】', '').strip()
        else:
            next_sib = parent.find_next_sibling()
            if next_sib:
                addr_text = next_sib.get_text(separator=' ', strip=True)

        if not addr_text:
            continue
        addr_text = re.sub(r'\s+', ' ', addr_text).strip()[:120]

        # 都道府県または数字-数字を含む住所らしい文字列か確認
        if not re.search(r'(?:都|道|府|県|市|区|町|村|\d+[-－]\d+)', addr_text):
            continue

        store_name = extract_store_name_before(parent)
        if not store_name:
            continue

        # 非グルメ除外
        if any(kw in store_name for kw in NONFOOD_KEYWORDS):
            continue

        # 周辺から tabelog URL を探す
        context = list(parent.previous_siblings)[:15] + list(parent.next_siblings)[:15]
        tabelog_url = _find_tabelog_in_elements(context)

        # 重複チェック
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

    # パターン2: テーブル（店名列 + 住所列）
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


def make_id(name, visited_date):
    h = hashlib.md5(name.encode()).hexdigest()[:8]
    if visited_date:
        return f"sixtones-{h}-{visited_date.replace('-', '')}"
    return f"sixtones-{h}-"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kosodate_sixtones.json')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--existing-json', default='')
    args = parser.parse_args()

    existing_source_urls = set()
    if args.existing_json:
        try:
            with open(args.existing_json, encoding='utf-8') as f:
                existing = json.load(f)
            existing_source_urls = {s.get('source_url', '') for s in existing if s.get('group') == GROUP}
            print(f'既存ソースURL: {len(existing_source_urls)}件スキップ対象', file=sys.stderr)
        except Exception:
            pass

    article_urls = get_all_article_urls()
    print(f'\n記事URL合計: {len(article_urls)}件', file=sys.stderr)

    all_shops = []
    for url in article_urls:
        if url in existing_source_urls:
            continue
        shops = scrape_article(url)
        if shops:
            print(f'  {url} → {len(shops)}件', file=sys.stderr)
        for s in shops:
            key = s['name'] + '|' + s['address'][:20]
            if any((e['name'] + '|' + e['address'][:20]) == key for e in all_shops):
                continue
            all_shops.append(s)
        time.sleep(SLEEP)

    # フィールド補完 & ID付与
    for s in all_shops:
        s.setdefault('group', GROUP)
        s.setdefault('groups', [GROUP])
        s.setdefault('members', ['ジェシー', '京本大我', '松村北斗', '髙地優吾', '田中樹', '森本慎太郎'])
        s.setdefault('genre', '')
        s.setdefault('description', '')
        s.setdefault('ordered_items', [])
        s.setdefault('lat', None)
        s.setdefault('lng', None)
        s['id'] = make_id(s['name'], s.get('visited_date', ''))

    print(f'\n合計: {len(all_shops)}件', file=sys.stderr)

    if args.dry_run:
        for s in all_shops:
            print(f"  {s['name']} | {s.get('address', '')[:50]} | {s.get('visited_date', '')} | tabelog={'あり' if s.get('tabelog_url') else 'なし'}")
        return

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)
    print(f'保存: {args.output}', file=sys.stderr)


if __name__ == '__main__':
    main()
