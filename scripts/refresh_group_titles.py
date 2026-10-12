"""
refresh_group_titles.py
_group_pages/*.md の title / description / shop_count を、今の data/shops.json の店数で書き直す（本文はさわらない）。
検索では「グループ名＋聖地巡礼・ロケ地＋東京・ご飯」で探されるので、その言葉をタイトルの前の方に置く。
サイト名は head.html が付けるので、タイトルには入れない。build_pages.sh から実行する。
"""
import collections
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENRES = json.load(open(os.path.join(ROOT, '_data', 'genres.json'), encoding='utf-8'))
if isinstance(GENRES, list):
    GENRES = {g['key']: g for g in GENRES}


def main():
    shops = json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8'))
    changed = 0
    for f in sorted(os.listdir(os.path.join(ROOT, '_group_pages'))):
        path = os.path.join(ROOT, '_group_pages', f)
        text = open(path, encoding='utf-8').read()
        m = re.search(r'^group_key: "([^"]+)"', text, re.M)
        lm = re.search(r'^group_label: "([^"]+)"', text, re.M)
        if not m or not lm:
            continue
        g, label = m.group(1), lm.group(1)
        xs = [s for s in shops if g in (s.get('groups') or [s.get('group')])]
        if not xs:
            continue
        n = len(xs)
        pref = collections.Counter(s.get('prefecture') for s in xs if s.get('prefecture')).most_common(1)
        tokyo = pref and pref[0][0] == '東京都'
        gs = [GENRES.get(k, {}).get('label', k) for k, _ in collections.Counter(s.get('genre') for s in xs if s.get('genre') and s.get('genre') != 'others').most_common(3)]
        title = f'{label}の聖地巡礼・ロケ地グルメ{n}選' + ('（東京ほか）' if tokyo else '')
        drama = sum(1 for s in xs if s.get('source_type') == 'drama') > n / 2
        desc = (f'{label}{"に登場した" if drama else "が訪れた"}お店{n}軒の聖地巡礼・ロケ地まとめ。'
                + (f'{pref[0][0]}を中心に、' if pref else '')
                + f'{"・".join(gs)}などのお店を、出てきた動画・番組つきで地図から探せます。')[:160]
        new = re.sub(r'^title: ".*"$', f'title: "{title}"', text, count=1, flags=re.M)
        new = re.sub(r'^description: ".*"$', f'description: "{desc}"', new, count=1, flags=re.M)
        new = re.sub(r'^shop_count: \d+$', f'shop_count: {n}', new, count=1, flags=re.M)
        if new != text:
            open(path, 'w', encoding='utf-8').write(new)
            changed += 1
    print(f'グループページのタイトルを更新: {changed}件')


if __name__ == '__main__':
    main()
