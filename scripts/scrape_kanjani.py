#!/usr/bin/env python3
"""
scrape_kanjani.py
ameblo.jp/yocorino-caputino の関ジャニ∞ロケ地巡り記事から飲食店データを収集

使い方:
  python scripts/scrape_kanjani.py --output scripts/scraped_kanjani.json
  python scripts/scrape_kanjani.py --dry-run
"""

import urllib.request
import json
import re
import time
import argparse
from bs4 import BeautifulSoup

GROUP = 'kanjani'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

MEMBERS_ALL = ['大倉忠義', '丸山隆平', '村上信五', '横山裕', '安田章大', '錦戸亮', '渋谷すばる']
MEMBER_NICK = {
    '大倉': '大倉忠義', 'ツッコミ': '大倉忠義',
    '丸山': '丸山隆平', 'まるちゃん': '丸山隆平',
    '村上': '村上信五', 'ムラ': '村上信五',
    '横山': '横山裕', 'ヨコ': '横山裕',
    '安田': '安田章大', 'やすくん': '安田章大', 'やっさん': '安田章大',
    '錦戸': '錦戸亮', '亮ちゃん': '錦戸亮', 'にしきん': '錦戸亮',
    'すばる': '渋谷すばる', 'すばるくん': '渋谷すばる',
}

# 番組名パターン
SHOW_PATTERNS = [
    'エイトブンノニ', '8/2', 'newsおかえり', 'ニュースおかえり',
    '関ジャム', 'ジャにのちゃんねる', 'WESTv.', '関ジャニ',
]

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん', '中華そば'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', 'サムギョプサル', 'カルビ'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'すし'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン', 'かき氷', '喫茶', '珈琲'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'パンケーキ', 'クレープ', 'アイス', 'かき氷'], 'スイーツ'),
    (['居酒屋', 'バー', '酒場', '焼き鳥', '串'], '居酒屋'),
    (['お好み焼き', 'もんじゃ', 'たこ焼き'], '食事'),
    (['カレー', 'インド', 'タイ', 'アジア'], '食事'),
    (['中華', '点心', '餃子', '飲茶', '担々麺'], '中華'),
    (['フレンチ', 'フランス', 'ビストロ'], '食事'),
    (['イタリアン', 'パスタ', 'ピザ'], '食事'),
    (['海鮮', '刺身', '天ぷら', '和食', '割烹', '料亭', 'うなぎ', '鰻'], '食事'),
    (['とんかつ', 'ハンバーグ', '洋食', 'ビーフ', '牛肉'], '食事'),
]

PREFECTURES = [
    '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
    '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
    '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
    '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
    '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
    '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
    '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]

# amebloのテーマページから取得できた記事エントリID一覧（73件中20件）
ENTRY_IDS = [
    '12960598429',  # 布施商店街〜俊徳道･布施ぶらり③〜
    '12960524792',  # 俊徳道駅〜俊徳道･布施ぶらり②〜
    '12960510668',  # ツナグ茶房〜俊徳道･布施ぶらり①〜
    '12560728048',  # 鉄板呑み屋ブッチャー@堀江∞
    '12543522925',  # ユニバ★ロケ地巡り②
    '12527305957',  # スカイツリー&ソラマチ∞ロケ地
    '12525585549',  # はちまき∞神保町ロケ地
    '12525585244',  # 神保町∞ロケ地巡り
    '12524430683',  # 銀座∞ロケ地
    '12524656190',  # 谷中銀座∞
    '12524064320',  # ひみつ堂∞
    '12510183886',  # お好み焼き∞たまちゃんviva!∞
    '12503807640',  # ShinShin@住吉店∞
    '12494981250',  # 若駒∞～札幌⑤★3日目～
    '12494980523',  # RAMAI&八鉱学園∞～札幌③★2日目～
    '12484971783',  # コロンボ.関テレ〜大阪∞②〜
    '12483599723',  # タリーズ&ロマン～6/6東京②～
    '12481273784',  # ちばチャン@錦糸町
    '12480560534',  # いづ美･今戸神社@浅草
    '12473329011',  # ラドリオ@神保町
]

# 非食スポットとして除外するキーワード
NON_FOOD_SKIP = ['神社', '神宮', '公園', 'ユニバ', 'USJ', '動物園', '水族館', '美術館', '博物館']


def fetch_html(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'ja,en;q=0.9',
    })
    return urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='replace')


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def extract_members(text):
    found = set()
    for nick, full in MEMBER_NICK.items():
        if nick in text:
            found.add(full)
    return sorted(found)


def extract_show(text):
    for show in SHOW_PATTERNS:
        if show in text:
            return show
    return '関ジャニ∞'


def extract_tabelog_url(html):
    m = re.search(r'https://tabelog\.com/[a-z]+/A\d+/A\d+/\d+/?', html)
    return m.group(0).rstrip('/') + '/' if m else ''


def clean_shop_name(title):
    """記事タイトルから店名を抽出"""
    # "@エリア" パターン: 「店名@エリア∞」→「店名」
    m = re.match(r'^(.+?)[@＠][^〜～\-]+', title)
    if m:
        name = m.group(1).strip()
        return name

    # 「店名∞〜補足〜」パターン
    m = re.match(r'^(.+?)∞', title)
    if m:
        name = m.group(1).strip()
        # 長すぎる・短すぎるは除外
        if 2 <= len(name) <= 30:
            return name

    # 「店名〜補足〜」パターン
    m = re.match(r'^(.+?)[〜～]', title)
    if m:
        name = m.group(1).strip()
        if 2 <= len(name) <= 20:
            return name

    return ''


