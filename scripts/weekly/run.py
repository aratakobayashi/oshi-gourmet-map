"""週1回の自動更新: 情報源（sources.json）ごとに新しい回の店を候補にし、scripts/merge_candidates.py で確かめて data/shops.json に足す。

使い方:
  python scripts/weekly/run.py --dry-run      # 候補と、足すもの・見送るものを表示するだけ（shops.json・state.json は書かない）
  python scripts/weekly/run.py                # shops.json に足し、state.json を進める
  python scripts/weekly/run.py --only burari  # 1つの情報源だけ
  python scripts/weekly/run.py --init-state   # state.json を今の data/shops.json の最新回から作り直す

GitHub Actions では、結果を $GITHUB_STEP_SUMMARY（Summary）に、足した件数を $GITHUB_OUTPUT の added に書く。
1つの情報源が失敗しても、ほかは続ける（Summary に失敗として出る）。
"""
import argparse
import collections
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from common import redact, today  # noqa: E402

STATE = os.path.join(HERE, 'state.json')
SOURCES = os.path.join(HERE, 'sources.json')

# merge_candidates.py の見送り理由 → 人が読む言葉
WHY = {
    'confidence': '確度が低い（住所が番地までない等）', 'visit_type': '店に行った回でない', 'closed': '閉店',
    'address': '住所なし・番地なし', 'no-image': '動画も番組画像もない', 'overseas': '海外・都道府県不明',
    'no-group': 'グループ未設定', 'dup-name': '登録済み（同じグループに同じ店）', 'dup-id': '登録済み（同じID）',
    'geocode': '国土地理院で住所が見つからない', 'geocode-mismatch': '国土地理院の住所と食い違う',
    'geocode-coarse': '国土地理院で番地まで確かめられない',
}


def log(*a):
    print(*a, flush=True)


def load(path, default):
    try:
        return json.load(open(path, encoding='utf-8'))
    except FileNotFoundError:
        return default


