#!/usr/bin/env python3
"""
scrape_oshikatsu_time.py
oshikatsu-time.com の timelesz グルメ記事をスクレイピング
出力: scripts/scraped_oshikatsu_time_timelesz.json

使い方:
  # 従来通りTARGET_ARTICLESのみ処理
  python scripts/scrape_oshikatsu_time.py

  # カテゴリページを自動巡回して新規記事も処理
  python scripts/scrape_oshikatsu_time.py --auto-discover

  # 出力ファイルを指定
  python scripts/scrape_oshikatsu_time.py --auto-discover --output /tmp/scraped.json
"""

import urllib.request
import json
import re
import time
import argparse
from bs4 import BeautifulSoup

GROUP   = 'timelesz'
MEMBERS = ['菊池風磨', '佐藤勝利', '松島聡', '寺西拓人', '原嘉孝',
           '橋本将生', '猪俣周杜', '篠塚大輝', '山下智久']

CATEGORY_URL = 'https://oshikatsu-time.com/category/artist/timelesz/'

# URLスラッグに含まれると食グルメ記事と判定するキーワード
FOOD_URL_KEYWORDS = [
    'location-food', 'cafe', 'coffee', 'gourmet', 'burger',
    'bread', 'pudding', 'gyoza', 'mala', 'udon', 'crepe', 'menu',
    'ramen', 'pizza', 'yakiniku', 'sushi', 'food', 'brunch',
    'restaurant', 'matome', 'tea', 'viking', 'buffet',
    'akafuku', 'hamburg',
]
# URLスラッグに含まれると食グルメ外と判定するキーワード（優先）
NONFOOD_URL_KEYWORDS = [
    'recipe', 'mbti', 'drama', 'movie', 'uranai', 'amazon', 'sale',
    'goods', 'lip', 'ambassador', 'sauna', 'bowling', 'tailor', 'abcmart',
    'keyring', 'bag', 'kiehls', 'disney-goods', 'intro-quiz', 'sokkuri',
    'halloween', 'profile', 'lyric', 'choreo',
    'rakuten', 'earphone', 'comic', 'manga', 'chabos',
    # 買い物番組(食以外)、MVロケ地(住所なし多い)、インスタ投稿(製品名)は除外
    'kaimonotatsujin', 'shanairenai', 'instagram',
    # スイーツ/お菓子系インスタ記事は製品名しか取れない
    'sweets', 'ice-cream', 'hokkaido',
]

PREF_KEYWORDS = [
    '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県',
    '茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
    '新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県',
    '静岡県','愛知県','三重県','滋賀県','京都府','大阪府','兵庫県',
    '奈良県','和歌山県','鳥取県','島根県','岡山県','広島県','山口県',
    '徳島県','香川県','愛媛県','高知県','福岡県','佐賀県','長崎県',
    '熊本県','大分県','宮崎県','鹿児島県','沖縄県',
]

GENRE_MAP = [
    (['ラーメン', '中華そば', '冷麺', 'つけめん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'カルビ', 'ホルモン'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', 'ベーカリー', 'パン', 'クレープ', 'スイーツ', 'ケーキ', 'プリン'], 'カフェ'),
    (['うどん', 'そば', 'SOBA'], 'ラーメン'),
    (['ハンバーガー', 'バーガー', 'Burger'], '食事'),
    (['ハンバーグ'], '食事'),
    (['餃子', 'ギョーザ', '中華', '麻婆', '麻辣', '火鍋'], '中華'),
    (['海鮮', '寿司', 'うに', 'ウニ', '海老', 'カニ', '刺身'], '寿司'),
    (['うなぎ', 'ウナギ'], '和食'),
    (['居酒屋', 'バー', '焼き鳥', '焼鳥'], '居酒屋'),
    (['しゃぶしゃぶ', 'すき焼き'], '食事'),
    (['ステーキ', '肉'], '焼肉'),
]

def is_food_url(url: str) -> bool:
    """URLが食グルメ記事候補かを判定"""
    slug = url.rstrip('/').split('/')[-1]
    if any(ng in slug for ng in NONFOOD_URL_KEYWORDS):
        return False
    return any(kw in slug for kw in FOOD_URL_KEYWORDS)


