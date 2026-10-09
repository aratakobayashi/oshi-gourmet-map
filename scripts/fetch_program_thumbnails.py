"""
fetch_program_thumbnails.py
画像のない店舗（youtube_id も thumbnail_url もない）に、出典のテレビ番組・ドラマの
TMDB 画像を thumbnail_url として補完する。

- source_video_title に含まれる番組名を下の PROGRAMS で TMDB の作品IDに対応づける
  （複数の番組名を含むときは、タイトルの先頭に近いほうを採用。
    『』の中は「『キントレ』と同じ店」のような引き合いが多いので見ない）
- エピソードの画像（still）があり、回が特定できるときはそれを使う
    * 「Season8 第8話」「Season11 Episode2」→ シーズン・話数
    * 「第5話」→ シーズン1の話数
    * 放送日（broadcast_date / visited_date / タイトル内の日付）が放送日と一致する回
- 回が特定できないときは作品のポスター
- tmdb_id / tmdb_type が空なら一緒に入れる（source_type は表示が変わるので触らない）
- 対応表にない番組（YouTube・MV・雑誌など）は対象外

使い方:
  python scripts/fetch_program_thumbnails.py --dry-run   # 変更せず件数だけ確認
  python scripts/fetch_program_thumbnails.py

TMDB_API_KEY は v3 の API キーでも v4 の読み取りトークン（eyJ...）でもよい。
"""

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter

TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')
TMDB_IMG = 'https://image.tmdb.org/t/p/w500'
SHOPS_PATH = 'data/shops.json'

# (タイトル中の番組名の正規表現, TMDB ID, 'tv' / 'movie')
# ID は TMDB で番組名・放送局・放送開始日を確認したもの
PROGRAMS = [
    (r'嵐にしやがれ', 106410, 'tv'),
    (r'キントレ', 230387, 'tv'),
    (r'V ?S魂', 115908, 'tv'),
    (r'それスノ|それSnow Man', 123947, 'tv'),
    (r'乃木坂工事中', 96386, 'tv'),
    (r'そこ曲がったら、?櫻坂', 207553, 'tv'),
    (r'だが、情熱はある', 222372, 'tv'),
    (r'乃木坂、逃避行', 262348, 'tv'),
    (r'乃木坂って、?どこ', 95855, 'tv'),
    (r'NOGIBINGO', 96069, 'tv'),
    (r'日向坂で会いましょう', 99748, 'tv'),
    (r'ブンブブーン', 82346, 'tv'),
    (r'リア突WEST', 111395, 'tv'),
    (r'イキスギ', 204158, 'tv'),
    (r'笑ってコラえて', 113701, 'tv'),
    (r'帰れマンデー', 113795, 'tv'),
    (r'ニノさん', 82913, 'tv'),
    (r'行列のできる', 111383, 'tv'),
    (r'ヒルナンデス', 45931, 'tv'),
    (r'トークィーンズ', 198097, 'tv'),
    (r'ゴールデンストーンズ', 289046, 'tv'),
    (r'ゲームオブストーンズ|Game of SixTONES', 280918, 'tv'),
    (r'6SixTONES|シクスト', 317409, 'tv'),
    (r'早起きせっかくグルメ', 230552, 'tv'),
    (r'せっかくグルメ|せかっくグルメ', 111380, 'tv'),
    (r'相席食堂', 111152, 'tv'),
    (r'タイムレスマン', 289474, 'tv'),
    (r'timelesz project -AUDITION', 271418, 'tv'),
    (r'timelesz project -REAL', 312921, 'tv'),
    (r'めざましテレビ', 6563, 'tv'),
    (r'アナザースカイ', 112062, 'tv'),
    (r'モニタリング', 107105, 'tv'),
    (r'シューイチ', 123590, 'tv'),
    (r'ごぶごぶ', 110816, 'tv'),
    (r'人生最高レストラン', 112042, 'tv'),
    (r'キスマイ超BUSAIKU', 123772, 'tv'),
    (r'気になるマン', 319679, 'tv'),
    (r'10万円でできるかな', 113796, 'tv'),
    (r'Travis Japanのダンスだぜ', 322733, 'tv'),
    (r'いただきハイジャンプ', 197002, 'tv'),
    (r'いたジャン', 295157, 'tv'),
    (r'あっちこっちAぇ', 254204, 'tv'),
    (r'過ぎるTV', 111078, 'tv'),
    (r'キンプる|King ?& ?Princeる', 197231, 'tv'),
    (r'オオカミ少年', 107585, 'tv'),
    (r'ケンミンSHOW', 46442, 'tv'),
    (r'初耳学', 111394, 'tv'),
    (r'金スマ', 200950, 'tv'),
    (r'グータンヌーボ', 111159, 'tv'),
    (r'ヒロミのおせっ買い', 297118, 'tv'),
    (r'所さんお届けモノです', 113814, 'tv'),
    (r'ドデスカ', 216191, 'tv'),
    (r'木村さ[〜～~]+ん', 195022, 'tv'),
    (r'かまいガチ', 113802, 'tv'),
    (r'孤独のグルメ', 55582, 'tv'),
    (r'Run BTS', 77696, 'tv'),
    (r'BLACKPINK House', 76722, 'tv'),
    (r'全知的おせっかい視点', 80736, 'tv'),
    # ドラマ・映画
    (r'アンサンブル', 278867, 'tv'),
    (r'東京タワー', 247850, 'tv'),
    (r'厨房のありす', 241790, 'tv'),
    (r'西園寺さんは家事をしない', 257510, 'tv'),
    (r'私たちが恋する理由', 270655, 'tv'),
    (r'リブート', 304194, 'tv'),
    (r'あの頃からわたしたちは', 257755, 'tv'),
    (r'恋ムズ|御曹司に恋はムズすぎる', 278132, 'tv'),
    (r'よめぼく|余命一年の僕が', 1291559, 'movie'),
]
PROGRAMS = [(re.compile(p), tid, typ) for p, tid, typ in PROGRAMS]