def init_state():
    """今の data/shops.json から、情報源ごとの「どこまで読んだか」を作る"""
    shops = json.load(open(os.path.join(ROOT, 'data', 'shops.json'), encoding='utf-8'))
    by = collections.defaultdict(list)
    for s in shops:
        by[s.get('group')].append(s)
    last = lambda g: max((s.get('visited_date') or '' for s in by[g]), default='2000-01-01')
    st = {
        'machichuka': {'last_date': last('machichuka')},
        'sakaba_horoki': {'last_id': max((int(m.group(1)) for s in by['sakaba_horoki']
                                          for m in [re.search(r'/sakaba/shop/(\d+)\.html', s.get('source_url') or '')] if m), default=0)},
        'burari': {'last_date': last('burari')},
        'syokusai': {'last_date': last('syokusai')},
        'omouma': {'last_date': last('omouma')},
        'youtube': {},
    }
    src = load(SOURCES, {'sources': []})
    for s in src['sources']:
        for ch in s.get('channels', []) if s['adapter'] == 'youtube' else []:
            # source_video_channel は空のことが多いので、空のものと名前が合うものの中の最新日（別チャンネルと分かるものは除く）
            ds = [x.get('visited_date') or '' for x in by[ch['group']] if x.get('youtube_id') and
                  (not x.get('source_video_channel') or ch.get('name', '') in x['source_video_channel'])]
            st['youtube'][ch['channel_id']] = {'last_date': max(ds, default='2000-01-01')}
    st['_updated'] = today()
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--init-state', action='store_true')
    ap.add_argument('--keep', help='候補JSONをここに残す（確かめる用）')
    a = ap.parse_args()

    if a.init_state:
        st = init_state()
        json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(STATE, 'a').write('\n')
        log(json.dumps(st, ensure_ascii=False, indent=2))
        return

    sources = load(SOURCES, {'sources': []})['sources']
    state = load(STATE, {})
    new_state = dict(state)
    cands, pre_skips, results = [], [], []
    for src in sources:
        sid = src['id']
        if not src.get('enabled', True) or (a.only and a.only != sid):
            continue
        log(f'== {src.get("name", sid)}')
        try:
            mod = importlib.import_module(src['adapter'])
            r = mod.collect(src, state.get(sid, {}), log)
            for c in r['new']:
                c.setdefault('group', sid)
                c['_source'] = sid
            cands += r['new']
            pre_skips += [(sid, w, n) for w, n in r.get('skipped', [])]
            new_state[sid] = r['state']
            results.append((sid, src.get('name', sid), 'ok', len(r['new']), len(r.get('skipped', []))))
            log(f'  候補 {len(r["new"])} / 読んだ段階で見送り {len(r.get("skipped", []))} / state {r["state"]}')
        except Exception as e:  # 1つの情報源の失敗で全体を止めない
            msg = redact(f'{type(e).__name__}: {e}')
            log('  失敗:', msg)
            log(redact(traceback.format_exc()))
            results.append((sid, src.get('name', sid), 'error: ' + msg, 0, 0))

    # merge_candidates.py で確かめる（国土地理院で番地まで一致・重複・画像あり など）
    added, skipped = [], []
    if cands:
        tmp = tempfile.mkdtemp()
        cpath = a.keep or os.path.join(tmp, 'candidates.json')
        rpath = os.path.join(tmp, 'report.json')
        json.dump({'new': cands}, open(cpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'merge_candidates.py'), cpath, '-', '--report', rpath]
        if not a.dry_run:
            cmd.append('--write')
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        log(p.stdout[-4000:])
        if p.returncode != 0:
            log(p.stderr[-4000:])
            raise SystemExit('merge_candidates.py が失敗しました（shops.json は書き換えていません）')
        rep = json.load(open(rpath, encoding='utf-8'))
        added, skipped = rep['added'], rep['skipped']

    src_of = {(c['name'], c.get('group')): c['_source'] for c in cands}
    summary = render(results, cands, added, skipped, pre_skips, src_of, a.dry_run)
    log(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(summary + '\n')
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write(f'added={0 if a.dry_run else len(added)}\n')
    if not a.dry_run:
        new_state['_updated'] = today()
        json.dump(new_state, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(STATE, 'a').write('\n')


def render(results, cands, added, skipped, pre_skips, src_of, dry):
    L = [f'## 週1回の自動更新（{today()}）' + ('　※dry-run（書き込みなし）' if dry else ''), '']
    new_skips = [s for s in skipped if s['why'] not in ('dup-name', 'dup-id')]
    dups = len(skipped) - len(new_skips)
    L.append(f'**足した店 {len(added)}件** ／ 見送り {len(new_skips) + len(pre_skips)}件 ／ 登録済みで外した {dups}件')
    L += ['', '| 情報源 | 状態 | 候補 | 足した | 見送り（確認で） | 見送り（読んだ段階） |', '|---|---|---:|---:|---:|---:|']
    for sid, name, st, n, pk in results:
        a_n = sum(1 for s in added if src_of.get((s['name'], s['group'])) == sid)
        k_n = sum(1 for s in new_skips if src_of.get((s['name'], s.get('group'))) == sid)
        L.append(f'| {name} | {"OK" if st == "ok" else "**失敗** " + st[:120].replace("|", "/")} | {n} | {a_n} | {k_n} | {pk} |')
    if added:
        L += ['', '### 足した店', '']
        for s in added:
            L.append(f"- {s['name']}（{s['group']}）{s['address']} — {s['source_video_title']}")
    if new_skips:
        L += ['', '### 見送った店（merge_candidates.py の確認で）', '']
        for why, n in collections.Counter(s['why'] for s in new_skips).most_common():
            L.append(f'- {WHY.get(why, why)}: {n}件')
        L += ['', '<details><summary>一覧</summary>', '']
        for s in new_skips:
            L.append(f"- [{WHY.get(s['why'], s['why'])}] {s['name']}（{s.get('group', '')}）{s.get('detail', '')}")
        L += ['', '</details>']
    if pre_skips:
        L += ['', '### 読んだ段階で外したもの', '']
        for (sid, why), n in collections.Counter((sid, w) for sid, w, _ in pre_skips).most_common():
            L.append(f'- {sid}: {why}: {n}件')
        L += ['', '<details><summary>一覧</summary>', '']
        for sid, why, n in pre_skips:
            L.append(f'- {sid}: [{why}] {n}')
        L += ['', '</details>']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
