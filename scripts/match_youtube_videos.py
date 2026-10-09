"""
match_youtube_videos.py
youtube_id のない店舗のうち、出典が公式YouTubeチャンネルの企画（すのちゅーぶ・Aぇちゅ〜ぶ など）
のものを、YouTube Data API で取ったチャンネルの動画一覧と照合して youtube_id を付ける。
youtube_id が付くと、動画サムネイル（i.ytimg.com）が店舗の画像になる。

照合のしかた（youtube_id は API から取ったものだけを使う。推測で作らない）
- 日付: visited_date / broadcast_date / タイトル中の日付と、動画の公開日の差
- タイトル: 出典タイトルと動画タイトルの文字の重なり（2文字単位）
- 自動で入れるのは「日付が2日以内で一致 かつ 候補が1本だけ」か
  「タイトルがよく似ていて（--min-sim 以上）2位と差があり、日付が1週間以内（日付不明なら不問）」のときだけ
- それ以外は scripts/youtube_match_review.json に候補を書き出す。目で確認して
  "youtube_id" を書き込み、--apply-review で反映する

使い方:
  export YOUTUBE_API_KEY="..."
  python scripts/match_youtube_videos.py --dry-run
  python scripts/match_youtube_videos.py
  python scripts/match_youtube_videos.py --apply-review   # 確認済みの候補を反映

動画一覧は scripts/cache/yt_<ハンドル>.json に保存する（--refresh で取り直し）。
"""

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date

API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
SHOPS_PATH = 'data/shops.json'
CACHE_DIR = 'scripts/cache'
REVIEW_PATH = 'scripts/youtube_match_review.json'

# (出典タイトルの正規表現, チャンネル: '@ハンドル' または 'UC...' のチャンネルID)
# 複数に当たるときは上にあるものを使う
SERIES = [
    (r'すのちゅーぶ|旅スノ', '@SnowMan.official.9'),
    (r'ストチューブ|^SixTONES - ', '@SixTONES_st'),
    (r'Aぇちゅ', '@Aegroup_official'),  # 2024-04 より前の動画はジュニアチャンネルにある
    (r'乃木坂配信中|さくさんぽ', 'UCfvohDfHt1v5N8l3BzPRsWQ'),
    (r'なにわTube', '@naniwadanshi_official'),
    (r'亀梨和也チャンネル|亀チャンネル', '@k_kamenashi_23'),
    (r'中丸銀河|銀河ちゃんねる', 'UCYTrZoOfDgoQo7Bdbttv9qw'),
    (r'よにの', 'UC2alHD2WkakOiTxCxF-uMAg'),
    # WESTube（WEST.）・ジャにのちゃんねる はハンドル未確認。確認したらここに足す
]
SERIES = [(re.compile(p), ch) for p, ch in SERIES]

# 照合で無視する語（どの出典タイトルにも出る言葉）
NOISE = re.compile(r'ロケ地|はどこ|どこ|食べた|メニュー|お店|店舗|撮影|いつ|何|聖地巡礼|まとめ|グルメ回|'
                   r'すのちゅーぶ|Snow ?Man|SixTONES|ストチューブ|Aぇちゅ〜ぶ|Aぇ!? ?group|[【】「」『』？?！!、。・（）()\s]')


