"""メシドラ ～兼近＆真之介のグルメドライブ～（日本テレビ）: 公式の記事データ /meshidora/articles.js（2023-10 以降の全回が1つのJSON）から、
MC（兼近大樹・満島真之介）とゲストが訪れた店を拾う。

- 1記事＝1回の放送（「OAまとめ」「見どころ」）。放送日は本文の「M月D日（曜）」（記事の公開日に近い年）。なければ公開日
- 出演者は記事の cast_tags（グループ名のタグは除く）。MC は cast_tags か本文に名前がある人だけ
- 店名は本文の「」の中。前に「到着」「お店」「店」などの言葉があるか、後ろが「へ」「に到着」などのものだけを店名の候補にし、
  ホットペッパーグルメAPI（HOTPEPPER_API_KEY）で、回の都道府県（題の地名）にあり、記事に出る地名と合う1軒に決める
  （hirunan.resolve。名前が完全に一致＝high、一部一致＝mid）。ホットペッパーにない店・施設・定休日や満席で入れなかった店は見送る
- 候補は group meshidora（visit_kind own_tv）。ゲストに放送日にグループにいた STARTO のメンバーがいれば、
  同じ店をそのグループにも（visit_kind guest_tv。期間表は hirunan._M）。merge_candidates.py に group - を渡す

使い方:
  週1回: scripts/weekly/run.py が collect() を呼ぶ（sources.json の meshidora。high だけ）
  過去の全回: python scripts/weekly/meshidora.py --backfill --out <候補.json> [--skipped <見送り.json>] [--cache <APIの控え.json>]
食べログにはアクセスしない。キーはログに出さない（common.redact）。
"""
import argparse
import collections
import datetime
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import days_before, fetch_text, genre_of, mk, nz, redact, today  # noqa: E402
from youtube import HP_GENRE  # noqa: E402
import hirunan  # noqa: E402
from hirunan import FACILITY, GENRE_LABEL, GROUP_NAMES, _cache, resolve, starto_in  # noqa: E402

JS = 'https://www.ntv.co.jp/meshidora/articles.js'
PROGRAM = 'メシドラ'
GROUP = 'meshidora'
TMDB_ID = 254708
POSTER = 'https://image.tmdb.org/t/p/w500/yp4RMis8H8sHsR6VcpAm6rRinc1.jpg'
HOSTS = ['兼近大樹', '満島真之介']
# cast_tags のうち人でないもの（グループ名）
NOT_PERSON = {'EXIT', 'SixTONES', 'Snow Man', 'EXILE', 'Da-iCE', 'TRF', 'KEY TO LIT', 'SUPER EIGHT', 'NEWS', 'なにわ男子',
              'Hey! Say! JUMP', 'Travis Japan', 'King & Prince', 'M!LK', 'GENERATIONS from EXILE TRIBE', 'FANTASTICS from EXILE TRIBE',
              '三代目 J SOUL BROTHERS from EXILE TRIBE', 'TEAM NACS', 'DA PUMP', '氣志團', '電気グルーヴ', '劇団EXILE', "なにわシーサー's"}
# 題に都道府県がない回の地名 → 都道府県
PLACE_PREF = [('秩父', '埼玉県'), ('河口湖', '山梨県'), ('房総', '千葉県'), ('鴨川', '千葉県'), ('大阪', '大阪府'), ('神戸', '兵庫県'),
              ('箱根', '神奈川県'), ('大分', '大分県'), ('しまなみ', '広島県 愛媛県'), ('山中湖', '山梨県')]
PREF_RE = r'(北海道|東京都|京都府|大阪府|[一-鿿]{2,3}県)'
WD = '月火水木金土日'