_cache = {}


def tmdb(path):
    if path in _cache:
        return _cache[path]
    url = f'https://api.themoviedb.org/3/{path}?' + urllib.parse.urlencode({'language': 'ja-JP'})
    headers = {'User-Agent': 'oshi-gourmet-map/1.0'}
    if TMDB_API_KEY.startswith('eyJ'):
        headers['Authorization'] = f'Bearer {TMDB_API_KEY}'
    else:
        url += '&api_key=' + TMDB_API_KEY
    try:
        req = urllib.request.Request(url, headers=headers)
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        print(f'  TMDB {path} 取得エラー: {e}')
        data = None
    _cache[path] = data
    time.sleep(0.1)
    return data


def match_program(title):
    title = re.sub(r'『[^』]*』', '', title)
    best = None
    for rx, tid, typ in PROGRAMS:
        m = rx.search(title)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), tid, typ)
    return best[1:] if best else None


def find_dates(shop):
    """放送日の候補（YYYY-MM-DD）"""
    dates = []
    for k in ('broadcast_date', 'visited_date'):
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', shop.get(k) or ''):
            dates.append(shop[k])
    for y, m, d in re.findall(r'(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})', shop.get('source_video_title') or ''):
        dates.append(f'{y}-{int(m):02d}-{int(d):02d}')
    return dates


def episode_still(tid, shop):
    """回が特定できればそのエピソード画像（なければ None）"""
    title = shop.get('source_video_title') or ''
    m = re.search(r'Season\s*(\d+)\s*(?:Episode\s*|第)(\d+)', title)
    if m:
        ep = tmdb(f'tv/{tid}/season/{m.group(1)}/episode/{m.group(2)}')
        return ep.get('still_path') if ep else None
    m = re.search(r'第(\d+)話', title)
    if m:
        ep = tmdb(f'tv/{tid}/season/1/episode/{m.group(1)}')
        return ep.get('still_path') if ep else None
    dates = find_dates(shop)
    if not dates:
        return None
    show = tmdb(f'tv/{tid}')
    for se in (show or {}).get('seasons', []):
        if not se.get('episode_count'):
            continue
        sd = tmdb(f"tv/{tid}/season/{se['season_number']}")
        for e in (sd or {}).get('episodes', []):
            if e.get('air_date') in dates and e.get('still_path'):
                return e['still_path']
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not TMDB_API_KEY:
        raise SystemExit('TMDB_API_KEY が未設定です。export TMDB_API_KEY=... を実行してください。')

    with open(SHOPS_PATH, encoding='utf-8') as f:
        shops = json.load(f)

    targets = [s for s in shops if not s.get('youtube_id') and not s.get('thumbnail_url')]
    print(f'画像なし: {len(targets)}件 / 全{len(shops)}件')

    kinds = Counter()
    by_program = Counter()
    skipped = Counter()
    for s in targets:
        hit = match_program(s.get('source_video_title') or '')
        if not hit:
            skipped[s.get('group')] += 1
            continue
        tid, typ = hit
        info = tmdb(f'{typ}/{tid}')
        if not info:
            skipped[s.get('group')] += 1
            continue
        still = episode_still(tid, s) if typ == 'tv' else None
        path = still or info.get('poster_path')
        if not path:
            skipped[s.get('group')] += 1
            continue
        kinds['エピソード画像' if still else 'ポスター'] += 1
        by_program[info.get('name') or info.get('title')] += 1
        if args.dry_run:
            continue
        s['thumbnail_url'] = TMDB_IMG + path
        if not s.get('tmdb_id'):
            s['tmdb_id'] = tid
            s['tmdb_type'] = typ

    print(f'補完: {sum(kinds.values())}件 {dict(kinds)}')
    for name, n in by_program.most_common():
        print(f'  {n:4d} {name}')
    print(f'対象外（対応する番組なし）: {sum(skipped.values())}件')
    for g, n in skipped.most_common():
        print(f'  {n:4d} {g}')

    if not args.dry_run:
        with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
        print(f'保存: {SHOPS_PATH}')


if __name__ == '__main__':
    main()