def api(path, **params):
    params['key'] = API_KEY
    url = f'https://www.googleapis.com/youtube/v3/{path}?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def channel_videos(channel, refresh=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, 'yt_' + re.sub(r'[^\w.-]', '', channel) + '.json')
    if os.path.exists(cache) and not refresh:
        return json.load(open(cache, encoding='utf-8'))
    if channel.startswith('@'):
        data = api('channels', part='contentDetails', forHandle=channel)
    else:
        data = api('channels', part='contentDetails', id=channel)
    if not data.get('items'):
        print(f'  チャンネルが見つかりません: {channel}')
        return []
    uploads = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    videos, token = [], None
    while True:
        params = dict(part='snippet', playlistId=uploads, maxResults=50)
        if token:
            params['pageToken'] = token
        page = api('playlistItems', **params)
        for it in page.get('items', []):
            sn = it['snippet']
            vid = sn['resourceId']['videoId']
            videos.append({'youtube_id': vid, 'title': sn['title'], 'published_at': sn['publishedAt'][:10]})
        token = page.get('nextPageToken')
        if not token:
            break
    json.dump(videos, open(cache, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  {channel}: {len(videos)}本')
    return videos


def shop_dates(s):
    out = []
    for k in ('visited_date', 'broadcast_date'):
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s.get(k) or ''):
            out.append(s[k])
    for y, m, d in re.findall(r'(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})', s.get('source_video_title') or ''):
        out.append(f'{y}-{int(m):02d}-{int(d):02d}')
    return [date.fromisoformat(x) for x in out]


def bigrams(t):
    t = re.sub(r'[\d/:.-]', '', NOISE.sub('', t))  # 日付は score() の日付で見る
    return {t[i:i + 2] for i in range(len(t) - 1)}


def similarity(a, b):
    A, B = bigrams(a), bigrams(b)
    return len(A & B) / len(A) if A else 0.0


def score(shop, video):
    sim = similarity(shop.get('source_video_title') or '', video['title'])
    days = None
    pub = date.fromisoformat(video['published_at'])
    for d in shop_dates(shop):
        diff = abs((pub - d).days)
        days = diff if days is None else min(days, diff)
    return sim, days


def apply(shop, video):
    shop['youtube_id'] = video['youtube_id']
    shop['source_video_url'] = f'https://www.youtube.com/watch?v={video["youtube_id"]}'
    shop['source_video_title'] = video['title']
    if not shop.get('visited_date'):
        shop['visited_date'] = video['published_at']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--refresh', action='store_true', help='動画一覧を取り直す')
    ap.add_argument('--min-sim', type=float, default=0.5)
    ap.add_argument('--apply-review', action='store_true')
    args = ap.parse_args()

    shops = json.load(open(SHOPS_PATH, encoding='utf-8'))
    by_id = {s['id']: s for s in shops}
    changed = 0

    if args.apply_review:
        review = json.load(open(REVIEW_PATH, encoding='utf-8'))
        for r in review:
            vid = (r.get('youtube_id') or '').strip()
            s = by_id.get(r['shop_id'])
            if not s or s.get('youtube_id') or not re.fullmatch(r'[\w-]{11}', vid):
                continue
            cand = next((c for c in r['candidates'] if c['youtube_id'] == vid), None)
            if not cand:
                print(f'  候補にない動画IDは使いません: {r["shop_id"]} {vid}')
                continue
            apply(s, cand)
            changed += 1
    else:
        if not API_KEY:
            raise SystemExit('YOUTUBE_API_KEY が未設定です。export YOUTUBE_API_KEY=... を実行してください。')
        used = {s['youtube_id'] for s in shops if s.get('youtube_id')}
        review = []
        auto = 0
        for s in shops:
            if s.get('youtube_id'):
                continue
            title = s.get('source_video_title') or ''
            ch = next((c for rx, c in SERIES if rx.search(title)), None)
            if not ch:
                continue
            videos = channel_videos(ch, args.refresh)
            scored = []
            for v in videos:
                sim, days = score(s, v)
                if (days is not None and days <= 2) or sim >= 0.3:
                    scored.append((sim, days, v))
            scored.sort(key=lambda x: (x[1] if x[1] is not None else 99, -x[0]))
            pick = None
            near = [x for x in scored if x[1] is not None and x[1] <= 2]
            if len(near) == 1:
                pick = near[0][2]
            else:
                by_sim = sorted(scored, key=lambda x: -x[0])
                if by_sim and by_sim[0][0] >= args.min_sim and (len(by_sim) == 1 or by_sim[0][0] - by_sim[1][0] >= 0.15):
                    # 日付がわかっているのに1週間以上ずれる動画は自動では入れない
                    if not shop_dates(s) or (by_sim[0][1] is not None and by_sim[0][1] <= 7):
                        pick = by_sim[0][2]
            if pick:
                auto += 1
                print(f'  ✓ {s["name"]} ← [{pick["published_at"]}] {pick["title"]}')
                if pick['youtube_id'] in used:
                    print('    （ほかの店と同じ動画。1本に複数店舗が出る回なら問題なし）')
                if not args.dry_run:
                    apply(s, pick)
                    changed += 1
            else:
                review.append({
                    'shop_id': s['id'], 'name': s['name'], 'source_video_title': title,
                    'dates': [d.isoformat() for d in shop_dates(s)], 'youtube_id': '',
                    'candidates': [dict(v, sim=round(sim, 2), days=days) for sim, days, v in scored[:5]],
                })
        print(f'自動で付与: {auto}件 / 確認待ち: {len(review)}件 → {REVIEW_PATH}')
        if not args.dry_run:
            json.dump(review, open(REVIEW_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    if changed and not args.dry_run:
        with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'保存: {SHOPS_PATH} {changed}件（このあと bash scripts/build_pages.sh）')


if __name__ == '__main__':
    main()