def url_to_meta(url: str) -> dict:
    """URLから記事メタ情報を生成"""
    slug = url.rstrip('/').split('/')[-1]

    # 日付: YYYYMMDD or YYMMDD パターン
    date_m = re.search(r'(\d{4})(\d{2})(\d{2})', slug)
    visited_date = f'{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}' if date_m else None

    # メンバー名: URLスラッグから推測
    member_map = {
        'kikuchifuma': '菊池風磨',
        'satoshori': '佐藤勝利',
        'satoshouri': '佐藤勝利',
        'matsushimaso': '松島聡',
        'teranishitakuto': '寺西拓人',
        'harayoshitaka': '原嘉孝',
        'hashimotomasaki': '橋本将生',
        'inomatashuto': '猪俣周杜',
        'shinozukataiki': '篠塚大輝',
        'yamashitatomohisa': '山下智久',
    }
    members = [v for k, v in member_map.items() if k in slug]

    return {
        'url': url,
        'source_title': slug.replace('-', ' '),
        'default_members': members,
        'visited_date': visited_date,
    }


def discover_articles(existing_source_urls: set) -> list:
    """カテゴリページを巡回して未処理の食グルメ記事URLを発見する"""
    found = []
    for page in range(1, 15):
        if page == 1:
            url = CATEGORY_URL
        else:
            url = f'{CATEGORY_URL}page/{page}/'
        try:
            html = fetch(url)
        except Exception as e:
            print(f'  カテゴリpage {page}: {e}')
            break

        articles = re.findall(
            r'href="(https://oshikatsu-time\.com/timelesz[^"]+)"', html
        )
        articles = list(dict.fromkeys(articles))
        new_in_page = 0
        for a in articles:
            a = a.rstrip('/')  + '/'
            if a in existing_source_urls:
                continue
            if not is_food_url(a):
                continue
            found.append(url_to_meta(a))
            new_in_page += 1

        print(f'  カテゴリpage {page}: {len(articles)}件中 新規食グルメ候補 {new_in_page}件')

        # 次ページが存在するか確認
        if 'next' not in html.lower() and f'page/{page+1}/' not in html:
            break
        time.sleep(0.5)

    return found


