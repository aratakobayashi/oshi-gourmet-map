"""会場ガイド（_guides/<会場>.html）の「泊まる」の章の最初の段落のあとに {% include venue-stay.html %} を置く（何度実行しても同じ）"""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venues = json.load(open(os.path.join(ROOT, '_data/venues.json'), encoding='utf-8'))
n = 0
for key in venues:
    p = os.path.join(ROOT, '_guides', key + '.html')
    if not os.path.exists(p):
        continue
    t = open(p, encoding='utf-8').read()
    if 'venue-stay.html' in t:
        continue
    m = re.search(r'<h2>[^<]*泊まる[^<]*</h2>\s*<p>.*?</p>', t, re.S)
    if not m:
        print('見つからない', key)
        continue
    t = t[:m.end()] + '\n{% include venue-stay.html %}' + t[m.end():]
    open(p, 'w', encoding='utf-8').write(t)
    n += 1
print('入れた', n)
