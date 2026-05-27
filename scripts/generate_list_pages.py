#!/usr/bin/env python3
"""
generate_list_pages.py
グループ×ジャンルの組み合わせページ(_list_pages/)を自動生成する。

使い方:
  python scripts/generate_list_pages.py
  python scripts/generate_list_pages.py --min 3   # 3件以上の組み合わせを対象に
"""

import json
import os
import re
import argparse
from collections import defaultdict

SCRIPTS_DIR  = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON   = os.path.join(SCRIPTS_DIR, '../data/shops.json')
OUTPUT_DIR   = os.path.join(SCRIPTS_DIR, '../_list_pages')

GROUP_LABELS = {
    'yonino':           'よにのちゃんねる',
    'snowman':          'Snow Man',
    'sixtones':         'SixTONES',
    'naniwa':           'なにわ男子',
    'kamenashi':        '亀梨和也',
    'kamaitachi':       'かまいたち',
    'equal_love':       '=LOVE',
    'notme':            '≠ME',
    'neajoy':           '≒JOY',
    'nogizaka46':       '乃木坂46',
    'sakurazaka46':     '櫻坂46',
    'hinatazaka46':     '日向坂46',
    'ginga':            '中丸雄一 銀河チャンネル',
    'kodoku_no_gurume': '孤独のグルメ',
    'timelesz':         'timelesz',
    'heysayjump':       'Hey! Say! JUMP',
    'kingprince':       'King & Prince',
    'shiori':           'しおり',
}

GROUP_BIO = {
    'yonino':           '二宮和也（嵐）・中丸雄一（KAT-TUN）・山田涼介（Hey! Say! JUMP）・菊池風磨（timelesz）の4人によるYouTubeチャンネル。グルメ企画が人気。',
    'snowman':          'Snow ManはSTARTO ENTERTAINMENTの9人組男性アイドルグループ。メンバーが各地の名店を訪れる動画・番組が多い。',
    'sixtones':         'SixTONES（ストーンズ）はSTARTO ENTERTAINMENTの6人組男性グループ。バラエティやYouTubeでグルメスポットを紹介。',
    'naniwa':           'なにわ男子はSTARTO ENTERTAINMENTの7人組男性アイドルグループ。関西発のグルメ情報が充実。',
    'kamenashi':        '亀梨和也はKAT-TUNのメンバーで俳優・タレント。ドラマやバラエティで訪れる名店情報が集まる。',
    'kamaitachi':       'かまいたちは山内健司・濱家隆一からなる人気お笑いコンビ（吉本興業）。関西を中心にグルメ巡りを精力的に行う。',
    'equal_love':       '=LOVE（イコールラブ）は指原莉乃プロデュースの女性アイドルグループ。YouTubeでのグルメ企画が人気。',
    'notme':            '≠ME（ノットイコールミー）は指原莉乃プロデュースの女性アイドルグループ。',
    'neajoy':           '≒JOY（ニアジョイ）は指原莉乃プロデュースの女性アイドルグループ。',
    'nogizaka46':       '乃木坂46は秋元康プロデュースの女性アイドルグループ。バラエティやSNSで話題になった店舗が多数。',
    'sakurazaka46':     '櫻坂46は元欅坂46が改名した、秋元康プロデュースの女性アイドルグループ。',
    'hinatazaka46':     '日向坂46は秋元康プロデュースの女性アイドルグループ。メンバーのグルメ発信が活発。',
    'ginga':            '中丸雄一（KAT-TUN）の個人YouTubeチャンネル「中丸銀河ちゃんねる」。ゲストを招いた対談企画が人気。',
    'kodoku_no_gurume': '「孤独のグルメ」はテレビ東京系のドラマ。松重豊演じる井之頭五郎が全国各地の飲食店を一人で堪能する。',
    'timelesz':         'timelesz（タイムレス）はSTARTO ENTERTAINMENTの男性グループ（元Sexy Zone）。',
    'heysayjump':       'Hey! Say! JUMPはSTARTO ENTERTAINMENTの男性アイドルグループ。メンバーのグルメ情報が各地に点在。',
    'kingprince':       'King & Prince（キンプリ）は永瀬廉・髙橋海人の2人組男性グループ（STARTO ENTERTAINMENT）。2023年5月から現体制で活動。',
    'shiori':           '「しおりのなんとなく日常」は女性ひとり飲み・ソロ活グルメを発信するYouTubeチャンネル。居酒屋や飲み歩き動画が人気で登録者数35万人超。',
}

