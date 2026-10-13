"""YouTube チャンネルの新しい動画の説明文から店を拾う（YouTube Data API。YOUTUBE_API_KEY）。
sources.json の youtube_channels に1チャンネル1項目。format（説明文の書式）は次のどちらか:

  "credit_hotpepper"  説明文の「撮影協力」の下の行（空行まで）を店名とみなし、ホットペッパーグルメAPI（HOTPEPPER_API_KEY）で
                      店名が完全に一致する店が全国で1軒だけのときに、その住所を使う（乃木坂配信中など）。
                      ホットペッパーに載る＝飲食店なので、会場・工場などの撮影協力は自然に外れる。
  "name_address"      説明文に「店名：…」「住所：…」の行がある（name_label / address_label で見出しの言葉を変えられる）。

出演者は「出演」の行（「出演\n乃木坂46 A、B」）、なければ members に書いた名前。
"""
import datetime
import os
import re
import urllib.parse

from common import JST, days_before, fetch_json, genre_of, mk, norm_name, nz, today

API = 'https://www.googleapis.com/youtube/v3/'
HP_API = 'https://webservice.recruit.co.jp/hotpepper/gourmet/v1/'
SKIP_TITLE = r'お取り寄せ|お弁当|弁当|差し入れ|デリバリー|Uber|出前|手作り|料理してみた|作ってみた|工場見学|ライブ配信|生配信|乃木坂ニュース|工事中」'
HP_GENRE = {'居酒屋': 'izakaya', 'ダイニングバー・バル': 'izakaya', 'バー・カクテル': 'izakaya', '和食': 'washoku', '洋食': 'shokuji',
            'イタリアン・フレンチ': 'shokuji', '中華': 'chuka', '焼肉・ホルモン': 'yakiniku', '韓国料理': 'shokuji', 'アジア・エスニック料理': 'shokuji',
            '各国料理': 'shokuji', 'カラオケ・パーティ': 'others', 'ラーメン': 'ramen', 'お好み焼き・もんじゃ': 'washoku',
            'カフェ・スイーツ': 'cafe', '創作料理': 'shokuji', 'その他グルメ': 'shokuji'}


def yt(ep, **p):
    key = os.environ.get('YOUTUBE_API_KEY')
    if not key:
        raise RuntimeError('YOUTUBE_API_KEY がない')
    p['key'] = key
    return fetch_json(API + ep + '?' + urllib.parse.urlencode(p), robots=False)  # 公式API（規約に従って使う）


def recent_videos(channel_id, since):
    """チャンネルのアップロード一覧（新しい順）から、since より後に公開された動画（snippet つき）"""
    ids, tok = [], None
    for _ in range(4):
        kw = dict(part='contentDetails', playlistId='UU' + channel_id[2:], maxResults=50)
        if tok:
            kw['pageToken'] = tok
        r = yt('playlistItems', **kw)
        stop = False
        for it in r.get('items', []):
            pub = it['contentDetails'].get('videoPublishedAt') or ''
            if pub and jst_date(pub) <= since:
                stop = True
                continue
            ids.append(it['contentDetails']['videoId'])
        tok = r.get('nextPageToken')
        if stop or not tok:
            break
    out = []
    for i in range(0, len(ids), 50):
        out += yt('videos', part='snippet', id=','.join(ids[i:i + 50])).get('items', [])
    return out


def jst_date(iso):
    t = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00'))
    return t.astimezone(JST).date().isoformat()


def section(desc, head):
    """「撮影協力」などの見出しの下、空行までの行"""
    lines = desc.split('\n')
    for i, l in enumerate(lines):
        m = re.match(r'^\s*[■▼【]?\s*(%s)\s*[】]?\s*[:：]?\s*(.*)$' % head, l)
        if not m:
            continue
        out = [m.group(2).strip()] if m.group(2).strip() else []
        for l2 in lines[i + 1:]:
            if not l2.strip() or re.match(r'^\s*[■▼]', l2):
                break
            out.append(l2.strip())
        return out
    return []


