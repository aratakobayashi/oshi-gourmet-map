"""週1回の自動更新（scripts/weekly/）の共通部品。

- fetch(): robots.txt を守り、同じホストへは1.2秒以上あけて取りに行く（失敗は数回やり直す）
- 住所を 都道府県・市区町村 に分ける、番地まであるかを見る
- 飲食店かどうか・ジャンルの見当
食べログ（tabelog.com）には決してアクセスしない。
"""
import datetime
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

UA = 'oshi-gourmet-map-weekly/1.0 (+https://gourmet.oshikatsu-guide.com/about/)'
MIN_INTERVAL = 1.2  # 秒。同じホストへの間隔
BLOCKED_HOSTS = ('tabelog.com',)  # 守るルール: 食べログにはアクセスしない
# テレビ東京系・名古屋テレビは robots.txt でAIを拒否しているので使わない
AVOID_HOSTS = ('tv-tokyo.co.jp', 'nagoyatv.com', 'nagoya-tv.co.jp')

JST = datetime.timezone(datetime.timedelta(hours=9))


def today():
    return datetime.datetime.now(JST).date().isoformat()


def days_before(date, n):
    return (datetime.date.fromisoformat(date) - datetime.timedelta(days=n)).isoformat()


_last = {}
_robots = {}


class FetchError(Exception):
    pass


def redact(url):
    """ログに出す前に APIキーを伏せる"""
    return re.sub(r'((?:^|[?&])(?:key|api_key|apikey)=)[^&]*', r'\1***', url)


def _robots_ok(url):
    p = urllib.parse.urlsplit(url)
    host = p.netloc.lower()
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        # 404 は「制限なし」。つながらないときは FetchError のまま（その情報源は失敗として Summary に出る）
        body = _get(f'{p.scheme}://{host}/robots.txt', robots=False)
        rp.parse(body.decode('utf-8', 'replace').splitlines() if body is not None else [])
        _robots[host] = rp
    return _robots[host].can_fetch(UA, url)


def _get(url, robots=True, tries=4, headers=None):
    host = urllib.parse.urlsplit(url).netloc.lower()
    if any(host == h or host.endswith('.' + h) for h in BLOCKED_HOSTS + AVOID_HOSTS):
        raise FetchError(f'アクセスしない決まりのサイト: {host}')
    if robots and not _robots_ok(url):
        raise FetchError(f'robots.txt で禁止: {redact(url)}')
    err = None
    for i in range(tries):
        w = MIN_INTERVAL - (time.time() - _last.get(host, 0))
        if w > 0:
            time.sleep(w)
        _last[host] = time.time()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            err = e
            if e.code in (401, 403):
                break
        except Exception as e:  # 接続のリセットなど
            err = e
        time.sleep(3 * (i + 1))
    raise FetchError(f'{redact(url)}: {type(err).__name__}: {redact(str(err))}')


def fetch(url, **kw):
    """本文（bytes）。404 は None。"""
    return _get(url, **kw)


def fetch_text(url, **kw):
    b = fetch(url, **kw)
    return None if b is None else b.decode('utf-8', 'replace')


def fetch_json(url, **kw):
    b = fetch(url, **kw)
    return None if b is None else json.loads(b.decode('utf-8', 'replace'))


# ---------------------------------------------------------------- 文字・住所
def nz(s):
    return unicodedata.normalize('NFKC', s or '')


def text_of(h):
    """HTML → 改行つきの文字"""
    h = re.sub(r'<(script|style)\b.*?</\1>', '', h or '', flags=re.S)
    h = re.sub(r'<br\s*/?>|</p>|</h\d>|</li>|</div>|</dd>|</dt>', '\n', h)
    t = html.unescape(re.sub(r'<[^>]+>', '', h))
    return re.sub(r'[ \t　]*\n\s*', '\n', t).strip()


PREFS = ('北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 '
         '福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 '
         '山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県').split()
TOKYO = ('千代田区 中央区 港区 新宿区 文京区 台東区 墨田区 江東区 品川区 目黒区 大田区 世田谷区 渋谷区 中野区 杉並区 豊島区 北区 荒川区 '
         '板橋区 練馬区 足立区 葛飾区 江戸川区 八王子市 立川市 武蔵野市 三鷹市 青梅市 府中市 昭島市 調布市 町田市 小金井市 小平市 日野市 '
         '東村山市 国分寺市 国立市 福生市 狛江市 東大和市 清瀬市 東久留米市 武蔵村山市 多摩市 稲城市 羽村市 あきる野市 西東京市').split()
