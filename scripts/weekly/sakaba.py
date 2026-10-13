"""吉田類の酒場放浪記（BS-TBS）: 公式の店ページ https://bs.tbs.co.jp/sakaba/shop/<番号>.html を前回の続きの番号から読む。
放送前のページ（住所なし）が先に出るので、初回放送日が今日より後のページが出たらそこで止める。
立ち寄り先は、店名で食べ物の店と分かるものだけ（神社・商店街・工房などは外す）。"""
import re

from common import fetch_text, mk, nz, text_of, today

URL = 'https://bs.tbs.co.jp/sakaba/shop/%d.html'
PROGRAM = '吉田類の酒場放浪記'
POSTER = 'https://image.tmdb.org/t/p/w500/hDDHfw4aNAaYauPQkByeVlUjZtF.jpg'
TMDB_ID = 227203

NEG = re.compile(r'神社|神宮|八幡|稲荷|寺|観音|不動|天満宮|大社|公園|博物館|資料館|美術館|記念館|会館|商店街|商店会|市場|海岸|温泉|の湯|湯$'
                 r'|ギャラリー|工房|製作所|工芸|薬局|書店|書房|雑貨|骨董|展望台|水族館|倉庫|通り|街$|用品|理容|美容|事務所|ミュージアム|窯|人形|呉服|楽器|城'
                 r'|道の駅|交流館|物産|観光|センター|ホテル|旅館|農園|牧場|直売所')
STRONG = re.compile(r'菓子|製菓|パン|ベーカリー|豆腐|とうふ|酒店|酒造|酒蔵|醸造|蔵元|酒屋|喫茶|カフェ|珈琲|コーヒー|茶屋|茶舗|団子|だんご|煎餅|せんべい'
                    r'|肉店|精肉|鮮魚|水産|魚店|惣菜|総菜|そば|蕎麦|うどん|寿司|すし|鮨|甘味|饅頭|まんじゅう|たい焼|鯛焼|焼き?芋|味噌|醤油|漬物|佃煮'
                    r'|食堂|弁当|納豆|鰹節|乾物|製麺|ケーキ|屋台|パーラー|コロッケ|牛乳|乳業|牡蠣|こんにゃく|ワイナリー|ブルワリー|ビール|食品|かまぼこ'
                    r'|蒲鉾|干物|麹|ラーメン|中華|餃子|焼鳥|焼き鳥|居酒屋|酒場|バー$|BAR|レストラン|ビストロ|カレー|とんかつ|料理|立ち?飲み?|餅|cafe', re.I)


def genre_of(name, kws, main):
    t = name + ' ' + ' '.join(kws)
    if re.search(r'ラーメン|らーめん|中華そば', t):
        return 'ramen'
    if re.search(r'中華|餃子|飯店|菜館', t):
        return 'chuka'
    if main:
        return 'izakaya'  # 本編の店は酒場
    if re.search(r'菓子|ケーキ|甘味|団子|だんご|饅頭|まんじゅう|たい焼|鯛焼|羊羹|最中|もなか|煎餅|せんべい|アイス|ジェラート|パーラー|あんみつ|かき氷|餅|焼き?芋', t):
        return 'sweets'
    if re.search(r'喫茶|カフェ|珈琲|コーヒー|cafe', t, re.I):
        return 'cafe'
    if re.search(r'そば|蕎麦|うどん|寿司|鮨|天ぷら|鰻|うなぎ|割烹|料亭', t):
        return 'washoku'
    if re.search(r'酒場|居酒屋|焼鳥|焼き鳥|やきとり|もつ|立ち飲み|立飲み|バー|BAR|おでん', t):
        return 'izakaya'
    if re.search(r'食堂|定食|レストラン|洋食|とんかつ|カレー', t):
        return 'shokuji'
    return 'others'


