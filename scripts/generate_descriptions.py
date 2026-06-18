"""
generate_descriptions.py
説明文（description）が空・短い店舗にテンプレートで自動生成する

対象: description が空または20文字以下の店舗
上書き: しない（既存説明文が20文字超の場合はスキップ）

使い方:
  python scripts/generate_descriptions.py          # 実行
  python scripts/generate_descriptions.py --dry-run  # 確認のみ
"""

import json
import re
import argparse

GROUP_LABELS = {
    "yonino":          "よにのちゃんねる",
    "snowman":         "すの日常（Snow Man）",
    "sixtones":        "ストチューブ（SixTONES）",
    "naniwa":          "なにわ男子",
    "kamenashi":       "亀梨和也",
    "kamaitachi":      "かまいたち",
    "equal_love":      "=LOVE",
    "notme":           "≠ME",
    "neajoy":          "≒JOY",
    "nogizaka46":      "乃木坂46",
    "hinatazaka46":    "日向坂46",
    "sakurazaka46":    "櫻坂46",
    "ginga":           "中丸雄一銀河チャンネル",
    "kodoku_no_gurume":"孤独のグルメ",
    "heysayjump":      "いただきハイジャンプ",
    "timelesz":        "Timelesz",
    "kpop_bts":        "BTS",
    "kpop_straykids":  "Stray Kids",
    "kpop_lesserafim": "LE SSERAFIM",
    "kpop_blackpink":  "BLACKPINK",
    "kpop_enhypen":    "ENHYPEN",
    "kpop_seventeen":  "SEVENTEEN",
    "kpop_riize":      "RIIZE",
    "kpop_nct":        "NCT",
    "kpop_twice":      "TWICE",
    "numberi":         "Number_i",
    "kingprince":      "King & Prince",
    "arashi":          "嵐",
    "west":            "WEST.",
    "kinkikids":       "KinKi Kids",
    "smap":            "SMAP",
    "v6":              "V6",
    "travisjapan":     "Travis Japan",
    "kismai":          "Kis-My-Ft2",
    "kattun":          "KAT-TUN",
    "kimura":          "木村拓哉",
    "shiori":          "しおりん",
    "agroup":          "Aぇ!group",
}

# グループ名と同じ名前のメンバーは主語に使わない（冗長になるため）
SOLO_GROUPS = {'kamenashi', 'ginga'}

# テーマとして無意味なキーワード（チャンネル名など）
NOISE_THEMES = {'すのちゅーぶ', 'ストチューブ', 'すの日常', 'なにわ男子Official'}

GENRE_SUFFIX = {
    "カフェ":   "カフェ",
    "ラーメン": "ラーメン店",
    "焼肉":     "焼肉店",
    "寿司":     "寿司店",
    "スイーツ": "スイーツ店",
    "居酒屋":   "居酒屋",
    "和食":     "和食店",
    "もんじゃ": "もんじゃ店",
    "食事":     "飲食店",
    "その他":   "お店",
    # 英語スラグ対応
    "cafe":     "カフェ",
    "ramen":    "ラーメン店",
    "yakiniku": "焼肉店",
    "shokuji":  "飲食店",
    "chuka":    "中華料理店",
    "washoku":  "和食店",
    "sweets":   "スイーツ店",
    "izakaya":  "居酒屋",
    "others":   "グルメスポット",
}


def extract_episode(title, group):
    """source_video_titleからエピソード情報を抽出して文字列を返す"""
    if not title:
        return ''

    # 孤独のグルメ・ドラマ系: グループ名プレフィックスを除去してエピソード部分だけ返す
    if group == 'kodoku_no_gurume' or 'Season' in title:
        # "孤独のグルメ Season1 第1話" → "Season1 第1話"
        cleaned = re.sub(r'^孤独のグルメ\s*', '', title).strip()
        return cleaned if cleaned else title

    # いただきハイジャンプ: 日付+テーマ形式 "2015.11.14/... テーマ（メンバー）"
    if group == 'heysayjump':
        # 日付部分を除いてテーマ部分だけ抽出
        m = re.search(r'[^\d/．・\s]{4,}', title)
        if m:
            return m.group(0)[:30]
        return title[:30]

    # YouTube系: #番号【テーマ】形式
    ep_num = ''
    ep_m = re.match(r'^#(\d+)', title)
    if ep_m:
        ep_num = f'#{ep_m.group(1)}'

    theme = ''
    # 【】内を全て試して、ノイズでないものを採用
    for m in re.finditer(r'[【「]([^】」]{2,25})[】」]', title):
        candidate = m.group(1)
        if candidate not in NOISE_THEMES:
            theme = candidate
            break

    if ep_num and theme:
        return f'{ep_num}「{theme}」'
    elif ep_num:
        return ep_num
    elif theme:
        return f'「{theme}」'
    else:
        # タイトルをそのまま短縮
        return f'「{title[:25]}」' if len(title) > 5 else ''


def make_subject(members, group_label, episode_str):
    """主語部分を生成"""
    n = len(members)
    if n == 0:
        return group_label, episode_str
    elif n == 1:
        return f'{members[0]}', f'{group_label}{episode_str}'
    elif n == 2:
        return f'{members[0]}・{members[1]}', f'{group_label}{episode_str}'
    else:
        return f'{members[0]}ら{n}名', f'{group_label}{episode_str}'


def generate_description(shop):
    group        = shop.get('group', '')
    members      = shop.get('members', [])
    title        = shop.get('source_video_title', '')
    genre        = shop.get('genre', '')
    ordered      = shop.get('ordered_items', [])
    group_label  = GROUP_LABELS.get(group, group)
    genre_label  = GENRE_SUFFIX.get(genre, '飲食店')

    episode_str = extract_episode(title, group)

    # ---- 文を組み立てる ----
    parts = []

    # ソログループ（亀梨和也など）はメンバーが自分自身なので「訪問」補足は不要
    is_solo = group in SOLO_GROUPS

    if episode_str:
        sep = '' if episode_str.startswith(('#', '「')) else ' '
        parts.append(f'{group_label}{sep}{episode_str}に登場した{genre_label}。')
        if members and not is_solo:
            who = '・'.join(members[:2])
            suffix = 'ら' if len(members) > 2 else ''
            parts.append(f'{who}{suffix}が訪問。')
    else:
        if members and not is_solo:
            who = '・'.join(members[:2])
            suffix = 'ら' if len(members) > 2 else ''
            parts.append(f'{group_label}の{who}{suffix}が訪れた{genre_label}。')
        else:
            parts.append(f'{group_label}が訪れた{genre_label}。')

    # 注文メニュー（1アイテム15文字以内のものだけ・最大3件）
    if ordered:
        short_items = [i for i in ordered if len(i) <= 15][:3]
        if short_items:
            parts.append(f'{"・".join(short_items)}を注文。')

    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with open('data/shops.json', encoding='utf-8') as f:
        shops = json.load(f)

    updated = 0
    skipped_existing = 0
    for shop in shops:
        current = shop.get('description', '')
        if len(current) > 20:
            skipped_existing += 1
            continue

        desc = generate_description(shop)
        if desc:
            if not args.dry_run:
                shop['description'] = desc
            else:
                print(f'[{shop["group"]}] {shop["name"]}')
                print(f'  → {desc}')
            updated += 1

    print(f'\n=== 結果 ===')
    print(f'既存説明文スキップ: {skipped_existing}件')
    print(f'生成{"（dry-run）" if args.dry_run else "・更新"}: {updated}件')

    if not args.dry_run:
        with open('data/shops.json', 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
        print('→ data/shops.json に保存しました')


if __name__ == '__main__':
    main()
