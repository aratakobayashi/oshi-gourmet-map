"""
fetch_venue_hotels.py
ライブ会場の近くの宿を、楽天トラベルの公式API（楽天ウェブサービス SimpleHotelSearch）で調べて
_data/venue_hotels.json に書く。会場ガイド・公演参戦ガイドの「会場の近くの宿」（_includes/venue-hotels.html）で使う。

- 会場の座標は _data/venues.json。会場から半径 RADIUS_KM 以内の宿を、会場からの直線距離が近い順に MAX_HOTELS 軒
- 載せるのは 宿の名前・会場からの距離・最寄り駅（APIの値）・画像・楽天トラベルの宿のページ（アフィリエイトID付き）だけ。
  料金・空室・口コミ点数は変わりやすいので載せない（リンク先で確かめてもらう）
- 楽天ウェブサービスの規約どおり、表示する場所にクレジット（Supported by Rakuten Developers）を出す（venue-hotels.html）
- キーは環境変数から読む（リポジトリに書かない）: RAKUTEN_APP_ID（アプリID）、RAKUTEN_ACCESS_KEY（アクセスキー。発行されていれば）
  アフィリエイトIDは _config.yml の affiliate.rakuten.id
- 1.5秒あけて1会場ずつ。何度実行しても同じ形（宿が見つからない会場は前回の値を残す）
使い方: python scripts/fetch_venue_hotels.py [会場キー …]   （省略で全会場。--dry-run で書かない）
"""
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 2026年以降に発行されたアプリID（UUID形式）は新しいドメイン openapi.rakuten.co.jp でだけ通る
# （旧 app.rakuten.co.jp/services/api は「specify valid applicationId」になる）。環境変数 RAKUTEN_API_BASE で上書きできる
API_BASE = os.environ.get('RAKUTEN_API_BASE', 'https://openapi.rakuten.co.jp/engine/api')
ENDPOINT = API_BASE + '/Travel/SimpleHotelSearch/20170426'
SITE = 'https://gourmet.oshikatsu-guide.com'
RADIUS_KM = 3.0
MAX_HOTELS = 6
WAIT = 1.5


def km(a, b):
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def affiliate_id():
    t = open(os.path.join(ROOT, '_config.yml'), encoding='utf-8').read()
    m = re.search(r'rakuten:\s*\n(?:\s*#.*\n)*\s*id:\s*"([^"]*)"', t)
    return m.group(1) if m else ''


def redact(s):
    for k in ('RAKUTEN_APP_ID', 'RAKUTEN_ACCESS_KEY'):
        v = os.environ.get(k)
        if v:
            s = s.replace(v, '***')
    return s


def search(lat, lng, app_id, access_key, aff, radius=RADIUS_KM, page=1):
    q = {'applicationId': app_id, 'format': 'json', 'formatVersion': '2', 'datumType': '1',
         'latitude': f'{lat:.6f}', 'longitude': f'{lng:.6f}', 'searchRadius': f'{radius:g}',
         'hits': '30', 'page': str(page), 'responseType': 'small'}
    if access_key:
        q['accessKey'] = access_key
    if aff:
        q['affiliateId'] = aff
    req = urllib.request.Request(ENDPOINT + '?' + urllib.parse.urlencode(q),
                                 headers={'User-Agent': 'oshi-gourmet-map (https://gourmet.oshikatsu-guide.com)',
                                          # 楽天ウェブサービスは「許可されたWebサイト」に登録したドメインからの要求だけ受け付ける
                                          'Referer': SITE + '/', 'Origin': SITE})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:300]
        if e.code == 404 and 'not_found' in body:
            return {'hotels': []}
        raise SystemExit(redact(f'楽天トラベルAPIのエラー {e.code}: {body}'))


def nfkc(s):
    """APIの宿名は全角英数字（ＫＯＫＯ　ＨＯＴＥＬ）が多く、スマホで1文字ずつ折り返すので半角にそろえる"""
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip()


def basic_infos(data):
    """formatVersion 1/2 のどちらの形でも hotelBasicInfo を取り出す"""
    out = []
    for h in data.get('hotels') or []:
        items = h if isinstance(h, list) else (h.get('hotel') or [])
        for x in items:
            if isinstance(x, dict) and 'hotelBasicInfo' in x:
                out.append(x['hotelBasicInfo'])
    return out


RADII = (1.0, 2.0, RADIUS_KM)   # APIは距離順に並ばないので、狭い半径から全ページ読んで近い順に並べる
MAX_PAGES = 10


def nearby_infos(lat, lng, app_id, access_key, aff):
    """半径1km→2km→3km の順に、MAX_HOTELS 軒以上見つかるまで全ページを読む"""
    infos = []
    for r in RADII:
        infos, page = [], 1
        while True:
            data = search(lat, lng, app_id, access_key, aff, r, page)
            infos += basic_infos(data)
            pc = (data.get('pagingInfo') or {}).get('pageCount') or 1
            if page >= min(pc, MAX_PAGES):
                break
            page += 1
            time.sleep(WAIT)
        if len(infos) >= MAX_HOTELS:
            break
        time.sleep(WAIT)
    return infos


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    app_id = os.environ.get('RAKUTEN_APP_ID')
    if not app_id:
        raise SystemExit('環境変数 RAKUTEN_APP_ID（楽天ウェブサービスのアプリID）がありません')
    access_key = os.environ.get('RAKUTEN_ACCESS_KEY', '')
    aff = affiliate_id()
    venues = json.load(open(os.path.join(ROOT, '_data/venues.json'), encoding='utf-8'))
    outp = os.path.join(ROOT, '_data/venue_hotels.json')
    out = json.load(open(outp, encoding='utf-8')) if os.path.exists(outp) else {}
    keys = args or list(venues)
    for i, k in enumerate(keys):
        v = venues[k]
        if i:
            time.sleep(WAIT)
        infos = nearby_infos(v['lat'], v['lng'], app_id, access_key, aff)
        rows = []
        for h in infos:
            try:
                d = km((v['lat'], v['lng']), (float(h['latitude']), float(h['longitude'])))
            except (KeyError, TypeError, ValueError):
                continue
            url = h.get('hotelInformationUrl') or ''
            if not url or d > RADIUS_KM:
                continue
            if any(x['u'] == url for x in rows):
                continue
            rows.append({'n': nfkc(h.get('hotelName', '')), 'u': url, 'm': int(round(d * 1000, -1)),
                         'st': nfkc(h.get('nearestStation') or ''),
                         'img': (h.get('hotelThumbnailUrl') or '').replace('http://', 'https://')})
        rows.sort(key=lambda x: x['m'])
        rows = rows[:MAX_HOTELS]
        print(k, v['name'], len(infos), '件中', len(rows), '軒')
        if rows:
            out[k] = {'hotels': rows, 'r': RADIUS_KM, 'at': time.strftime('%Y-%m-%d')}
    if not dry:
        json.dump(out, open(outp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('書き込み', outp)


if __name__ == '__main__':
    main()
