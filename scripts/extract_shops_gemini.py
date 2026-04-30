"""
extract_shops_gemini.py
飲食関連動画リストをGemini APIに投げてお店データを抽出するスクリプト

使い方:
  bash scripts/run_extract_yonino.sh
  python scripts/extract_shops_gemini.py --input scripts/food_yonino.json --group yonino --output scripts/shops_raw_yonino.json
"""

import json
import os
import argparse
import time
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise RuntimeError('環境変数 GEMINI_API_KEY が設定されていません')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

GENRE_LIST = 'カフェ / ラーメン / 焼肉 / 食事 / スイーツ / 寿司 / 和食 / 居酒屋 / その他'


def build_prompt(video: dict, group: str) -> str:
    return f"""あなたはYouTube動画から飲食店情報を抽出するアシスタントです。

以下の動画を見て、実際に飲食店を訪問している動画であればお店情報をJSONで返してください。
飲食店訪問ではない場合（キャンプ・自炊・料理系など）は null を返してください。

【動画情報】
タイトル: {video['title']}
youtube_id: {video['youtube_id']}
投稿日: {video['published_at']}
説明文: {video.get('description', '')}

【ルール】
- メンバー名はフルネームで（例：二宮和也）
- 住所は番地まで書く。不明な場合は空欄にする
- 架空の情報は書かない
- JSONのみ出力すること（説明文不要）

【出力形式】
飲食店あり：
{{
  "youtube_id": "{video['youtube_id']}",
  "source_video_title": "{video['title']}",
  "visited_date": "{video['published_at']}",
  "name": "店名",
  "genre": "{GENRE_LIST} から1つ選ぶ",
  "address": "東京都○○区...（不明なら空欄）",
  "members": ["フルネーム"],
  "group": "{group}",
  "groups": ["{group}"],
  "description": "お店の特徴・動画の内容（100文字以内）"
}}

飲食店なし：
null"""


def extract_json(text: str):
    """Geminiの返答からJSONを抽出。nullなら None を返す"""
    text = text.strip()
    if text.lower() == 'null':
        return None
    if '```json' in text:
        start = text.index('```json') + 7
        end = text.index('```', start)
        text = text[start:end].strip()
    elif '```' in text:
        start = text.index('```') + 3
        end = text.index('```', start)
        text = text[start:end].strip()
    parsed = json.loads(text)
    return None if parsed is None else parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='飲食動画JSONファイル')
    parser.add_argument('--group', required=True, help='グループ名（例: yonino）')
    parser.add_argument('--output', required=True, help='抽出結果の出力ファイル名')
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        videos = json.load(f)

    print(f'動画数: {len(videos)}件 → 1件ずつ処理します\n')

    shops = []
    skipped = 0

    for i, video in enumerate(videos):
        print(f'[{i+1}/{len(videos)}] {video["title"]}')
        prompt = build_prompt(video, args.group)

        try:
            response = model.generate_content(prompt)
            shop = extract_json(response.text)
            if shop:
                shops.append(shop)
                print(f'  → ✅ {shop["name"]} ({shop["genre"]})')
            else:
                skipped += 1
                print(f'  → スキップ（飲食店なし）')
        except Exception as e:
            print(f'  → ❌ エラー: {e}')
            skipped += 1

        time.sleep(2)  # レート制限対策

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f'\n完了: {len(shops)}件抽出 / {skipped}件スキップ')
    print(f'→ {args.output} に保存しました')


if __name__ == '__main__':
    main()
