"""
filter_food_videos.py
動画リストから飲食関連動画を抽出し、Gemini用プロンプトを生成するスクリプト

使い方:
  python scripts/filter_food_videos.py --input scripts/videos_yonino.json --group yonino
  python scripts/filter_food_videos.py --input scripts/videos_yonino.json --group yonino --output scripts/food_yonino.json
"""

import json
import argparse

FOOD_KEYWORDS = [
    'メシ', '飯', 'グルメ', '食', 'ランチ', 'ディナー', 'カフェ', 'ラーメン', '寿司', 'すし',
    '焼肉', 'うどん', 'そば', 'パン', 'スイーツ', '居酒屋', '焼き', '鍋', '肉', '魚',
    '海鮮', 'ピザ', 'パスタ', 'イタリアン', 'フレンチ', '中華', 'カレー', '丼',
    '朝食', '昼食', '夕食', 'ご飯', 'おにぎり', '弁当', '定食', '串', '天ぷら',
    'しゃぶ', '唐揚げ', '餃子', '蕎麦', 'とんかつ', '料理',
]

EXCLUDE_KEYWORDS = ['料理作', 'レシピ', 'クッキング', '手作り']

def is_food_video(title: str) -> bool:
    # 除外ワードがあればスキップ
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return False
    # 飲食キーワードを含むか
    for kw in FOOD_KEYWORDS:
        if kw in title:
            return True
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='動画JSONファイル（fetch_channel_videosの出力）')
    parser.add_argument('--group', required=True, help='グループ名（例: yonino）')
    parser.add_argument('--output', help='飲食動画リストの出力ファイル名（省略時は表示のみ）')
    parser.add_argument('--prompt', action='store_true', help='Gemini用プロンプトも出力する')
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        videos = json.load(f)

    food_videos = [v for v in videos if is_food_video(v['title'])]
    print(f'全動画: {len(videos)}件 → 飲食関連: {len(food_videos)}件')
    print()

    for v in food_videos:
        print(f'[{v["published_at"]}] {v["title"]}')
        print(f'  https://www.youtube.com/watch?v={v["youtube_id"]}')
    print()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(food_videos, f, ensure_ascii=False, indent=2)
        print(f'→ {args.output} に保存しました')

    if args.prompt:
        print_gemini_prompt(food_videos, args.group)

def print_gemini_prompt(food_videos, group):
    video_list = '\n'.join(
        f'{i+1}. [{v["published_at"]}] {v["title"]}\n   URL: https://www.youtube.com/watch?v={v["youtube_id"]}'
        for i, v in enumerate(food_videos)
    )

    prompt = f"""以下は YouTubeチャンネル「{group}」の飲食関連動画リストです。
各動画を確認し、実際に飲食店に訪問している動画を特定してください。

【動画リスト】
{video_list}

【出力形式】
訪問している飲食店が特定できた動画について、以下のJSON配列で出力してください。
特定できない動画はスキップしてください。

```json
[
  {{
    "youtube_id": "動画ID（11文字）",
    "source_video_title": "動画タイトル",
    "visited_date": "YYYY-MM-DD",
    "name": "お店名",
    "genre": "カフェ/ラーメン/焼肉/食事/スイーツ/寿司/和食/居酒屋/その他 から選ぶ",
    "prefecture": "都道府県名（例: 東京都）",
    "city": "市区町村名",
    "address": "住所（できるだけ詳細に）",
    "members": ["メンバー名"],
    "group": "{group}",
    "description": "動画の内容・お店の特徴（100文字以内）"
  }}
]
```

【注意事項】
- youtube_id は正確に11文字の英数字で入力すること
- 同じ店が複数動画に登場する場合は、最新の動画1件だけを使用すること
- 架空・不明なお店は含めないこと
- 住所が分からない場合は address を空文字にすること
"""
    print('=' * 60)
    print('【Gemini用プロンプト】')
    print('=' * 60)
    print(prompt)

if __name__ == '__main__':
    main()
