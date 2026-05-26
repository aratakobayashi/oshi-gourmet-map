"""
enrich_descriptions.py
description が短い（50文字未満）店舗のdescriptionをデータから自動生成して充実させる

使い方:
  python scripts/enrich_descriptions.py --dry-run   # 変更内容確認のみ
  python scripts/enrich_descriptions.py             # shops.jsonを直接更新
  python scripts/enrich_descriptions.py --min 30    # 30文字未満を対象に
"""

import json, re, argparse, os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON  = os.path.join(SCRIPTS_DIR, '../data/shops.json')

GROUP_LABELS = {
    'yonino':          'よにのちゃんねる',
    'snowman':         'Snow Man',
    'sixtones':        'SixTONES',
    'naniwa':          'なにわ男子',
    'kamenashi':       '亀梨和也',
    'kamaitachi':      'かまいたち',
    'equal_love':      '=LOVE',
    'notme':           '≠ME',
    'neajoy':          '≒JOY',
    'nogizaka46':      '乃木坂46',
    'sakurazaka46':    '櫻坂46',
    'hinatazaka46':    '日向坂46',
    'ginga':           '中丸雄一 銀河チャンネル',
    'kodoku_no_gurume':'孤独のグルメ',
    'timelesz':        'timelesz',
    'heysayjump':      'Hey! Say! JUMP',
    'kingprince':      'King & Prince',
    'shiori':          'しおり',
    'miruwz':          'miruwz',
}

GENRE_WORDS = {
    'カフェ':   'カフェ',
    'ラーメン': 'ラーメン店',
    '焼肉':    '焼肉店',
    '寿司':    '寿司店',
    'スイーツ': 'スイーツショップ',
    '居酒屋':  '居酒屋',
    '和食':    '和食店',
    'もんじゃ': 'もんじゃ焼き店',
    '中華':    '中華料理店',
    '食事':    'レストラン',
    'その他':  'グルメスポット',
}


def format_date(date_str):
    if not date_str:
        return ''
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        return f'{m.group(1)}年{int(m.group(2))}月'
    return ''


def format_members(members, max_count=3):
    if not members:
        return ''
    shown = members[:max_count]
    result = '・'.join(shown)
    if len(members) > max_count:
        result += 'ら'
    return result


def extract_episode_num(video_title):
    if not video_title:
        return ''
    m = re.search(r'#(\d+)', video_title)
    return f'#{m.group(1)}' if m else ''


def generate_description(shop):
    existing = shop.get('description', '').strip()

    name    = shop.get('name', '')
    genre   = shop.get('genre', 'その他')
    city    = shop.get('city', '')
    pref    = shop.get('prefecture', '')
    members = shop.get('members') or []
    group   = shop.get('group', '')
    label   = GROUP_LABELS.get(group, group)
    date    = shop.get('visited_date', '')
    items   = shop.get('ordered_items') or []
    tags    = shop.get('tags') or []
    title   = shop.get('source_video_title', '') or ''
    seating = shop.get('seating_note', '') or ''
    source_type = shop.get('source_type', '')

    genre_word = GENRE_WORDS.get(genre, 'グルメスポット')
    location   = city or pref

    # ドラマ・映画ソースは専用テンプレート
    if source_type == 'drama':
        ep_num = extract_episode_num(title)
        parts = [f'{location}の{genre_word}。']
        if title:
            parts.append(f'ドラマ「{title}」に登場。')
        elif label:
            parts.append(f'{label}の聖地スポット。')
        return ''.join(parts)

    parts = []

    # ① 場所・ジャンルの導入
    if location:
        parts.append(f'{location}の{genre_word}。')
    else:
        parts.append(f'{genre_word}。')

    # ② 誰が・いつ訪れたか
    member_str = format_members(members)
    date_str   = format_date(date)
    ep_num     = extract_episode_num(title)

    if member_str and date_str:
        parts.append(f'{member_str}が{date_str}に訪れた。')
    elif member_str:
        parts.append(f'{member_str}が訪れた{label}のロケ地。')
    elif label:
        parts.append(f'{label}が訪れたロケ地。')

    # ③ 注文アイテム（あれば）
    if items:
        item_str = '・'.join(items[:3])
        parts.append(f'{item_str}を堪能。')

    # ④ 特徴的なタグ（食べ物・飲み物・料理に関するものだけ抽出）
    LOCATION_SUFFIXES = ('区', '市', '町', '村', '駅', '橋', '坂', '丘', '園', '台', 'タウン', 'シティ',
                         '沢', '木', '谷', '川', '原', '島', '浜', '野', '田', '山', '池', '浦')
    SKIP_TAGS = {genre, city, pref, genre_word, 'カフェ', 'ラーメン', '焼肉', '寿司',
                 'スイーツ', '居酒屋', '和食', '中華', '食事', '聖地巡礼', 'ロケ地',
                 'コーヒースタンド', 'ベーカリー', 'レストラン', '定食屋', '食堂'}
    def is_food_tag(tag):
        if tag in SKIP_TAGS:
            return False
        if any(tag.endswith(s) for s in LOCATION_SUFFIXES):
            return False
        if len(tag) < 3:
            return False
        return True
    feature_tags = [t for t in tags if is_food_tag(t)][:2]
    if feature_tags and not items:
        parts.append(f'{"・".join(feature_tags)}が楽しめる。')

    # ⑤ 既存descriptionに内容があれば末尾に追記（重複除去）
    if existing and existing not in ''.join(parts):
        # 既存が短い場合はそのまま追記
        combined = ''.join(parts) + existing
        if len(combined) <= 200:
            return combined

    result = ''.join(parts)

    # 長すぎる場合は切る
    if len(result) > 150:
        result = result[:150] + '。'

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--min', type=int, default=50, help='この文字数未満を対象（デフォルト50）')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    targets = [s for s in shops if len(s.get('description', '')) < args.min]
    print(f'対象: {len(targets)}件（{args.min}文字未満）\n')

    updated = 0
    for shop in shops:
        if len(shop.get('description', '')) >= args.min:
            continue

        old = shop.get('description', '')
        new = generate_description(shop)

        if new and new != old and len(new) > len(old):
            if args.dry_run:
                print(f'[{shop["group"]}] {shop["name"]}')
                print(f'  before: 「{old}」({len(old)}文字)')
                print(f'  after:  「{new}」({len(new)}文字)')
                print()
            else:
                shop['description'] = new
            updated += 1

    print(f'\n{updated}件を更新')

    if not args.dry_run:
        with open(SHOPS_JSON, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
        print('shops.json を上書き保存しました')


if __name__ == '__main__':
    main()
