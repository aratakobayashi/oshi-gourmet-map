"""
fetch_hotpepper_photos.py
hotpepper_url のある店舗に、ホットペッパーグルメ公式API（グルメサーチAPI）の店舗写真を
hotpepper_photo として付ける。

- 店舗IDは hotpepper_url（https://www.hotpepper.jp/strJ000000000/）から取る
- 写真は API が返す photo.pc.l（画像はホットペッパーのサーバーを直接参照する）
- API で見つからなくなった店（掲載終了など）は hotpepper_photo を外す
- 表示の優先順: YouTube動画 → hotpepper_photo → thumbnail_url（TMDB等）
  hotpepper_photo を出すページ・サイトにはクレジット
  「Powered by ホットペッパー Webサービス」を表示する（shop.html / footer.html）
- 写真は掲載内容が変わるので、ときどき再実行して最新にする

hotpepper_url がまだない店は、先に add_hotpepper_urls.py で付ける（名前の一致を目で確認すること）。

使い方:
  export HOTPEPPER_API_KEY="..."   # https://webservice.recruit.co.jp/ で取得
  python scripts/fetch_hotpepper_photos.py --dry-run
  python scripts/fetch_hotpepper_photos.py
"""

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request

HOTPEPPER_API = 'https://webservice.recruit.co.jp/hotpepper/gourmet/v1/'
SHOPS_PATH = 'data/shops.json'
SLEEP_SEC = 0.5


def shop_id_of(url):
    m = re.search(r'/str(J\d+)', url or '')
    return m.group(1) if m else None


def lookup(api_key, hp_id):
    """店舗IDで1件取得。見つからなければ {}、通信エラーなら None"""
    params = {'key': api_key, 'id': hp_id, 'format': 'json'}
    url = HOTPEPPER_API + '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'oshi-gourmet-map/1.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        print(f'  {hp_id} APIエラー: {e}')
        return None
    results = data.get('results', {})
    if 'error' in results:
        raise SystemExit(f'APIエラー: {results["error"]}')
    shops = results.get('shop') or []
    return shops[0] if shops else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    api_key = os.environ.get('HOTPEPPER_API_KEY', '')
    if not api_key:
        raise SystemExit('HOTPEPPER_API_KEY が未設定です。export HOTPEPPER_API_KEY=... を実行してください。')

    with open(SHOPS_PATH, encoding='utf-8') as f:
        shops = json.load(f)

    targets = [s for s in shops if shop_id_of(s.get('hotpepper_url'))]
    print(f'対象（hotpepper_urlあり）: {len(targets)}件 / 全{len(shops)}件')

    added = updated = removed = errors = 0
    for s in targets:
        hp = lookup(api_key, shop_id_of(s['hotpepper_url']))
        time.sleep(SLEEP_SEC)
        if hp is None:
            errors += 1
            continue
        photo = (((hp.get('photo') or {}).get('pc') or {}).get('l')) or ''
        old = s.get('hotpepper_photo', '')
        if photo == old:
            continue
        if not photo:
            removed += 1
            print(f'  写真なし・掲載終了?: {s["name"]} ({s["hotpepper_url"]})')
            if not args.dry_run:
                s.pop('hotpepper_photo', None)
            continue
        if old:
            updated += 1
        else:
            added += 1
            print(f'  + {s["name"]} ← {hp.get("name")}')
        if not args.dry_run:
            s['hotpepper_photo'] = photo

    print(f'追加 {added}件 / 更新 {updated}件 / 削除 {removed}件 / エラー {errors}件')
    if not args.dry_run and (added or updated or removed):
        with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'保存: {SHOPS_PATH}（このあと bash scripts/build_pages.sh）')


if __name__ == '__main__':
    main()
