"""
add_group.py
新しいグループ（推し）を足す。_data/groups.json に表示名を入れ、_group_pages/<id>.md を作る。
タイトル・説明・店数は refresh_group_titles.py（build_pages.sh で実行）が店のデータから書き直す。
使い方: python scripts/add_group.py <id> <表示名> <色 #rrggbb> [<薄い色 #rrggbb>]
例:    python scripts/add_group.py acees "ACEes" "#0f766e"
id は英小文字・数字・_ だけ（URL は /groups/<id の _ を - にしたもの>/）。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lighten(hex_color, k=0.55):
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return '#%02x%02x%02x' % tuple(int(c + (255 - c) * k) for c in (r, g, b))


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    gid, label, color = sys.argv[1], sys.argv[2], sys.argv[3]
    color2 = sys.argv[4] if len(sys.argv) > 4 else lighten(color)
    if not re.fullmatch(r'[a-z0-9_]+', gid):
        raise SystemExit('id は英小文字・数字・_ だけにしてください')
    path = os.path.join(ROOT, '_data', 'groups.json')
    groups = json.load(open(path, encoding='utf-8'))
    groups[gid] = label
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(groups.items())), f, ensure_ascii=False, indent=2)
        f.write('\n')
    page = os.path.join(ROOT, '_group_pages', gid + '.md')
    if not os.path.exists(page):
        with open(page, 'w', encoding='utf-8') as f:
            f.write('\n'.join(['---', f'group_key: "{gid}"', f'group_label: "{label}"', f'group_color: "{color}"',
                               f'group_color2: "{color2}"', 'shop_count: 0', f'title: "{label}の聖地巡礼・ロケ地グルメ"',
                               f'description: "{label}が訪れたお店の聖地巡礼・ロケ地まとめ。"', '---', '']))
    print(f'グループを追加: {gid}（{label}）')


if __name__ == '__main__':
    main()
