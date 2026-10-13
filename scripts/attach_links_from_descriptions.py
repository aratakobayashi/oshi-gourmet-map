"""
attach_links_from_descriptions.py
YouTube の店について、動画の説明文（YouTuber 本人が書いたもの）にある
食べログの店ページのURLとホットペッパーの店ページのURLを、その店に付ける。
- 食べログのページには一切アクセスしない（説明文に書かれたURLの文字列だけを使う）。
  本人が説明文に載せた店ページのURLなので tabelog_verified: true を付ける（店舗ページのボタンが店のページへ直接つながる）。
- 1本の動画に店が複数あるときは、説明文の中で店名の行のすぐ近く（前後4行）にあるURLだけを使う。
  1本の動画に店が1軒で、説明文に店名があり、店ページURLも1つだけのときは、そのURLを使う。どちらでもなければ付けない。
- すでに tabelog_verified の店・hotpepper_url がある店は変えない。
使い方: python scripts/attach_links_from_descriptions.py [--write] [--group susuru,shinoken]
YOUTUBE_API_KEY が必要。書き込んだあとは bash scripts/build_pages.sh。
"""
import collections
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'shops.json')
TB = re.compile(r'https?://(?:s\.)?tabelog\.com/([a-z]+/A\d{4}/A\d{6}/\d{6,9})/?')
HP = re.compile(r'https?://(?:www\.)?hotpepper\.jp/(str[JS]\d{9})/?')


def norm(s):
    return re.sub(r'[\s　・\-－~〜（）()【】「」『』]', '', unicodedata.normalize('NFKC', s or '')).lower()


def descriptions(ids, key):
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({'part': 'snippet', 'id': ','.join(ids[i:i + 50]), 'key': key})
        with urllib.request.urlopen('https://www.googleapis.com/youtube/v3/videos?' + q, timeout=30) as r:
            for it in json.load(r).get('items', []):
                out[it['id']] = it['snippet'].get('description', '')
        time.sleep(0.2)
    return out


def near_url(lines, shop_name, pattern):
    key = norm(shop_name)[:6]
    if len(key) < 2:
        return None
    for i, ln in enumerate(lines):
        if key in norm(ln):
            found = []
            for j in range(max(0, i - 4), min(len(lines), i + 5)):
                found += pattern.findall(lines[j])
            found = list(dict.fromkeys(found))
            if len(found) == 1:
                return found[0]
    return None


def main():
    write = '--write' in sys.argv
    only = None
    if '--group' in sys.argv:
        only = set(sys.argv[sys.argv.index('--group') + 1].split(','))
    key = os.environ['YOUTUBE_API_KEY']
    raw = open(PATH, encoding='utf-8').read()
    shops = json.loads(raw)
    by_vid = collections.defaultdict(list)
    for s in shops:
        if s.get('youtube_id') and (only is None or s.get('group') in only):
            by_vid[s['youtube_id']].append(s)
    desc = descriptions(by_vid.keys(), key)
    n_tb = n_hp = 0
    for vid, ss in by_vid.items():
        text = desc.get(vid, '')
        if not text:
            continue
        lines = text.splitlines()
        all_tb = list(dict.fromkeys(TB.findall(text)))
        all_hp = list(dict.fromkeys(HP.findall(text)))
        for s in ss:
            if norm(s['name'])[:6] not in norm(text):
                continue  # 説明文に店名がない回は付けない（別の店のURLかもしれないため）
            if not s.get('tabelog_verified'):
                t = near_url(lines, s['name'], TB) if len(ss) > 1 else (all_tb[0] if len(all_tb) == 1 else near_url(lines, s['name'], TB))
                if t:
                    s['tabelog_url'] = f'https://tabelog.com/{t}/'
                    s['tabelog_verified'] = True
                    n_tb += 1
            if not s.get('hotpepper_url'):
                h = near_url(lines, s['name'], HP) if len(ss) > 1 else (all_hp[0] if len(all_hp) == 1 else near_url(lines, s['name'], HP))
                if h:
                    s['hotpepper_url'] = f'https://www.hotpepper.jp/{h}/'
                    n_hp += 1
    print(f'食べログの店ページ: {n_tb}軒 / ホットペッパー: {n_hp}軒（説明文を見た動画 {len(desc)}本）')
    if write:
        with open(PATH, 'w', encoding='utf-8') as f:
            f.write(json.dumps(shops, ensure_ascii=False, indent=2 if raw.startswith('[\n  {') else None) + ('\n' if raw.endswith('\n') else ''))
        print('data/shops.json に書き込みました')


if __name__ == '__main__':
    main()
