#!/usr/bin/env python3
"""
scrape_chiicrane.py
chiicrane-life.fun (大人のゆる推し日和) からなにわ男子のどっち派グルメ情報をスクレイピング

使い方:
  python scripts/scrape_chiicrane.py --auto-discover --output scripts/scraped_chiicrane.json
  python scripts/scrape_chiicrane.py --urls URL1 URL2 --output scripts/scraped_chiicrane.json
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit('pip install beautifulsoup4 を実行してください')

CATEGORY_URL = 'https://www.chiicrane-life.fun/category/location/which/'
GROUP = 'naniwa'
MEMBERS = ['大西流星', '道枝駿佑', '高橋恭平', '長尾謙杜', '西畑大吾', '藤原丈一郎', '大橋和也']

FOOD_TITLE_KEYWORDS = [
    'グルメ', 'スイーツ', 'カフェ', '飲食店', 'パン', 'ラーメン', '朝食',
    'シメ飯', '料理', 'フードコート', '卵', 'ファミレス', '一人飯',
    'かき氷', 'ジェラート', '築地', '中華街', '和グルメ', 'お弁当',
    'お惣菜', '進化系', '新業態', 'コラボメニュー', '肉フェス', '焼肉',
    '寿司', '鍋', 'ハンバーグ', 'ホットドッグ', 'パスタ', 'ピザ',
    'スープ', 'チーズ', 'スーパー', 'ロピア', '道の駅', 'グルメスポット',
    '名店', 'アヒージョ', 'チョコ', '居酒屋', 'バーガー', '海鮮',
    'お好み焼き', '餃子', 'イチゴ', 'お取り寄せグルメ', '食べられる',
    '食べた', '飲食', 'レストラン', 'デリ', '行ったお店',
]
NONFOOD_TITLE_KEYWORDS = [
    '家電', '習い事', 'プール', '花火', '紅葉スポット', '温泉スポット',
    'レジャースポット', 'イルミネーション', 'プラネタリウム', '廃校',
    '体験施設', '花見', '万博', '自動販売機', 'シーズニング', 'レトルト',
    '冷凍食品', 'USJで体験', '遊べる施設', 'ピクニック', 'グランピング',
    '睡眠', '便利家電', 'あったか家電', '便利グッズ', '最新家電',
    'キッチン家電', '生活家電', 'アトラクション',
]

SKIP_NAME_PATTERNS = [
    'まとめ', 'アクセス', '購入先', 'お取り寄せ', 'SNS', 'Twitter',
    'Instagram', 'スポンサー', '広告', 'PR', '関連記事', 'よく読まれている',
    'コメント', '関連情報', '詳細', 'プロフィール', 'カテゴリ', 'タグ',
    'リンク', 'お問い合わせ',
]

# 店名に含まれていたら非グルメ施設として除外するキーワード
NONFOOD_VENUE_KEYWORDS = [
    '大学', '専門学校', '中学校', '小学校', '高等学校', '高校',
    '博物館', '美術館', '水族館', '動物園', '植物園',
    '公園', 'テーマパーク', '遊園地', '映画館', '図書館',
    '体育館', 'スタジアム', '球場', 'キャンパス',
    '郷土資料館', '記念館', '資料館', 'ミュージアム',
]


def log(msg):
    print('[%s] %s' % (datetime.now().strftime('%H:%M:%S'), msg))


def fetch_html(url, delay=1.5):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'oshi-gourmet-map/1.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode('utf-8', errors='replace')
        time.sleep(delay)
        return html
    except Exception as e:
        log('  取得エラー: %s — %s' % (url, e))
        return None


def is_food_article(title):
    """タイトルから食事関連かどうか判定。判定不可の場合None"""
    for kw in NONFOOD_TITLE_KEYWORDS:
        if kw in title:
            return False
    for kw in FOOD_TITLE_KEYWORDS:
        if kw in title:
            return True
    return None


def discover_article_urls():
    """カテゴリページから全エピソードURLを収集"""
    all_urls = []
    seen = set()
    page = 1
    while True:
        url = '%spage/%d/' % (CATEGORY_URL, page) if page > 1 else CATEGORY_URL
        log('カテゴリ p%d: %s' % (page, url))
        html = fetch_html(url, delay=1.0)
        if not html:
            break
        soup = BeautifulSoup(html, 'html.parser')
        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href'].rstrip('/')
            if 'chiicrane-life.fun/mezamashi' in href and href not in seen:
                seen.add(href)
                all_urls.append(href)
                found += 1
        log('  %d件追加 (累計%d件)' % (found, len(all_urls)))
        if found == 0:
            break
        next_link = (
            soup.find('a', class_=re.compile(r'next', re.I)) or
            soup.find('a', string=re.compile(r'次|Next', re.I))
        )
        if not next_link:
            break
        page += 1
        if page > 20:
            break
    return all_urls


def extract_date_from_url(url):
    m = re.search(r'mezamashi[-_](\d{4})[-_](\d{2})[-_](\d{2})', url)
    if m:
        return '%s-%s-%s' % (m.group(1), m.group(2), m.group(3))
    return ''


def extract_member(text):
    for m in MEMBERS:
        if m in text:
            return m
    return ''


def clean_shop_name(raw):
    """h3テキストから店名をクリーニング"""
    name = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩\d]+[.．）\)\s、]*', '', raw).strip()
    name = re.sub(r'^[：:\-–—\s]+', '', name).strip()
    name = re.sub(r'\s*（[^）]{0,20}ロケ地[^）]{0,20}）\s*$', '', name).strip()

    # 「地域」「店名」形式 → 「」内の店名を抽出
    bracket_m = re.search(r'「([^」]+)」\s*$', name)
    if bracket_m:
        name = bracket_m.group(1).strip()
    # 【エリア】店名 形式 → 【】を除去して店名を取得
    sumikakko_m = re.match(r'【[^】]+】\s*(.+)$', name)
    if sumikakko_m:
        name = sumikakko_m.group(1).strip()

    # 半角カタカナ読み仮名を除去 (例: 囍鵲亭ｷｼﾞｬｸﾃｲ)
    name = re.sub(r'[ｦ-ﾟ]+$', '', name).strip()

    if any(kw in name for kw in SKIP_NAME_PATTERNS):
        return ''
    if len(name) < 2:
        return ''
    if re.match(r'^[（\(]', name):
        return ''
    return name


def extract_address(text):
    """テキストブロックから住所を抽出"""
    # 〒XXX-XXXX 都道府県〜
    m = re.search(
        r'〒\d{3}[-－]\d{4}\s*(.{5,80}?)(?:\n|TEL|電話|営業|定休|URL|$)',
        text, re.DOTALL
    )
    if m:
        addr = re.sub(r'\s+', ' ', m.group(0)).strip()
        return addr[:120]
    # ■住所 / 住所: / 住所\n〒... など各種形式
    m = re.search(r'[■▪●]?\s*住所\s*[：:）):]?\s*\n?\s*(.{5,80}?)(?:\n|$)', text)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) >= 5 and not candidate.startswith('■'):
            return candidate[:120]
    # 都道府県 + 市区町村 + 番地パターン（丁目番号必須でノイズを除去）
    m = re.search(
        r'(東京都|大阪府|京都府|北海道|.{2,3}県)'
        r'[^\n]{2,20}[市区町村]'
        r'[^\n]{2,40}(?:\d+[-－]\d+|\d+丁目)',
        text
    )
    if m:
        return m.group(0).strip()[:120]
    return ''


def _resolve_tabelog_href(href):
    if 'vc_url=' in href:
        vm = re.search(r'vc_url=([^&]+)', href)
        if vm:
            actual = urllib.parse.unquote(vm.group(1))
            if 'tabelog.com' in actual:
                return actual
    elif re.search(r'tabelog\.com/.+/\d+', href):
        return href
    return ''


def extract_tabelog_url(elements):
    for el in elements:
        # el 自身が <a> タグの場合（find_all は自身を含まない）
        if getattr(el, 'name', None) == 'a':
            href = el.get('href', '')
            if 'tabelog.com' in href:
                result = _resolve_tabelog_href(href)
                if result:
                    return result
        if not hasattr(el, 'find_all'):
            continue
        for a in el.find_all('a', href=True):
            href = a['href']
            if 'tabelog.com' in href:
                result = _resolve_tabelog_href(href)
                if result:
                    return result
    return ''


def extract_hotpepper_url(elements):
    for el in elements:
        if getattr(el, 'name', None) == 'a':
            href = el.get('href', '')
            if 'hotpepper' in href.lower():
                return href
        if not hasattr(el, 'find_all'):
            continue
        for a in el.find_all('a', href=True):
            href = a['href']
            if 'hotpepper' in href.lower():
                return href
    return ''


def extract_ordered_items(text):
    items = []
    for m in re.finditer(r'([^\n]{2,30}?)\s*[：:]\s*([\d,]+円)', text):
        items.append('%s（%s）' % (m.group(1).strip(), m.group(2)))
    if not items:
        for m in re.finditer(r'([^\n]{5,40}?)\s+[\d,]+円', text):
            items.append(m.group(0).strip())
    return list(dict.fromkeys(items))[:5]


def detect_genre(name, text):
    combined = name + ' ' + text
    GENRE_MAP = [
        (['ラーメン', 'つけ麺', '冷麺', 'ヌードル'], 'ラーメン'),
        (['焼肉', 'ステーキ', '肉', 'BBQ'], '焼肉'),
        (['寿司', '鮨', '海鮮丼', '回転寿司'], '寿司'),
        (['カフェ', 'コーヒー', '珈琲', 'COFFEE', 'coffee', 'トースト'], 'カフェ'),
        (['パン', 'ベーカリー', 'デニッシュ', 'クロワッサン'], 'カフェ'),
        (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'ジェラート', 'チョコ', 'デザート',
          'ドーナツ', 'スラビ', 'ヨーグルト', 'チーズケーキ', 'プリン'], 'スイーツ'),
        (['居酒屋', 'バー', '酒場'], '居酒屋'),
        (['餃子', 'もんじゃ', 'お好み焼き', '中華'], '食事'),
        (['ハンバーガー', 'バーガー', 'ホットドッグ'], '食事'),
        (['ピザ', 'パスタ', 'イタリアン', 'アヒージョ'], '食事'),
    ]
    for keywords, genre in GENRE_MAP:
        if any(kw in combined for kw in keywords):
            return genre
    return '食事'


def scrape_article(url, existing_names=None):
    """1記事からグルメ店舗情報を抽出"""
    if existing_names is None:
        existing_names = set()
    visited_date = extract_date_from_url(url)

    html = fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')

    og = soup.find('meta', property='og:title')
    title = og['content'] if og else ''
    if not title:
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else ''

    if not visited_date:
        dm = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', title)
        if dm:
            visited_date = '%s-%02d-%02d' % (
                dm.group(1), int(dm.group(2)), int(dm.group(3))
            )

    member = extract_member(title)
    source_title = (
        'なにわ男子のどっち派 (%s)' % visited_date
        if visited_date else 'なにわ男子のどっち派'
    )

    article = (
        soup.find('article') or
        soup.find('div', class_=re.compile(
            r'entry.content|post.content|article.content', re.I
        )) or
        soup.find('main') or
        soup.body
    )
    if not article:
        return []

    shops = []
    headings = article.find_all(['h2', 'h3'])

    for heading in headings:
        raw_name = heading.get_text(strip=True)

        if heading.name == 'h2':
            # h2は「店名」or【エリア】店名パターンのみ処理（セクションヘッダーを除外）
            has_kakko = ('「' in raw_name and '」' in raw_name)
            has_sumikakko = ('【' in raw_name and '】' in raw_name)
            if not has_kakko and not has_sumikakko:
                continue

        shop_name = clean_shop_name(raw_name)
        if not shop_name:
            continue
        if shop_name in existing_names:
            continue

        sibling_els = []
        for sib in heading.next_siblings:
            if not hasattr(sib, 'name') or not sib.name:
                continue
            if sib.name in ('h1', 'h2', 'h3', 'h4'):
                break
            sibling_els.append(sib)

        if not sibling_els:
            continue

        full_text = '\n'.join(
            el.get_text(separator='\n', strip=True)
            for el in sibling_els
            if hasattr(el, 'get_text')
        )

        address = extract_address(full_text)
        if not address:
            continue

        # 明らかな非グルメ施設（大学・博物館・公園等）はスキップ
        if any(kw in shop_name for kw in NONFOOD_VENUE_KEYWORDS):
            continue

        tabelog_url = extract_tabelog_url(sibling_els)
        hotpepper_url = extract_hotpepper_url(sibling_els)
        ordered_items = extract_ordered_items(full_text)
        genre = detect_genre(shop_name, full_text)

        affiliate_links = []
        if tabelog_url:
            affiliate_links.append({'label': '食べログで見る', 'url': tabelog_url})
        if hotpepper_url:
            affiliate_links.append({'label': 'ホットペッパーで予約', 'url': hotpepper_url})

        shops.append({
            'name': shop_name,
            'genre': genre,
            'group': GROUP,
            'groups': [GROUP],
            'members': [member] if member else [],
            'address': address,
            'visited_date': visited_date,
            'source_video_title': source_title,
            'source_url': url,
            'tabelog_url': tabelog_url,
            'hotpepper_url': hotpepper_url,
            'affiliate_links': affiliate_links,
            'ordered_items': ordered_items,
            'description': '',
            'lat': None,
            'lng': None,
        })

    return shops


def main():
    parser = argparse.ArgumentParser(description='chiicrane-life.fun スクレイパー')
    parser.add_argument('--auto-discover', action='store_true',
                        help='カテゴリページから全URLを自動収集')
    parser.add_argument('--urls', nargs='+', help='スクレイプするURLを直接指定')
    parser.add_argument('--output', default='scripts/scraped_chiicrane.json')
    parser.add_argument('--existing-json', help='既存shops.jsonパス（重複チェック用）')
    args = parser.parse_args()

    existing_names = set()
    if args.existing_json:
        try:
            with open(args.existing_json, encoding='utf-8') as f:
                existing = json.load(f)
            existing_names = {s['name'] for s in existing}
            log('既存店舗読み込み: %d件' % len(existing_names))
        except Exception as e:
            log('既存JSON読み込みエラー: %s' % e)

    if args.auto_discover:
        article_urls = discover_article_urls()
        log('全URL収集完了: %d件' % len(article_urls))

        food_urls = []
        skip_urls = []
        pending_urls = []
        for url in article_urls:
            slug = url.split('/')[-1] if not url.endswith('/') else url.split('/')[-2]
            result = is_food_article(slug)
            if result is True:
                food_urls.append(url)
            elif result is False:
                skip_urls.append(url)
            else:
                pending_urls.append(url)

        for url in pending_urls:
            html = fetch_html(url, delay=0.5)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                og = soup.find('meta', property='og:title')
                title = og['content'] if og else ''
                result = is_food_article(title)
                if result is not False:
                    food_urls.append(url)
            else:
                food_urls.append(url)

        log('食事関連URL: %d件 / スキップ: %d件' % (len(food_urls), len(skip_urls)))
        target_urls = food_urls
    elif args.urls:
        target_urls = args.urls
    else:
        parser.error('--auto-discover か --urls を指定してください')
        return

    all_shops = []
    seen_names = set(existing_names)

    for i, url in enumerate(target_urls):
        log('[%d/%d] %s' % (i + 1, len(target_urls), url))
        shops = scrape_article(url, existing_names=seen_names)
        for s in shops:
            if s['name'] not in seen_names:
                all_shops.append(s)
                seen_names.add(s['name'])
                log('  + %s (%s)' % (s['name'], s.get('address', '')[:40]))
        if not shops:
            log('  店舗なし')

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)
    log('完了: %d件 → %s' % (len(all_shops), args.output))


if __name__ == '__main__':
    main()
