#!/usr/bin/env python3
"""
scrape_tmdb_hybrid.py
TMDB×Web検索ハイブリッドスクレイパー

流れ:
  1. TMDB APIで番組名・エピソード一覧を取得
  2. DuckDuckGoで「{番組名} グルメ ロケ地 まとめ」を検索
  3. ヒットしたファンブログから店名・住所を抽出
  4. 既存shops.jsonと重複排除して新規候補を出力

使い方:
  python scripts/scrape_tmdb_hybrid.py --tmdb-id 106410 --group arashi --output scripts/scraped_hybrid_arashi.json
  python scripts/scrape_tmdb_hybrid.py --tmdb-id 106410 --group arashi --dry-run
"""

import json, re, time, hashlib, argparse, os, urllib.request, urllib.parse
from bs4 import BeautifulSoup

TMDB_API_KEY  = os.environ.get('TMDB_API_KEY', '4573ec6c37323f6f89002cb24c690875')
DDG_URL       = 'https://html.duckduckgo.com/html/'
SLEEP         = 2.0
UA_BROWSER    = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
UA_BOT        = 'oshi-gourmet-map/1.0 (+https://gourmet.oshikatsu-guide.com)'

SCRIPTS_DIR       = os.path.dirname(os.path.abspath(__file__))
SHOPS_JSON        = os.path.join(SCRIPTS_DIR, '../data/shops.json')
DDG_CACHE_JSON    = os.path.join(SCRIPTS_DIR, 'ddg_search_cache.json')
DDG_CACHE_TTL_SEC = 86400  # 24時間キャッシュ

JP_PREFS = ('東京都','大阪府','京都府','北海道','神奈川','愛知','福岡','埼玉','千葉',
            '兵庫','静岡','茨城','広島','宮城','栃木','群馬','岡山','新潟','長野',
            '福島','岐阜','三重','滋賀','鹿児島','熊本','沖縄','山口','愛媛','長崎',
            '奈良','青森','岩手','大分','石川','山形','富山','秋田','香川','和歌山',
            '山梨','佐賀','福井','徳島','高知','島根','宮崎','鳥取')


# ──────────────────────────────────────────
# TMDB
# ──────────────────────────────────────────

def tmdb_get(path):
    url = f'https://api.themoviedb.org/3{path}?api_key={TMDB_API_KEY}&language=ja'
    req = urllib.request.Request(url, headers={'User-Agent': UA_BOT})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def get_show_info(tmdb_id):
    data = tmdb_get(f'/tv/{tmdb_id}')
    return {
        'name':     data.get('name', ''),
        'episodes': data.get('number_of_episodes', 0),
        'seasons':  data.get('number_of_seasons', 0),
    }


def get_episode_dates(tmdb_id, max_seasons=20):
    """全エピソードの放送日を {season}x{ep}: date の辞書で返す"""
    show = tmdb_get(f'/tv/{tmdb_id}')
    dates = {}
    for s in show.get('seasons', []):
        sn = s['season_number']
        if sn == 0 or sn > max_seasons:
            continue
        try:
            season_data = tmdb_get(f'/tv/{tmdb_id}/season/{sn}')
            for ep in season_data.get('episodes', []):
                air = ep.get('air_date', '')
                if air:
                    dates[f'S{sn}E{ep["episode_number"]}'] = air
            time.sleep(0.3)
        except Exception as e:
            print(f'  シーズン{sn} 取得エラー: {e}')
    return dates


# ──────────────────────────────────────────
# Web検索（DuckDuckGo）
# ──────────────────────────────────────────

def _load_ddg_cache():
    if not os.path.exists(DDG_CACHE_JSON):
        return {}
    with open(DDG_CACHE_JSON, encoding='utf-8') as f:
        return json.load(f)

