"""
fetch_channel_videos.py
YouTubeチャンネルの動画一覧を取得してJSONで出力するスクリプト

使い方:
  python scripts/fetch_channel_videos.py --channel UCxxxxxx --group yonino --output videos_yonino.json
"""

import os
import json
import argparse
import urllib.request
import urllib.parse

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise RuntimeError("環境変数 YOUTUBE_API_KEY が設定されていません")

# グループ別チャンネルID
CHANNELS = {
    "yonino":       "UC2alHD2WkakOiTxCxF-uMAg",
    "snowman":      "UCuFPaemAaMR8R5cHzjy23dQ",
    "sixtones":     "UCwFDNbq5N2lBcCQPg3QlE4g",  # 要確認
    "equal_love":   "UCEBTzMCwDXEoMPJQA06jw3g",  # 要確認
    "nogizaka46":   "UCdYBBJRbE7FqLxBWbMH9-6g",  # 要確認
    "hinatazaka46": "UC2b7WYrUaNTZ-GBXQ7fBxRQ",  # 要確認
    "sakurazaka46": "UCjiGiqRGBCiHpIkHpJKjNiQ",  # 要確認
}

def api_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "oshi-gourmet-map/1.0"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def get_uploads_playlist_id(channel_id):
    url = (
        "https://www.googleapis.com/youtube/v3/channels"
        f"?part=contentDetails&id={channel_id}&key={API_KEY}"
    )
    data = api_get(url)
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def fetch_videos(playlist_id, max_videos=200):
    videos = []
    next_page = None

    while len(videos) < max_videos:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": API_KEY,
        }
        if next_page:
            params["pageToken"] = next_page

        url = "https://www.googleapis.com/youtube/v3/playlistItems?" + urllib.parse.urlencode(params)
        data = api_get(url)

        for item in data.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            videos.append({
                "youtube_id": video_id,
                "title": snippet["title"],
                "published_at": snippet["publishedAt"][:10],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "description": snippet.get("description", "")[:200],
            })

        next_page = data.get("nextPageToken")
        if not next_page:
            break

    return videos

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", help="チャンネルID（直接指定）")
    parser.add_argument("--group", choices=list(CHANNELS.keys()), help="グループ名")
    parser.add_argument("--max", type=int, default=200, help="最大取得動画数（デフォルト200）")
    parser.add_argument("--output", default="videos.json", help="出力ファイル名")
    args = parser.parse_args()

    channel_id = args.channel or CHANNELS.get(args.group)
    if not channel_id:
        print("--channel または --group を指定してください")
        print("利用可能なグループ:", list(CHANNELS.keys()))
        return

    print(f"チャンネルID: {channel_id}")
    print("再生リストID取得中...")
    playlist_id = get_uploads_playlist_id(channel_id)

    print(f"動画一覧取得中（最大{args.max}件）...")
    videos = fetch_videos(playlist_id, args.max)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {len(videos)}件 → {args.output}")
    print("\n最新5件:")
    for v in videos[:5]:
        print(f"  [{v['published_at']}] {v['title']}")
        print(f"    {v['url']}")

if __name__ == "__main__":
    main()