# 「」の前にあれば店名の候補（同じ文の中）
BEFORE = r'(到着|やってきた|やって来た|たどり着|辿り着|向かった|訪れ|立ち寄|入った|最初は|最初に|続いて|続いては|次は|最後は|最後に|お店|店$|店は|屋さん|喫茶|カフェ|食堂|専門|老舗|名店|レストラン|定食|創業|軒目|ランチ)'
# 「」の後ろがこれなら店名の候補
AFTER = r'^(へ|に到着|に向か|に立ち寄|を訪|に入|で(は)?(ランチ|昼食|朝食|夕食|食事|注文|いただ|合流)|。(?!」))'
NOT_NAME = r'メシドラ|お悩み|カーラジオ|ゲーム|しりとり|合戦|^\d|円$|定食$|セット$|カレー$|丼$|ラーメン$|そば$|うどん$|パフェ$|かき氷$|ピザ$|焼き?$'
NOT_EAT_HP = r'カラオケ|ボウル|ゴルフ|ジム|バッティング|ネットカフェ|まんが喫茶|漫画喫茶'
SPEECH = r'^[(（]|(たい|ます|です|した|ない|ってる|てた|だろ|よね|かな|ね|よ|わ|じゃん|っす|すね|なー)$'
NO_ENTRY = r'定休|満席|休み|閉ま|閉店|営業して(い)?な|準備中|入れず|入れなかった|断られ|売り切れ|諦め|あきらめ'


def load_articles():
    s = fetch_text(JS)
    if not s:
        raise RuntimeError('articles.js が取れない')
    return parse_js(s)


def parse_js(s):
    return json.loads(s[s.index('['):s.rstrip().rstrip(';').rindex(']') + 1])


def article_url(a):
    return 'https://www.ntv.co.jp/meshidora/articles/%s%s.html' % (a['content_id'], a['item_id'])


def body_text(body):
    b = re.sub(r'<br\s*/?>|</p>|</h\d>|</li>|</div>', '\n', body or '')
    return nz(html.unescape(re.sub(r'<[^>]+>', '', b)))


def broadcast_date(text, pub):
    """本文の初めの「M月D日（曜）」→ 公開日に近い年（曜日が合うもの）。なければ公開日"""
    base = datetime.date.fromisoformat(pub[:10])
    for m in re.finditer(r'(\d{1,2})月\s*(\d{1,2})日\s*[(（]([月火水木金土日])[)）]', text[:400]):
        mo, d, w = int(m.group(1)), int(m.group(2)), m.group(3)
        for y in (base.year - 1, base.year, base.year + 1):
            try:
                dt = datetime.date(y, mo, d)
            except ValueError:
                continue
            if WD[dt.weekday()] == w and abs((dt - base).days) <= 40:
                return dt.isoformat()
    return base.isoformat()


def place_of(title, text=''):
    """→ (町の表示, [都道府県])。題に地名がなければ本文の初めの「○○県○○市」"""
    for t in (nz(title), nz(text)[:300]):
        prefs, towns = [], []
        for m in re.finditer(PREF_RE + r'[・]?([^\s！!？?・、「」『』“”]{1,8}?(?:市|区|町|村|半島|房総))?(?=[のへでと・！!、。\s]|$)', t):
            if m.group(1) not in prefs:
                prefs.append(m.group(1))
            towns.append(m.group(2) or m.group(1))
        for w, p in PLACE_PREF:
            if w in t and not any(w in x for x in towns):
                towns = [x for x in towns if x not in p.split()]  # 「千葉県・鴨川」→ 鴨川
                towns.append(w)
                prefs += [x for x in p.split() if x not in prefs]
        if prefs:
            return '・'.join(towns), prefs
    return '', []


def cast_of(a, title, text):
    tags = [nz(x.get('text') or '').strip() for x in (a['data'].get('cast_tags') or [])]
    hosts = [h for h in HOSTS if h in tags or h in text]
    guests = [x for x in tags if x and x not in HOSTS and x not in NOT_PERSON]
    if not guests:  # タグがない回は題の「○○・○○と行く」
        m = re.match(r'^(.{2,30}?)(?:と行く|と一緒に|が案内|と\S{0,6}(?:へ|の旅))', nz(title))
        if m:
            guests = [re.sub(r'^(SixTONES|Snow Man|NEWS|なにわ男子|King & Prince|Travis Japan|SUPER EIGHT|M!LK)\s*', '', g).strip()
                      for g in re.split(r'[・＆&、]|\s(?=\S+$)', m.group(1)) if g.strip()]
    guests = [g for g in guests if g in nz(title) or g in text]
    return hosts, guests


