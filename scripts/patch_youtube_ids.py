"""
patch_youtube_ids.py
shops.json の source_video_title から YouTube Data API で youtube_id を補完する

対象グループ: sixtones, nogizaka46, hinatazaka46, sakurazaka46, ginga
使い方:
  export YOUTUBE_API_KEY="..."
  python scripts/patch_youtube_ids.py [--dry-run]
"""

import json
import os
import time
import urllib.request
import urllib.parse
import argparse

API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
SHOPS_PATH = 'data/shops.json'

TARGET_GROUPS = {'sixtones', 'nogizaka46', 'hinatazaka46', 'sakurazaka46', 'ginga'}

# グループごとのチャンネルID（YouTube Data API で確認済み）
CHANNEL_IDS = {
    'sixtones':     'UCwjAKjycHHT1QzHrQN5Stww',  # ストチューブ（確認済み）
    'nogizaka46':   'UCUzpZpX2wRYOk3J8QTFGxDg',  # 乃木坂46 OFFICIAL（確認済み）
    'nogizaka46_haishin': 'UCfvohDfHt1v5N8l3BzPRsWQ',  # 乃木坂配信中（確認済み）
    'hinatazaka46': 'UCR0V48DJyWbwEAdxLL5FjxA',  # 日向坂46 OFFICIAL（確認済み）
    'sakurazaka46': 'UCmr9bYmymcBmQ1p2tLBRvwg',  # 櫻坂46 OFFICIAL（確認済み）
}

# 乃木坂46 のvlog系はhaishinチャンネルで検索するタイトル一覧
NOGI_HAISHIN_TITLES = {
    '乃木坂46 浅草食べ歩きVlog',
    '乃木坂46 久保史緒里のカレー探訪',
    '乃木坂46 絶品うどんを食す',
    '乃木坂ってどこ？',
    '乃木坂どこへ',
    '乃木坂工事中',
    '松村沙友理ちゃんねる',
}

# MV系タイトル → 乃木坂チャンネルで検索するキーワードマッピング
NOGI_MV_SEARCH = {
    '17thインフルエンサーType-A': '乃木坂46 インフルエンサー Type-A',
    '17thインフルエンサーType-C': '乃木坂46 インフルエンサー Type-C',
    '20thシンクロニシティType-B': '乃木坂46 シンクロニシティ Type-B',
    '21thジコチューで行こう！Type-D': '乃木坂46 ジコチューで行こう Type-D',
    '22nd帰り道は遠回りしたくなるType-A': '乃木坂46 帰り道は遠回りしたくなる',
    '他の星から': '乃木坂46 他の星から',
}

def yt_search(q, channel_id=None, max_results=5):
    """YouTube Data API で動画を検索し、(video_id, title) リストを返す"""
    params = {
        'part': 'snippet',
        'q': q,
        'type': 'video',
        'maxResults': max_results,
        'key': API_KEY,
    }
    if channel_id:
        params['channelId'] = channel_id
    url = 'https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        items = data.get('items', [])
        return [(i['id']['videoId'], i['snippet']['title']) for i in items if i['id'].get('videoId')]
    except Exception as e:
        print(f'  API Error: {e}')
        return []

def title_match_score(query, result_title):
    """クエリのキーワードがresult_titleにどれだけ含まれるか（0.0〜1.0）"""
    # 記号・助詞を除いたキーワードを抽出
    import re
    # 括弧の内容含め分割
    words = re.split(r'[\s　【】「」\-　]+', query)
    words = [w for w in words if len(w) >= 2]
    if not words:
        return 0.0
    matched = sum(1 for w in words if w in result_title)
    return matched / len(words)

def get_group(shop):
    gs = shop.get('groups', [shop.get('group', '')])
    return gs[0] if gs else ''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='shops.jsonを更新せずに結果だけ表示')
    args = parser.parse_args()

    if not API_KEY:
        print('ERROR: YOUTUBE_API_KEY が設定されていません')
        return

    with open(SHOPS_PATH, encoding='utf-8') as f:
        shops = json.load(f)

    # youtube_id / thumbnail_url がなく、source_video_title があるターゲット店舗を収集
    targets = []
    for shop in shops:
        g = get_group(shop)
        if g not in TARGET_GROUPS:
            continue
        if shop.get('youtube_id') or shop.get('thumbnail_url'):
            continue
        title = shop.get('source_video_title', '').strip()
        if not title:
            continue
        targets.append(shop)

    print(f'補完対象: {len(targets)} 件')

    # ユニーク(グループ, タイトル) でAPIを叩く
    title_to_yt = {}  # (group, title) -> youtube_id

    unique_pairs = list({(get_group(s), s['source_video_title'].strip()) for s in targets})
    unique_pairs.sort()

    for group, title in unique_pairs:
        key = (group, title)
        if key in title_to_yt:
            continue

        # 検索クエリ構築
        if group == 'nogizaka46' and title in NOGI_MV_SEARCH:
            q = NOGI_MV_SEARCH[title]
        else:
            q = title

        # チャンネルID選択（乃木坂はvlog系とMV系で分ける）
        if group == 'nogizaka46' and title in NOGI_HAISHIN_TITLES:
            channel_id = CHANNEL_IDS.get('nogizaka46_haishin')
        else:
            channel_id = CHANNEL_IDS.get(group)

        print(f'\n[{group}] "{title}" → 検索: "{q}"')
        results = yt_search(q, channel_id=channel_id)
        time.sleep(0.3)

        # タイトルマッチスコアで最良結果を選択（スコア0.3以上）
        MIN_SCORE = 0.3
        best_id, best_title, best_score = None, None, 0.0
        for yt_id, yt_title in results:
            score = title_match_score(q, yt_title)
            if score > best_score:
                best_score, best_id, best_title = score, yt_id, yt_title

        if best_id and best_score >= MIN_SCORE:
            print(f'  ✓ [{best_score:.2f}] {best_id} : {best_title[:60]}')
            title_to_yt[key] = best_id
        elif results and channel_id:
            # チャンネル内で見つからない場合はチャンネルなしで再検索
            results2 = yt_search(q)
            time.sleep(0.3)
            for yt_id, yt_title in results2:
                score = title_match_score(q, yt_title)
                if score > best_score:
                    best_score, best_id, best_title = score, yt_id, yt_title
            if best_id and best_score >= MIN_SCORE:
                print(f'  ✓ (global) [{best_score:.2f}] {best_id} : {best_title[:60]}')
                title_to_yt[key] = best_id
            else:
                print(f'  ✗ スコア不足 (最高{best_score:.2f}): {best_title[:40] if best_title else "none"}')
                title_to_yt[key] = None
        else:
            print(f'  ✗ 見つからず')
            title_to_yt[key] = None

    # shops.json 更新
    updated = 0
    for shop in shops:
        g = get_group(shop)
        if g not in TARGET_GROUPS:
            continue
        if shop.get('youtube_id') or shop.get('thumbnail_url'):
            continue
        title = shop.get('source_video_title', '').strip()
        if not title:
            continue
        yt_id = title_to_yt.get((g, title))
        if yt_id:
            shop['youtube_id'] = yt_id
            updated += 1

    print(f'\n合計 {updated} 件に youtube_id を付与')

    if not args.dry_run:
        with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
        print(f'shops.json を更新しました')
    else:
        print('(dry-run: shops.json は更新していません)')

if __name__ == '__main__':
    main()
