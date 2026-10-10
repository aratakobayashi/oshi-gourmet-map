"""
fill_video_titles.py
youtube_id があるのに source_video_title が空の店に、YouTube の公式 oEmbed から動画タイトルを入れる（キー不要）。
あわせて source_video_channel（チャンネル名）も入れる。何度実行しても同じ結果。

使い方: python scripts/fill_video_titles.py          # 試算（件数と例を表示）
        python scripts/fill_video_titles.py --write  # data/shops.json に書き込む
書き込んだあとは bash scripts/build_pages.sh でページを作り直す。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'shops.json')


def oembed(vid):
    url = 'https://www.youtube.com/oembed?format=json&url=' + urllib.parse.quote(f'https://www.youtube.com/watch?v={vid}', safe='')
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def main():
    write = '--write' in sys.argv
    raw = open(PATH, encoding='utf-8').read()
    shops = json.loads(raw)
    cache = {}
    done = miss = 0
    for s in shops:
        vid = s.get('youtube_id')
        if not vid or s.get('source_video_title'):
            continue
        if vid not in cache:
            cache[vid] = oembed(vid)
            time.sleep(0.2)
        d = cache[vid]
        if not d:
            miss += 1
            continue
        s['source_video_title'] = d['title']
        s.setdefault('source_video_channel', d.get('author_name', ''))
        done += 1
        if done <= 5:
            print(s['id'], '→', d['author_name'], '|', d['title'])
    print(f'タイトルを入れた店 {done} 件 / 取れなかった店 {miss} 件')
    if write:
        indent = 2 if raw.startswith('[\n  {') else None
        open(PATH, 'w', encoding='utf-8').write(json.dumps(shops, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else ''))
        print('data/shops.json に書き込みました')


if __name__ == '__main__':
    main()
