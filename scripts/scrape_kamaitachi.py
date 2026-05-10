"""
scrape_kamaitachi.py
かまいたちチャンネル「ロケで行った飲食店まとめ」から店舗データを生成する

動画説明文に記載されたフォーマット「・料理名／店名【エリア】」を解析。
"""

import json
import re
import argparse
import unicodedata

GROUP = 'kamaitachi'
MEMBERS = ['山内健司', '濱家隆一']

# ・料理名／店名【エリア】 形式
SHOP_PATTERN = re.compile(r'・(.+?)／(.+?)【(.+?)】')

# 動画説明文（確認済みテキスト）
VIDEOS = [
    {
        'youtube_id': 'kU8SZpaXoBE',
        'title': 'かまいたちがロケで行った飲食店まとめ【関西編】',
        'visited_date': None,
        'description': """
・うなしゃぶ／おゝ杉【滋賀】
・スパイスカレー／ワルン【大阪】
・スパイスカレー／ツキノワ【大阪】
・スペアリブ／再度山荘【兵庫】
・ラーメン・チャーハン／大貫本店【兵庫】
・コロラド【京都】
・香住のシロイカ／香住・かどや【兵庫】
・隠れ鉄板酒屋 風流【大阪】
""",
    },
    {
        'youtube_id': 'n6aabEP44lU',
        'title': 'かまいたちがロケで行った飲食店まとめ【関東編】',
        'visited_date': None,
        'description': """
・純レバ／三徳【東京森下】
・シロ／もつ焼のんき【東京堀切】
・トムヤム飯／パーバーン【東京新御徒町】
・特大生姜焼き／ぐりるスズコウ【東京蒲田】
・鉄板焼ステーキ とみい【東京浅草】
・トルコ料理ムラート【兵庫神戸】
・蛤の天ぷら／天ぷら もっこす【群馬高崎】
""",
    },
]

# エリア文字列 → (prefecture, city, nearest_station_hint)
AREA_MAP = {
    '滋賀':     ('滋賀県', '', ''),
    '大阪':     ('大阪府', '大阪市', ''),
    '兵庫':     ('兵庫県', '', ''),
    '京都':     ('京都府', '京都市', ''),
    '東京森下':  ('東京都', '江東区', '森下駅'),
    '東京堀切':  ('東京都', '葛飾区', '堀切菖蒲園駅'),
    '東京新御徒町': ('東京都', '台東区', '新御徒町駅'),
    '東京蒲田':  ('東京都', '大田区', '蒲田駅'),
    '東京浅草':  ('東京都', '台東区', '浅草駅'),
    '兵庫神戸':  ('兵庫県', '神戸市', ''),
    '群馬高崎':  ('群馬県', '高崎市', '高崎駅'),
}

GENRE_MAP = {
    'うなしゃぶ':      '和食',
    'スパイスカレー':   'カレー',
    'スペアリブ':      '食事',
    'ラーメン':        'ラーメン',
    'チャーハン':      '食事',
    '純レバ':         '居酒屋',
    'シロ':           '居酒屋',
    'トムヤム飯':      '食事',
    '特大生姜焼き':    '食事',
    '鉄板焼ステーキ':  '食事',
    'トルコ料理':      '食事',
    '蛤の天ぷら':      '和食',
    'カレー':         'カレー',
}


def normalize(text: str) -> str:
    return unicodedata.normalize('NFKC', text).strip()


def infer_genre(dish: str) -> str:
    dish_n = normalize(dish)
    for keyword, genre in GENRE_MAP.items():
        if keyword in dish_n:
            return genre
    return 'その他'


def make_id(name: str, index: int) -> str:
    slug = re.sub(r'[^\w]', '', name)[:20]
    return f'kamaitachi-{slug}-{index:03d}'


def parse_video(video: dict) -> list:
    shops = []
    desc = video['description']
    for m in SHOP_PATTERN.finditer(desc):
        dish = normalize(m.group(1))
        name = normalize(m.group(2))
        area = normalize(m.group(3))

        pref, city, station = AREA_MAP.get(area, ('', '', ''))
        genre = infer_genre(dish)

        shop = {
            'name': name,
            'genre': genre,
            'prefecture': pref,
            'city': city,
            'address': '',
            'lat': None,
            'lng': None,
            'youtube_id': video['youtube_id'],
            'source_video_title': video['title'],
            'source_video_url': f'https://www.youtube.com/watch?v={video["youtube_id"]}',
            'visited_date': video.get('visited_date') or '',
            'members': MEMBERS,
            'groups': [GROUP],
            'group': GROUP,
            'description': dish,
            'nearest_station': station,
            'tags': [],
            'affiliate_links': [],
        }
        if station:
            shop['tags'].append(station)
        shops.append(shop)

    # コロラド【京都】などで料理名のみのパターンを追加処理
    # 「・コロラド【京都】」→ 店名=コロラド、料理名なし（行頭の・のみ対象）
    extra_pattern = re.compile(r'^・([^／\n【]+?)【(.+?)】', re.MULTILINE)
    for m in extra_pattern.finditer(desc):
        if '／' in m.group(0):
            continue  # 通常パターンで処理済み
        name = normalize(m.group(1))
        area = normalize(m.group(2))
        if not name:
            continue
        pref, city, station = AREA_MAP.get(area, ('', '', ''))
        shop = {
            'name': name,
            'genre': '食事',
            'prefecture': pref,
            'city': city,
            'address': '',
            'lat': None,
            'lng': None,
            'youtube_id': video['youtube_id'],
            'source_video_title': video['title'],
            'source_video_url': f'https://www.youtube.com/watch?v={video["youtube_id"]}',
            'visited_date': video.get('visited_date') or '',
            'members': MEMBERS,
            'groups': [GROUP],
            'group': GROUP,
            'description': '',
            'nearest_station': station,
            'tags': [],
            'affiliate_links': [],
        }
        shops.append(shop)

    return shops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='scripts/scraped_kamaitachi.json')
    args = parser.parse_args()

    all_shops = []
    for video in VIDEOS:
        shops = parse_video(video)
        print(f'{video["title"]}: {len(shops)}件')
        all_shops.extend(shops)

    # 重複除去（同名店舗）
    seen = set()
    unique = []
    for s in all_shops:
        key = s['name']
        if key not in seen:
            seen.add(key)
            unique.append(s)

    # ID付与
    for i, s in enumerate(unique):
        s['id'] = make_id(s['name'], i + 1)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f'\n合計 {len(unique)}件 → {args.output} に保存しました')


if __name__ == '__main__':
    main()
