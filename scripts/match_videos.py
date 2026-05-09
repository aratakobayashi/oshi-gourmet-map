"""
match_videos.py
スクレイピングした店舗データにYouTube動画IDを日付照合で紐付けるスクリプト

使い方:
  python scripts/match_videos.py \
    --shops scripts/geocoded_naniwa.json \
    --videos scripts/videos_naniwa.json \
    --output scripts/matched_naniwa.json \
    --tolerance 3

  --tolerance: 日付の許容ズレ（日数）。デフォルト3日。
               ロケ収録日と公開日のズレを吸収するための値。
"""

import json
import argparse
from datetime import date, timedelta


def parse_date(s: str):
    """YYYY-MM-DD → date オブジェクト"""
    if not s:
        return None
    try:
        y, m, d = s[:10].split('-')
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shops', required=True, help='geocoded shops JSON')
    parser.add_argument('--videos', required=True, help='videos JSON (fetch_channel_videos.py の出力)')
    parser.add_argument('--output', required=True, help='出力ファイル')
    parser.add_argument('--tolerance', type=int, default=3, help='日付ズレの許容日数')
    args = parser.parse_args()

    with open(args.shops, encoding='utf-8') as f:
        shops = json.load(f)

    with open(args.videos, encoding='utf-8') as f:
        videos = json.load(f)

    # videos を日付でインデックス化
    date_to_videos: dict[date, list] = {}
    for v in videos:
        d = parse_date(v.get('published_at', ''))
        if d:
            date_to_videos.setdefault(d, []).append(v)

    matched = 0
    unmatched = 0

    for shop in shops:
        if shop.get('youtube_id'):
            matched += 1
            continue

        shop_date = parse_date(shop.get('visited_date', ''))
        if not shop_date:
            unmatched += 1
            continue

        # 許容範囲内で最も近い動画を探す
        best_video = None
        best_delta = timedelta(days=args.tolerance + 1)

        for delta_days in range(args.tolerance + 1):
            for sign in ([0] if delta_days == 0 else [1, -1]):
                candidate_date = shop_date + timedelta(days=delta_days * sign)
                candidates = date_to_videos.get(candidate_date, [])
                if candidates:
                    delta = timedelta(days=abs(delta_days))
                    if delta < best_delta:
                        best_delta = delta
                        best_video = candidates[0]

        if best_video:
            shop['youtube_id'] = best_video['youtube_id']
            shop['source_video_title'] = best_video['title']
            shop['source_video_url'] = best_video['url']
            delta_str = f'±{best_delta.days}日' if best_delta.days > 0 else '完全一致'
            print(f'  ✓ [{shop["visited_date"]}] {shop["name"]} → {best_video["youtube_id"]} ({delta_str})')
            print(f'       "{best_video["title"]}"')
            matched += 1
        else:
            print(f'  ✗ [{shop.get("visited_date","")}] {shop["name"]} → 紐付け失敗')
            unmatched += 1

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n=== 結果 ===')
    print(f'紐付け成功: {matched}件')
    print(f'紐付け失敗: {unmatched}件')
    print(f'→ {args.output}')


if __name__ == '__main__':
    main()
