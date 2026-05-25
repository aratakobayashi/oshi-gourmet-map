"""
scrape_shiori.py
なんとなくしおり（@nantonakushiori）チャンネルの食事系動画から
飲食店情報を抽出してJSONを生成するスクリプト

チャンネルID: UCHYa60S50wJ3W-mcTbVQPew
"""

import os, json, re, urllib.request, urllib.parse, time

API_KEY    = os.environ["YOUTUBE_API_KEY"]
CHANNEL_ID = "UCHYa60S50wJ3W-mcTbVQPew"
GROUP_ID   = "shiori"
OUT_RAW    = "scripts/shiori_raw_videos.json"
OUT_SHOPS  = "scripts/shiori_extracted_shops.json"

# 食事・飲み系キーワード
FOOD_KEYWORDS = [
    "はしご酒", "飲み", "ひとり飲み", "グルメ", "食べ",
    "居酒屋", "ラーメン", "もつ", "焼肉", "寿司", "うどん",
    "ランチ", "ディナー", "カフェ", "スイーツ", "bar", "BAR",
    "酒場", "飯", "食堂", "定食", "鍋", "しゃぶ", "天ぷら",
    "焼き鳥", "餃子", "カレー", "パスタ", "ピザ", "まぐろ",
    "海鮮", "刺身", "ワイン", "ウイスキー", "サウナ飯",
    "旅", "vlog", "弾丸", "新潟", "名古屋", "浅草", "神保町",
    "立川", "高田馬場", "高崎",
]

def api_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "oshi-gourmet-map/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def get_uploads_playlist_id():
    url = (
        "https://www.googleapis.com/youtube/v3/channels"
        f"?part=contentDetails&id={CHANNEL_ID}&key={API_KEY}"
    )
    data = api_get(url)
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def fetch_all_videos(playlist_id):
    """再生リストから全動画を取得（snippet.descriptionは最初の200文字のみ）"""
    videos, next_page = [], None
    while True:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": API_KEY,
        }
        if next_page:
            params["pageToken"] = next_page
        data = api_get("https://www.googleapis.com/youtube/v3/playlistItems?" + urllib.parse.urlencode(params))
        for item in data.get("items", []):
            s = item["snippet"]
            vid = s["resourceId"]["videoId"]
            videos.append({
                "youtube_id": vid,
                "title": s["title"],
                "published_at": s["publishedAt"][:10],
                "description_head": s.get("description", "")[:300],
            })
        next_page = data.get("nextPageToken")
        if not next_page:
            break
        time.sleep(0.3)
    return videos

def is_food_video(video):
    t = video["title"] + " " + video["description_head"]
    return any(kw in t for kw in FOOD_KEYWORDS)

def fetch_full_descriptions(video_ids):
    """videos.list で概要欄フルテキストを取得（50件ずつ）"""
    desc_map = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        ids_str = ",".join(chunk)
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet&id={ids_str}&key={API_KEY}"
        )
        data = api_get(url)
        for item in data.get("items", []):
            desc_map[item["id"]] = item["snippet"].get("description", "")
        time.sleep(0.3)
    return desc_map

# ── 店舗情報パーサー ──────────────────────────────────────────

# よくある食べログURL
TABELOG_RE  = re.compile(r"https://tabelog\.com/[^\s\)\"']+")
HOTPEPPER_RE = re.compile(r"https://www\.hotpepper\.jp/[^\s\)\"']+")
GMAPS_RE    = re.compile(r"https://maps\.(?:google\.com|app\.goo\.gl)/[^\s\)\"']+")
GURUNAVI_RE = re.compile(r"https://r\.gnavi\.co\.jp/[^\s\)\"']+")
RETTY_RE    = re.compile(r"https://retty\.me/[^\s\)\"']+")

def extract_urls(text):
    urls = {}
    m = TABELOG_RE.search(text)
    if m: urls["tabelog_url"] = m.group().rstrip(".")
    m = HOTPEPPER_RE.search(text)
    if m: urls["hotpepper_url"] = m.group().rstrip(".")
    m = GMAPS_RE.search(text)
    if m: urls["google_maps_url"] = m.group().rstrip(".")
    return urls

def _is_shop_name(name: str) -> bool:
    """テキストが店名として有効かチェック"""
    if not name or len(name) < 2 or len(name) > 40:
        return False
    if re.match(r'^〒?\d{3}-?\d{4}', name):  # 郵便番号
        return False
    if re.search(r'タイアップ|スポンサー|プロモーション|キャンペーン|特設サイト|告知情報|株式会社|©|Copyright', name):
        return False
    if re.search(r'instagram\.com|twitter\.com|youtube\.com|spotify|amazon\.co', name, re.I):
        return False
    return True