def _save_ddg_cache(cache):
    with open(DDG_CACHE_JSON, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def search_ddg(query, max_results=8):
    """DuckDuckGo HTMLエンドポイントでURLリストを返す（24時間キャッシュ付き）"""
    cache = _load_ddg_cache()
    now = time.time()

    # キャッシュヒット
    if query in cache and now - cache[query].get('ts', 0) < DDG_CACHE_TTL_SEC:
        print(f'  (キャッシュ使用)', end='')
        return cache[query]['results']

    data = urllib.parse.urlencode({'q': query, 'kl': 'jp-jp'}).encode()
    req  = urllib.request.Request(DDG_URL, data=data, headers={
        'User-Agent':   UA_BROWSER,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept-Language': 'ja,en;q=0.9',
    })
    try:
        html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  DDG検索エラー: {e}')
        return cache.get(query, {}).get('results', [])  # エラー時は古いキャッシュを使用

    soup = BeautifulSoup(html, 'html.parser')
    hits = soup.select('a.result__a')
    if not hits:
        print(f'  DDGレート制限の可能性（ヒット0件）')
        return cache.get(query, {}).get('results', [])  # レート制限時は古いキャッシュを使用

    results = []
    for a in hits[:max_results]:
        href = a.get('href', '')
        title = a.get_text(strip=True)
        m = re.search(r'uddg=([^&]+)', href)
        url = urllib.parse.unquote(m.group(1)) if m else href
        if url.startswith('http') and 'duckduckgo.com' not in url:
            results.append({'title': title, 'url': url})

    # キャッシュ保存
    cache[query] = {'ts': now, 'results': results}
    _save_ddg_cache(cache)
    return results


def fetch_html(url):
    req = urllib.request.Request(url, headers={
        'User-Agent':    UA_BROWSER,
        'Accept-Language': 'ja,en;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read().decode('utf-8', errors='replace')


# ──────────────────────────────────────────
# レストラン抽出
# ──────────────────────────────────────────

SKIP_KEYWORDS = ('広告', 'ランキング', '読者', 'プロフィール', 'コメント',
                 'カテゴリ', 'タグ', 'このブログ', '関連記事', 'シェア')

# 料理名・メニュー名っぽい末尾パターン（店名ではない）
MENU_SUFFIXES = ('中華', '定食', '丼', '鍋', '焼き', '揚げ', '炒め', '煮', '刺身',
                 'ラーメン', 'うどん', 'そば', 'パスタ', 'ピザ', 'ケーキ', 'プリン',
                 'アイス', 'クレープ', 'プレート', 'セット', 'コース', '盛り合わせ',
                 '詰め合わせ', '前', '本', '個', '枚', '種')

# 店名に含まれてはいけないキーワード（商品説明文の断片）
NAME_NG_PATTERNS = [
    r'県産の', r'産の[ア-ン]', r'[をでにが]使', r'ミキサー', r'調味料',
    r'レシピ', r'作り方', r'召し上がり', r'お取り寄せ', r'\d+[gmlkg]',
    r'知事賞', r'企業秘密', r'[一-龠]{2,}[賞認証]',
]

def is_japan_address(text):
    return any(p in text for p in JP_PREFS)

def clean_name(raw):
    name = re.sub(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+[.\.\．、．)\s]+', '', raw).strip()
    name = re.sub(r'[\U00010000-\U0010ffff]', '', name)   # 絵文字除去
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def clean_tabelog_link_text(raw):
    """「『店名』の予約はこちら」→「店名」に変換"""
    t = raw.strip()
    # 予約・詳細系の末尾を除去
    t = re.sub(r'(の予約はこちら|の予約|で予約[を]?する|を予約[を]?する|の詳細はこちら|はこちら).*$', '', t)
    # 「食べログで」「食べログ』で」などのプレフィックスを除去
    t = re.sub(r'^[『「【]?食べログ[』」】]?で', '', t)
    # 残った引用符を複数回除去（「「店名」→ 店名）
    for _ in range(3):
        t = re.sub(r'^[『「【]', '', t)
        t = re.sub(r'[』」】]$', '', t)
        t = t.strip()
    # 店名の後ろに「の『メニュー名』」が付く場合を除去
    t = re.sub(r'の[『「].*?[』」]$', '', t)
    # 読み仮名（括弧内カタカナ・ひらがな）を除去
    t = re.sub(r'[（(][ぁ-んァ-ン]+[）)]', '', t)
    return t.strip()

def is_valid_shop_name(name):
    """店名として妥当かチェック"""
    if len(name) < 2 or len(name) > 50:
        return False
    # 括弧内を除いた実質的な名前でチェック
    core = re.sub(r'[（(][^）)]*[）)]', '', name).strip()
    # 料理名っぽい末尾
    if any(core.endswith(s) for s in MENU_SUFFIXES):
        return False
    # 商品説明文の断片
    if any(re.search(p, name) for p in NAME_NG_PATTERNS):
        return False
    # 地名・エリア名だけ
    if re.match(r'^(エリア|地域|東京|大阪|全国|近畿|関東|九州)$', name):
        return False
    # 数字だけ・記号含む（レビュー文・評価数など）
    if re.match(r'^\d+[人件票]?$', name):
        return False
    if any(c in name for c in ('@', '♪', '♡', '★', '☆', '▼', '▶')):
        return False
    # レビュー文の断片
    if any(kw in name for kw in ('は絶品', 'ハズレなし', 'おすすめ', 'まずは', 'ぜひ行')):
        return False
    return True

def is_valid_address(text):
    """実際の住所かどうかチェック（商品説明文を除外）"""
    if not is_japan_address(text):
        return False
    # 都道府県名の直後が「産」「県産」ならNG（産地説明）
    if re.search(r'[都道府県][産市区町村]?の', text):
        if re.search(r'[都道府県]産', text):
            return False
    # 住所らしいパターンが含まれているか
    return bool(re.search(r'[都道府県市区町村].*[\d\-ー]|[都道府県市区町村].*丁目|[都道府県市区町村].*番地', text)
                or re.search(r'[都道府県][市区町村].+[市区町村]', text))

def extract_prefecture(addr):
    for p in JP_PREFS:
        if p in addr:
            return p if p.endswith(('都','道','府','県')) else p + ('都' if p=='東京' else '')
    return ''

def extract_shops_from_html(html, source_url, group, show_name):
    soup = BeautifulSoup(html, 'html.parser')
    shops = []

    # 戦略1: 番号付き見出し（h2/h3）＋ 住所パターン（最も一般的なまとめブログ形式）
    events = []
    for tag in soup.find_all(True):
        t = tag.get_text(strip=True)
        if not t or any(kw in t for kw in SKIP_KEYWORDS):
            continue

        # 店名候補: h2/h3/strong で数字や①などで始まる
        if tag.name in ('h2', 'h3', 'strong', 'b') and 2 < len(t) < 60:
            name = clean_name(t)
            # 「店名の『メニュー名』」パターンを除去
            name = re.sub(r'の[『「].*?[』」]$', '', name).strip()
            if name and not re.match(r'^(まとめ|紹介|第\d|シーズン|\d{4}年)', name) and is_valid_shop_name(name):
                events.append(('shop', id(tag), name))

        # 住所候補
        elif tag.name in ('p', 'span', 'li', 'td') and ('住所' in t or '所在地' in t) and len(t) < 200:
            addr = re.sub(r'^(住所|所在地)[：:\s〒]*', '', t)
            addr = re.sub(r'^\d{3}-\d{4}\s*', '', addr).strip()
            if addr and is_valid_address(addr):
                events.append(('addr', id(tag), addr))

        # 住所そのもの（「住所：」ラベルなしで都道府県から始まる）
        elif tag.name in ('p', 'span', 'li') and re.match(r'.{2,4}[都道府県]', t) and is_valid_address(t) and len(t) < 120:
            events.append(('addr', id(tag), t.strip()))

    # 重複除去
    seen_ids = set()
    uniq = []
    for kind, eid, val in events:
        if eid not in seen_ids:
            seen_ids.add(eid)
            uniq.append((kind, val))

    # shop → addr 対応付け
    current_name = None
    for kind, val in uniq:
        if kind == 'shop':
            current_name = val
        elif kind == 'addr' and current_name:
            pref = extract_prefecture(val)
            h = hashlib.md5(f'{group}:{current_name}'.encode()).hexdigest()[:8]
            shops.append({
                'id':                  f'{group}-{h}',
                'name':                current_name,
                'group':               group,
                'groups':              [group],
                'source_type':         'tv',
                'source_video_title':  show_name,
                'source_url':          source_url,
                'address':             val,
                'prefecture':          pref,
                'lat':                 None,
                'lng':                 None,
            })
            current_name = None

    # 戦略2: 食べログURLから店名を取得
    for a in soup.find_all('a', href=re.compile(r'tabelog\.com/[a-z]+/A\d+/A\d+/\d+')):
        href = a['href'].split('?')[0].rstrip('/') + '/'
        link_text = a.get_text(strip=True)
        if not link_text:
            continue
        # リンクテキストをクリーニング（「〜の予約はこちら」などを除去）
        name = clean_tabelog_link_text(link_text)
        name = clean_name(name)
        if not name or not is_valid_shop_name(name):
            continue
        h = hashlib.md5(f'{group}:{name}'.encode()).hexdigest()[:8]
        shops.append({
            'id':                 f'{group}-{h}',
            'name':               name,
            'group':              group,
            'groups':             [group],
            'source_type':        'tv',
            'source_video_title': show_name,
            'source_url':         source_url,
            'tabelog_url':        href,
            'lat':                None,
            'lng':                None,
        })

    # 重複（同名）除去
    seen_names = set()
    unique = []
    for s in shops:
        if s['name'] not in seen_names:
            seen_names.add(s['name'])
            unique.append(s)

    return unique


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tmdb-id',  type=int, required=True, help='TMDBの番組ID')
    parser.add_argument('--group',    required=True, help='グループID（例: arashi）')
    parser.add_argument('--output',   default='scripts/scraped_hybrid.json')
    parser.add_argument('--dry-run',  action='store_true', help='検索URLのみ表示')
    parser.add_argument('--max-urls', type=int, default=6, help='スクレイピングするURL数')
    args = parser.parse_args()

    # 既存shops.jsonの店名セット（重複チェック用）
    with open(SHOPS_JSON, encoding='utf-8') as f:
        existing = json.load(f)
    existing_names = {s['name'] for s in existing if s.get('group') == args.group}
    print(f'既存 {args.group} 店舗: {len(existing_names)}件')

    # TMDB から番組情報取得
    print(f'\nTMDB ID {args.tmdb_id} の情報を取得中...')
    info = get_show_info(args.tmdb_id)
    show_name = info['name']
    print(f'番組名: {show_name}  全{info["episodes"]}話')

    # 検索クエリ生成（複数パターン）
    queries = [
        f'{show_name} グルメ お店 まとめ',
        f'{show_name} 紹介 飲食店 ロケ地',
        f'{show_name} グルメデスマッチ お店 一覧',
    ]

    print(f'\n=== DuckDuckGo検索 ===')
    all_urls = {}  # url → title（重複除去）
    for q in queries:
        print(f'検索: {q}')
        results = search_ddg(q, max_results=5)
        for r in results:
            if r['url'] not in all_urls:
                all_urls[r['url']] = r['title']
                print(f'  → {r["title"][:50]}')
                print(f'     {r["url"][:80]}')
        time.sleep(SLEEP)

    # 除外ドメイン（SNS・動画サイト等）
    SKIP_DOMAINS = ('twitter.com', 'x.com', 'youtube.com', 'instagram.com',
                    'tiktok.com', 'amazon.co.jp', 'wikipedia.org', 'google.com')
    candidate_urls = [
        (url, title) for url, title in all_urls.items()
        if not any(d in url for d in SKIP_DOMAINS)
    ][:args.max_urls]

    if args.dry_run:
        print(f'\n対象URL ({len(candidate_urls)}件):')
        for url, title in candidate_urls:
            print(f'  {title[:50]}')
            print(f'  {url}')
        return

    # スクレイピング
    print(f'\n=== スクレイピング ({len(candidate_urls)}件) ===')
    all_shops = []
    for i, (url, title) in enumerate(candidate_urls):
        print(f'[{i+1}/{len(candidate_urls)}] {title[:50]}')
        print(f'  {url[:80]}')
        try:
            html = fetch_html(url)
            shops = extract_shops_from_html(html, url, args.group, show_name)
            new_shops = [s for s in shops if s['name'] not in existing_names]
            print(f'  → 抽出: {len(shops)}件 / 新規: {len(new_shops)}件')
            all_shops.extend(new_shops)
            time.sleep(SLEEP)
        except Exception as e:
            print(f'  エラー: {e}')
            time.sleep(SLEEP)

    # 全体重複除去
    seen = set()
    unique_shops = []
    for s in all_shops:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique_shops.append(s)

    print(f'\n=== 結果 ===')
    print(f'新規候補: {len(unique_shops)}件')
    addr_count = sum(1 for s in unique_shops if s.get('address'))
    tabelog_count = sum(1 for s in unique_shops if s.get('tabelog_url'))
    print(f'  住所あり: {addr_count}件（ジオコーディング可能）')
    print(f'  食べログURL: {tabelog_count}件')
    print()
    for s in unique_shops[:20]:
        addr = s.get('address') or s.get('tabelog_url', '')
        print(f'  {s["name"]} / {addr[:50]}')
    if len(unique_shops) > 20:
        print(f'  ... 他{len(unique_shops)-20}件')

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique_shops, f, ensure_ascii=False, indent=2)
    print(f'\n→ {args.output} に保存')


if __name__ == '__main__':
    main()