def shop_addr(block):
    m = re.search(r'<div class="shop-info">\s*<p>(.*?)</p>', block, re.S)
    if not m:
        return ''
    for line in text_of(m.group(1)).split('\n'):
        mm = re.match(r'\s*住\s*　?\s*所\s*[：:]\s*(.*)', line)
        if mm:
            return re.sub(r'[\s　]+', ' ', mm.group(1)).strip()
    return ''


def parse(n, s, now):
    """→ (候補, 見送り, 放送済みか)"""
    m = re.search(r'<h2 id="shop-name"><span class="num">#?([^<]*)</span>(.*?)</h2>', s, re.S)
    if not m:
        return [], [], True
    num = m.group(1).strip()
    title = re.sub(r"「([^」\]]*)\]", r"「\1」", text_of(m.group(2)).strip())
    d = re.search(r'初回放送：\s*(\d{4})年(\d{1,2})月(\d{1,2})日', s)
    date = '%s-%02d-%02d' % (d.group(1), int(d.group(2)), int(d.group(3))) if d else ''
    if not date or date > now:
        return [], [], False
    url = URL % n
    closed = '閉店' in title
    title = re.sub(r'[\(（]\s*閉店\s*[\)）]', '', title).strip()
    nm = re.search(r'「(.+?)[」\]］]', title)
    end = s.find('<section id="shop-tachiyori"')
    main = s[m.end(): end if end > 0 else len(s)]
    kws = re.findall(r'\?keyword=[^"]*">([^<]+)</a>', main)
    area = (re.findall(r'\?area=[^"]*">([^<]+)</a>', main) or [''])[0]
    src = f'{PROGRAM} #{num} {title}（{date} BS-TBS）'
    common = dict(members=['吉田類'], visited_date=date, program=PROGRAM, source_video_title=src, source_url=url,
                  thumbnail_url=POSTER, tmdb_id=TMDB_ID, tmdb_type='tv', group='sakaba_horoki')
    out, skipped = [], []
    if re.search(r'お家呑み|おうち|お取り寄せ', title):
        return [], [('お家呑み・お取り寄せの回', title)], True
    if not nm or '吉田類' in nm.group(1):
        skipped.append(('特別編（店名なし）', title))
    elif closed:
        skipped.append(('閉店', nm.group(1)))
    else:
        name = nm.group(1).strip()
        out.append(mk(name=nz(name), address=shop_addr(main), prefecture=area if area.endswith(('都', '道', '府', '県')) else '',
                      genre=genre_of(name, kws, True), **common))
    if end > 0:
        tsec = s[end:]
        te = tsec.find('shop-notice')
        tsec = tsec[:te if te > 0 else len(tsec)]
        for p in re.split(r'<h3 class="shop-tachiyori-name">', tsec)[1:]:
            tn = text_of(p[:p.find('</h3>')]).strip()
            if '閉店' in tn:
                skipped.append(('閉店（立ち寄り）', tn))
                continue
            n2 = nz(tn)
            if NEG.search(n2) or not STRONG.search(n2):
                skipped.append(('立ち寄り先・食べ物の店と言い切れない', tn))
                continue
            out.append(mk(name=n2, address=shop_addr(p), prefecture=area if area.endswith(('都', '道', '府', '県')) else '',
                          genre=genre_of(n2, [], False), **common))
    return out, skipped, True


def collect(cfg, state, log):
    last = int(state.get('last_id', 0))
    now = today()
    start = max(1, last - cfg.get('lookback', 2) + 1)  # 直近の数ページは読み直す（住所が後から入ることがある）
    new, skipped, newest = [], [], last
    misses, n = 0, start
    while misses < cfg.get('max_missing', 4) and n < last + 60:
        s = fetch_text(URL % n)
        if s is None:
            misses += 1
            n += 1
            continue
        misses = 0
        items, sk, aired = parse(n, s, now)
        if not aired:
            log(f'  #{n} は未放送なのでここで止める')
            break
        new += items
        skipped += sk
        newest = max(newest, n)
        n += 1
    return {'new': new, 'skipped': skipped, 'state': {'last_id': newest}}