def shop_quotes(text):
    """→ [(店名, その文)]"""
    out, seen = [], set()
    for m in re.finditer(r'「([^「」\n]{2,30})」', text):
        q = m.group(1).strip()
        if re.search(r'[。！？!?、…〜~]', q) or re.search(NOT_NAME, q) or re.search(SPEECH, q) or q in seen:
            continue
        st = max(text.rfind('。', 0, m.start()), text.rfind('\n', 0, m.start())) + 1
        before = text[max(st, m.start() - 30):m.start()]
        after = text[m.end():m.end() + 8]
        if re.search(r'[（(][^）)]{1,8}[）)]', after[:6]) and re.match(r'^[（(]', after):  # 「…」（満島）＝せりふ
            continue
        if not (re.search(BEFORE, before.rstrip('のは、 ')) or re.search(BEFORE, before) or re.match(AFTER, after)):
            continue
        en = text.find('。', m.end())
        sent = text[st:(en + 1 if en >= 0 else len(text))]
        seen.add(q)
        out.append((q, sent))
    return out


def process(arts, since, until, log):
    new, skipped, newest = [], [], since
    arts = sorted(arts, key=lambda a: a.get('publish_date') or '')
    for a in arts:
        d = a.get('data') or {}
        title = nz(d.get('title') or '')
        text = body_text(d.get('body'))
        if not re.search(r'旅|ドライブ|ゲスト', title) or re.search(r'グッズ|放送スタート', title):  # 番組の告知・グッズ
            continue
        date = broadcast_date(text, a.get('publish_date') or a.get('calendar_date') or today())
        if date <= since or date > until:
            continue
        newest = max(newest, date)
        url = article_url(a)
        town, prefs = place_of(title, text)
        label = re.split(r'[！!]', title)[0][:40]
        if not prefs:
            skipped.append(('回の都道府県が分からない', f'{label}（{date}）'))
            continue
        hosts, guests = cast_of(a, title, text)
        if not guests:
            skipped.append(('ゲストのいない回（MCだけ）', f'{label}（{date}）'))
        hit, miss = starto_in(' '.join(guests), date)
        for nm, why in miss:
            skipped.append((f'STARTO のグループには足さない: {why}', f'{nm}（{date} {label}）'))
        sgroups = {}
        for nm, g in hit:
            sgroups.setdefault(g, [])
            if nm not in sgroups[g]:
                sgroups[g].append(nm)
        for g in [g for g in sgroups if g not in GROUP_NAMES]:
            skipped.append(('STARTO のグループ未作成（_data/groups.json にない）: ' + g, f"{'・'.join(sgroups[g])}（{date} {label}）"))
        sgroups = {g: v for g, v in sgroups.items() if g in GROUP_NAMES}
        people = hosts + [g for g in guests if g not in hosts]
        area_text = title + '\n' + text

        def ok(s):
            return any(nz(s.get('address') or '').startswith(p) for p in prefs)
        done = set()
        for q, sent in shop_quotes(text):
            nm = re.sub(r'\s+', ' ', q).strip()
            if nm in done:
                continue
            done.add(nm)
            if re.search(FACILITY, nm, re.I):
                skipped.append(('飲食店でない（施設・物販など）', f'{nm}（{date} {town}）'))
                continue
            if re.search(NO_ENTRY, sent):
                skipped.append(('定休日・満席などで入れなかった店のおそれ', f'{nm}（{date} {town}）'))
                continue
            try:
                shop, conf, why = resolve(nm, area_text, ok=ok, area_kw=town)
            except Exception as e:
                skipped.append(('ホットペッパーAPIの失敗', redact(f'{nm}: {e}')))
                continue
            if not shop:
                skipped.append((why, f'{nm}（{date} {town}）'))
                continue
            gname = (shop.get('genre') or {}).get('name') or ''
            if re.search(NOT_EAT_HP, gname + ' ' + shop['name']):
                skipped.append(('飲食店でない（カラオケ・遊びの施設）', f"{nm} → {shop['name']}（{date} {town}）"))
                continue
            genre = HP_GENRE.get(gname, '') or genre_of(shop['name'], nm)
            y, mo, dd = date.split('-')
            jdate = f'{int(y)}年{int(mo)}月{int(dd)}日'
            kind = {'shokuji': '', 'others': ''}.get(genre, GENRE_LABEL.get(genre, ''))
            common = dict(name=nm if conf == 'high' else shop['name'], address=shop.get('address', ''), genre=genre,
                          visited_date=date, program=PROGRAM, source_video_title=f'{label}（{date} 日本テレビ『{PROGRAM}』）',
                          source_url=url, thumbnail_url=POSTER, tmdb_id=TMDB_ID, tmdb_type='tv', confidence=conf)
            rows = [dict(group=GROUP, members=people, visit_kind='own_tv',
                         description=f'『{PROGRAM}』の{town}の回（{jdate}放送）で、{"・".join(people)}が訪れた{kind + "の" if kind else ""}店。')]
            for g, mem in sgroups.items():
                gl = 'SUPER EIGHT' if g == 'kanjani' and date >= '2024-02-04' else GROUP_NAMES.get(g, g)
                members = mem + [p for p in people if p not in mem]
                rows.append(dict(group=g, members=members, visit_kind='guest_tv',
                                 description=f'{gl}の{"・".join(mem)}が『{PROGRAM}』の{town}の回（{jdate}放送）で、'
                                             f'{"・".join(p for p in people if p not in mem)}と訪れた{kind + "の" if kind else ""}店。'))
            for row in rows:
                r = mk(**common, **row)
                if r['confidence'] == 'low':
                    skipped.append(('住所が番地までない', f'{nm}（{date} {town}）'))
                    break
                r['hotpepper_url'] = ((shop.get('urls') or {}).get('pc') or '').split('?')[0]
                ph = ((shop.get('photo') or {}).get('pc') or {}).get('l')
                if ph:
                    r['hotpepper_photo'] = ph
                r['hotpepper_name'] = shop['name']
                r['listed_name'] = q
                r['episode_town'] = town
                new.append(r)
    return new, skipped, newest