BIG_CITY = {'札幌市': '北海道', '仙台市': '宮城県', 'さいたま市': '埼玉県', '千葉市': '千葉県', '横浜市': '神奈川県', '川崎市': '神奈川県',
            '相模原市': '神奈川県', '横須賀市': '神奈川県', '鎌倉市': '神奈川県', '藤沢市': '神奈川県', '新潟市': '新潟県', '静岡市': '静岡県',
            '浜松市': '静岡県', '名古屋市': '愛知県', '京都市': '京都府', '大阪市': '大阪府', '堺市': '大阪府', '神戸市': '兵庫県',
            '岡山市': '岡山県', '広島市': '広島県', '北九州市': '福岡県', '福岡市': '福岡県', '熊本市': '熊本県'}
DESIGNATED = '札幌 仙台 さいたま 千葉 横浜 川崎 相模原 新潟 静岡 浜松 名古屋 京都 大阪 堺 神戸 岡山 広島 北九州 福岡 熊本'.split()


def clean_addr(a):
    a = nz(a).strip()
    a = re.sub(r'^(住所|所在地|所番地)\s*[:：]?\s*', '', a)
    a = re.sub(r'^〒?\s*\d{3}-?\d{4}\s*', '', a)
    a = re.sub(r'(?<=[^\x00-\x7f]) (?=\d)', '', a)  # 「区高田西 1-18-2」→ 続ける
    a = re.sub(r'(?<=\d)[ー‐－−―](?=\d)', '-', a)
    return re.sub(r'\s+', ' ', a).strip(' 　')


def split_addr(a, hint_pref=''):
    """→ (都道府県, 市区町村, 都道府県から始まる住所)。都道府県が分からなければ ('', '', a)"""
    a = clean_addr(a)
    pref = next((p for p in PREFS if a.startswith(p)), '')
    if not pref:
        for c, p in BIG_CITY.items():
            if a.startswith(c):
                pref = p
                break
        if not pref and any(a.startswith(w) for w in TOKYO):
            pref = '東京都'
        if not pref and hint_pref in PREFS:
            pref = hint_pref
        if not pref:
            return '', '', a
        a = pref + a
    rest = a[len(pref):]
    m = re.match(r'(四日市市|廿日市市|野々市市|市川市|市原市|大和郡山市|郡山市|小郡市|村山市|東村山市|武蔵村山市|町田市|十日町市|大町市)', rest)
    if m:
        city = m.group(1)
    else:
        m = re.match(r'(.{1,6}?郡.{1,5}?[町村]|.{1,6}?市|.{1,4}?区|.{1,5}?[町村])', rest)
        city = m.group(1) if m else ''
        if city.endswith('市') and city[:-1] in DESIGNATED:
            m2 = re.match(r'(.{1,4}?区)', rest[len(city):])
            if m2:
                city += m2.group(1)
    return pref, city, a


def has_banchi(a):
    """都道府県から始まり、町名のあとに番地（数字）がある"""
    a = nz(a)
    if not any(a.startswith(p) for p in PREFS):
        return False
    if re.search(r'京都.*(上ル|下ル|入ル|上る|下る|入る)', a) and re.search(r'\d', a):
        return True
    return bool(re.search(r'\d+(?![\d丁fFＦ階])', a))


def norm_name(n):
    n = nz(n).lower()
    return re.sub(r'[\s・･.\-‐ー－〜~!！?？「」『』"\'&＆/／()（）]', '', n)


# ---------------------------------------------------------------- 飲食店・ジャンル
# 店名に出る「その場で食べる店」の言葉
EAT_IN = (r'食堂|カフェ|cafe|café|喫茶|珈琲|コーヒー|coffee|レストラン|restaurant|ラーメン|らーめん|拉麺|中華そば|そば|蕎麦|うどん|寿司|鮨|すし'
          r'|焼肉|焼き肉|ホルモン|居酒屋|酒場|バル|ビストロ|bistro|トラットリア|trattoria|リストランテ|オステリア|食事処|ダイニング|dining'
          r'|キッチン|kitchen|カレー|中華|飯店|菜館|餃子|ピッツァ|ピザ|pizza|天ぷら|天麩羅|とんかつ|洋食|和食|割烹|料亭|料理|定食|丼'
          r'|ステーキ|ハンバーグ|バーガー|burger|焼鳥|焼き鳥|やきとり|鰻|うなぎ|もんじゃ|お好み焼|たこ焼|甘味|茶房|茶寮|パーラー|グリル|grill'
          r'|ちゃんこ|しゃぶ|すき焼|ジンギスカン|ビアホール|立ち?飲み?|立呑|角打|酒房|炉端|おでん|もつ|串|鉄板焼|ごはん|めし|飯$|亭$|軒$')