# スクレイピング対象記事（手動追加分）
TARGET_ARTICLES = [
    {
        'url': 'https://oshikatsu-time.com/timelesz-matsushimaso-cafe-matome/',
        'source_title': '松島聡 カフェ巡りまとめ（インスタ）',
        'default_members': ['松島聡'],
        'visited_date': None,
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-timeleszman-datsurakutabi-location-food/',
        'source_title': 'タイムレスマン ゴールデン特番「東海道中！脱落旅」',
        'default_members': [],
        'visited_date': None,
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-timeleszman-are-you-hungry-man-location-food/',
        'source_title': 'タイムレスマン「アーユーハングリーマン」',
        'default_members': ['松島聡', '橋本将生', '猪俣周杜', '篠塚大輝'],
        'visited_date': None,
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-aiba-marubatsubu-20250927-udon/',
        'source_title': '相葉◎×部（2025年9月27日）',
        'default_members': ['松島聡'],
        'visited_date': '2025-09-27',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-harayoshitaka-ninosan-20250912-location-mala/',
        'source_title': 'ニノさん 高田馬場麻辣グルメ（2025年9月12日）',
        'default_members': ['原嘉孝', '菊池風磨', '寺西拓人', '篠塚大輝'],
        'visited_date': '2025-09-12',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-teranishitakuto-hamburger/',
        'source_title': '寺西拓人 ハンバーガーまとめ',
        'default_members': ['寺西拓人'],
        'visited_date': None,
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-matsushimaso-furusatotimecapsule-20250629-hokkaido-menu/',
        'source_title': 'ふるさとタイムレスカプセル 北海道・稚内（2025年6月29日）',
        'default_members': ['松島聡'],
        'visited_date': '2025-06-29',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-harayoshitaka-ninosan-20250622-location-gyoza/',
        'source_title': 'ニノさん 神保町餃子ベスト3（2025年6月22日）',
        'default_members': ['原嘉孝', '菊池風磨'],
        'visited_date': '2025-06-22',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-hashimotomasaki-shinozukataiki-kamaigachi-20250615-location-food/',
        'source_title': 'かまいガチ 焼肉・中目黒食べ歩き（2025年6月15日）',
        'default_members': ['橋本将生', '篠塚大輝'],
        'visited_date': '2025-06-15',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-hashimotomasaki-inomatashuto-shinozukataiki-mezamashitv-20250603-kawagoe-location-food/',
        'source_title': 'めざましテレビ 川越ロケ（2025年6月3日）',
        'default_members': ['橋本将生', '猪俣周杜', '篠塚大輝'],
        'visited_date': '2025-06-03',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-aiba-marubatsubu-20250524-cafe/',
        'source_title': '相葉◎×部 喫茶店ロケ（2025年5月24日）',
        'default_members': ['原嘉孝'],
        'visited_date': '2025-05-24',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-inomatashuto-chantoyarerukana-20250518-atami-location-food/',
        'source_title': 'ちゃんとやれるかな？ 熱海ロケ（2025年5月18日）',
        'default_members': ['猪俣周杜'],
        'visited_date': '2025-05-18',
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-timelsznojikandesuyo-shinozukataiki-crepe-kitty/',
        'source_title': 'タイムレスの時間ですよ マリオンクレープ',
        'default_members': ['篠塚大輝'],
        'visited_date': None,
    },
    {
        'url': 'https://oshikatsu-time.com/timelesz-timeleszman-nitakuman-bread/',
        'source_title': 'タイムレスマン「2択マン」表参道モニカ',
        'default_members': [],
        'visited_date': None,
    },
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept-Language': 'ja,en;q=0.9',
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8', errors='replace')


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(k in text for k in keywords):
            return genre
    return '食事'


def extract_prefecture(text):
    for p in PREF_KEYWORDS:
        if p in text:
            return p
    return '東京都'


def extract_members_from_text(text):
    return [m for m in MEMBERS if m in text]


def clean_shop_name(raw):
    """H3テキストから店名を抽出"""
    # 第N位：メニュー（店名）パターン → 括弧内の店名を優先
    rank_bracket = re.match(r'^第\d+位[：:][^（(]*[（(]([^）)]+)[）)]', raw)
    if rank_bracket:
        return rank_bracket.group(1).strip()
    # 第N位：店名 パターン → 「第N位：」を除去
    raw = re.sub(r'^第\d+位[：:]\s*', '', raw)
    # 【エリア】プレフィックスを除去（先に除去してからNo.を処理）
    raw = re.sub(r'^【[^】]*】\s*', '', raw)
    # No.N などの番号プレフィックスを除去
    raw = re.sub(r'^No\.\d+\s*', '', raw, flags=re.IGNORECASE)
    # （サブ名・ルビ）を除去
    raw = re.sub(r'（[^）]*）', '', raw)
    raw = re.sub(r'\([^)]*\)', '', raw)
    # 余分な空白・記号を除去
    raw = raw.strip('　 \n\t・／/①②③④⑤⑥⑦⑧⑨⑩')
    return raw.strip()


def is_likely_shop_name(text):
    """H3テキストが店名らしいか判定"""
    if len(text) < 2 or len(text) > 50:
        return False
    # グルメ以外のキーワードを除外
    ng_words = ['まとめ', 'レシピ', 'とは', '意味', 'ランキング', 'プロフィール',
                'インスタ', 'アカウント', 'モデル', '衣装', 'ドラマ', '映画',
                'ライブ', 'アルバム', '公式', 'ツアー', '結果', '詳細',
                '注文', '店舗情報', '場所', '口コミ', 'アクセス', '営業時間',
                '神社', '神宮', '寺院', '温泉', '商店街', 'スタジアム',
                'GYM', 'ジム', 'スポーツ', 'アクアパーク', 'カプセル',
                '◎×部', 'の湯', '平和通り', '時の鐘', 'リゾナーレ',
                '橋', '公園', '広場', 'ハングリー', '北壁', '商店街',
                '温泉', '神社', '神宮', '寺', 'ゆらゆら',
                # 食品以外の物販ショップ
                'ナイフセンター', 'プロナイフ', 'HENCKELS', 'ジョーマローン',
                '香水', 'フレグランス', 'コスメ', '化粧品', 'スキンケア',
                'ちゃぼす', 'ハラハラ',
                # 製品名・キーワードがそのまま店名になるパターン
                '詰合せ', '季節限定', 'ルイボス', '個入', '個詰',
                # 帽子・服飾・雑貨
                'THE CAP', 'CAP TOKYO',
                # 複数ワードが入った商品名
                'ソフトクリーム', 'アイスクリーム', 'メロンソフト',
                ]
    if any(w in text for w in ng_words):
        return False
    # 「〇〇駅」は鉄道駅
    if re.search(r'.駅$', text):
        return False
    # 番号+択 (「2択マン」など)
    if re.search(r'\d+択', text):
        return False
    return True


def extract_shop_from_h2_article(content, article_meta):
    """H3がない記事（H2構造）から店舗情報を抽出"""
    url           = article_meta['url']
    source_title  = article_meta['source_title']
    default_members = article_meta['default_members']
    visited_date  = article_meta['visited_date']

    shops = []

    for h2 in content.find_all('h2'):
        h2_text = h2.get_text().strip()
        if any(w in h2_text for w in ['まとめ', 'エピソード', '関連', '感想', 'プロフィール',
                                        'メニュー', '登場', '出演', '料金', '予約', '口コミ']):
            continue

        members    = list(default_members)
        menu_items = []
        address    = ''
        genre_hint = h2_text
        shop_name  = ''

        # H2直後要素を走査してp/divを先に確認し店名を取得
        sibling_texts = []
        for sib in h2.next_siblings:
            if hasattr(sib, 'name') and sib.name == 'h2':
                break
            if not hasattr(sib, 'name') or sib.name is None:
                continue
            sibling_texts.append(sib)

        # pタグのテキストから先に「店名」を探す（番組名誤検出を防ぐ）
        # 各p内の全候補をチェックして最初にOKなものを採用
        for sib in sibling_texts:
            if sib.name == 'p':
                sib_text = sib.get_text()
                for m in re.finditer(r'[「『]([^」』]{2,50})[」』]', sib_text):
                    candidate = clean_shop_name(m.group(1).strip())
                    if is_likely_shop_name(candidate):
                        shop_name = candidate
                        break
                if shop_name:
                    break

        # pで見つからなければH2テキストから補完
        if not shop_name:
            m = re.search(r'[「『]([^」』]{2,50})[」』]', h2_text)
            if m:
                candidate = clean_shop_name(m.group(1).strip())
                if is_likely_shop_name(candidate):
                    shop_name = candidate

        # 各兄弟要素から住所・メニュー・メンバーを抽出
        for sib in sibling_texts:
            sib_text = sib.get_text()

            # p / div から「店名」を補完（まだ未取得の場合）
            if not shop_name:
                m2 = re.search(r'[「『]([^」』]{2,50})[」』]', sib_text)
                if m2:
                    candidate = clean_shop_name(m2.group(1).strip())
                    if is_likely_shop_name(candidate):
                        shop_name = candidate

            # 住所（〒番号がある場合のみ採用 — 説明文の都道府県名誤検出を防ぐ）
            if not address and '〒' in sib_text:
                addr_m = re.search(r'(〒\d{3}-\d{4}[^\n]*)', sib_text)
                if addr_m:
                    address = addr_m.group(1).strip()

            # メンバー
            found = extract_members_from_text(sib_text)
            if found:
                members = list(set(members + found))

            # メニュー（strong/b）
            for tag in sib.find_all(['strong', 'b']):
                item = tag.get_text().strip()
                if (item and 2 <= len(item) < 40 and item not in menu_items
                        and not any(ng in item for ng in ['出典', 'http', '©', '参考'])):
                    menu_items.append(item)

            genre_hint += ' ' + sib_text[:100]

        if not shop_name or not is_likely_shop_name(shop_name):
            continue

        prefecture = extract_prefecture(address) if address else '東京都'
        genre = detect_genre(genre_hint)

        vis_date = visited_date
        if not vis_date:
            date_m = re.search(r'(\d{4})(\d{2})(\d{2})', url)
            if date_m:
                vis_date = f'{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}'

        shops.append({
            'name':               shop_name,
            'genre':              genre,
            'prefecture':         prefecture,
            'address':            address,
            'visited_date':       vis_date or '',
            'members':            members,
            'groups':             [GROUP],
            'group':              GROUP,
            'source_video_title': source_title,
            'source_url':         url,
            'ordered_items':      menu_items,
        })

    return shops


def parse_article(article_meta):
    url           = article_meta['url']
    source_title  = article_meta['source_title']
    default_members = article_meta['default_members']
    visited_date  = article_meta['visited_date']

    print(f'  取得中: {url}')
    try:
        html = fetch(url)
    except Exception as e:
        print(f'  ERROR: {e}')
        return []

    soup = BeautifulSoup(html, 'html.parser')

    # 記事タイトル（h1）
    h1 = soup.find('h1')
    article_title = h1.get_text().strip() if h1 else source_title

    # 本文エリアを特定
    content = soup.find('article') or soup.find('div', class_=re.compile(r'content|entry|post'))
    if not content:
        content = soup

    shops = []

    # H3要素を全て取得して店舗候補を探す
    for h3 in content.find_all('h3'):
        raw_text = h3.get_text().strip()
        shop_name = clean_shop_name(raw_text)

        if not is_likely_shop_name(shop_name):
            continue

        # H3直後の要素を解析
        members    = list(default_members)
        menu_items = []
        address    = ''
        prefecture = ''
        genre_hint = shop_name + ' ' + raw_text

        # H3テキスト内のメンバー抽出
        found_in_h3 = extract_members_from_text(raw_text)
        if found_in_h3:
            members = list(set(members + found_in_h3))

        # 直後の兄弟要素を走査
        for sib in h3.next_siblings:
            if sib.name in ['h2', 'h3']:
                break

            if not hasattr(sib, 'name') or sib.name is None:
                continue

            sib_text = sib.get_text()

            # H4：店舗情報セクション
            if sib.name == 'h4':
                h4_text = sib.get_text()
                if '店舗情報' in h4_text or '場所' in h4_text:
                    # 直後のul/ol または div を取得
                    next_el = sib.find_next_sibling(['ul', 'ol', 'div'])
                    if next_el:
                        el_text = next_el.get_text()
                        addr_m = re.search(r'(〒\d{3}-\d{4}[^\n]*)', el_text)
                        if addr_m:
                            address = addr_m.group(1).strip()
                        else:
                            for li in next_el.find_all('li'):
                                li_text = li.get_text()
                                if '〒' in li_text or any(p in li_text for p in PREF_KEYWORDS):
                                    address = li_text.strip()
                                    break
                                if '住所' in li_text:
                                    address = li_text.replace('住所', '').strip(' ：:')
                                    break

            # P：メニュー（strongタグ）・メンバー・住所
            if sib.name == 'p':
                # メンバー抽出
                found = extract_members_from_text(sib_text)
                if found:
                    members = list(set(members + found))

                # メニュー（strong/b）
                for tag in sib.find_all(['strong', 'b']):
                    item = tag.get_text().strip()
                    if (item and len(item) > 1 and len(item) < 40
                            and item not in menu_items
                            and not any(ng in item for ng in ['出典', 'http', '©', '参考', '詳細'])):
                        menu_items.append(item)

                # 住所の補足
                if not address:
                    addr_m = re.search(r'(〒\d{3}-\d{4}[^\n。]*)', sib_text)
                    if addr_m:
                        address = addr_m.group(1).strip()
                    elif any(p in sib_text for p in PREF_KEYWORDS):
                        for p in PREF_KEYWORDS:
                            if p in sib_text:
                                addr_m2 = re.search(rf'({re.escape(p)}[^\n。]{{3,30}})', sib_text)
                                if addr_m2:
                                    address = addr_m2.group(1).strip()
                                break

                genre_hint += ' ' + sib_text[:100]

            # DIV：住所情報が入っていることがある
            if sib.name == 'div' and not address:
                div_text = sib_text
                addr_m = re.search(r'(〒\d{3}-\d{4}[^\n]*)', div_text)
                if addr_m:
                    address = addr_m.group(1).strip()

            # UL：リスト形式の店舗情報
            if sib.name in ['ul', 'ol']:
                for li in sib.find_all('li'):
                    li_text = li.get_text()
                    if '〒' in li_text or any(p in li_text for p in PREF_KEYWORDS):
                        if not address:
                            address = li_text.strip()

        # 都道府県を住所から抽出
        if address:
            prefecture = extract_prefecture(address)
        else:
            prefecture = '東京都'

        genre = detect_genre(genre_hint)

        # 日付が未設定の場合URLから推測
        vis_date = visited_date
        if not vis_date:
            date_m = re.search(r'(\d{4})(\d{2})(\d{2})', url)
            if date_m:
                vis_date = f'{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}'

        shops.append({
            'name':               shop_name,
            'genre':              genre,
            'prefecture':         prefecture,
            'address':            address,
            'visited_date':       vis_date or '',
            'members':            members,
            'groups':             [GROUP],
            'group':              GROUP,
            'source_video_title': source_title,
            'source_url':         url,
            'ordered_items':      menu_items,
        })

    # H3が0件の場合はH2構造の記事としてパース
    if not shops:
        shops = extract_shop_from_h2_article(content, article_meta)

    print(f'    → {len(shops)}件取得')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto-discover', action='store_true',
                        help='カテゴリページを巡回して新規記事を自動発見する')
    parser.add_argument('--output', default='scripts/scraped_oshikatsu_time_timelesz.json',
                        help='出力ファイルパス')
    parser.add_argument('--skip-existing', action='store_true',
                        help='既存shops.jsonのsource_urlをスキップ')
    args = parser.parse_args()

    articles_to_process = list(TARGET_ARTICLES)

    if args.auto_discover or args.skip_existing:
        # 既存データのsource_urlを取得
        existing_source_urls = set()
        try:
            with open('data/shops.json', encoding='utf-8') as f:
                existing = json.load(f)
            existing_source_urls = {s.get('source_url', '').rstrip('/') + '/' for s in existing if s.get('source_url')}
            print(f'既存shops.json: {len(existing)}件, source_url: {len(existing_source_urls)}件')
        except Exception as e:
            print(f'shops.json読み込みエラー: {e}')

        if args.auto_discover:
            print('\nカテゴリページ自動巡回...')
            discovered = discover_articles(existing_source_urls)
            print(f'新規記事発見: {len(discovered)}件')
            # TARGET_ARTICLESのうち既存URLをスキップ
            articles_to_process = [
                a for a in TARGET_ARTICLES
                if a['url'].rstrip('/') + '/' not in existing_source_urls
            ] + discovered
        elif args.skip_existing:
            articles_to_process = [
                a for a in TARGET_ARTICLES
                if a['url'].rstrip('/') + '/' not in existing_source_urls
            ]

    # URL重複除去（TARGET_ARTICLESと自動発見で同一URLが入ることがある）
    seen_urls = set()
    dedup_articles = []
    for a in articles_to_process:
        u = a['url'].rstrip('/') + '/'
        if u not in seen_urls:
            seen_urls.add(u)
            dedup_articles.append(a)
    articles_to_process = dedup_articles

    print(f'\n処理対象: {len(articles_to_process)}件\n')

    all_shops = []
    for meta in articles_to_process:
        shops = parse_article(meta)
        all_shops.extend(shops)
        time.sleep(1.5)

    # 重複除去（同名・同グループ）
    seen = set()
    deduped = []
    for s in all_shops:
        key = s['name'].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print(f'\n合計 {len(deduped)}件 → {args.output}')
    for s in deduped:
        print(f"  {s['name'][:25]:25} {s['prefecture']:5} {s.get('visited_date',''):10} {s['source_video_title'][:30]}")


if __name__ == '__main__':
    main()
