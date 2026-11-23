"""
live_freshness.py
ライブのページ（参戦ガイド・ツアーまとめ・はじめてのライブ）の「見直すべきところ」を一覧にする。
チケットの受付・グッズ・セトリは日々変わるので、週1回これを見て公式を確かめ、データを直してから
live_article.py・tour_hub.py・first_live_article.py を実行し直す。

- これから14日以内に始まる・終わるチケットの受付（そのころに公式で次の発表が出やすい）
- 日程が「未発表」の受付（一般発売など。発表されたら tickets に書く）
- 確かめてから21日以上たったデータ（checked_at）
- 終わった公演でセトリ（setlist）がまだないもの（大手報道のライブレポートを探す）
- 公演まで30日以内なのに、グッズなどが「未発表」のままのデータ

使い方: python scripts/live_freshness.py [--days 14] [--stale 21]
GitHub Actions では GITHUB_STEP_SUMMARY に Markdown で書き足す（週1回の自動更新の Summary に出る）
"""
import argparse
import datetime
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))


def J(p):
    return json.load(open(p, encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=14)
    ap.add_argument('--stale', type=int, default=21)
    a = ap.parse_args()
    now = datetime.datetime.now(JST)
    today = now.date()
    soon = (now + datetime.timedelta(days=a.days)).strftime('%Y-%m-%dT%H:%M')
    nows = now.strftime('%Y-%m-%dT%H:%M')

    tk_rows, tba_rows, stale_rows, setl_rows, tba_soon = [], [], [], [], []
    lives = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'scripts/live_data/*.json'))):
        d = J(p)
        slug = d['slug']
        lives[slug] = d
        last = max(d['dates'])
        if last < (today - datetime.timedelta(days=60)).isoformat():
            continue   # だいぶ前に終わった公演は見ない
        for t in d.get('tickets') or []:
            s, e = t.get('start') or '', t.get('end') or ''
            if s and nows <= s <= soon:
                tk_rows.append((s, slug, t['name'], '始まる'))
            if e and nows <= e <= soon:
                tk_rows.append((e, slug, t['name'], '終わる'))
            if not s and last >= today.isoformat():
                tba_rows.append((slug, t['name'], t.get('note') or ''))
        ck = d.get('checked_at')
        if ck and last >= today.isoformat() and (today - datetime.date.fromisoformat(ck)).days >= a.stale:
            stale_rows.append((ck, f'scripts/live_data/{slug}.json'))
        if last < today.isoformat() and not d.get('setlist'):
            setl_rows.append((last, slug))

    for kind in ('tour_hub_data', 'first_live_data'):
        for p in sorted(glob.glob(os.path.join(ROOT, f'scripts/{kind}/*.json'))):
            d = J(p)
            ck = d.get('checked_at')
            rel = os.path.relpath(p, ROOT)
            if ck and (today - datetime.date.fromisoformat(ck)).days >= a.stale:
                stale_rows.append((ck, rel))
            # 公演が30日以内なのに「未発表」「発表されていません」が残っている
            dates = [x for lv in d.get('lives', []) if lv in lives for x in lives[lv]['dates']]
            dates += [x for s in d.get('shows', []) for x in s.get('dates', [])]
            up = sorted(x for x in dates if x >= today.isoformat())
            txt = json.dumps(d, ensure_ascii=False)
            if up and (datetime.date.fromisoformat(up[0]) - today).days <= 30 and ('未発表' in txt or '発表されていません' in txt):
                tba_soon.append((up[0], rel))

    out = [f'## ライブのページの見直し（{today.isoformat()}）', '']
    out.append(f'### これから{a.days}日以内に始まる・終わるチケットの受付（{len(tk_rows)}）')
    out += [f'- {x[0].replace("T", " ")} {x[3]}: {x[2]}（{x[1]}）' for x in sorted(tk_rows)] or ['- なし']
    out += ['', f'### 日程が未発表の受付（{len(tba_rows)}。公式で発表されていないか確かめる）']
    out += [f'- {x[0]}: {x[1]}{"（" + x[2] + "）" if x[2] else ""}' for x in tba_rows] or ['- なし']
    out += ['', f'### 公演まで30日以内なのに「未発表」が残っているデータ（{len(tba_soon)}）']
    out += [f'- {x[1]}（次の公演 {x[0]}）' for x in sorted(tba_soon)] or ['- なし']
    out += ['', f'### 終わった公演でセトリがまだないもの（{len(setl_rows)}。大手報道のライブレポートを探して live_data の setlist に）']
    out += [f'- {x[0]} {x[1]}' for x in sorted(setl_rows, reverse=True)] or ['- なし']
    out += ['', f'### 確かめてから{a.stale}日以上たったデータ（{len(stale_rows)}）']
    out += [f'- {x[0]} {x[1]}' for x in sorted(stale_rows)] or ['- なし']
    text = '\n'.join(out) + '\n'
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write('\n' + text)


if __name__ == '__main__':
    main()
