"""食彩の王国（テレビ朝日）: 公式の店舗データ /syokusai/api/shop.json（回・放送日・【紹介の見出し】店名・住所）。
見出しで「食べられる店」と分かるものだけ（農家・酒蔵・直売所・メーカーなどは外す）。ジャンルは公式の見出しを優先。"""
import html
import re

from common import days_before, fetch_json, genre_of, mk, nz, today

API = 'https://www.tv-asahi.co.jp/syokusai/api/shop.json'
PROGRAM = '食彩の王国'
POSTER = 'https://image.tmdb.org/t/p/w500/45EZ4BQMBgeVadnlKA4Abx3IuOm.jpg'
TMDB_ID = 203647

STRONG = (r'料理店|料理屋|レストラン|食堂|カフェ|寿司|鮨|すし店|そば店|蕎麦|うどん|ラーメン|割烹|料亭|懐石|ビストロ|イタリアン|フレンチ|中華料理|中国料理'
          r'|居酒屋|居食屋|バル|トラットリア|リストランテ|ピッツァ|ピザ|オーベルジュ|味わえる店|楽しめる店|食べられる店|味わえるお店|楽しめるお店|和食店'
          r'|洋食|鉄板焼|焼肉|焼き鳥|焼鳥|うなぎ店|鰻店|天ぷら|とんかつ|定食|日本料理|郷土料理|創作料理|ダイニング|喫茶')
NON = (r'農園|農家|農場|生産|養殖|漁師|漁協|漁業|協会|組合|会社|直売|購入|通販|市場|酒蔵|醸造|蔵元|味噌蔵|工房|養鶏|養蜂|牧場|メーカー|製造|開発|育て|栽培'
       r'|キャンプ|施設|神社|寺|温泉|ホテル|旅館|宿|道の駅|マルシェ|米店|精米|商店|販売|研究|大学|学校|加工|問屋|卸|水産|鮮魚店|精肉店|八百屋|青果'
       r'|サービスエリア|名産品|百貨店|テイクアウト|持ち帰り|お取り寄せ|豆腐店|豆腐屋|酒店|菓子店|和菓子屋|パン店|本舗|宿坊|教室|ご家庭|家庭で')
WEAK = r'料理|味わえる|楽しめる|堪能|食べられる|一皿|ランチ|ディナー|コース|お店'


def is_rest(label, name):
    if re.search(NON, label + ' ' + name):
        return False
    if re.search(STRONG, label):
        return True
    if re.search(WEAK, label):
        return True
    if not label:
        return bool(re.search(r'食堂|レストラン|料理|寿司|鮨|そば|蕎麦|うどん|ラーメン|カフェ|割烹|ビストロ|トラットリア|リストランテ|居酒屋|焼肉', nz(name)))
    return False


def collect(cfg, state, log):
    last = state.get('last_date', '2000-01-01')
    since = days_before(last, cfg.get('lookback_days', 14))
    now = today()
    d = fetch_json(API)
    if not d:
        raise RuntimeError('shop.json が取れない')
    new, skipped, newest = [], [], last
    for x in d:
        date = (x.get('date') or '').replace('/', '-')
        if not date or date <= since or date > now:
            continue
        newest = max(newest, date)
        raw = nz(html.unescape(x.get('shop') or '')).strip()
        m = re.match(r'\s*【(.+?)】\s*', raw)
        label = m.group(1) if m else ''
        name = raw[m.end():] if m else raw
        name = re.sub(r'^[（(][^）)]*[）)]\s*', '', re.sub(r'<[^>]+>', '', name)).strip()
        if not is_rest(label, name):
            skipped.append(('飲食店でない（公式の見出しで判断）', f'{name}（{label[:40]}）'))
            continue
        info = html.unescape(re.sub(r'<br\s*/?>', '\n', x.get('shopinfo') or ''))
        ma = re.search(r'(?:住所|所在地)\s*[：:]\s*([^\n]+)', info)
        ep = nz(html.unescape(x.get('title') or '')).strip()
        r = mk(name=name, address=ma.group(1).strip() if ma else '', genre=genre_of(label, name, last=True), members=[],
               visited_date=date, program=PROGRAM, source_video_title=f'{PROGRAM} {ep}（{date} テレビ朝日）',
               source_url='https://www.tv-asahi.co.jp/syokusai/shop/%s/' % x['id'], thumbnail_url=POSTER, tmdb_id=TMDB_ID,
               tmdb_type='tv', group='syokusai')
        new.append(r)
    return {'new': new, 'skipped': skipped, 'state': {'last_date': newest}}
