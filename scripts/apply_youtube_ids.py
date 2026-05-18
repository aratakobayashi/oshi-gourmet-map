"""
apply_youtube_ids.py
YouTube API dry-run で確認済みの youtube_id を shops.json に適用する

対象: SixTONES (24件)・乃木坂46 MV+番組 (9件)・日向坂46 (1件)
"""
import json

SHOPS_PATH = 'data/shops.json'

# (group, source_video_title) -> youtube_id
# ※ 動画タイトルのキーワードと合致を確認済みのもののみ収録
TITLE_TO_YT = {
    # ===== SixTONES =====
    ('sixtones', 'SixTONES - Singapore Travel Vlog'):      'BK4o1X5khKU',  # 絶品朝メシinシンガポール
    ('sixtones', 'SixTONES - シンガポール自由行動'):        'RtDfRvCiBEo',  # 俺たちに絆はあるのか!?inシンガポール
    ('sixtones', 'SixTONES - ラーメン大好きグループ'):      'fjljPstbzAw',  # 豚骨を８時間煮込んで究極のラーメン
    ('sixtones', 'SixTONES - 京都で最高の和食'):           'kDFP1_FLpJc',  # Kyoto Drive Vol.2
    ('sixtones', 'SixTONES - 月島でもんじゃ！'):           '_vywZByqAdw',  # TOKYOグルメガイド 駄菓子もんじゃ
    ('sixtones', 'SixTONES - 秩父で天然氷のかき氷！'):     'ki6-4nUfMTM',  # ドライブ企画 秩父編
    ('sixtones', 'SixTONES - 秩父グルメを堪能'):           'ki6-4nUfMTM',  # ドライブ企画 秩父編（同動画）
    ('sixtones', 'SixTONES - 都内散歩'):                   'QxC80mUBnpQ',  # Harajuku Walk 原宿散歩
    ('sixtones', 'SixTONES - 金沢で回転寿司！'):           'g58loSsI8Rw',  # Kanazawa Travel Vol.1
    ('sixtones', 'SixTONES - 金沢・ひがし茶屋街を歩く'):  'g58loSsI8Rw',  # Kanazawa Travel Vol.1（同動画）
    ('sixtones', 'SixTONES【中目黒焼き鳥回】'):           '0dnJrRmFRXo',  # 無限シリーズ~焼き鳥
    ('sixtones', 'SixTONES【日本橋蕎麦回】'):             'Ya8aKNX5vOs',  # そば大食い企画 わんこそば
    ('sixtones', 'SixTONES【松村北斗の食べたいものを当てろ】'): 'SCn4CdAOcoc',  # 松村北斗のトリセツ
    ('sixtones', 'SixTONES【浅草アポなし旅】'):           '3_cm61ZXb2E',  # アポなし旅 2024夏
    ('sixtones', 'SixTONES【浅草洋食回】'):               '3_cm61ZXb2E',  # アポなし旅 2024夏（同動画）
    ('sixtones', 'SixTONES【鳥貴族で全メニュー当てろ！】'): '0dnJrRmFRXo',  # 無限シリーズ~焼き鳥

    # ===== 乃木坂46 (MV・公式番組) =====
    ('nogizaka46', '17thインフルエンサーType-A'):          'r4SdiT7mm7Y',  # 乃木坂46 インフルエンサーMV
    ('nogizaka46', '17thインフルエンサーType-C'):          'r4SdiT7mm7Y',  # 乃木坂46 インフルエンサーMV（同）
    ('nogizaka46', '20thシンクロニシティType-B'):          'f0wbnQw89J0',  # 乃木坂46 シンクロニシティMV
    ('nogizaka46', '21thジコチューで行こう！Type-D'):      '7eoiyP4kaAQ',  # 乃木坂46 ジコチューで行こう！MV
    ('nogizaka46', '22nd帰り道は遠回りしたくなるType-A'):  's1cgEj5JowM',  # 乃木坂46 帰り道は遠回りしたくなるMV
    ('nogizaka46', '他の星から'):                          '5gtHfCYK0Aw',  # 乃木坂46 他の星からShort
    ('nogizaka46', '乃木坂どこへ'):                        'ellqj4rVq6g',  # 乃木坂どこへ 4期生ぶらり旅
    ('nogizaka46', '乃木坂工事中'):                        'Nm_W7Ii-eW8',  # 乃木坂工事中 公式

    # ===== 日向坂46 =====
    ('hinatazaka46', 'あくびLetter'):                      'KcpvHDt0bPc',  # 日向坂46 あくびLetter MV

    # ===== SixTONES 追加 (WebSearch確認済み) =====
    ('sixtones', 'SixTONES - 高級うなぎを食す'):           'IL6OX1NjzsM',  # Tokyo Drive Vol.2（うなぎ徳 渋谷確認済み）
}

def get_group(shop):
    gs = shop.get('groups', [shop.get('group', '')])
    return gs[0] if gs else ''

def main():
    with open(SHOPS_PATH, encoding='utf-8') as f:
        shops = json.load(f)

    updated = 0
    for shop in shops:
        if shop.get('youtube_id') or shop.get('thumbnail_url'):
            continue
        g = get_group(shop)
        title = shop.get('source_video_title', '').strip()
        yt_id = TITLE_TO_YT.get((g, title))
        if yt_id:
            shop['youtube_id'] = yt_id
            updated += 1
            print(f'✓ [{g}] {shop["name"]} ← {yt_id}')

    print(f'\n{updated} 件を更新')
    with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print('shops.json を更新しました')

if __name__ == '__main__':
    main()
