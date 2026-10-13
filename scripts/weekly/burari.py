"""ぶらり途中下車の旅（日本テレビ）: 公式の記事データ /burari/articles.js の「おじゃましたところ」
（見出しが店名、【所番地/所在地/住所】が住所）。傑作選（再放送）は除く。
店名で「その場で食べる店」と分かるものだけ（持ち帰りの菓子・パン、工房・施設は外す。手作業の判定と照らして約96%一致）。"""
import json
import re

from common import days_before, fetch_text, genre_of, is_restaurant, mk, nz, text_of, today

JS = 'https://www.ntv.co.jp/burari/articles.js'
PROGRAM = 'ぶらり途中下車の旅'
POSTER = 'https://image.tmdb.org/t/p/w500/3Ys7RAWxcpV7rLBghqq7nsklyop.jpg'
TMDB_ID = 57952


def collect(cfg, state, log):
    last = state.get('last_date', '2000-01-01')
    since = days_before(last, cfg.get('lookback_days', 14))
    now = today()
    s = fetch_text(JS)
    if not s:
        raise RuntimeError('articles.js が取れない')
    arts = json.loads(s[s.index('['):s.rstrip().rstrip(';').rindex(']') + 1])
    new, skipped, newest = [], [], last
    for a in arts:
        d = a.get('data') or {}
        title, body = d.get('title') or '', d.get('body') or ''
        if not re.search(r'【(所番地|所在地|住所)】', body):
            continue
        T = text_of(body)
        m = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*放送', nz(T))
        if not m:
            continue
        date = '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3)))
        if date <= since or date > now:
            continue
        if '傑作選' in title:
            skipped.append(('傑作選（再放送）', title))
            continue
        m2 = re.search(r'旅人は[、,]?\s*(.+?)[。\n]', T)
        m3 = re.match(r'(.+?)が(.+?)で(?:ぶらり途中下車の旅|途中下車)', title)
        m4 = re.search(r'放送の「ぶらり途中下車の旅」は(.+?)の旅', T)
        line = m4.group(1) if m4 else (m3.group(2) if m3 else '')
        trav = m2.group(1).strip() if m2 else (m3.group(1) if m3 else '')
        members = [re.sub(r'（.*?）|\(.*?\)', '', x).strip() for x in re.split(r'[・、]', trav) if x.strip()]
        url = 'https://www.ntv.co.jp/burari/articles/%s%s.html' % (a['content_id'], a['item_id'])
        src = f"{PROGRAM} {line}の旅 旅人：{'・'.join(members)}（{date} 日本テレビ）" if line else f"{PROGRAM} 旅人：{'・'.join(members)}（{date} 日本テレビ）"
        lastname = ''
        for sec in re.split(r'<h2[^>]*>', body)[1:]:
            h, _, rest = sec.partition('</h2>')
            name = text_of(h).strip() or lastname
            lastname = name
            st = text_of(rest)
            ma = re.search(r'【(?:所番地|所在地|住所)】\s*\n?\s*([^\n【]+)', st)
            if not ma:
                continue
            mst = re.match(r'(.*?)[（(]([^（()）]*駅[^（()）]*)[）)]\s*$', name)
            nm = nz(mst.group(1).strip() if mst else name).strip()
            desc = st.split('【')[0].strip()
            if not is_restaurant(nm, desc):
                skipped.append(('飲食店と言い切れない（持ち帰り・施設など）', nm))
                continue
            r = mk(name=nm, address=ma.group(1).strip(), genre=genre_of(nm, desc[:60]), members=members, visited_date=date,
                   program=PROGRAM, source_video_title=src, source_url=url, thumbnail_url=POSTER, tmdb_id=TMDB_ID,
                   tmdb_type='tv', group='burari')
            new.append(r)
        newest = max(newest, date)
    return {'new': new, 'skipped': skipped, 'state': {'last_date': newest}}
