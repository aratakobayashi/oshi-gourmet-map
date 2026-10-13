"""オモウマい店（中京テレビ）: 公式の放送内容フィード /omouma/feed/onair-1.json（新しい5回分）の「店名：… ■住所：…」。
紹介されたメニュー（値段つき）は「頼んだもの」ではないので ordered_items にしない（ジャンルの見当にだけ使う）。"""
import re

from common import days_before, fetch_json, genre_of, mk, nz, text_of, today

FEED = 'https://www.ctv.co.jp/omouma/feed/onair-%d.json'
PROGRAM = 'オモウマい店'
POSTER = 'https://image.tmdb.org/t/p/w500/jKhI5P8VlGJzjw35BJUvdvSaJrI.jpg'
TMDB_ID = 290707


def rows_of(it):
    date = it['publish_date'][:10]
    title = nz(text_of(it['data']['title']))
    lines = [re.sub(r'\s+', ' ', l).strip() for l in nz(text_of(it['data']['text'])).replace('\xa0', ' ').split('\n')]
    rows, seg, cur = [], '', None
    for l in filter(None, lines):
        if (re.match(r'^[～〜~].*[～〜~]$', l) or l.startswith('～') or l.endswith('～')) and '店名' not in l:
            seg = l.strip('～〜~ ')
            if cur:
                rows.append(cur)
                cur = None
            continue
        m = re.search(r'店名\s*[:：]\s*(.*?)(?:\s*■\s*住所\s*[:：]\s*(.*))?$', l)
        if m:
            if cur:
                rows.append(cur)
            cur = dict(name=m.group(1).strip(), address=(m.group(2) or '').strip(), date=date, title=title, seg=seg,
                       notes=[], menu=[], url='https://www.ctv.co.jp/omouma/article/%s.html' % it['item_id'])
            continue
        if cur is None:
            continue
        m = re.search(r'住所\s*[:：]\s*(.*)$', l)
        if m and not cur['address']:
            cur['address'] = m.group(1).strip()
        elif l.startswith('※') or '移転' in l or '閉店' in l:
            cur['notes'].append(l)
        elif '円' in l or l.startswith('■'):
            cur['menu'].append(l)
    if cur:
        rows.append(cur)
    return rows


def collect(cfg, state, log):
    last = state.get('last_date', '2000-01-01')
    since = days_before(last, cfg.get('lookback_days', 14))
    now = today()
    items = fetch_json(FEED % 1)
    if items is None:
        raise RuntimeError('フィードが取れない')
    new, skipped, newest = [], [], last
    for it in items:
        date = it['publish_date'][:10]
        if date <= since or date > now:
            continue
        newest = max(newest, date)
        for r in rows_of(it):
            name = r['name']
            note = ''
            if '※' in name:
                name, note = [x.strip() for x in name.split('※', 1)]
            addr = re.sub(r'^店舗・', '', r['address'])
            notes = ' '.join(r['notes']) + ' ' + note + ' ' + addr
            mv = re.search(r'移転先[^：:]*[：:]\s*(\S+)', notes)
            addr = re.sub(r'\s*(※|移転先).*$', '', addr)
            if mv:
                addr = mv.group(1)
            if re.search(r'閉店(しました|いたしました|しております|しています|済|$|\s)|\d+日閉店|日に閉店', notes) and '時閉店' not in notes:
                skipped.append(('閉店', name))
                continue
            y, mo, d = date.split('-')
            sub = r['seg'] or r['title']
            new.append(mk(name=name, address=addr, genre=genre_of(name, ' '.join(r['menu'])), members=[], visited_date=date,
                          program=PROGRAM, source_video_title=f'{PROGRAM} {sub}（{int(y)}年{int(mo)}月{int(d)}日 中京テレビ・日本テレビ系）',
                          source_url=r['url'], thumbnail_url=POSTER, tmdb_id=TMDB_ID, tmdb_type='tv', group='omouma'))
    return {'new': new, 'skipped': skipped, 'state': {'last_date': newest}}
