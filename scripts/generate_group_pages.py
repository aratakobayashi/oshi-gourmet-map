#!/usr/bin/env python3
"""
generate_group_pages.py
_group_pages/{group}.md を24グループ分生成する。
Jekyll collection group_pages → /groups/{group}/ でビルドされる。
"""
import json, os
from collections import Counter

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOPS_JSON = os.path.join(ROOT, 'data', 'shops.json')
OUT_DIR   = os.path.join(ROOT, '_group_pages')
os.makedirs(OUT_DIR, exist_ok=True)

with open(SHOPS_JSON, encoding='utf-8') as f:
    shops = json.load(f)

GROUP_LABELS = {
    'yonino':           'よにのちゃんねる',
    'snowman':          'Snow Man',
    'sixtones':         'SixTONES',
    'naniwa':           'なにわ男子',
    'kamenashi':        '亀梨和也',
    'ginga':            '中丸雄一 銀河チャンネル',
    'kamaitachi':       'かまいたち',
    'kodoku_no_gurume': '孤独のグルメ',
    'heysayjump':       'Hey! Say! JUMP',
    'timelesz':         'timelesz',
    'equal_love':       '=LOVE',
    'notme':            '≠ME',
    'neajoy':           '≒JOY',
    'nogizaka46':       '乃木坂46',
    'hinatazaka46':     '日向坂46',
    'sakurazaka46':     '櫻坂46',
    'shiori':           'しおりのなんとなく日常',
    'kingprince':       'King & Prince',
    'arashi':           '嵐',
    'kimura':           '木村拓哉',
    'kpop_enhypen':     'ENHYPEN',
    'kpop_seventeen':   'SEVENTEEN',
    'kpop_riize':       'RIIZE',
    'kpop_nct':         'NCT',
}

GROUP_COLORS = {
    'yonino':           ('#e8537a', '#f7a1b5'),
    'snowman':          ('#3b82f6', '#93c5fd'),
    'sixtones':         ('#7c3aed', '#a78bfa'),
    'equal_love':       ('#f43f5e', '#fb923c'),
    'notme':            ('#0d9488', '#5eead4'),
    'neajoy':           ('#d946ef', '#f0abfc'),
    'sakurazaka46':     ('#e11d48', '#fda4af'),
    'nogizaka46':       ('#0ea5e9', '#7dd3fc'),
    'hinatazaka46':     ('#f59e0b', '#fde68a'),
    'naniwa':           ('#f97316', '#fbbf24'),
    'kamenashi':        ('#059669', '#6ee7b7'),
    'ginga':            ('#6366f1', '#a5b4fc'),
    'kamaitachi':       ('#8b5cf6', '#c4b5fd'),
    'kodoku_no_gurume': ('#92400e', '#d97706'),
    'heysayjump':       ('#ef4444', '#fbbf24'),
    'timelesz':         ('#1d4ed8', '#60a5fa'),
    'shiori':           ('#ec4899', '#f9a8d4'),
    'kingprince':       ('#f472b6', '#fbcfe8'),
    'arashi':           ('#dc2626', '#fb923c'),
    'kimura':           ('#0891b2', '#67e8f9'),
    'kpop_enhypen':     ('#7c3aed', '#a78bfa'),
    'kpop_seventeen':   ('#0ea5e9', '#7dd3fc'),
    'kpop_riize':       ('#ef4444', '#fca5a5'),
    'kpop_nct':         ('#10b981', '#6ee7b7'),
}

# グループごとの件数・代表ジャンルを集計
by_group = {}
for s in shops:
    g = s.get('group', '')
    if g not in by_group:
        by_group[g] = []
    by_group[g].append(s)

generated = 0
for group, label in GROUP_LABELS.items():
    group_shops = by_group.get(group, [])
    count = len(group_shops)
    c1, c2 = GROUP_COLORS[group]

    # 上位ジャンル最大3つ
    genre_counts = Counter(s.get('genre', '') for s in group_shops if s.get('genre'))
    top_genres = [g for g, _ in genre_counts.most_common(3) if g]
    genre_str = '・'.join(top_genres) if top_genres else 'グルメ'

    # 代表YouTubeサムネ（最初に見つかったyoutube_idを使用）
    youtube_id = next((s.get('youtube_id') for s in group_shops if s.get('youtube_id')), None)

    desc = (
        f'{label}が実際に訪れたグルメスポット{count}件をまとめています。'
        f'{genre_str}など多彩なお店をYouTube・テレビ番組から調査。'
        f'聖地巡礼の参考にどうぞ。'
    )[:160]

    title = f'{label}のグルメ聖地{count}選｜推しグルメ巡礼MAP'

    lines = [
        '---',
        f'group_key: "{group}"',
        f'group_label: "{label}"',
        f'group_color: "{c1}"',
        f'group_color2: "{c2}"',
        f'shop_count: {count}',
        f'title: "{title}"',
        f'description: "{desc}"',
    ]
    if youtube_id:
        lines.append(f'group_youtube_id: "{youtube_id}"')
    lines += ['---', '']

    out_path = os.path.join(OUT_DIR, f'{group}.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    generated += 1
    print(f'  {group:22} {count}件')

print(f'\n{generated}件生成完了 → {OUT_DIR}')