# 持ち帰り・物販・飲食店でないもの（点検で外した種類）
NOT_EAT_IN = (r'菓子|製菓|パン|ベーカリー|bakery|ベーグル|ブーランジェ|クロワッサン|直売|販売|製造|工場|工房|酒造|酒蔵|蔵元|醸造|蒸溜|蒸留|酒店|酒屋'
              r'|商店|豆腐|とうふ|蒲鉾|かまぼこ|精肉|鮮魚|水産|青果|八百屋|惣菜|総菜|弁当|佃煮|漬物|干物|農園|牧場|ファーム|市場|マルシェ|道の駅'
              r'|美術館|博物館|ミュージアム|museum|ギャラリー|gallery|資料館|記念館|神社|寺$|公園|ホテル|旅館|温泉|銭湯|雑貨|ショップ|shop|ストア|store'
              r'|たいやき|たい焼|いなり|cake|ドールハウス|さん[（(]|株式会社|有限会社|NPO|協会|組合|センター|アリーナ|スタジアム|学校|教室|スタジオ|サロン|キッチンカー|移動販売|テイクアウト|フードコート|百貨店|スーパー')


def is_restaurant(name, desc=''):
    """店名に「その場で食べる店」の言葉があり、物販・施設の言葉がない店だけ True（迷うものは外す）"""
    n = nz(name)
    if re.search(NOT_EAT_IN, n, re.I):
        return False
    if re.search(EAT_IN, n, re.I):
        return True
    return False


GENRE = [
    ('ramen', r'ラーメン|らーめん|らあめん|らぁ麺|拉麺|中華そば|中華蕎麦|麺屋|つけ麺|まぜそば|油そば|担々麺|担担麺|煮干'),
    ('yakiniku', r'焼肉|焼き肉|ジンギスカン|ホルモン|牛タン|焼きしゃぶ'),
    ('chuka', r'中華|中国料理|飯店|菜館|餃子|点心|焼売|麻婆|飲茶|台湾料理|小籠包|四川|広東|上海料理'),
    ('izakaya', r'居酒屋|酒場|大衆酒|バル|立ち?飲み|立呑|角打|ビアホール|酒房|炉端|やきとり|焼鳥|焼き鳥|串焼|おでん|もつ焼|ワインバー|スナック'),
    ('washoku', r'寿司|鮨|すし|そば|蕎麦|うどん|天ぷら|天麩羅|天丼|割烹|料亭|和食|日本料理|懐石|会席|鰻|うなぎ|とんかつ|釜飯|ふぐ|もんじゃ|お好み焼|たこ焼'
                r'|しゃぶしゃぶ|すき焼|海鮮|郷土料理|小料理|おばんざい|定食屋|食事処'),
    ('cafe', r'カフェ|cafe|café|喫茶|珈琲|コーヒー|coffee|茶房|茶寮|ティールーム|パーラー'),
    ('sweets', r'スイーツ|ケーキ|パティスリー|パフェ|かき氷|甘味|和菓子|洋菓子|ジェラート|アイスクリーム|クレープ|プリン|ドーナツ|団子|だんご|大福|たい焼'),
    ('shokuji', r'食堂|洋食|レストラン|restaurant|フレンチ|フランス料理|イタリア|ビストロ|トラットリア|リストランテ|オステリア|ステーキ|ハンバーグ|カレー'
                r'|グリル|ダイニング|キッチン|ピザ|ピッツァ|パスタ|バーガー|オーベルジュ|韓国料理|タイ料理|ベトナム料理|インド料理|スペイン料理|定食'),
]


def genre_of(*texts, default='shokuji', last=False):
    """texts を順に見て、最初に当たったジャンル。last=True なら1つの文の中で最後に出た種類の言葉（見出しの「…が楽しめる○○店」向け）"""
    for t in texts:
        t = nz(t)
        if not t:
            continue
        if last:
            hits = [(m.end(), g) for g, p in GENRE for m in re.finditer(p, t, re.I)]
            if hits:
                return max(hits)[1]
        else:
            for g, p in GENRE:  # 並び順が優先順（中華そば→ラーメン など）
                if re.search(p, t, re.I):
                    return g
    return default


def mk(**kw):
    """候補1件（merge_candidates.py が受け付ける形）"""
    r = dict(name='', address='', prefecture='', city='', genre='shokuji', members=[], visited_date='', program='',
             source_video_title='', source_url='', confidence='high', visit_type='visit', group='')
    r.update(kw)
    pref, city, full = split_addr(r['address'], r.get('prefecture', '')) if r['address'] else ('', '', '')
    if pref:
        r['address'], r['prefecture'], r['city'] = full, pref, city
    if not r['address'] or not has_banchi(r['address']):
        r['needs_address'] = True
        r['confidence'] = 'low'
    return r
