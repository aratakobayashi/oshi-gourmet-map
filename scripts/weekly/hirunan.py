"""ヒルナンデス!（日本テレビ）: 公式の記事データ /hirunan/articles.js（2022-10 以降の全回が1つのJSON）から、
STARTO ENTERTAINMENT のタレントがロケで訪れた店を拾う。

- 記事をコーナーに分け、＜出演者＞＜ＶＴＲ出演＞などの出演者の行に、放送日にグループにいた STARTO のメンバーがいるコーナーだけを読む
  （Sexy Zone 時代＝2024-03 以前の timelesz、2023-05 以降の平野・岸・神宮寺 などは除く。MEMBERS の期間）
- ＜訪れた場所＞＜紹介したお店＞などの見出しの下の店名（【店名】／●■★・店名）を、ホットペッパーグルメAPI（HOTPEPPER_API_KEY）で
  コーナーの地域（題・本文に出る地名）にある1軒に決める。名前が完全に一致する店が地域に1軒なら confidence high、
  名前の一部が一致する店が地域に1軒なら mid。決まらない店・施設・スタジオに料理が出ただけのコーナーは見送る
- グループごとに1候補（1コーナーに2グループいれば2候補。group は候補ごと＝merge_candidates.py に - を渡す）

使い方:
  週1回: scripts/weekly/run.py が collect() を呼ぶ（sources.json の hirunan）
  過去の全回: python scripts/weekly/hirunan.py --backfill --out <候補.json> [--skipped <見送り.json>] [--cache <APIの控え.json>]
食べログにはアクセスしない。キーはログに出さない（common.redact）。
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import days_before, fetch_json, fetch_text, genre_of, mk, norm_name, nz, redact, today  # noqa: E402
from youtube import HP_API, HP_GENRE  # noqa: E402

JS = 'https://www.ntv.co.jp/hirunan/articles.js'
PROGRAM = 'ヒルナンデス！'  # 既存データの表記（全角！）
POSTER = 'https://image.tmdb.org/t/p/w500/fCpO35eK37moODH9ENbKU2jZhyO.jpg'
TMDB_ID = 45931
ROOT = os.path.dirname(os.path.dirname(HERE))

# ---------------------------------------------------------------- メンバー（放送日に所属していた期間）
# (グループID, 名前, 開始日, 終了日)。日付は含む。'' は制限なし。
# _data/groups.json にないグループは MISSING に（候補にせず「グループ未作成」として見送りに出す）
_M = [
    ('heysayjump', '山田涼介 知念侑李 中島裕翔 有岡大貴 髙木雄也 伊野尾慧 八乙女光 薮宏太', '', ''),
    ('kanjani', '横山裕 村上信五 丸山隆平 安田章大 大倉忠義', '', ''),  # 関ジャニ∞ → SUPER EIGHT（2024-02）も同じID
    ('sixtones', 'ジェシー 京本大我 松村北斗 髙地優吾 森本慎太郎 田中樹', '2015-05-01', ''),
    ('snowman', '岩本照 深澤辰哉 ラウール 渡辺翔太 向井康二 阿部亮平 目黒蓮 宮舘涼太 佐久間大介', '', ''),
    ('west', '重岡大毅 桐山照史 中間淳太 神山智洋 藤井流星 濵田崇裕 小瀧望', '', ''),
    ('naniwa', '西畑大吾 大西流星 道枝駿佑 高橋恭平 長尾謙杜 藤原丈一郎 大橋和也', '', ''),
    ('kingprince', '永瀬廉 髙橋海人', '', ''),
    ('kingprince', '平野紫耀 岸優太 神宮寺勇太', '', '2023-05-22'),
    ('timelesz', '菊池風磨 佐藤勝利 松島聡', '2024-04-01', ''),
    ('timelesz', '寺西拓人 原嘉孝 橋本将生 篠塚大輝', '2025-02-05', ''),
    ('timelesz', '猪俣周杜', '2025-02-05', '2026-09-30'),
    ('travisjapan', '宮近海斗 中村海人 七五三掛龍也 川島如恵留 吉澤閑也 松田元太 松倉海斗', '', ''),
    ('agroup', '末澤誠也 小島健 佐野晶哉 正門良規', '', ''),
    ('agroup', '草間リチャード敬太', '', '2024-11-25'),
    ('kismai', '藤ヶ谷太輔 玉森裕太 宮田俊哉 横尾渉 二階堂高嗣 千賀健永', '', ''),
    ('kismai', '北山宏光', '', '2023-08-31'),
    ('kinkikids', '堂本光一 堂本剛', '', ''),
    ('news', '増田貴久 小山慶一郎 加藤シゲアキ', '', ''),
    ('kattun', '上田竜也 中丸雄一', '', '2025-03-31'),
    ('kamenashi', '亀梨和也', '', ''),
    ('arashi', '大野智 櫻井翔 相葉雅紀 二宮和也 松本潤', '', ''),
    ('kimura', '木村拓哉', '', ''),
    ('sevenmen_samurai', '中村嶺亜 本髙克樹 佐々木大光 今野大輝 矢花黎 菅田琳寧', '', '2025-06-30'),
    ('hihijets', '井上瑞稀 橋本涼 猪狩蒼弥 作間龍斗 髙橋優斗', '', '2024-12-31'),
    ('keytolit', '井上瑞稀 佐々木大光 猪狩蒼弥 中村嶺亜 岩﨑大昇', '2025-07-01', ''),
    ('acees', '浮所飛貴 那須雄登 佐藤龍我 作間龍斗 深田竜生', '2025-07-01', ''),
    ('shonen_ninja', '川﨑皇輝 ヴァサイェガ渉 織山尚大 内村颯太 元木湧 檜山光成 北川拓実 黒田光輝 青木滉平 川﨑星輝 鈴木悠仁 '
                     '瀧陽次朗 豊田陸人 安嶋秀生 久保廉 小田将聖 山井飛翔 稲葉通陽 田村海琉 長瀬結星', '', '2025-11-30'),
    # _data/groups.json にないグループ（候補にしない）
    ('abcz', '橋本良亮 戸塚祥太 塚田僚一 五関晃一', '', ''),
    ('abcz', '河合郁人', '', '2023-12-31'),
    ('bishonen', '岩﨑大昇 佐藤龍我 那須雄登 浮所飛貴 藤井直樹 金指一世', '', '2025-06-30'),
    ('lilkansai', '嶋﨑斗亜 西村拓哉 大西風雅 岡﨑彪太郎 當間琉巧', '', ''),
    ('20th_century', '坂本昌行 長野博 井ノ原快彦', '', ''),
    ('solo:風間俊介', '風間俊介', '', ''),
    ('solo:生田斗真', '生田斗真', '', ''),
]
# 名前はあるが、その日にどのグループにもいない（所属の切り替わり時期・グループ外）
OUTSIDE = {
    '中島健人': 'Sexy Zone／ソロ（timelesz 在籍中の回でない）',
    '平野紫耀': 'Number_i（STARTO でない）', '岸優太': 'Number_i（STARTO でない）', '神宮寺勇太': 'Number_i（STARTO でない）',
}
GROUP_NAMES, GENRE_LABEL = {}, {}
try:
    GENRE_LABEL = {k: v.get('label', '') for k, v in json.load(open(os.path.join(ROOT, '_data', 'genres.json'), encoding='utf-8')).items()}
except Exception:
    pass
try:
    GROUP_NAMES = json.load(open(os.path.join(ROOT, '_data', 'groups.json'), encoding='utf-8'))
except Exception:
    pass


def _k(n):
    n = nz(n).replace('髙', '高').replace('濵', '濱').replace('﨑', '崎').replace('塚', '塚')
    return re.sub(r'\s', '', n)


MEMBERS = []  # (key, 正式表記, group, start, end)
for g, names, s, e in _M:
    for nm in names.split():
        MEMBERS.append((_k(nm), nm, g, s, e))
ALL_KEYS = sorted({m[0] for m in MEMBERS} | {_k(x) for x in OUTSIDE}, key=len, reverse=True)


def starto_in(cast, date):
    """出演者の文字から → ([(正式表記, group)], [(名前, 見送りの理由)])"""
    t = _k(cast)
    hit, miss = [], []
    for key in ALL_KEYS:
        if key not in t:
            continue
        rows = [m for m in MEMBERS if m[0] == key]
        ok = [m for m in rows if (not m[3] or date >= m[3]) and (not m[4] or date <= m[4])]
        if ok:
            for m in ok:
                hit.append((m[1], m[2]))
        else:
            nm = rows[0][1] if rows else key
            if key == _k('菊池風磨') or key == _k('佐藤勝利') or key == _k('松島聡'):
                miss.append((nm, 'Sexy Zone 時代（2024-03 以前）'))
            else:
                miss.append((nm, OUTSIDE.get(nm) or 'その日にどのグループにもいない（所属の切り替わり時期など）'))
    return hit, miss


# ---------------------------------------------------------------- 記事 → コーナー
WD = '月火水木金土日'


def broadcast_date(title, cal):
    """題の「M月D日（曜）」→ 年は曜日が合い calendar_date に近い年"""
    t = nz(title)
    m = re.search(r'(\d{1,2})月\s*(\d{1,2})日\s*[(（]?([月火水木金土日])?', t)
    if not m:
        return ''
    mo, d, w = int(m.group(1)), int(m.group(2)), m.group(3)
    base = datetime.date.fromisoformat(cal[:10]) if cal else datetime.date.today()
    best = None
    for y in range(base.year - 7, base.year + 2):
        try:
            dt = datetime.date(y, mo, d)
        except ValueError:
            continue
        if w and WD[dt.weekday()] != w:
            continue
        if dt > datetime.date.fromisoformat(today()):
            continue
        if best is None or abs((dt - base).days) < abs((best - base).days):
            best = dt
    return best.isoformat() if best else ''


def body_lines(body):
    """HTML → 行（太字・下線は [[ ]] で残す）"""
    b = re.sub(r'<(u|strong|b)\b[^>]*>', '[[', body or '')
    b = re.sub(r'</(u|strong|b)>', ']]', b)
    b = re.sub(r'<br\s*/?>|</p>|</h\d>|</li>|</div>|<p\b[^>]*>', '\n', b)
    t = nz(html.unescape(re.sub(r'<[^>]+>', '', b)))
    out = []
    for l in t.split('\n'):
        l = l.replace('　', ' ').strip()
        while '[[]]' in l:
            l = l.replace('[[]]', '')
        out.append(l)
    return out


def plain(l):
    return re.sub(r'\[\[|\]\]', '', l).strip()


HEAD = re.compile(r'^\s*(?:\[\[)*\s*[<〈《【\[＜]\s*([^<>〈〉【】\[\]]{1,24}?)\s*[>〉》】\]＞]\s*(?:\]\])*\s*[:：]?\s*(.*)$')
CAST_HEAD = r'^(コーナー|ロケ|VTR|スタジオ)?\s*(出演者?|ゲスト|出演者・ゲスト|旅人|メンバー)$'
SHOP_HEAD = r'(店|施設|場所|スポット|伺|訪れ|紹介内容|ご協力|協力|立ち寄|巡った|商店街|グルメ|紹介した商品|紹介商品)'
NOT_SHOP_HEAD = r'(材料|プレゼント|作り方|レシピ|乗車券|バス$|テーマ|料金|入場料|入園料|営業時間|定休日|ランキング|アイテム|開催|期間|時間|ルール|問い合わせ|お部屋|リフォーム|の達人|家族|料理$)'
# スタジオに料理が出ただけ・店頭のロケでないコーナー
STUDIO = r'行きつけでSHOW|スタジオ試食|スタジオで試食|スタジオに|お取り寄せ|通販|コンビニ|チェーン店|ファミレス|冷凍食品|スーパー|業務スーパー|コストコ|ドンキ|100均|ダイソー|セリア|無印良品|カルディ|ニトリ|IKEA|イケア|ふるさと納税|ご当地うますぎ|クッキング|レシピ|リフォーム'
# 店名でない・飲食店でないもの（ホットペッパーに聞く前に外す）
FACILITY = (r'公園|神社|神宮|大社|八幡宮|寺$|寺院|院$|城$|城跡|美術館|博物館|ミュージアム|記念館|資料館|水族館|動物園|植物園|遊園地|ゆうえんち|ランド$|パーク|'
            r'温泉$|湯$|旅館|ホテル|HOTEL|リゾート|空港|駅$|港$|海岸|海水浴場|展望台|タワー$|ロープウェイ|ケーブルカー|フェリー|クルーズ|遊覧船|乗り場|'
            r'商店街|通り$|横丁$|市場$|朝市|道の駅|アウトレット|モール|百貨店|ショッピングセンター|SA$|PA$|サービスエリア|パーキングエリア|'
            r'農園|牧場|ファーム|果樹園|ぶどう園|いちご園|酒造|醸造|蒸溜|蒸留|ワイナリー|工房|工場|体験|教室|スタジオ|サロン|ショップ|ストア|'
            r'雑貨|書店|本屋|洋服|古着|POPUP|ポップアップ|キッチンカー|移動販売|ガラス|陶芸|染め|物産|土産|みやげ|直売所|売店|銭湯|サウナ|桑拿|'
            r'園$|Pasar|パサール|ハウステンボス|ディズニー|USJ|ユニバーサル|ロフト|LOFT|高島屋|松坂屋|三越|伊勢丹|大丸|そごう|西武$|パルコ|PARCO|ルミネ|イオン|ららぽーと|'
            r'バス$|鉄道|列車|電車|観光|案内所|センター$|会館$|ホール$|プール|キャンプ場|グランピング')
MARK = r'^[■●◼◆▼▽★☆○◎・◇□▶︎▷\-‐]+\s*(.+)$'
TAKEOUT = r'弁当|テイクアウト|持ち帰り|お土産|手土産|通販|お取り寄せ|販売予定|箱入り|袋入り'
PRICE = r'\d[\d,]*\s*円|時価|円~|円〜|\d+円|価格|税込|税別'


def split_corners(lines):
    """→ [(題, [行])]。題は【】や★…★・[[…]] の見出し行。出演者の見出しごとに1コーナー（その前の題を使う）"""
    titles = []  # (行番号, 題)
    casts = []
    for i, l in enumerate(lines):
        p = plain(l)
        m = HEAD.match(l)
        if m and re.search(CAST_HEAD, nz(m.group(1)).replace(' ', '')):
            casts.append(i)
            continue
        if not p or m:
            continue
        if (re.match(r'^★.+★$', p) or (l.startswith('[[') and l.endswith(']]') and not re.match(r'^[■●◼◆▼・]', p))
                or re.match(r'^[「『].+[」』]$', p)) and len(p) <= 60:
            titles.append((i, p.strip('★「」『』 ')))
    # 出演者の見出しが続く（＜VTR出演者＞＜ゲスト＞など）ときは、あいだに題がなければ同じコーナー
    merged = []
    for c in casts:
        if merged and not any(merged[-1][-1] < ii < c for ii, _ in titles):
            merged[-1].append(c)
        else:
            merged.append([c])
    out = []
    for k, grp in enumerate(merged):
        c = grp[0]
        end = merged[k + 1][0] if k + 1 < len(merged) else len(lines)
        prev = merged[k - 1][-1] if k else -1
        t = [tt for ii, tt in titles if prev < ii < c]
        title = t[-1] if t else ''
        nxt = [ii for ii, _ in titles if grp[-1] < ii < end]
        stop = nxt[-1] if nxt and k + 1 < len(merged) else end
        desc_start = max([ii for ii, _ in titles if prev < ii < c] or [prev + 1])
        out.append((title, lines[desc_start:stop], [x - desc_start for x in grp]))
    return out


def cast_text(seg, cis):
    return '\n'.join(_cast1(seg, ci) for ci in cis)


def _cast1(seg, ci):
    """出演者の見出し（seg[ci]）の右と、下の行（空行・次の見出しまで）"""
    m = HEAD.match(seg[ci])
    out = [m.group(2)] if m and m.group(2) else []
    for l in seg[ci + 1:]:
        if not plain(l) or HEAD.match(l):
            if out:
                break
            continue
        out.append(plain(l))
        if len(out) > 12:
            break
    return '\n'.join(out)


def cast_names(t):
    """出演者の文字 → 名前の並び。「・、」で区切られた行は空白を名前の中の空白とみなす（「久本 雅美」）"""
    t = re.sub(r'[(（][^()（）]*[)）]', '', nz(t))
    names = []
    for line in t.split('\n'):
        line = re.sub(r'^[^:：]{1,8}[:：]', '', line.strip(' ▼▽●■・-'))  # 「ゲスト:」「マドンナ:」
        if re.search(r'[・、,，/／&＆]', line):
            parts = [re.sub(r'\s+', '', x) for x in re.split(r'[・、,，/／&＆]', line)]
        else:
            toks = line.split()
            parts = []
            for x in toks:  # 「久本 雅美」のように2文字ずつに分かれた名前はつなぐ
                if parts and len(parts[-1]) <= 2 and len(x) <= 3 and re.fullmatch(r'[\u4e00-\u9fff々]+', parts[-1] + x):
                    parts[-1] += x
                else:
                    parts.append(x)
        for x in parts:
            x = x.strip(' ・●-▼▽')
            if x and len(x) <= 14 and not re.search(r'さん$|ほか|など|チーム$|曜日?$', x):
                names.append(x)
    return names


def shop_names(seg):
    """店の見出しの下の店名"""
    res, i, n = [], 0, len(seg)
    while i < n:
        m = HEAD.match(seg[i])
        if not m:
            i += 1
            continue
        h = nz(m.group(1)).replace(' ', '')
        if re.search(CAST_HEAD, h) or not re.search(SHOP_HEAD, h) or re.search(NOT_SHOP_HEAD, h):
            i += 1
            continue
        header = h
        block = [m.group(2)] if m.group(2) else []
        j = i + 1
        while j < n:
            l = seg[j]
            mm = HEAD.match(l)
            if mm:
                hh = nz(mm.group(1)).replace(' ', '')
                if re.search(CAST_HEAD, hh) or re.search(NOT_SHOP_HEAD, hh) or re.search(SHOP_HEAD, hh) and re.search(r'(紹介|伺|訪れ|協力)', hh):
                    break
            p = plain(l)
            if re.match(r'^★.+★$', p) or re.match(r'^\[\[[「『].+[」』]\]\]$', l):
                break
            block.append(l)
            j += 1
        bracket = [b for b in block if re.match(r'^(\[\[)*\s*【[^【】]{1,40}】\s*(\]\])*$', b)]
        for bi, b in enumerate(block):
            p = plain(b)
            if not p:
                continue
            if bracket:
                mm = re.match(r'^【([^【】]+)】$', p)
                if not mm:
                    continue
                nm = mm.group(1)
            else:
                mm = re.match(MARK, p)
                if mm:
                    nm = mm.group(1)
                elif HEAD.match(b):
                    continue
                else:
                    nm = p
            nm = nm.strip(' 　')
            if (not nm or re.search(PRICE, nm) or '。' in nm or len(nm) > 40 or re.match(r'^(\d|※|営業|定休|住所|電話|TEL|URL|http|〒)', nm)
                    or re.match(r'^(北海道|東京都|京都府|大阪府|.{2,3}県)', nm) or nm.endswith(('!', '?'))
                    or re.search(r'\.\.\.|・・・|…|ヒルナンデス|テーマ|\d駅目|^\d+[.、]', nm)):
                continue
            detail = []  # 店名の下の行（次の店名まで）
            for b2 in block[bi + 1:bi + 12]:
                p2 = plain(b2)
                if (re.match(r'^【[^【】]+】$', p2) if bracket else (re.match(MARK, p2) and not re.search(PRICE, p2))):
                    break
                detail.append(p2)
            res.append((nm, header, '\n'.join(detail)))
        i = j
    return res


def clean_name(nm):
    nm = nz(nm)
    nm = re.sub(r'[「」『』]', ' ', nm)
    nm = re.sub(r'\s*[(（][^()（）]*[)）]\s*', ' ', nm)
    nm = re.sub(r'[※*].*$', '', nm)
    nm = re.sub(r'\s*[:：].*$', '', nm)
    return re.sub(r'\s+', ' ', nm).strip()


# ---------------------------------------------------------------- ホットペッパー
_cache = {}


def hp_search(keyword):
    if keyword in _cache:
        return _cache[keyword]
    key = os.environ.get('HOTPEPPER_API_KEY')
    if not key:
        raise RuntimeError('HOTPEPPER_API_KEY がない')
    q = urllib.parse.urlencode({'key': key, 'keyword': keyword, 'count': 100, 'format': 'json'})
    d = fetch_json(HP_API + '?' + q, robots=False)  # 公式API（クレジット表記はサイトのフッター）
    shops = (d or {}).get('results', {}).get('shop', []) or []
    keep = ('id', 'name', 'address', 'lat', 'lng', 'genre', 'urls', 'photo', 'station_name', 'large_area', 'middle_area', 'small_area',
            'large_service_area')
    shops = [{k: s.get(k) for k in keep} for s in shops]
    _cache[keyword] = shops
    return shops


def area_words(s):
    w = set()
    a = nz(s.get('address') or '')
    m = re.match(r'^(?:東京都|北海道|(?:京都|大阪)府|.{2,3}県)(.+?[市区町村])', a)
    if m:
        c = m.group(1)
        w.add(c)
        w.add(re.sub(r'[市区町村]$', '', c))
        m2 = re.match(r'(.+?市)(.+?区)', c)
        if m2:
            w.add(m2.group(2)); w.add(m2.group(2)[:-1]); w.add(m2.group(1)[:-1])
        rest = a[len(m.group(0)):]
        m3 = re.match(r'^([^\d０-９一二三四五六七八九十-]{2,6}?)(?:\d|[一二三四五六七八九十]+丁目|丁目|$)', rest)
        if m3:
            w.add(m3.group(1))
    for k in ('small_area', 'middle_area'):
        nmx = nz((s.get(k) or {}).get('name') or '')
        for p in re.split(r'[・/／、]', nmx):
            p = re.sub(r'(周辺|駅前|駅|エリア|その他)$', '', p.strip())
            if p:
                w.add(p)
    st = nz(s.get('station_name') or '')
    if st:
        w.add(re.sub(r'駅$', '', st))
    return {x for x in w if len(x) >= 2 and x not in ('その他', '東京', '大阪', '駅前', '中央', '本町', '栄町', '駅')}


def resolve(name, area_text):
    """→ (shop, confidence, 理由)"""
    want = norm_name(name)
    if len(want) < 2:
        return None, '', '店名が短すぎる'
    kws = [name]
    base = re.sub(r'\s*\S*(本店|支店|店)$', '', name).strip()
    if base and base != name:
        kws.append(base)
    if ' ' in name:
        kws.append(max(name.split(' '), key=len))
    seen, shops = set(), []
    for kw in kws:
        for s in hp_search(kw):
            if s['id'] not in seen:
                seen.add(s['id'])
                shops.append(s)
        if shops:
            break
    if not shops:
        return None, '', 'ホットペッパーにない（飲食店でない・未掲載）'
    at = nz(area_text)

    def in_area(s):
        return any(w in at for w in area_words(s))
    exact = [s for s in shops if norm_name(s['name']) == want]
    ea = [s for s in exact if in_area(s)]
    if len(ea) == 1:
        return ea[0], 'high', ''
    if len(ea) > 1:
        return None, '', f'同じ名前の店が地域に{len(ea)}軒'
    # 名前の一部が一致: ホットペッパーの店名が載っている名前で始まる（「翠雲」→「翠雲 上野店」）か、
    # 載っている名前がホットペッパーの店名で終わる（「日本料理 よつ谷」→「よつ谷」）ものだけ。
    # 「横浜赤レンガ倉庫」→「クアアイナ 横浜赤レンガ倉庫店」のような、施設の中の別の店を拾わないため
    wb = norm_name(base) if base else want

    def near(s):
        h = norm_name(s['name'])
        if len(h) < 2:
            return False
        if (len(want) >= 2 and h.startswith(want)) or (len(wb) >= 3 and h.startswith(wb)):
            rest = nz(s['name'])  # 店名の残り（支店名）に、コーナーに出てこない地名があれば別の店
            for w in (name, base):
                rest = rest.replace(w, '') if w else rest
            places = re.findall(r'[\u4e00-\u9fff々ヶ]{2,}', re.sub(r'(本店|支店|店)$', '', rest.strip()))
            return all(p in at for p in places)
        return len(h) >= 3 and want.endswith(h)
    part = [s for s in shops if near(s)]
    pa = [s for s in part if in_area(s)]
    if len(pa) == 1:
        return pa[0], 'mid', ''
    if len(pa) > 1:
        return None, '', f'名前の近い店が地域に{len(pa)}軒（どの店か決められない）'
    if exact:
        return None, '', '名前が一致する店はあるが地域が合わない'
    return None, '', 'ホットペッパーで名前の合う店なし'


# ---------------------------------------------------------------- 本体
def load_articles():
    s = fetch_text(JS)
    if not s:
        raise RuntimeError('articles.js が取れない')
    return json.loads(s[s.index('['):s.rstrip().rstrip(';').rindex(']') + 1])


def article_url(a):
    return 'https://www.ntv.co.jp/hirunan/articles/%s%s.html' % (a['content_id'], a['item_id'])


def process(arts, since, until, log):
    new, skipped, newest = [], [], since
    for a in arts:
        d = a.get('data') or {}
        title = nz(d.get('title') or '')
        date = broadcast_date(title, a.get('calendar_date') or '')
        if not date or date <= since or date > until:
            continue
        newest = max(newest, date)
        lines = body_lines(d.get('body'))
        url = article_url(a)
        for ctitle, seg, ci in split_corners(lines):
            cast = cast_text(seg, ci)
            hit, miss = starto_in(cast, date)
            label = ctitle or re.split(r'★|」「', re.sub(r'^.*?ヒルナンデス[!！]\s*(は)?[・.…\s]*', '', title).strip('★「」 '))[0][:40] or 'ヒルナンデス!'
            label = label.strip('◎★ ')
            for nm, why in miss:
                skipped.append((f'メンバーが対象外: {why}', f'{nm}（{date} {label}）'))
            if not hit:
                continue
            groups = {}
            for nm, g in hit:
                groups.setdefault(g, [])
                if nm not in groups[g]:
                    groups[g].append(nm)
            missing = [g for g in groups if g not in GROUP_NAMES]
            for g in missing:
                skipped.append(('グループ未作成（_data/groups.json にない）: ' + g, f"{'・'.join(groups[g])}（{date} {label}）"))
            groups = {g: v for g, v in groups.items() if g in GROUP_NAMES}
            if not groups:
                continue
            ctext = '\n'.join(plain(l) for l in seg)
            if re.search(STUDIO, ctitle + '\n' + ctext[:400]):
                skipped.append(('スタジオ・物販のコーナー（店に行った回でない）', f'{label}（{date}）'))
                continue
            shops = shop_names(seg)
            if not shops:  # 見出しなしで、出演者の下に記号つきの店名が並ぶ回
                shops = [(m.group(1), '', '') for l in seg[max(ci) + 1:] for m in [re.match(MARK, plain(l))] if m and not HEAD.match(l)]
                shops = [x for x in shops if not re.search(PRICE, x[0]) and len(x[0]) <= 40 and '。' not in x[0]]
            if not shops:
                skipped.append(('店の見出しがない（ロケ先なし・書式が違う）', f'{label}（{date}）'))
                continue
            starto_all = [nm for v in groups.values() for nm in v]
            others = []
            for x in cast_names(cast):  # 同じコーナーのほかの出演者（ほかのグループの STARTO のメンバーも）
                if not any(_k(x) in _k(s) or _k(s) in _k(x) for s in starto_all + others):
                    others.append(x)
            others = [nm for nm in starto_all] + others
            area_text = (ctitle or title) + '\n' + ctext  # 記事の題には別のコーナーの地名も入るので使わない
            done = set()
            for raw, header, detail in shops:
                nm = clean_name(raw)
                if not nm or nm in done:
                    continue
                done.add(nm)
                if re.search(TAKEOUT, detail):
                    skipped.append(('持ち帰り・物販の紹介（その場で食べたか分からない）', f'{nm}（{date} {label}）'))
                    continue
                if re.search(FACILITY, nm, re.I):
                    skipped.append(('飲食店でない（施設・物販など）', f'{nm}（{date} {label}）'))
                    continue
                try:
                    shop, conf, why = resolve(nm, area_text)
                except Exception as e:
                    skipped.append(('ホットペッパーAPIの失敗', redact(f'{nm}: {e}')))
                    continue
                if not shop:
                    skipped.append((why, f'{nm}（{date} {label}）'))
                    continue
                gname = (shop.get('genre') or {}).get('name') or ''
                genre = HP_GENRE.get(gname, '') or genre_of(shop['name'], nm)
                y, mo, dd = date.split('-')
                for g, mem in groups.items():
                    members = mem + [o for o in others if o not in mem]
                    gl = 'SUPER EIGHT' if g == 'kanjani' and date >= '2024-02-04' else GROUP_NAMES.get(g, g)
                    who = '・'.join(mem)
                    kind = {'shokuji': '', 'others': ''}.get(genre, GENRE_LABEL.get(genre, ''))
                    desc = f'{gl}の{who}が『{PROGRAM}』の「{label}」（{int(y)}年{int(mo)}月{int(dd)}日放送）で訪れた{kind + "の" if kind else ""}店。'
                    r = mk(name=nm if conf == 'high' else shop['name'], address=shop.get('address', ''), genre=genre, members=members,
                           visited_date=date, program=PROGRAM, visit_kind='guest_tv',
                           source_video_title=f'{label}（{date} 日本テレビ『{PROGRAM}』）', source_url=url,
                           thumbnail_url=POSTER, tmdb_id=TMDB_ID, tmdb_type='tv', confidence=conf, group=g, description=desc)
                    if r['confidence'] == 'low':
                        skipped.append(('住所が番地までない', f'{nm}（{date} {label}）'))
                        break
                    r['hotpepper_url'] = ((shop.get('urls') or {}).get('pc') or '').split('?')[0]
                    ph = ((shop.get('photo') or {}).get('pc') or {}).get('l')
                    if ph:
                        r['hotpepper_photo'] = ph
                    r['hotpepper_name'] = shop['name']
                    r['listed_name'] = raw
                    new.append(r)
    return new, skipped, newest


def collect(cfg, state, log):
    # 状態がないときに全回（数千件の問い合わせ）を読まないよう、最初は30日前から。過去の回は --backfill で
    last = state.get('last_date') or days_before(today(), 30)
    since = days_before(last, cfg.get('lookback_days', 14))
    new, skipped, newest = process(load_articles(), since, today(), log)
    # 週1回の自動更新では、地域の中で名前が完全に一致した店（high）だけを足す。一部一致（mid）は別の支店を拾うことがあるので見送り
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
    if a.articles:
        s = open(a.articles, encoding='utf-8').read()
        arts = json.loads(s[s.index('['):s.rstrip().rstrip(';').rindex(']') + 1])
    else:
        arts = load_articles()
    try:
        new, skipped, newest = process(arts, a.since, today(), print)
    finally:
        if a.cache:
            json.dump(_cache, open(a.cache, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'new': new}, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.skipped:
        json.dump([{'why': w, 'name': n} for w, n in skipped], open(a.skipped, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import collections
    print('候補', len(new), collections.Counter(r['group'] for r in new))
    print('見送り', len(skipped))
    for w, c in collections.Counter(w for w, _ in skipped).most_common():
        print(f'  {c:4d} {w}')


if __name__ == '__main__':
    main()
