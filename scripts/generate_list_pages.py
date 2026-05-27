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
    'miruwz':           'miruwz',
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
