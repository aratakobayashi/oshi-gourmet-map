"""
scrape_nogizaka.py
乃木坂46グルメ聖地まとめブログからお店情報をスクレイピング

対応ソース:
  - senublog.com : h2（店名：地域）+ scroll-box table形式

使い方:
  python scripts/scrape_nogizaka.py \\
    --urls https://senublog.com/nogizaka46-sanctuary-summarize/ \\
    --output scripts/scraped_nogizaka.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
from bs4 import BeautifulSoup

GROUP = 'nogizaka46'
MEMBERS = [
    '秋元真夏', '衛藤美彩', '新内眞衣', '齋藤飛鳥', '松村沙友理',
    '西野七瀬', '桜井玲香', '白石麻衣', '堀未央奈', '生田絵梨花',
    '星野みなみ', '松井玲奈', '橋本奈々未', '若月佑美', '高山一実',
    '川後陽菜', '斉藤優里', '伊藤万理華', '深川麻衣', '大和里菜',
    '中元日芽香', '能條愛未', '大園桃子', '与田祐希', '山下美月',
    '岩本蓮加', '阪口珠美', '北野日奈子', '佐藤楓', '梅澤美波',
    '遠藤さくら', '賀喜遥香', '筒井あやめ', '田村真佑', '矢久保美緒',
    '柴田柚菜', '金川紗耶', '池田瑛紗', '中西アルノ', '五百城茉央',
    '井上和', '一ノ瀬美空', '冨里奈央', '林瑠奈',
    # 愛称・略称
    '飛鳥', 'まいやん', 'まいちゅん', 'いくちゃん', '西野', '桜井',
]

MEMBER_ALIASES = {
    '松井さん': '松井玲奈',
    '星野さん': '星野みなみ',
    '佐藤さん': '佐藤楓',
    '飛鳥さん': '齋藤飛鳥',
    '白石さん': '白石麻衣',
    '生田さん': '生田絵梨花',
}

GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺', 'そば', 'うどん'], 'ラーメン'),
    (['焼肉', '焼き肉', 'ステーキ', '肉', 'BBQ', 'バーベキュー'], '焼肉'),
    (['寿司', '鮨', '回転寿司', 'すし'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'ベーカリー', 'パン', 'トースト', 'めろんぱん'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'かき氷', 'アイス', 'パティスリー', 'チョコ', 'プリン', 'タルト'], 'スイーツ'),
    (['居酒屋', 'バー', '酒'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], 'もんじゃ'),
    (['カレー', 'インド', 'スパイス'], '食事'),
    (['ハンバーガー', 'バーガー'], '食事'),
    (['中華', 'チャイナ', '点心', '飲茶', '餃子'], '中華'),
    (['イタリアン', 'パスタ', 'ピザ', 'リゾット'], '食事'),
    (['焼き鳥', '鶏', '天ぷら'], '和食'),
]


def make_tabelog_url(name):
    return 'https://tabelog.com/rstLst/?vs=1&sa=&sk=' + urllib.parse.quote(name)


def detect_genre(text):
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def extract_members_from_text(text):
    """説明文・メンバーボックスから乃木坂メンバー名を抽出"""
    found = set()
    for alias, name in MEMBER_ALIASES.items():
        if alias in text:
            found.add(name)
    for name in MEMBERS:
        if name in text:
            found.add(name)
    return list(found)


def extract_program(text):
    """『番組名』を抽出"""
    matches = re.findall(r'[『｢「](.*?)[』｣」]', text)
    return matches[0] if matches else ''


def parse_table(scroll_box):
    """scroll-box内のテーブルをラベル:値の辞書に変換"""
    info = {}
    if not scroll_box:
        return info
    table = scroll_box.find('table')
    if not table:
        return info
    for row in table.find_all('tr'):
        tds = row.find_all('td')
        if len(tds) == 2:
            label = tds[0].get_text(strip=True)
            value = tds[1].get_text(separator=' ', strip=True)
            info[label] = value
    return info


def split_prefecture_city(area_text):
    """「東京都渋谷区」→ prefecture='東京都', city='渋谷区'"""
    prefectures = [
        '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
        '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
        '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
        '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
        '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
        '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
        '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
    ]
    for pref in prefectures:
        if area_text.startswith(pref):
            city = area_text[len(pref):].strip()
            return pref, city
    return area_text, ''


def parse_mybox_info(mybox):
    """st-in-mybox の p タグをラベル/値の辞書に変換"""
    info = {}
    ps = [p.get_text(strip=True) for p in mybox.find_all('p') if p.get_text(strip=True)]
    LABELS = {'店名', '住所', '予約・問い合わせ', '問い合わせ', 'お問い合わせ', '予約・お問い合わせ', '電話番号', '営業時間', '定休日', '交通アクセス', '駐車場', 'ホームページ', 'URL'}
    i = 0
    while i < len(ps):
        p = ps[i]
        if p in LABELS and i + 1 < len(ps):
            # collect value lines until next label
            val_lines = []
            j = i + 1
            while j < len(ps) and ps[j] not in LABELS:
                if not ps[j].startswith('>>') and '現在' not in ps[j]:
                    val_lines.append(ps[j])
                j += 1
            info[p] = ' '.join(val_lines)
            i = j
        else:
            i += 1
    return info


def scrape_senublog_individual(url, soup):
    """senublog.com 個別ページ形式: st-in-mybox (p ラベル/値)"""
    myboxes = soup.find_all(class_='st-in-mybox')
    if not myboxes:
        return []

    shops = []
    for mybox in myboxes:
        info = parse_mybox_info(mybox)
        shop_name = info.get('店名', '').strip()
        address = info.get('住所', '').strip()
        # 〒XXX-XXXX を除去し、>>リンクや電話番号も除去
        address = re.sub(r'〒\d{3}-\d{4}\s*', '', address).strip()
        address = re.sub(r'>>[^\s].*', '', address).strip()
        address = re.sub(r'\d{2,4}-\d{3,4}-\d{3,4}.*', '', address).strip()
        nearest = info.get('交通アクセス', '').strip()

        if not shop_name or not address:
            continue

        # ページ全文からメンバー・番組名・説明を抽出
        full_text = soup.get_text(separator=' ', strip=True)
        members = extract_members_from_text(full_text)
        program = extract_program(full_text)

        # 最初の st-kaiwa-hukidashi を説明文として使う
        hukidashi = soup.find(class_='st-kaiwa-hukidashi')
        description = hukidashi.get_text(separator=' ', strip=True) if hukidashi else ''
        description = re.sub(r'\s+', ' ', description).strip()

        prefecture, city = split_prefecture_city(address)
        genre = detect_genre(shop_name + description)
        tabelog_url = make_tabelog_url(shop_name)

        # メンバー重複除去
        full_names = set(m for m in members if len(m) >= 3 and m in MEMBERS)
        members = list(dict.fromkeys(
            m for m in members
            if m in full_names or (m not in full_names and not any(m in n for n in full_names))
        ))

        shops.append({
            'name': shop_name,
            'genre': genre,
            'prefecture': prefecture,
            'city': city,
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': program,
            'source_video_url': '',
            'visited_date': '',
            'members': members,
            'groups': [GROUP],
            'group': GROUP,
            'description': description,
            'nearest_station': nearest,
            'price_range': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': '',
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}],
        })

    return shops


def scrape_senublog(url, soup):
    """senublog.com 形式: h2（店名：地域）+ scroll-box テーブル"""
    shops = []
    h2_tags = soup.find_all('h2')

    for h2 in h2_tags:
        raw = h2.get_text(strip=True)

        # 「店名：地域」形式のh2だけ処理（目次・ヘッダー除外）
        if '：' not in raw and ':' not in raw:
            continue
        # 区切り文字で分割
        sep = '：' if '：' in raw else ':'
        parts = raw.split(sep, 1)
        shop_name_base = parts[0].strip()
        area_raw = parts[1].strip() if len(parts) > 1 else ''

        # 都道府県が複数の場合（例: 東京都千代田区・渋谷区）は最初の都道府県だけ使う
        area_primary = area_raw.split('・')[0].strip()
        prefecture, city = split_prefecture_city(area_primary)

        # h2以降、次のh2までの要素を収集
        siblings = []
        for sib in h2.next_siblings:
            if not hasattr(sib, 'name') or not sib.name:
                continue
            if sib.name == 'h2':
                break
            siblings.append(sib)

        # カイワボックスから説明文・番組名・メンバー抽出
        description = ''
        program = ''
        members = []
        for sib in siblings:
            # 説明文（kaiwa-hukidashi）
            hukidashi = sib.find(class_='st-kaiwa-hukidashi') if hasattr(sib, 'find') else None
            if hukidashi:
                desc_text = hukidashi.get_text(separator=' ', strip=True)
                if not description:
                    description = re.sub(r'\s+', ' ', desc_text).strip()
                if not program:
                    program = extract_program(desc_text)
                members.extend(extract_members_from_text(desc_text))

            # メンバーボックス（来店メンバー / 優勝チームなど）
            if hasattr(sib, 'find_all'):
                for mybox in sib.find_all(class_='st-in-mybox'):
                    box_text = mybox.get_text(separator='・', strip=True)
                    members.extend(extract_members_from_text(box_text))

        # 支店対応: scroll-box が複数ある場合は最初のものを代表住所として使う
        scroll_boxes = [sib for sib in siblings if hasattr(sib, 'get') and sib.get('class') and 'scroll-box' in sib.get('class', [])]
        if not scroll_boxes:
            # div直下でなくネストしている場合
            scroll_boxes = []
            for sib in siblings:
                if hasattr(sib, 'find_all'):
                    scroll_boxes.extend(sib.find_all(class_='scroll-box'))

        # 支店ごとにエントリを作るか、代表1件にまとめるか
        # → 代表1件（最初の scroll-box）にまとめる
        info = parse_table(scroll_boxes[0]) if scroll_boxes else {}

        address = info.get('住所', '')
        # 住所から都道府県・市区町村を上書き補完
        if address and not prefecture:
            prefecture, city = split_prefecture_city(address)

        genre = detect_genre(shop_name_base + description)
        tabelog_url = make_tabelog_url(shop_name_base)

        # テーブルなし = 店舗ブロックではないのでスキップ
        if not info and not address:
            continue

        # メンバー: 愛称と正式名が両方入った場合は正式名だけ残す
        full_names = set(m for m in members if len(m) >= 3 and m in MEMBERS)
        members = list(dict.fromkeys(
            m for m in members
            if m in full_names or (m not in full_names and not any(m in n for n in full_names))
        ))

        shops.append({
            'name': shop_name_base,
            'genre': genre,
            'prefecture': prefecture,
            'city': city,
            'address': address,
            'lat': None,
            'lng': None,
            'youtube_id': '',
            'source_video_title': program,
            'source_video_url': '',
            'visited_date': '',
            'members': members,
            'groups': [GROUP],
            'group': GROUP,
            'description': description,
            'nearest_station': '',
            'price_range': '',
            'tabelog_url': tabelog_url,
            'hotpepper_url': '',
            'google_maps_url': '',
            'tags': [],
            'affiliate_links': [{'label': '食べログで見る', 'url': tabelog_url}],
        })

    return shops


def scrape_page(url):
    print(f'取得中: {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    html = urllib.request.urlopen(req, timeout=20).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    if 'senublog.com' in url:
        # 個別ページ（st-in-mybox あり）か まとめページ（scroll-box あり）かで分岐
        if soup.find(class_='st-in-mybox'):
            shops = scrape_senublog_individual(url, soup)
        else:
            shops = scrape_senublog(url, soup)
    else:
        print(f'  未対応のURL形式: {url}')
        shops = []

    print(f'  → {len(shops)}件取得')
    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--output', default='scripts/scraped_nogizaka.json')
    args = parser.parse_args()

    all_shops = []
    for url in args.urls:
        all_shops.extend(scrape_page(url))

    # 重複除去（店名）
    seen = set()
    unique = []
    for s in all_shops:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    no_addr = [s for s in unique if not s['address']]
    no_member = [s for s in unique if not s['members']]
    print(f'\n完了: {len(unique)}件（重複除去後）')
    print(f'→ {args.output} に保存しました')
    print(f'住所なし: {len(no_addr)}件 / メンバー不明: {len(no_member)}件')
    print('\n次のステップ:')
    print('  python scripts/geocode_shops.py --input scripts/scraped_nogizaka.json --output scripts/geocoded_nogizaka.json')
    print('  python scripts/merge_shops.py --input scripts/geocoded_nogizaka.json')


if __name__ == '__main__':
    main()