def extract_area_from_title(title):
    """タイトルからエリアを推定"""
    cities = ['東京', '大阪', '福岡', '札幌', '京都', '神戸', '名古屋', '横浜',
              '堀江', '神保町', '銀座', '浅草', '錦糸町', '谷中', '住吉', '堺',
              '新橋', '渋谷', '新宿', '池袋', '秋葉原', '六本木']
    for city in cities:
        if city in title:
            return city
    return ''


def parse_article(entry_id, dry_run=False):
    url = f'https://ameblo.jp/yocorino-caputino/entry-{entry_id}.html'
    print(f'  [{entry_id}]', end=' ', flush=True)

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, 'html.parser')

        # タイトル取得
        title_el = soup.select_one('h1.skin-entryTitle, .articleTitle, h1[class*="title"]')
        title = title_el.get_text(strip=True) if title_el else ''
        if not title:
            title_el = soup.find('title')
            if title_el:
                title = title_el.text.split('|')[0].strip()

        print(f'「{title[:40]}」', end=' ', flush=True)

        # 非食スポットのスキップ
        for kw in NON_FOOD_SKIP:
            if kw in title:
                print(f'→ スキップ（{kw}）')
                return []

        # 本文テキスト
        body_el = soup.select_one('.articleText, .skin-entryBody, [class*="entryBody"]')
        body = body_el.get_text(separator=' ', strip=True) if body_el else soup.get_text(separator=' ', strip=True)
        body = re.sub(r'\s+', ' ', body)[:3000]

        # 食べログURL
        tabelog_url = extract_tabelog_url(html)

        # 店名候補の抽出
        shop_name = clean_shop_name(title)
        if not shop_name:
            print('→ 店名抽出失敗、スキップ')
            return []

        # エリア
        area = extract_area_from_title(title) or extract_area_from_title(body[:500])

        # 都道府県の推定
        prefecture = ''
        for pref in PREFECTURES:
            if pref in body[:1000] or pref[:-1] in title:
                prefecture = pref
                break
        if not prefecture:
            # エリアから推定
            area_pref = {
                '東京': '東京都', '銀座': '東京都', '浅草': '東京都', '神保町': '東京都',
                '渋谷': '東京都', '新宿': '東京都', '錦糸町': '東京都', '谷中': '東京都',
                '大阪': '大阪府', '堀江': '大阪府', '堺': '大阪府',
                '福岡': '福岡県', '住吉': '福岡県',
                '札幌': '北海道',
                '京都': '京都府',
                '神戸': '兵庫県',
                '横浜': '神奈川県',
            }
            for k, v in area_pref.items():
                if k in title or k in body[:500]:
                    prefecture = v
                    break

        # メンバー
        members = extract_members(body)

        # 番組
        source = extract_show(body)

        # ジャンル
        genre = detect_genre(body + ' ' + shop_name)

        # メニュー（箇条書きや「〇〇を注文」パターン）
        ordered = []
        menu_patterns = re.findall(r'[「『]([^」』]{2,20})[」』]', body)
        for m in menu_patterns[:8]:
            if re.search(r'(定食|ランチ|セット|焼き|揚げ|炒め|煮|鍋|スープ|サラダ|デザート|ケーキ|パン|麺|丼|弁当|カレー|ラーメン|そば|うどん|寿司|刺身|天ぷら|串|餃子|点心|ビール|酒|チーズ)', m):
                ordered.append(m)

        shop = {
            'id': f'kanjani-{re.sub(r"[^a-z0-9]", "-", shop_name.lower().replace(" ", "-"))[:40]}',
            'name': shop_name,
            'group': GROUP,
            'groups': [GROUP],
            'genre': genre,
            'prefecture': prefecture,
            'members': members,
            'source_url': url,
            'source_video_title': f'関ジャニ∞ロケ地巡り - {title}',
            'description': '',
        }
        if tabelog_url:
            shop['tabelog_url'] = tabelog_url
            shop['affiliate_links'] = [{'label': '食べログで見る', 'url': tabelog_url}]
        if ordered:
            shop['ordered_items'] = ordered
        if source:
            shop['source_type'] = 'blog'

        print(f'→ OK ({prefecture} / {genre} / メンバー{len(members)}人)')
        return [shop]

    except Exception as e:
        print(f'→ エラー: {e}')
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kanjani.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print(f'関ジャニ∞ amebloスクレイピング開始 ({len(ENTRY_IDS)}記事)')
    print()

    all_shops = []
    for i, entry_id in enumerate(ENTRY_IDS):
        shops = parse_article(entry_id, dry_run=args.dry_run)
        all_shops.extend(shops)
        if i < len(ENTRY_IDS) - 1:
            time.sleep(2.5)

    print()
    print(f'取得: {len(all_shops)}件')

    if not args.dry_run and all_shops:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(all_shops, f, ensure_ascii=False, indent=2)
        print(f'→ {args.output}')


if __name__ == '__main__':
    main()
