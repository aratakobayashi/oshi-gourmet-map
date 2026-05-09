"""
scrape_naniwa.py
なにわ男子ロケ地まとめページから店舗情報をスクレイピング

対応ソース:
  - illmnt.com  : h2形式、TV番組ロケ地
  - hatenablog  : table形式、YouTube(なにわチューブ)ロケ地
                  食べログ・ホットペッパーの直URLをValueCommerceアフィリ経由で取得

使い方:
  python scripts/scrape_naniwa.py \\
    --urls https://www.illmnt.com/posts/0000049 \\
           https://8888-info.hatenablog.com/entry/%E3%81%AA%E3%81%AB%E3%82%8Ftube \\
    --output scripts/scraped_naniwa.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
from bs4 import BeautifulSoup

GROUP = 'naniwa'
MEMBERS = ['大西流星', '道枝駿佑', '高橋恭平', '長尾謙杜', '西畑大吾', '藤原丈一郎', '大橋和也']

# メンバー名の表記ゆれ → 正規名に変換
MEMBER_ALIASES = {
    '大西くん': '大西流星',
    '流星くん': '大西流星',
    '道枝くん': '道枝駿佑',
    'みちえだくん': '道枝駿佑',
    '高橋くん': '高橋恭平',
    '恭平くん': '高橋恭平',
    '長尾くん': '長尾謙杜',
    'けんとくん': '長尾謙杜',
    '西畑くん': '西畑大吾',
    'だいごくん': '西畑大吾',
    '藤原くん': '藤原丈一郎',
    'じょいくん': '藤原丈一郎',
    '大橋くん': '大橋和也',
    'かずやくん': '大橋和也',
}

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん', 'そうめん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', '肉', 'BBQ', 'バーベキュー'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'coffee', 'ベーカリー', 'パン', 'トースト'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'パティスリー', 'チョコ'], 'スイーツ'),
    (['居酒屋', 'バー', '酒'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['ハンバーガー', 'バーガー'], '食事'),
]


def make_tabelog_url(name):
    return 'https://tabelog.com/rstLst/?vs=1&sa=&sk=' + urllib.parse.quote(name)


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def extract_date(text):
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return ''


def extract_member(text):
    for alias, name in MEMBER_ALIASES.items():
        if alias in text:
            return name
    for name in MEMBERS:
        if name in text:
            return name
    return ''


def extract_address(info_text):
    """＜店舗情報＞ブロックから住所を抽出"""
    m = re.search(r'住所[：:]\s*(.+?)(?:\n|アクセス|TEL|電話|$)', info_text)
    if m:
        return m.group(1).strip()
    return ''


def extract_vc_url(href):
    """ValueCommerceアフィリエイトリンクから実URLを取得"""
    m = re.search(r'vc_url=([^&]+)', href)
    if m:
        return urllib.parse.unquote(m.group(1))
    return ''


def scrape_hatenablog(url, soup):
    """8888-info.hatenablog.com 形式のスクレイピング（table構造）"""
    shops = []
    tables = soup.find_all('table')

    # h3から年を特定するマップを作る
    year_map = {}
    for h3 in soup.find_all('h3'):
        y_m = re.search(r'(\d{4})年', h3.get_text())
        if y_m:
            year = y_m.group(1)
            # このh3以降のtableに年を対応付け
            for sib in h3.next_siblings:
                if not hasattr(sib, 'name') or not sib.name:
                    continue
                if sib.name == 'h3':
                    break
                if sib.name == 'table':
                    year_map[id(sib)] = year

    for table in tables:
        text = table.get_text(separator='\n', strip=True)

        # 店名: 【店名】
        name_m = re.search(r'【(.+?)】', text)
        if not name_m:
            continue
        shop_name = name_m.group(1).strip()

        # 日付: XX月XX日配信
        date_m = re.search(r'(\d+)月(\d+)日配信', text)
        year = year_map.get(id(table), '2024')
        if date_m:
            visited_date = f'{year}-{int(date_m.group(1)):02d}-{int(date_m.group(2)):02d}'
        else:
            continue

        # 住所: 【住所】の後の〒XXX-XXXXと住所行
        addr_m = re.search(r'〒(\d{3}-\d{4})\s*\n?(.+?)(?:\n☎|\n【|$)', text, re.DOTALL)
        if addr_m:
            address = addr_m.group(2).replace('\n', '').strip()
            # ビル名・階数が次行にある場合は結合済みなのでそのまま
        else:
            address = ''

        # 都道府県をヘッダー行から取得: XX月XX日配信／東京都渋谷区
        area_m = re.search(r'配信／(.+)', text)
        area_hint = area_m.group(1).strip() if area_m else ''

        # アフィリエイトリンクからtabelog/hotpepper URL取得
        tabelog_url = ''
        hotpepper_url = ''
        for a in table.find_all('a'):
            label = a.get_text(strip=True)
            href = a.get('href', '')
            actual_url = extract_vc_url(href)
            if '食べログ' in label and actual_url:
                tabelog_url = actual_url
            elif 'ホットペッパー' in label and actual_url:
                hotpepper_url = actual_url

        # 食べログURLがなければ検索URLで代用
        if not tabelog_url:
            tabelog_url = make_tabelog_url(shop_name)

        genre = detect_genre(shop_name + area_hint)

        affiliate_links = [{'label': '食べログで見る', 'url': tabelog_url}]
        if hotpepper_url:
            affiliate_links.append({'label': 'ホットペッパーで予約', 'url': hotpepper_url})

        shops.append({
            'name': shop_name,
            'visited_date': visited_date,
            'description': '',
            'genre': genre,
            'group': GROUP,
            'groups': [GROUP],
            'members': [],
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': '',
            'source_video_url': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': hotpepper_url,
            'affiliate_links': affiliate_links,
        })

    return shops


def scrape_page(url):
    print(f'取得中: {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    # ソース判定
    if 'hatenablog' in url:
        shops = scrape_hatenablog(url, soup)
        print(f'  → {len(shops)}件取得')
        return shops

    shops = []
    h2s = soup.find_all('h2', class_='post-element-h2')

    for h2 in h2s:
        raw_name = h2.get_text(strip=True)

        # ページヘッダー・フッターのh2は除外（店名｜地域 形式でないもの）
        if '｜' not in raw_name and 'まとめ' in raw_name:
            continue
        if '｜' in raw_name:
            shop_name = raw_name.split('｜')[0].strip()
        else:
            shop_name = raw_name.strip()

        # h2直後のp要素を収集
        paras = []
        for sib in h2.next_siblings:
            if not hasattr(sib, 'name') or not sib.name:
                continue
            if sib.name == 'h2':
                break
            if sib.name == 'p':
                paras.append(sib.get_text(separator='\n', strip=True))

        if not paras:
            continue

        desc_text = paras[0] if len(paras) > 0 else ''
        info_text = paras[1] if len(paras) > 1 else ''

        visited_date = extract_date(desc_text)
        if not visited_date:
            continue  # 日付がないのは記事の導入・まとめ文

        member = extract_member(desc_text)
        address = extract_address(info_text)
        genre = detect_genre(shop_name + desc_text)
        tabelog_url = make_tabelog_url(shop_name)

        desc_clean = re.sub(r'\s+', ' ', desc_text).strip()

        shops.append({
            'name': shop_name,
            'visited_date': visited_date,
            'description': desc_clean,
            'genre': genre,
            'group': GROUP,
            'groups': [GROUP],
            'members': [member] if member else [],
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': '',
            'source_video_url': '',
            'tabelog_url': tabelog_url,
            'affiliate_links': [
                {'label': '食べログで見る', 'url': tabelog_url}
            ],
        })

    print(f'  → {len(shops)}件取得')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--output', default='scripts/scraped_naniwa.json')
    args = parser.parse_args()

    all_shops = []
    for url in args.urls:
        all_shops.extend(scrape_page(url))

    # 重複除去（同名店舗）
    seen = set()
    unique = []
    for s in all_shops:
        key = s['name']
        if key not in seen:
            seen.add(key)
            unique.append(s)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(unique)}件（重複除去後）')
    print(f'→ {args.output} に保存しました')
    print(f'\nyoutube_id未設定: {len([s for s in unique if not s["youtube_id"]])}件')
    print('次のステップ: YouTube動画一覧取得後に match_videos.py で紐付け')


if __name__ == '__main__':
    main()