def parse_shops_from_description(video, full_desc):
    """
    概要欄から店舗情報を抽出する。

    パターン1: 行頭に「■店名」「◆店名」「▶店名」「【店名】」＋絵文字
    パターン2: 「店名\nhttps://tabelog.com/...」（しおり形式：名前の直後にURL）
    パターン3: 「今回の店舗一覧」セクション内の箇条書き
    """
    lines = full_desc.splitlines()
    shop_blocks = []

    # ── パターン2優先: URL直前行を店名として扱う ──────────────────
    # URL行のインデックスを収集
    url_line_indices = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (TABELOG_RE.match(stripped) or HOTPEPPER_RE.match(stripped)
                or GURUNAVI_RE.match(stripped) or RETTY_RE.match(stripped)):
            url_line_indices.add(i)

    used_lines = set()
    for url_idx in sorted(url_line_indices):
        url_line = lines[url_idx].strip()
        urls = extract_urls(url_line)

        # URL直前の非空行を店名候補とする
        name_line = ""
        for back in range(1, 4):
            prev_i = url_idx - back
            if prev_i < 0:
                break
            prev = lines[prev_i].strip()
            if not prev:
                continue
            # 別のURLや宣伝文（タイアップ等）はスキップ
            if re.search(r'https?://', prev):
                break
            if re.search(r'タイアップ|スポンサー|プロモーション|キャンペーン|PR\b', prev):
                break
            # 「今回のはしご酒店舗一覧」のようなヘッダー行はスキップ
            if re.search(r'一覧|店舗リスト|訪問先', prev):
                break
            name_line = prev
            break

        if not name_line or len(name_line) < 2:
            continue

        if not _is_shop_name(name_line):
            continue

        # 前後数行から住所を探す
        address = ""
        for bl in lines[max(0, url_idx-3):url_idx+3]:
            if re.search(r'(?:東京都|大阪府|[^\s]{2,4}[都道府県]).+[区市町村]', bl):
                address = bl.strip()
                break

        if url_idx not in used_lines:
            shop_blocks.append({"name": name_line, "address": address, **urls})
            used_lines.add(url_idx)

    # ── パターン1: 記号・絵文字・番号で始まる行 ──────────────────
    name_pat = re.compile(
        r'^[■◆▶▷★☆🍺🍻🍜🍣🍛🍖🥩🍱🍝🍕🥗🍷🍸🍾🥂📍〒①②③④⑤⑥⑦⑧⑨⑩]'
        r'|^(?:【.{2,20}】)|^\d[．\.\)、](?!\d)',
        re.MULTILINE
    )
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if name_pat.match(line):
            shop_name = re.sub(
                r'^[■◆▶▷★☆🍺🍻🍜🍣🍛🍖🥩🍱🍝🍕🥗🍷🍸🍾🥂📍〒①②③④⑤⑥⑦⑧⑨⑩]+\s*',
                "", line
            ).strip()
            if not shop_name:
                m2 = re.match(r'【(.{2,20})】', line)
                if m2:
                    shop_name = m2.group(1)
            if len(shop_name) < 2:
                i += 1
                continue

            block_text = "\n".join(lines[i:min(i+8, len(lines))])
            urls = extract_urls(block_text)
            address = ""
            for bl in lines[i:min(i+8, len(lines))]:
                if re.search(r'(?:東京都|大阪府|[^\s]{2,4}[都道府県]).+[区市町村]', bl):
                    address = bl.strip()
                    break

            if not _is_shop_name(shop_name):
                i += 1
                continue
            already = any(b["name"] == shop_name for b in shop_blocks)
            if not already:
                shop_blocks.append({"name": shop_name, "address": address, **urls})
        i += 1

    # 最終的な店舗データ構築
    shops = []
    for block in shop_blocks:
        if not block.get("name"):
            continue

        shop = {
            "name": block["name"],
            "genre": "居酒屋",  # デフォルト（しおりは飲み系が多い）
            "youtube_id": video["youtube_id"],
            "source_video_title": video["title"],
            "source_video_url": f"https://www.youtube.com/watch?v={video['youtube_id']}",
            "visited_date": video["published_at"],
            "members": ["しおり"],
            "groups": [GROUP_ID],
            "group": GROUP_ID,
            "address": block.get("address", ""),
            "prefecture": "",
            "city": "",
            "description": f"{video['title']} で訪れた飲食店。",
        }

        if block.get("tabelog_url"):
            shop["tabelog_url"] = block["tabelog_url"]
            shop["affiliate_links"] = [{"label": "食べログで見る", "url": block["tabelog_url"]}]
        if block.get("hotpepper_url"):
            shop["hotpepper_url"] = block["hotpepper_url"]
        if block.get("google_maps_url"):
            shop["google_maps_url"] = block["google_maps_url"]

        # 都道府県・市区町村を住所から推定
        if shop["address"]:
            m = re.match(r'(東京都|大阪府|[^都道府県]+[都道府県])([^市区町村]+[市区町村])', shop["address"])
            if m:
                shop["prefecture"] = m.group(1)
                shop["city"] = m.group(2)

        shops.append(shop)

    return shops

