#!/usr/bin/env python3
"""
normalize_links.py
shops.json の外部リンクを正規化する（何度実行しても同じ結果になる）。

- 食べログは tabelog_url、ホットペッパーは hotpepper_url だけを正とする
- affiliate_links から食べログ・ホットペッパーの重複分を削除し、
  公式サイト・一休などその他のリンクだけを残す
- tabelog_url が空で affiliate_links にだけ食べログURLがある場合は tabelog_url へ移す
- tabelog_url と affiliate_links の食べログURLが食い違う場合は、
  手動確認用に tabelog_url_alt へ退避する（確認後に削除する想定）
- tabelog_url を店舗トップURLにそろえる（他サイトの追跡パラメータやサブページを除去）
- hotpepper_url からクエリ（?vos=... などの追跡用パラメータ）を取り除く

使い方:
  python scripts/normalize_links.py          # 変更内容を表示して保存
  python scripts/normalize_links.py --dry-run
"""
import argparse
import json
import re

SHOPS_PATH = 'data/shops.json'


def is_tabelog(url):
    return bool(re.match(r'https?://(s\.)?tabelog\.com/', url or ''))


def is_hotpepper(url):
    return bool(re.match(r'https?://www\.hotpepper\.jp/', url or ''))


def strip_query(url):
    return re.sub(r'[?#].*$', '', url)


def canonical_tabelog(url):
    """店舗トップのURLにそろえる（クエリ・口コミ/写真/メニュー等のサブページを除去）"""
    m = re.match(r'(https?://(?:s\.)?tabelog\.com/[a-z]+/A\d{4}/A\d{6}/\d+/)', strip_query(url) + '/')
    return m.group(1).replace('://s.tabelog', '://tabelog').replace('http://', 'https://') if m else url


def same_url(a, b):
    return strip_query(a).rstrip('/') == strip_query(b).rstrip('/')


def normalize(shop, stats):
    links = shop.get('affiliate_links') or []
    tabelog_links = [l['url'] for l in links if is_tabelog(l.get('url'))]
    hotpepper_links = [l['url'] for l in links if is_hotpepper(l.get('url'))]

    if tabelog_links:
        if not shop.get('tabelog_url'):
            shop['tabelog_url'] = tabelog_links[0]
            stats['tabelog_promoted'] += 1
        else:
            alts = [canonical_tabelog(u) for u in tabelog_links
                    if canonical_tabelog(u) != canonical_tabelog(shop['tabelog_url'])]
            if alts:
                shop['tabelog_url_alt'] = alts[0]
                stats['tabelog_alt_saved'] += 1

    if shop.get('tabelog_url'):
        canon = canonical_tabelog(shop['tabelog_url'])
        if canon != shop['tabelog_url']:
            shop['tabelog_url'] = canon
            stats['tabelog_canonicalized'] += 1

    if shop.get('tabelog_url_alt'):
        alt = canonical_tabelog(shop['tabelog_url_alt'])
        if alt == shop.get('tabelog_url'):
            del shop['tabelog_url_alt']
        else:
            shop['tabelog_url_alt'] = alt

    if hotpepper_links and not shop.get('hotpepper_url'):
        shop['hotpepper_url'] = hotpepper_links[0]
        stats['hotpepper_promoted'] += 1

    if shop.get('hotpepper_url'):
        cleaned = strip_query(shop['hotpepper_url'])
        if cleaned != shop['hotpepper_url']:
            shop['hotpepper_url'] = cleaned
            stats['hotpepper_params_stripped'] += 1

    if 'affiliate_links' in shop:
        kept = [l for l in links if not is_tabelog(l.get('url')) and not is_hotpepper(l.get('url'))]
        stats['affiliate_links_removed'] += len(links) - len(kept)
        if kept:
            shop['affiliate_links'] = kept
        else:
            del shop['affiliate_links']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(SHOPS_PATH, encoding='utf-8') as f:
        shops = json.load(f)

    stats = {k: 0 for k in ['tabelog_promoted', 'tabelog_canonicalized', 'tabelog_alt_saved', 'hotpepper_promoted',
                            'hotpepper_params_stripped', 'affiliate_links_removed']}
    for shop in shops:
        normalize(shop, stats)

    for k, v in stats.items():
        print(f'  {k}: {v}')

    if not args.dry_run:
        with open(SHOPS_PATH, 'w', encoding='utf-8') as f:
            json.dump(shops, f, ensure_ascii=False, indent=2)
        print(f'保存しました: {SHOPS_PATH}')


if __name__ == '__main__':
    main()