def members_of(desc, cfg):
    perf = section(desc, '出演')
    names = []
    for l in perf:
        l = re.sub(r'^(乃木坂46|櫻坂46|日向坂46)\s*', '', nz(l))
        names += [x.strip() for x in re.split(r'[、,，・/／]', l) if x.strip()]
    return names or list(cfg.get('members') or [])


def hp_lookup(name, log):
    key = os.environ.get('HOTPEPPER_API_KEY')
    if not key:
        return None, 'HOTPEPPER_API_KEY がない'
    q = urllib.parse.urlencode({'key': key, 'keyword': name, 'count': 10, 'format': 'json'})
    d = fetch_json(HP_API + '?' + q, robots=False)  # 公式API（クレジット表記はサイトのフッター）
    shops = (d or {}).get('results', {}).get('shop', [])
    want = norm_name(name)
    exact = [s for s in shops if norm_name(s.get('name')) == want]
    if len(exact) == 1:
        return exact[0], ''
    if len(exact) > 1:
        return None, f'ホットペッパーに同じ名前が{len(exact)}軒（どの店か決められない）'
    return None, 'ホットペッパーで店名が一致する店なし'


def collect_channel(ch, state, log):
    fmt = ch.get('format') or ''
    if fmt not in ('credit_hotpepper', 'name_address'):
        return [], [('説明文の書式が未設定（sources.json の format）', ch.get('name', ch.get('channel_id')))], state
    last = state.get('last_date', '2000-01-01')
    since = days_before(last, ch.get('lookback_days', 14))
    now = today()
    new, skipped, newest = [], [], last
    for v in recent_videos(ch['channel_id'], since):
        s = v['snippet']
        date = jst_date(s['publishedAt'])
        if date <= since or date > now:
            continue
        newest = max(newest, date)
        title, desc = s['title'], s.get('description') or ''
        if re.search(ch.get('skip_title') or SKIP_TITLE, title):
            continue
        base = dict(members=members_of(desc, ch), visited_date=date, youtube_id=v['id'], source_video_title=title,
                    source_url='https://www.youtube.com/watch?v=' + v['id'], group=ch['group'],
                    program=ch.get('name', ''))
        if fmt == 'credit_hotpepper':
            for line in section(desc, ch.get('credit_label') or '撮影協力'):
                name = re.sub(r'^[・\-‐*●]\s*', '', nz(line)).strip(' 「」')
                if not name or re.match(r'https?://', name):
                    continue
                shop, why = hp_lookup(name, log)
                if not shop:
                    skipped.append((why, f'{name}（{title[:30]}）'))
                    continue
                r = mk(name=name, address=shop.get('address', ''), genre=HP_GENRE.get((shop.get('genre') or {}).get('name'), '') or genre_of(name),
                       confidence='mid', **base)
                r['hotpepper_url'] = (shop.get('urls') or {}).get('pc', '').split('?')[0]
                new.append(r)
        else:
            nl = ch.get('name_label') or '店名|店舗名|お店'
            al = ch.get('address_label') or '住所|所在地'
            cur = None
            for l in desc.split('\n'):
                l = nz(l).strip()
                m = re.match(r'^[■▼【・]?\s*(?:%s)\s*[】]?\s*[:：]\s*(.+)$' % nl, l)
                if m:
                    cur = m.group(1).strip()
                    continue
                m = re.match(r'^[■▼【・]?\s*(?:%s)\s*[】]?\s*[:：]\s*(.+)$' % al, l)
                if m and cur:
                    new.append(mk(name=cur, address=m.group(1).strip(), genre=genre_of(cur), confidence='high', **base))
                    cur = None
    return new, skipped, {'last_date': newest}


def collect(cfg, state, log):
    new, skipped, st = [], [], {}
    for ch in cfg.get('channels', []):
        if not ch.get('enabled', True):
            continue
        cid = ch['channel_id']
        try:
            n, sk, s2 = collect_channel(ch, state.get(cid, {}), log)
        except Exception as e:
            skipped.append(('チャンネルの取得に失敗', f"{ch.get('name', cid)}: {e}"))
            s2 = state.get(cid, {})
            n, sk = [], []
        log(f"  {ch.get('name', cid)}: 候補 {len(n)}")
        new += n
        skipped += sk
        st[cid] = s2
    return {'new': new, 'skipped': skipped, 'state': st}
