"""
live_data_split.py
公演の公式データ（ツアー単位: scripts/tour_data/<slug>.json の形、またはその配列のJSON）を、
会場ごとの scripts/live_data/<slug>.json（live_article.py の入力）に分ける。

- 会場名は _data/venues.json の会場に当てはめる（旧名・表記ゆれは ALIAS）。当てはまらない会場は「会場ガイドなし」として一覧に出すだけ
- 終わった公演（最後の日が今日より前）は作らない
- slug は <グループ>-<会場キー>-<最初の公演の年>-<月>（例 equal-love-vantelin-dome-nagoya-2026-12）
使い方: python scripts/live_data_split.py <ツアーJSON> [...]   （--dry-run で書かない）
"""
import datetime
import json
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()
ALIAS = {
    'sapporo-dome': ['札幌ドーム', 'プレミストドーム'],
    'vantelin-dome-nagoya': ['ナゴヤドーム', 'バンテリンドーム'],
    'mizuho-paypay-dome': ['paypayドーム', 'ペイペイドーム', '福岡ドーム'],
    'kyocera-dome-osaka': ['京セラドーム'],
    'saitama-super-arena': ['さいたまスーパーアリーナ', 'gmoアリーナさいたま'],
    'nippon-gaishi-hall': ['日本ガイシホール', 'ガイシホール', 'クロコくんホール'],
    'musashino-forest-sport-plaza': ['武蔵野の森総合スポーツプラザ', '京王アリーナtokyo', '京王アリーナ'],
    'kobe-world-kinen-hall': ['神戸ワールド記念ホール', 'ワールド記念ホール'],
    'marine-messe-fukuoka': ['マリンメッセ福岡'],
    'yoyogi-national-gymnasium': ['代々木競技場第一体育館', '代々木第一体育館', '国立代々木競技場'],
    'makuhari-messe': ['幕張メッセ'],
    'pia-arena-mm': ['ぴあアリーナmm'],
    'hokkai-kitaeru': ['北海きたえーる', '北海道立総合体育センター'],
    'qa-stadium-miyagi': ['キューアンドエースタジアムみやぎ', 'ひとめぼれスタジアム宮城', '宮城スタジアム'],
    'xebio-arena-sendai': ['ゼビオアリーナ仙台'],
    'shizuoka-ecopa-arena': ['エコパアリーナ'],
    'asue-arena-osaka': ['asueアリーナ大阪', '丸善インテックアリーナ大阪', '大阪市中央体育館'],
    'lala-arena-tokyo-bay': ['lalaarenatokyo-bay', 'ららアリーナ'],
    'tokyo-garden-theater': ['東京ガーデンシアター'],
    'k-arena-yokohama': ['kアリーナ横浜'],
    'nissan-stadium': ['日産スタジアム'],
    'belluna-dome': ['ベルーナドーム'],
    'aichi-sky-expo': ['aichiskyexpo'],
}


def norm(s):
    return unicodedata.normalize('NFKC', s or '').replace(' ', '').replace('　', '').lower()


def venue_key(name, venues):
    n = norm(name)
    for k, v in venues.items():
        if norm(v['name']) in n:
            return k
    for k, al in ALIAS.items():
        if any(norm(a) in n for a in al):
            return k
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    venues = json.load(open(os.path.join(ROOT, '_data/venues.json'), encoding='utf-8'))
    os.makedirs(os.path.join(ROOT, 'scripts/live_data'), exist_ok=True)
    made, noguide = [], []
    for a in args:
        d = json.load(open(a, encoding='utf-8'))
        for t in (d if isinstance(d, list) else [d]):
            if t.get('none') or not t.get('stops'):
                continue
            for st in t['stops']:
                dates = sorted(x for x in st.get('dates') or [] if x)
                if not dates or dates[-1] < TODAY:
                    continue
                key = st.get('key') or venue_key(st['venue'], venues)
                if not key or not os.path.exists(os.path.join(ROOT, f'scripts/venue_data/{key}.json')):
                    noguide.append((t['group'], st['venue'], dates[0]))
                    continue
                slug = f'{t["group"].replace("_", "-")}-{key}-{dates[0][:4]}-{dates[0][5:7]}'
                out = {'slug': slug, 'group': t['group'], 'tour': t['tour'], 'official_url': t['official_url'],
                       'checked_at': t['checked_at'], 'sources': t['sources'], 'venue_key': key,
                       'venue_official': st['venue'], 'pref': st.get('pref', ''), 'dates': dates}
                if st.get('times'):
                    out['times'] = {k: v for k, v in st['times'].items() if k in dates}
                if t.get('note'):
                    out['note'] = t['note']
                made.append(slug)
                if not dry:
                    json.dump(out, open(os.path.join(ROOT, 'scripts/live_data', slug + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('会場ごとのデータ', len(made))
    for s in made:
        print(' ', s)
    print('会場ガイドのない会場', len(noguide))
    for x in noguide:
        print(' ', *x)


if __name__ == '__main__':
    main()
