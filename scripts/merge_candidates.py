"""
merge_candidates.py
調べた候補JSON（{"new":[...],"attach":[...]}）を確かめて data/shops.json に足す。
採用: confidence high/mid・visit_type visit・住所あり（needs_address でない）・youtube_id 11文字・国土地理院で番地まで一致（海外は除外）
attach: high/mid で、既存店に youtube_id がない場合だけ付ける。
使い方: python scripts/merge_candidates.py <候補.json> <group> [--write]
  group に - を渡すと、候補ごとの group 項目を使う（ジュニアCHANNELなど複数グループの候補）。
  候補の項目: name address prefecture city genre members visited_date youtube_id source_video_title
             source_url confidence(high/mid/low) visit_type(visit/...) needs_address closed ordered_items
書き込んだあとは bash scripts/build_pages.sh でページを作り直す。"""
import json, re, sys, time, hashlib, unicodedata, urllib.request, urllib.parse
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path, group = sys.argv[1], sys.argv[2]
write = '--write' in sys.argv
d = json.load(open(path))
raw = open(ROOT + '/data/shops.json').read(); shops = json.loads(raw)
by = {s['id']: s for s in shops}
def n(a): return re.sub(r'[\s　]', '', unicodedata.normalize('NFKC', a or ''))
def first(a): return re.split(r'[\s　]', unicodedata.normalize('NFKC', a or '').strip())[0]  # 建物名・階の前まで
KAN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
def kan2(s):
    s = n(s)
    def rep(m):
        t = m.group(1)
        if '十' in t:
            a, _, b = t.partition('十'); return str((KAN.get(a,1) if a else 1)*10 + (KAN.get(b,0) if b else 0))
        return str(KAN[t])
    return re.sub(r'([一二三四五六七八九十]+)(?=丁目|条)', rep, s)
def nums(a): return re.findall(r'\d+', kan2(first(a)))
names = {}
for s in shops:
    for gg in (s.get('groups') or [s.get('group')]):
        names.setdefault(gg, set()).add(n(s['name']))
added, attached, skipped = [], 0, []
for x in d.get('new', []):
    g = x.get('group') if group == '-' else group
    why = None
    if x.get('confidence') not in ('high', 'mid'): why = 'confidence'
    elif x.get('visit_type') != 'visit': why = 'visit_type'
    elif x.get('closed'): why = 'closed'
    elif x.get('needs_address') or not x.get('address'): why = 'address'
    elif not re.fullmatch(r'[\w-]{11}', x.get('youtube_id') or ''): why = 'youtube_id'
    elif not x.get('prefecture'): why = 'overseas'
    elif not g: why = 'no-group'
    elif n(x['name']) in names.get(g, set()): why = 'dup-name'
    if why: skipped.append((why, x['name'])); continue
    addr = x['address']
    q = urllib.parse.quote(re.split(r'[\s　]', addr)[0])
    try:
        r = json.load(urllib.request.urlopen('https://msearch.gsi.go.jp/address-search/AddressSearch?q=' + q, timeout=20))
    except Exception:
        r = []
    time.sleep(0.4)
    if not r: skipped.append(('geocode', x['name'])); continue
    title = r[0]['properties']['title']; lng, lat = r[0]['geometry']['coordinates']
    a, b = nums(addr), nums(title)
    unver = False
    if not b and n(addr).startswith(n(title)) and x.get('confidence') == 'high':
        unver = True  # 大字までしか分からない地方の住所。座標は地区の中心なので「近くの店」には出さない
    elif not b or (len(b) < 2 and '番地' not in title) or a[:len(b)] != b or n(title)[:5] != n(addr)[:5]:
        skipped.append(('geocode-mismatch', x['name'] + ' / ' + title)); continue
    sid = f"{g}-{hashlib.md5((x['name']+x['youtube_id']).encode()).hexdigest()[:8]}-{x['visited_date'].replace('-','')}"
    mem = '・'.join(x.get('members') or [])
    s = {'id': sid, 'name': x['name'], 'genre': x['genre'], 'prefecture': x['prefecture'], 'city': x.get('city',''),
         'address': addr, 'lat': lat, 'lng': lng, 'youtube_id': x['youtube_id'],
         'source_video_title': x['source_video_title'], 'source_video_url': 'https://www.youtube.com/watch?v=' + x['youtube_id'],
         'visited_date': x['visited_date'], 'members': x.get('members') or [], 'groups': [g], 'group': g,
         'description': (f"{mem}が" if mem else '') + 'YouTubeの動画で訪れたお店。', 'source_url': x.get('source_url',''), 'source_type': 'youtube'}
    if x.get('ordered_items'): s['ordered_items'] = x['ordered_items']
    if unver: s['location_unverified'] = True
    shops.append(s); names.setdefault(g, set()).add(n(x['name'])); added.append(s)
for a in d.get('attach', []):
    s = by.get(a.get('shop_id'))
    if not s or s.get('youtube_id') or a.get('confidence', 'low') not in ('high', 'mid'): continue
    s['youtube_id'] = a['youtube_id']; s['source_video_url'] = 'https://www.youtube.com/watch?v=' + a['youtube_id']
    if a.get('source_video_title'): s['source_video_title'] = a['source_video_title']
    attached += 1
print(f'追加 {len(added)} / 動画を付けた {attached} / 見送り {len(skipped)}')
for s in added: print('  +', s['name'], '|', s['address'])
for w, nm in skipped: print('  -', w, nm)
if write:
    open(ROOT + '/data/shops.json', 'w').write(json.dumps(shops, ensure_ascii=False, indent=2 if raw.startswith('[\n  {') else None) + ('\n' if raw.endswith('\n') else ''))
    print('書き込みました')
