"""
merge_candidates.py
調べた候補JSON（{"new":[...],"attach":[...]}）を確かめて data/shops.json に足す。
採用: confidence high/mid・visit_type visit・住所あり（needs_address でない）・youtube_id 11文字・国土地理院で番地まで一致（海外は除外）
attach: high/mid で、既存店に youtube_id がない場合だけ付ける。
使い方: python scripts/merge_candidates.py <候補.json> <group> [--write] [--report <結果.json>]
  group に - を渡すと、候補ごとの group 項目を使う（ジュニアCHANNELなど複数グループの候補）。
  候補の項目: name address prefecture city genre members visited_date youtube_id（または thumbnail_url=TMDB画像・tmdb_id・program） source_video_title
             source_url confidence(high/mid/low) visit_type(visit/...) needs_address closed ordered_items
             tabelog_url＋tabelog_verified（番組公式ページに載っている食べログ） hotpepper_url（ホットペッパーAPIで決めた店）
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
    return re.sub(r'([一二三四五六七八九十]+)(?=丁目|丁|条|地割|号)', rep, s)
def nums(a): return re.findall(r'\d+', kan2(first(a)))
def base(a):
    # 比べやすい形: 郡の名前・大字・字を除き、数字より前（町名まで）だけ
    s = kan2(first(a))
    s = re.sub(r'(?<=[都道府県])[^都道府県市区町村]{1,6}郡', '', s)
    s = s.replace('大字', '').replace('ヶ', 'ケ').replace('ゝ', 'ス')
    s = re.sub(r'(?<=[市区町村])字', '', s)
    return re.split(r'\d', s)[0].rstrip('丁目番地号の第')
def same_place(addr, title):
    a, b = base(addr), base(title)
    return bool(b) and (a.startswith(b) or b.startswith(a))
def key(s):  # 同じ店かどうか: 店名＋町名まで（同じ名前の別の店を残すため）
    return n(s['name']) + '|' + base(s.get('address') or '')
names = {}
for s in shops:
    for gg in (s.get('groups') or [s.get('group')]):
        names.setdefault(gg, set()).add(key(s))
added, attached, skipped = [], 0, []
for x in d.get('new', []):
    g = x.get('group') if group == '-' else group
    why = None
    if x.get('confidence') not in ('high', 'mid'): why = 'confidence'
    elif x.get('visit_type') != 'visit' and x.get('relation') != 'guest_favorite': why = 'visit_type'
    elif x.get('closed'): why = 'closed'
    elif x.get('needs_address') or not x.get('address'): why = 'address'
    elif not re.fullmatch(r'[\w-]{11}', x.get('youtube_id') or '') and not (x.get('thumbnail_url') or '').startswith('https://image.tmdb.org/'): why = 'no-image'
    elif not x.get('prefecture'): why = 'overseas'
    elif not g: why = 'no-group'
    elif key(x) in names.get(g, set()): why = 'dup-name'
    if why: skipped.append(dict(why=why, name=x['name'], group=g, detail='')); continue
    addr = x['address']
    q = urllib.parse.quote(re.split(r'[\s　]', addr)[0])
    try:
        r = json.load(urllib.request.urlopen('https://msearch.gsi.go.jp/address-search/AddressSearch?q=' + q, timeout=20))
    except Exception:
        r = []
    time.sleep(0.4)
    if not r: skipped.append(dict(why='geocode', name=x['name'], group=g, detail=addr)); continue
    title = r[0]['properties']['title']; lng, lat = r[0]['geometry']['coordinates']
    a, b = nums(addr), nums(title)
    unver = False
    if not same_place(addr, title) and not (len(b) >= 2 and a[:len(b)] == b and n(title)[:3] == n(addr)[:3]):
        skipped.append(dict(why='geocode-mismatch', name=x['name'], group=g, detail=addr + ' → ' + title)); continue
    if not b or (len(b) < 2 and not re.search(r'番地?$|番\d', kan2(title))):
        if x.get('confidence') != 'high':
            skipped.append(dict(why='geocode-coarse', name=x['name'], group=g, detail=addr + ' → ' + title)); continue
        unver = True  # 町名・大字までしか分からない住所。座標はその地区なので「近くの店」には出さない
    elif a[:len(b)] != b:
        skipped.append(dict(why='geocode-mismatch', name=x['name'], group=g, detail=addr + ' → ' + title)); continue
    sid = f"{g}-{hashlib.md5((x['name']+(x.get('youtube_id') or x['source_video_title'])).encode()).hexdigest()[:8]}-{(x.get('visited_date') or '').replace('-','')}"
    mem = '・'.join(x.get('members') or [])
    yt = x.get('youtube_id') or ''
    s = {'id': sid, 'name': x['name'], 'genre': x['genre'], 'prefecture': x['prefecture'], 'city': x.get('city',''),
         'address': addr, 'lat': lat, 'lng': lng,
         'source_video_title': x['source_video_title'],
         'visited_date': x.get('visited_date') or '', 'members': x.get('members') or [], 'groups': [g], 'group': g,
         'description': (f"{mem}が" if mem else '') + 'YouTubeの動画で訪れたお店。', 'source_url': x.get('source_url',''), 'source_type': 'youtube'}
    if sid in {s0['id'] for s0 in shops}: skipped.append(dict(why='dup-id', name=x['name'], group=g, detail='')); continue
    if yt:
        s['youtube_id'] = yt; s['source_video_url'] = 'https://www.youtube.com/watch?v=' + yt
    else:  # テレビ番組・ドラマ（TMDBの画像）
        s['source_type'] = x.get('source_type') or 'tv'
        s['thumbnail_url'] = x['thumbnail_url']
        if x.get('tmdb_id'): s['tmdb_id'] = x['tmdb_id']; s['tmdb_type'] = x.get('tmdb_type') or 'tv'
        verb = '紹介した' if x.get('relation') == 'guest_favorite' else '訪れた'  # ゲストが番組で挙げた店（人生最高レストランなど）
        s['description'] = (f"{mem}が" if mem else '') + f"『{x.get('program') or x['source_video_title']}』で{verb}お店。"
    if x.get('ordered_items'): s['ordered_items'] = x['ordered_items']
    m = re.match(r'https://tabelog\.com/[a-z]+/A\d+/A\d+/\d+/', x.get('tabelog_url') or '')
    if m and x.get('tabelog_verified'):  # 番組公式ページが載せている食べログの店ページ（食べログにはアクセスしない）
        s['tabelog_url'] = m.group(0); s['tabelog_verified'] = True
    if re.match(r'https://www\.hotpepper\.jp/strJ\d+/$', x.get('hotpepper_url') or ''):  # ホットペッパーAPIで決めた店
        s['hotpepper_url'] = x['hotpepper_url']
    if unver: s['location_unverified'] = True
    shops.append(s); names.setdefault(g, set()).add(key(x)); added.append(s)
for a in d.get('attach', []):
    s = by.get(a.get('shop_id'))
    if not s or s.get('youtube_id') or a.get('confidence', 'low') not in ('high', 'mid'): continue
    s['youtube_id'] = a['youtube_id']; s['source_video_url'] = 'https://www.youtube.com/watch?v=' + a['youtube_id']
    if a.get('source_video_title'): s['source_video_title'] = a['source_video_title']
    attached += 1
print(f'追加 {len(added)} / 動画を付けた {attached} / 見送り {len(skipped)}')
for s in added: print('  +', s['name'], '|', s['address'])
for k in skipped: print('  -', k['why'], k['name'] + (' / ' + k['detail'] if k['detail'] else ''))
if '--report' in sys.argv:  # scripts/weekly/run.py が Summary に使う
    json.dump({'added': [{k: a.get(k, '') for k in ('id', 'name', 'group', 'address', 'source_video_title')} for a in added],
               'attached': attached, 'skipped': skipped},
              open(sys.argv[sys.argv.index('--report') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if write:
    open(ROOT + '/data/shops.json', 'w').write(json.dumps(shops, ensure_ascii=False, indent=2 if raw.startswith('[\n  {') else None) + ('\n' if raw.endswith('\n') else ''))
    print('書き込みました')
