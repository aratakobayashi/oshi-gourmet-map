"""
course_stops.py
まとめ記事の「半日で巡るなら」を、front matter の courses から道順のリスト（<ol class="stops">）にする。
手描き風のコース図（post_course.py の course-<n>.svg）の代わり。何度実行しても同じ結果。

  courses:
    - title: "押上から両国へ"
      stops: [店のID, ...]          # 回る順
      labels: ["ソラマチ", ...]      # 店名の代わりに出す短い名前（省略時は店名）
      legs: ["半蔵門線で1駅", ...]   # 次の店までの移動（事実だけ。省略可）。直線距離は自動で添える

本文の <figure class="fig course">…course-<n>.svg…</figure> か、前に作った <!-- stops:<n> -->…<!-- /stops --> を置き換える。
使い方: python scripts/course_stops.py <記事のslug>
"""
import glob, html, json, math, os, re, sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a['lat'], a['lng'], b['lat'], b['lng']))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def place(s):
    a = s.get('address') or ''
    rest = a.replace(s.get('prefecture') or '', '', 1).replace(s.get('city') or '', '', 1)
    town = re.split(r'[0-9０-９]', rest)[0].strip()
    m = re.match(r'([0-9０-９]+)', rest[len(town):].strip())
    chome = f'{int(m.group(1))}丁目' if m and re.match(r'[0-9０-９]+[-－‐丁]', rest[len(town):].strip()) else ''
    pre = '' if s.get('prefecture') == '東京都' else (s.get('prefecture') or '')
    return f'{pre}{s.get("city") or ""}{town}{chome}'


def build(n, course, S, C):
    ids = [str(x) for x in course.get('stops') or []]
    labels = course.get('labels') or []
    legs = course.get('legs') or []
    items = []
    for i, sid in enumerate(ids):
        s, c = S.get(sid), C.get(sid) or {}
        if not s:
            continue
        name = labels[i] if i < len(labels) and labels[i] else s['name']
        ms = s.get('members') or []
        mem = '・'.join(ms) if len(ms) <= 3 else f'メンバー{len(ms)}人'
        sub = place(s) + (f'／{mem}' if mem else '')
        li = f'  <li><a href="{c.get("u", "")}"><b>{html.escape(name)}</b><span>{html.escape(sub)}</span></a>'
        if i + 1 < len(ids) and S.get(ids[i + 1]) and s.get('lat') and S[ids[i + 1]].get('lat'):
            d = km(s, S[ids[i + 1]])
            leg = legs[i] if i < len(legs) and legs[i] else ''
            dist = f'直線で約{d:.1f}km'
            li += f'<small>次へ：{html.escape(leg)}（{dist}）</small>' if leg else f'<small>次のお店まで{dist}</small>'
        items.append(li + '</li>')
    return (f'<!-- stops:{n} -->\n<ol class="stops">\n' + '\n'.join(items) + '\n</ol>\n'
            '<p class="note">距離はお店どうしの直線距離です。営業日は各お店の公式情報で確かめてください。</p>\n<!-- /stops -->')


def main():
    slug = sys.argv[1]
    path = glob.glob(os.path.join(ROOT, '_posts', f'*-{slug}.md'))[0]
    t = open(path, encoding='utf-8').read()
    fm = yaml.safe_load(t.split('---')[1]) or {}
    S = {s['id']: s for s in json.load(open(os.path.join(ROOT, 'data/shops.json'), encoding='utf-8'))}
    C = json.load(open(os.path.join(ROOT, '_data/shop_cards.json'), encoding='utf-8'))
    for n, course in enumerate(fm.get('courses') or [], 1):
        block = build(n, course, S, C)
        pat_fig = re.compile(r'<figure class="fig course"><img src="[^"]*/course-%d\.svg".*?</figure>' % n, re.S)
        pat_old = re.compile(r'<!-- stops:%d -->.*?<!-- /stops -->' % n, re.S)
        if pat_old.search(t):
            t = pat_old.sub(lambda m: block, t)
        elif pat_fig.search(t):
            t = pat_fig.sub(lambda m: block, t)
        else:
            print('  見つからない: course', n)
        svg = os.path.join(ROOT, 'assets/img/posts', slug, f'course-{n}.svg')
        if os.path.exists(svg):
            os.remove(svg)
    open(path, 'w', encoding='utf-8').write(t)
    print(slug, len(fm.get('courses') or []), 'courses')


if __name__ == '__main__':
    main()