def main():
    print("=== なんとなくしおり 店舗情報スクレイパー ===")

    # 1. 動画一覧取得
    print("\n[1] チャンネル動画一覧取得中...")
    playlist_id = get_uploads_playlist_id()
    all_videos = fetch_all_videos(playlist_id)
    print(f"  総動画数: {len(all_videos)}")

    # 2. 食事系動画フィルタ
    food_videos = [v for v in all_videos if is_food_video(v)]
    print(f"  食事系動画: {len(food_videos)} 件")

    # RAWデータ保存
    with open(OUT_RAW, "w", encoding="utf-8") as f:
        json.dump({"all": len(all_videos), "food": len(food_videos), "videos": food_videos}, f, ensure_ascii=False, indent=2)
    print(f"  → {OUT_RAW} に保存")

    print("\n食事系動画タイトル（最新30件）:")
    for v in food_videos[:30]:
        print(f"  [{v['published_at']}] {v['title']}")

    # 3. 概要欄フルテキスト取得
    print(f"\n[2] 概要欄フルテキスト取得中（{len(food_videos)}件）...")
    video_ids = [v["youtube_id"] for v in food_videos]
    desc_map = fetch_full_descriptions(video_ids)

    # 4. 店舗情報抽出
    print("\n[3] 店舗情報抽出中...")
    all_shops = []
    shops_by_video = {}

    for video in food_videos:
        vid = video["youtube_id"]
        full_desc = desc_map.get(vid, "")
        shops = parse_shops_from_description(video, full_desc)
        if shops:
            shops_by_video[vid] = {
                "title": video["title"],
                "date": video["published_at"],
                "shops": shops,
                "desc_preview": full_desc[:500],
            }
            all_shops.extend(shops)

    print(f"  抽出された店舗数: {len(all_shops)}")

    # 5. 概要欄サンプル表示（パーサー確認用）
    print("\n=== 概要欄サンプル（店舗情報あり上位5件） ===")
    count = 0
    for vid, info in shops_by_video.items():
        if count >= 5:
            break
        print(f"\n【{info['title']}】")
        print(f"  抽出店舗: {[s['name'] for s in info['shops']]}")
        print(f"  概要欄冒頭:\n{info['desc_preview'][:300]}")
        count += 1

    # 6. 概要欄全文も別途出力（手動確認用）
    print("\n=== 全食事系動画の概要欄（手動確認用） ===")
    desc_output = []
    for video in food_videos:
        vid = video["youtube_id"]
        full_desc = desc_map.get(vid, "")
        desc_output.append({
            "youtube_id": vid,
            "title": video["title"],
            "published_at": video["published_at"],
            "description": full_desc,
            "shops_found": [s["name"] for s in shops_by_video.get(vid, {}).get("shops", [])],
        })

    desc_file = "scripts/shiori_descriptions.json"
    with open(desc_file, "w", encoding="utf-8") as f:
        json.dump(desc_output, f, ensure_ascii=False, indent=2)
    print(f"  → {desc_file} に全概要欄を保存")

    # 7. 抽出店舗JSON保存
    with open(OUT_SHOPS, "w", encoding="utf-8") as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)
    print(f"  → {OUT_SHOPS} に抽出店舗データ保存")

    print("\n完了！次のステップ:")
    print("  1. scripts/shiori_descriptions.json を確認して概要欄の構造を把握")
    print("  2. 店舗名が手動確認で正しければ geocode_shops.py でジオコーディング")
    print("  3. merge_shops.py でshops.jsonにマージ")

if __name__ == "__main__":
    main()
