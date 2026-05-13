"""
ジャンル正規化スクリプト
shops.json の genre="食事" を適切なジャンルに分類し直す
"""

import json
import re
from pathlib import Path

# ============================================================
# ジャンル分類ルール（優先度順）
# shop.name + shop.description を連結した文字列でマッチング
# ============================================================
RULES = [
    # ラーメン・麺類
    ('ラーメン', [
        'ラーメン', 'らーめん', 'らあめん', 'ラ〜メン',
        '油そば', 'つけ麺', '担々麺', '中華そば', '豚骨',
        'みそきん', '中本', '山岡家', '一蘭', '千里眼',
        'ぽっぽっ屋', '侍 本丸', '魂心家', '人類みな麺類',
        '北ノ醤油', '天下一品',
    ]),
    # 寿司
    ('寿司', [
        '寿司', 'すし', '鮨', '回転寿し', '回転ずし', '回転寿司',
        'まいもん', 'すしざんまい', '活一鮮', '海将',
    ]),
    # もんじゃ・お好み焼き
    ('もんじゃ', [
        'もんじゃ', 'お好み焼き', 'お好み村',
    ]),
    # 焼肉
    ('焼肉', [
        '焼肉', '焼き肉', 'ホルモン', '和牛', '近江牛',
        'エイジングビーフ', 'エイジング・ビーフ', 'トラジ',
        'うしごろ', 'ushihachi', 'USHIHACHI',
        '哲 TETSU', '哲 tetsu', '哲tetsu',
    ]),
    # 居酒屋・串焼き系
    ('居酒屋', [
        '居酒屋', '酒場', '酒処', 'はしご酒',
        'もつ焼', 'やきとん', 'やきとり', '焼き鳥', '焼鳥',
        '串カツ', '串かつ', '鳥貴族',
        '赤鬼', 'じゃじゃ馬', 'のんき', 'やきとん長良',
        'あちらぼ', 'まんまじぃま', 'あとむ', 'えどもんど',
        'Litty', 'litty', 'えびす', '清介',
        '釣船茶屋', 'ざうお',
    ]),
    # カレー
    ('カレー', [
        'カレー', 'curry', 'Curry', 'CURRY',
        'CoCo壱', 'セイロン', 'スパイスカレー', '魯珈',
    ]),
    # スイーツ・デザート系
    ('スイーツ', [
        'スイーツ', 'パフェ', 'クレープ', 'ケーキ', 'タルト',
        'プリン', 'アイス', 'かき氷', 'ソフトクリーム',
        '大福', '饅頭', '和菓子', 'もみじ', '紅葉堂',
        'さくらの夢見屋', '茶々本店', '芋ぴっぴ',
        'LONG! LONGER', 'MARION CREPES', 'マリオンクレープ',
        'FLIPPER', 'フリッパーズ', 'スイーツパラダイス',
        'シュガークレープ', 'くずきり', '舟和', '浅草 いづ美',
        'いづ美', 'コロッケ', '近江町コロッケ',
        '杉養蜂園', '又一庵', '熱海プリン',
    ]),
    # カフェ・喫茶（中華より先に評価して誤分類を防ぐ）
    ('カフェ', [
        'カフェ', 'CAFE', 'Cafe', 'cafe',
        '喫茶', 'コーヒー', 'Coffee', 'COFFEE', '珈琲',
        'mateki', 'GEBURA', 'パスティス', 'Pastis',
        'DOG DEPT', '2D Cafe', 'ブルーシール',
        'Samoyed', '鳥のいるカフェ', '猫カフェ',
        'COA GINZA', 'コロラド',
    ]),
    # 中華・アジア系
    ('中華', [
        '火鍋', '餃子', '小籠包', '点心', '飲茶',
        '海底撈', '炎麻堂', 'プングム', '金華園',
        '六覺燈', 'バーミヤン', '中華料理',
        '新三浦', '中華街餃子館',
    ]),
    # 和食（そば・海鮮・定食など）
    ('和食', [
        'そば', '蕎麦', 'うどん', 'わんこそば',
        'おにぎり', 'ぼんご', '定食',
        '天ぷら', '天丼', 'とんかつ', '刺身',
        '海鮮', '鮮魚', 'シーフード', '魚', '海鮮家',
        'うなぎ', '鰻', 'あなごめし', 'あなご',
        'おかべ家', 'げんかん', 'なかよし', '野さか',
        '安立屋', '磯丸水産', '八倉',
        '壱番屋', 'ともや', 'からあげ',
        '沼津港', 'ふじたや', '徳造丸',
        'やまへい', '手打ちそば',
    ]),
    # その他（飲食店ではない・珍しいカテゴリ）
    ('その他', [
        'ゲーセン', 'タイトーステーション', 'ユナイテッドシネマ',
        'モーリーファンタジー', 'コスメキッチン', 'WEGO',
        'SANRIO CAFE', 'DOG&CAT', 'ひろしま夢ぷらざ',
        'アーバンスポーツ', '劇場', '市場', '商店街',
        '夢ぷらざ', '博覧館',
    ]),
]


def classify_genre(name: str, description: str = ''):
    """キーワードマッチでジャンルを返す。マッチしない場合は None"""
    text = (name + ' ' + description).lower()
    # 元のケースも保持して大文字小文字を区別したい部分のためにオリジナルも使う
    text_orig = name + ' ' + description

    for genre, keywords in RULES:
        for kw in keywords:
            if kw.lower() in text or kw in text_orig:
                return genre
    return None


def main():
    json_path = Path(__file__).parent.parent / 'data' / 'shops.json'
    with open(json_path, encoding='utf-8') as f:
        shops = json.load(f)

    changed = 0
    skipped = 0
    log = []

    for shop in shops:
        if shop.get('genre') != '食事':
            continue  # 食事以外は変更しない

        new_genre = classify_genre(
            shop.get('name', ''),
            shop.get('description', ''),
        )
        if new_genre and new_genre != '食事':
            log.append(f"  {shop['name'][:30]: <32}  食事 → {new_genre}")
            shop['genre'] = new_genre
            changed += 1
        else:
            skipped += 1

    print(f'変更: {changed}件 / 変更なし（食事のまま）: {skipped}件')
    print()
    print('=== 変更ログ ===')
    for line in log:
        print(line)

    # 確認後に保存
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f'\n✅ {json_path} を更新しました')

    # 更新後の分布
    from collections import Counter
    genres = Counter(s.get('genre', '') for s in shops)
    print()
    print('=== 更新後のジャンル分布 ===')
    for g, c in genres.most_common():
        print(f'  {g or "(空)": <12} {c}件')


if __name__ == '__main__':
    main()