def collect(cfg, state, log):
    # 状態がないときは30日前から（過去の回は --backfill で）
    last = state.get('last_date') or days_before(today(), 30)
    since = days_before(last, cfg.get('lookback_days', 14))
    new, skipped, newest = process(load_articles(), since, today(), log)
    # 週1回の自動更新では名前が完全に一致した店（high）だけ。一部一致（mid）は別の支店を拾うことがあるので見送り
    skipped += [('名前が一部一致だけ（別の支店のおそれ）', f"{r['listed_name']} → {r['hotpepper_name']}") for r in new if r['confidence'] != 'high']
    new = [r for r in new if r['confidence'] == 'high']
    return {'new': new, 'skipped': skipped, 'state': {'last_date': max(newest, last)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backfill', action='store_true', help='過去の全回を読む')
    ap.add_argument('--since', default='2000-01-01')
    ap.add_argument('--out', required=True)
    ap.add_argument('--skipped')
    ap.add_argument('--cache', help='ホットペッパーAPIの結果の控え（やり直しを速くする）')
    ap.add_argument('--articles', help='手元の articles.js（なければ取りに行く）')
    a = ap.parse_args()
    if a.cache and os.path.exists(a.cache):
        _cache.update(json.load(open(a.cache, encoding='utf-8')))
    arts = parse_js(open(a.articles, encoding='utf-8').read()) if a.articles else load_articles()
    try:
        new, skipped, newest = process(arts, a.since, today(), print)
    finally:
        if a.cache:
            json.dump(_cache, open(a.cache, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'new': new}, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.skipped:
        json.dump([{'why': w, 'name': n} for w, n in skipped], open(a.skipped, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('候補', len(new), collections.Counter((r['group'], r['confidence']) for r in new))
    print('見送り', len(skipped))
    for w, c in collections.Counter(w for w, _ in skipped).most_common():
        print(f'  {c:4d} {w}')


if __name__ == '__main__':
    main()