GROUP_COLORS = {
    'snowman':          '#3b82f6',
    'sixtones':         '#f97316',
    'naniwa':           '#a855f7',
    'equal_love':       '#ec4899',
    'notme':            '#8b5cf6',
    'neajoy':           '#6366f1',
    'nogizaka46':       '#ef4444',
    'sakurazaka46':     '#e11d48',
    'hinatazaka46':     '#f59e0b',
    'heysayjump':       '#10b981',
    'kingprince':       '#f472b6',
    'yonino':           '#14b8a6',
    'kamenashi':        '#f59e0b',
    'kamaitachi':       '#6b7280',
    'kodoku_no_gurume': '#78716c',
    'ginga':            '#8b5cf6',
    'timelesz':         '#0ea5e9',
    'shiori':           '#f43f5e',
}

GENRE_EMOJI = {
    'カフェ':   '☕',
    'ラーメン': '🍜',
    '焼肉':    '🥩',
    '寿司':    '🍣',
    'スイーツ': '🍰',
    '居酒屋':  '🍺',
    '和食':    '🍱',
    'もんじゃ': '🥘',
    '中華':    '🥟',
    '食事':    '🍽️',
    'カレー':  '🍛',
    '海鮮':    '🐟',
    'その他':  '🍴',
}


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text.strip('-')


def group_slug(group: str) -> str:
    return group.replace('_', '-')


def genre_slug(genre: str) -> str:
    table = {
        'カフェ': 'cafe', 'ラーメン': 'ramen', '焼肉': 'yakiniku',
        '寿司': 'sushi', 'スイーツ': 'sweets', '居酒屋': 'izakaya',
        '和食': 'washoku', 'もんじゃ': 'monjya', '中華': 'chuka',
        '食事': 'shokuji', 'カレー': 'curry', '海鮮': 'kaisen',
        'その他': 'others',
    }
    return table.get(genre, slugify(genre))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--min', type=int, default=5, help='最小件数（デフォルト5）')
    args = parser.parse_args()

    with open(SHOPS_JSON, encoding='utf-8') as f:
        shops = json.load(f)

    # 閉店を除いてカウント
    combo = defaultdict(list)
    for s in shops:
        if s.get('closed'):
            continue
        combo[(s['group'], s.get('genre', 'その他'))].append(s['id'])

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated = 0
    for (group, genre), ids in sorted(combo.items(), key=lambda x: -len(x[1])):
        if len(ids) < args.min:
            continue

        label = GROUP_LABELS.get(group, group)
        emoji = GENRE_EMOJI.get(genre, '🍴')
        color = GROUP_COLORS.get(group, '')
        bio = GROUP_BIO.get(group, '')
        gslug = group_slug(group)
        eslug = genre_slug(genre)
        slug_id = f'{gslug}-{eslug}'
        filename = f'{slug_id}.md'

        title = f'{label}が行った{genre}{len(ids)}選'
        description = f'{label}のメンバーが実際に訪れた{genre}スポットを{len(ids)}件まとめました。聖地巡礼・ロケ地めぐりの参考に。'

        # 関連ページ: 同グループの他ジャンル上位3件
        related_genres = [
            f'{gslug}-{genre_slug(g2)}'
            for (gr2, g2), ids2 in sorted(combo.items(), key=lambda x: -len(x[1]))
            if gr2 == group and g2 != genre and len(ids2) >= args.min
        ][:3]

        # 同ジャンルの他グループ上位3件
        related_groups = [
            f'{group_slug(gr2)}-{eslug}'
            for (gr2, g2), ids2 in sorted(combo.items(), key=lambda x: -len(x[1]))
            if g2 == genre and gr2 != group and len(ids2) >= args.min
        ][:3]

        front_matter_lines = [
            '---',
            f'title: "{title}"',
            f'description: "{description}"',
            f'group: {group}',
            f'genre: {genre}',
            f'group_label: "{label}"',
            f'slug_id: {slug_id}',
            f'shop_count: {len(ids)}',
        ]
        if color:
            front_matter_lines.append(f'group_color: "{color}"')
        if bio:
            front_matter_lines.append(f'group_bio: "{bio}"')
        if related_genres:
            front_matter_lines.append('related_genres:')
            for r in related_genres:
                front_matter_lines.append(f'  - {r}')
        if related_groups:
            front_matter_lines.append('related_groups:')
            for r in related_groups:
                front_matter_lines.append(f'  - {r}')
        front_matter_lines.append('---')

        content = '\n'.join(front_matter_lines) + '\n'

        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f'生成: {filename} ({len(ids)}件) → /list/{slug_id}/')
        generated += 1

    print(f'\n完了: {generated}ページ生成 → {OUTPUT_DIR}')


if __name__ == '__main__':
    main()
