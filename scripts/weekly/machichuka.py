"""町中華で飲ろうぜ（BS-TBS）: 公式の店舗一覧XML → 新しい回の店ページ（店名・場所・放送回・初回放送日・行った人）。
店ページの食べログリンクは番組公式が載せているもの（tabelog_verified）。食べログ自体にはアクセスしない。"""
import re

from common import days_before, fetch_text, mk, nz, text_of, today

XML = 'https://bs.tbs.co.jp/machichuka/xml/shop.xml'
BASE = 'https://bs.tbs.co.jp'
PROGRAM = '町中華で飲ろうぜ'
POSTER = 'https://image.tmdb.org/t/p/w500/6yeoOYU6Evt9nPV91ZsYm05zAkz.jpg'
TMDB_ID = 273426


def collect(cfg, state, log):
    last = state.get('last_date', '2000-01-01')
    since = days_before(last, cfg.get('lookback_days', 14))  # 店ページが後から埋まる回を拾い直す
    now = today()
    x = fetch_text(XML)
    if not x:
        raise RuntimeError('店舗一覧XMLが取れない')
    new, skipped, newest = [], [], last
    seen = set()
    for it in re.findall(r'<item>(.*?)</item>', x, re.S):
        g = lambda t: [v.strip() for v in re.findall(r'<%s>(.*?)</%s>' % (t, t), it, re.S)]
        oa, link = g('oa')[0], g('link')[0]
        date = f'{oa[:4]}-{oa[4:6]}-{oa[6:8]}'
        if date <= since or date > now or link in seen:
            continue
        seen.add(link)
        url = BASE + link
        page = fetch_text(url)
        m = re.search(r'<dl class="store-detail__information">(.*?)</dl>', page or '', re.S)
        if not m:
            skipped.append(('店ページに店舗情報なし', url))
            continue
        info = {text_of(a): b for a, b in re.findall(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>', m.group(1), re.S)}
        name = text_of(info.get('店名', ''))
        if re.search(r'閉店|閉業|営業終了', text_of(m.group(1))):
            skipped.append(('閉店', name))
            continue
        name = re.sub(r'\s*[【\[(（]閉店[】\])）]\s*', '', name).strip()
        addr = re.sub(r'\s+', ' ', text_of(info.get('場所', '')))
        dm = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text_of(info.get('初回放送日', '')))
        if dm:
            date = '%s-%02d-%02d' % (dm.group(1), int(dm.group(2)), int(dm.group(3)))
        if date > now:
            continue
        members = []
        for w in re.split(r'[、,，＆&\s]+', text_of(info.get('行った人', ''))):
            w = re.sub(r'^ゲスト[：:]', '', w.strip())
            w = re.sub(r'[（(][^）)]*[）)]$', '', w).strip()
            w = re.sub(r'アナウンサー$', '', w).strip()
            if w and w not in members:
                members.append(w)
        members = members or g('sort_cast')
        ep = text_of(info.get('放送回', ''))
        epm = re.match(r'#(\d+)\s*「?(.*?)」?$', ep)
        title = re.sub(r'<!\[CDATA\[|\]\]>', '', g('title')[0]).strip()
        sm = re.search(r'（([^（）]*)）$', title)
        epno = epm.group(1) if epm else ''
        sub = (epm.group(2) if epm else '') or (sm.group(1) if sm else '')
        r = mk(name=nz(name), address=addr, genre='chuka', members=members, visited_date=date, program=PROGRAM,
               source_video_title=(f'{PROGRAM} #{epno} {sub}（{date} BS-TBS）' if epno else f'{PROGRAM} {sub}（{date} BS-TBS）'),
               source_url=url, thumbnail_url=POSTER, tmdb_id=TMDB_ID, tmdb_type='tv', group='machichuka')
        tl = re.search(r'href="(https://tabelog\.com/[a-z]+/A\d+/A\d+/\d+/)"', info.get('食べログ', ''))
        if tl:  # 番組公式ページに載っている食べログの店ページ
            r['tabelog_url'] = tl.group(1)
            r['tabelog_verified'] = True
        new.append(r)
        newest = max(newest, date)
    return {'new': new, 'skipped': skipped, 'state': {'last_date': newest}}
