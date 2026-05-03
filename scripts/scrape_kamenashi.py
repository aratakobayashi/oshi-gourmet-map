"""
scrape_kamenashi.py
fananablog.com の亀梨和也ロケ地まとめページから店舗情報をスクレイピング

使い方:
  python scripts/scrape_kamenashi.py --output scripts/scraped_kamenashi.json
"""

import urllib.request
import urllib.parse
import json
import re
import argparse
from bs4 import BeautifulSoup

URL = 'https://fananablog.com/kamenashiyoutube-seichi/'

# 飲食店と判断するキーワード（説明文・店名に含まれる場合）
FOOD_KEYWORDS = [
    '食べ', '飲み', 'ランチ', 'ディナー', '朝食', '夕食', 'ご飯', '料理',
    'レストラン', 'ラーメン', '寿司', '鮨', '焼肉', 'カフェ', 'コーヒー',
    '珈琲', 'うどん', '蕎麦', 'パスタ', 'ステーキ', '居酒屋', 'バー',
    'スイーツ', 'ケーキ', 'パン', 'かき氷', '定食', '食堂', '弁当',
    '餃子', 'もんじゃ', 'お好み焼き', '天ぷら', '刺身', '海鮮',
    '冷麺', 'ビール', 'ワイン', '日本酒', '焼き鳥', 'バーベキュー', 'BBQ',
]

# 飲食店でないと判断するキーワード
NON_FOOD_KEYWORDS = [
    'ゴルフ', '幼稚園', '神社', '家具', 'ワークマン', 'パビリオン',
    '万博', '足ツボ', '足壺', '美容', 'スタジオ',
    'ショッピング', '百貨店', '書店', '本屋', 'スポーツ', 'ジム',
    '病院', '公園', '博物館', '美術館',
    '資生堂', 'SHISEIDO', '化粧', 'コスメ', '宝くじ', 'チャンスセンター',
    'スーパー', '東急ストア', 'ワインショップ', '酒屋',
    '青果', '水産', '花屋', '薬局', 'ドラッグ',
    '貸別荘', 'ヴィラ', 'ビラ', '別荘', '旅館', 'ホテル',
    '空港', '港', '城', '占い', '足湯', '温泉', '銭湯',
    '刃物', '包丁', '古着', 'ファッション', '衣料', '電気',
    'ビックカメラ', 'ヨドバシ', '花火', 'ヘッドスパ',
    'マリーナ', 'センター', 'プラザ', 'モール',
]

# ジャンル推定
GENRE_MAP = [
    (['ラーメン', '冷麺', 'つけ麺'], 'ラーメン'),
    (['焼肉', '牛角', '焼き肉', '肉', 'ステーキ', 'BBQ', 'バーベキュー'], '焼肉'),
    (['寿司', '鮨', '回転寿司'], '寿司'),
    (['カフェ', 'コーヒー', '珈琲', 'coffee'], 'カフェ'),
    (['スイーツ', 'ケーキ', 'パン', 'かき氷', 'アイス', 'パティスリー'], 'スイーツ'),
    (['うどん', '蕎麦', 'そば', 'パスタ', 'イタリアン'], '食事'),
    (['居酒屋', 'バー', '酒'], '居酒屋'),
    (['もんじゃ', 'お好み焼き'], '食事'),
]


def detect_genre(name, description):
    text = name + description
    for keywords, genre in GENRE_MAP:
        if any(kw in text for kw in keywords):
            return genre
    return '食事'


def is_food(name, description):
    text = name + description
    if any(kw in text for kw in NON_FOOD_KEYWORDS):
        return False
    if any(kw in text for kw in FOOD_KEYWORDS):
        return True
    # 「お店」「来た」を含む説明があればとりあえず含める
    if 'お店' in text or '来た' in text or '行った' in text:
        return True
    return False


def make_tabelog_url(shop_name):
    return 'https://tabelog.com/rstLst/?vs=1&sa=&sk=' + urllib.parse.quote(shop_name)


def parse_date(h3_text):
    """'2025/07/19 盛岡回' → '2025-07-19'"""
    m = re.match(r'(\d{4})/(\d{2})/(\d{2})', h3_text)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return ''


def scrape(url):
    print('HTMLを取得中...')
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    content = soup.find('article') or soup.find('main') or soup.body
    h3s = content.find_all('h3')

    shops = []
    for h3 in h3s:
        date_str = parse_date(h3.get_text(strip=True))
        if not date_str:
            continue

        # h3の次のh3までの要素を収集
        siblings = []
        for sib in h3.next_siblings:
            if sib.name == 'h3':
                break
            siblings.append(sib)

        # p→h4→p の順で店舗ごとに処理
        current_desc = ''
        for el in siblings:
            if not hasattr(el, 'name') or not el.name:
                continue
            text = el.get_text(strip=True)
            if not text:
                continue

            if el.name == 'p' and not current_desc:
                # h4の前のpは動画の説明文
                current_desc = text

            elif el.name == 'h4':
                shop_name = text
                # h4直後のpを説明として取得
                shop_desc = ''
                for next_el in el.next_siblings:
                    if not hasattr(next_el, 'name') or not next_el.name:
                        continue
                    if next_el.name in ('h3', 'h4'):
                        break
                    if next_el.name == 'p' and next_el.get_text(strip=True):
                        shop_desc += next_el.get_text(strip=True) + ' '

                shop_desc = shop_desc.strip()

                if not is_food(shop_name, current_desc + shop_desc):
                    continue

                genre = detect_genre(shop_name, current_desc + shop_desc)
                tabelog_url = make_tabelog_url(shop_name)

                shops.append({
                    'name': shop_name,
                    'visited_date': date_str,
                    'description': shop_desc or current_desc,
                    'genre': genre,
                    'group': 'kamenashi',
                    'groups': ['kamenashi'],
                    'members': ['亀梨和也'],
                    'address': '',
                    'tabelog_url': tabelog_url,
                    'affiliate_links': [
                        {'label': '食べログで見る', 'url': tabelog_url}
                    ],
                })

    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kamenashi.json')
    args = parser.parse_args()

    shops = scrape(URL)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(shops)}件')
    print(f'→ {args.output} に保存しました')
    print('\n=== 最初の5件 ===')
    for s in shops[:5]:
        print(f'[{s["visited_date"]}] {s["name"]} ({s["genre"]})')
        print(f'  {s["description"][:60]}')


if __name__ == '__main__':
    main()
