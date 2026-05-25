"""
extract_shiori_hashtags.py
しおりのなんとなく日常 — ハッシュタグから店名候補を抽出するスクリプト

多くの動画でハッシュタグに店名が含まれている。
エリアタグ・汎用タグを除外し、店名らしいタグを抽出してJSONに保存。
"""

import json, re

INPUT_DESC  = "scripts/shiori_descriptions.json"
OUTPUT      = "scripts/shiori_hashtag_shops.json"

# ── 除外タグ（場所・カテゴリ・旅行用語・SNS向け汎用語）──────────────
EXCLUDE = {
    # 食事カテゴリ・行動語
    "食べ歩き","グルメ","ひとり旅","ぼっち飯","ソロ活","はしご酒","1人旅","一人旅",
    "1人飲み","ひとり飲み","ラーメン","寿司","回転寿司","居酒屋","カフェ","スイーツ",
    "焼肉","定食","飲み","昼飲み","夜飲み","ビール","日本酒","ワイン","旅","旅行",
    "観光","散歩","グルメ旅","食べ放題","大食い","爆食","昇天","宅飲み","ビジホ飲み",
    "料理","自炊","晩酌","パスタ","ホテルステイ","ダイエット","ダイエットレシピ",
    "二郎系","ビジネスクラス","爆食い","チェーン店","ファミレス",
    "ハシゴ酒","飲み歩き","食べ飲み歩き","食べ飲み","飲み歩き","ぼっち飲み",
    "町中華","個室","サウナ","せんべろ","おひとりさま","1人でも",
    "酒豪","お酒","酒造見学","親知らず","抜歯","晩酌",
    # 地名・エリア（都市・区・丁目レベル）
    "東京","大阪","北海道","函館","京都","名古屋","横浜","川越","福島","島根","沼津",
    "静岡","渋谷","新宿","恵比寿","銀座","浅草","秋葉原","池袋","上野","新橋","目黒",
    "高輪ゲートウェイ","埼玉","神奈川","兵庫","奈良","博多","福岡","仙台","千葉",
    "日本","ニューヨーク","マレーシア","クアラルンプール","ネパール","NY",
    "小江戸川越","松江市","出雲市","代々木","代々木上原","歌舞伎町",
    "虎ノ門","港区","中目黒","野毛","ぴおシティ","赤坂","下北沢","旭川",
    "忘年会","年末","年始","ジンギスカン","酸辣湯麺","飲茶","しゃぶしゃぶ食べ放題",
    "激辛","恵比寿サウナー",
    # 旅行・ライフスタイル
    "女子旅","ご褒美旅","弾丸","日帰り","1人旅","親子旅","家族旅行","ソロ旅",
    "プチ旅行","ホテル","宿","温泉","観光地","海外","南米","ユナイテッド","ANA",
    "羽田空港","ビジネスクラス",
    # SNS・プロモーション
    "japanesefood","japan","tokyo","sushi","ramen","osaka","hokkaido","hakodate",
    "malaysia","kualalumpur","nyc","shimane",
    # 食材
    "蟹","海鮮","焼き鳥","牛タン","天ぷら","もつ鍋","鍋","つけ麺",
    "うなぎ","刺身","海老","牡蠣","焼き肉","餃子","カレー","丼",
    # その他
    "山手線","山手線一周","二郎","明大前","子ども食堂","学芸大学","ふるさと納税",
    "クリスマス","美肌県しまね","島根観光","島根旅行","島根冬旅","福島グルメ",
    "横浜グルメ","新橋グルメ","川越グルメ","松江しんじ湖温泉","松江市観光","出雲市観光",
}

# ── エリア判定用の地名リスト（店名ではないが場所を示す）──────────────
LOCATION_TAGS = {
    "函館":"北海道函館市", "北海道":"北海道", "川越":"埼玉県川越市",
    "横浜":"神奈川県横浜市", "野毛":"神奈川県横浜市中区野毛",
    "新橋":"東京都港区新橋", "恵比寿":"東京都渋谷区恵比寿",
    "中目黒":"東京都目黒区中目黒", "渋谷":"東京都渋谷区",
    "新宿":"東京都新宿区", "銀座":"東京都中央区銀座",
    "浅草":"東京都台東区浅草", "代々木":"東京都渋谷区代々木",
    "虎ノ門":"東京都港区虎ノ門", "港区":"東京都港区",
    "沼津":"静岡県沼津市", "島根":"島根県", "白河":"福島県白河市",
    "ぴおシティ":"神奈川県横浜市中区野毛",
}

def extract_location_from_tags(tags: list) -> tuple:
    """タグリストから都道府県・市区町村を推定（より詳細な地名を優先）"""
    best_pref, best_city = "", ""
    for tag in tags:
        addr = LOCATION_TAGS.get(tag)
        if not addr:
            continue
        m = re.match(r'(東京都|北海道|(?:京都|大阪)府|.{2,3}県)(.+)?', addr)
        if not m:
            continue
        pref = m.group(1)
        city_m = re.match(r'([^市区町村]+[市区町村])', m.group(2) or "")
        city = city_m.group(1) if city_m else ""
        # 市区町村が特定できる地名を優先
        if city and not best_city:
            best_pref, best_city = pref, city
        elif not best_pref:
            best_pref = pref
    return best_pref, best_city


# 例外的に登録したい「〜横丁」「〜市場」系の有名スポット
EXPLICIT_ALLOW = {
    "思い出横丁", "大門横丁", "野毛横丁", "自由市場", "二条市場",
    "ニュー新橋ビル", "横浜西口一番街",
}

def is_shop_candidate(tag: str) -> bool:
    """ハッシュタグが店名候補かどうか判定"""
    if tag in EXPLICIT_ALLOW:
        return True
    if tag in EXCLUDE:
        return False
    # 英数字のみ（japanesefood等のSNSタグ）
    if re.match(r'^[a-zA-Z0-9#]+$', tag):
        return False
    # 2文字以下は除外
    if len(tag) < 2:
        return False
    # 数字で始まるタグ（#2024等）
    if re.match(r'^\d', tag):
        return False
    # 「〜グルメ」「〜旅行」「〜観光」「〜市場」「〜横丁」など（明示許可以外）
    if re.search(r'グルメ$|旅行$|観光$|温泉$|市場$|空港$|駅$|中華街$', tag):
        return False
    # 行動語系の長いフレーズ
    if re.search(r'飯$|飲み$|歩き$|はしご$|ソロ$|ひとり$|1人$|ぼっち$', tag):
        return False
    return True


def extract_genre_from_context(title: str, tags: list) -> str:
    """動画タイトルとタグからジャンルを推定"""
    text = title + " " + " ".join(tags)
    if re.search(r'寿司|すし|鮨', text):
        return "寿司"
    if re.search(r'ラーメン|らーめん|拉麺', text):
        return "ラーメン"
    if re.search(r'はしご酒|居酒屋|酒場|飲み', text):
        return "居酒屋"
    if re.search(r'カフェ|cafe|coffee|コーヒー', text, re.I):
        return "カフェ"
    if re.search(r'焼肉|焼き肉|BBQ', text, re.I):
        return "焼肉"
    if re.search(r'スイーツ|ケーキ|パフェ|パン', text):
        return "スイーツ"
    return "食事"


def main():
    with open(INPUT_DESC, encoding="utf-8") as f:
        descs = json.load(f)

    all_shops = []
    seen = set()  # (shop_name, youtube_id) の重複防止

    for d in descs:
        desc = d.get("description", "")
        title = d.get("title", "")
        youtube_id = d.get("youtube_id", "")
        published_at = d.get("published_at", "")

        # ハッシュタグ全抽出（「#しげ吉#はなたれ」のような連結も分割）
        raw_tags = re.findall(r'#([^\s#]+)', desc)
        tags = []
        for t in raw_tags:
            # 各タグ内に残った#を分割
            parts = re.split(r'#', t)
            tags.extend(p for p in parts if p)
        if not tags:
            continue

        # 店名候補タグを抽出
        shop_tags = [t for t in tags if is_shop_candidate(t)]
        if not shop_tags:
            continue

        # エリア情報を取得
        pref, city = extract_location_from_tags(tags)

        # エリアが特定できない動画はスキップ（精度が低いため）
        if not pref:
            continue

        genre = extract_genre_from_context(title, tags)

        for shop_name in shop_tags:
            key = (shop_name, youtube_id)
            if key in seen:
                continue
            seen.add(key)

            all_shops.append({
                "name": shop_name,
                "genre": genre,
                "address": f"{pref}{city}",
                "prefecture": pref,
                "city": city,
                "youtube_id": youtube_id,
                "source_video_title": title,
                "source_video_url": f"https://www.youtube.com/watch?v={youtube_id}",
                "visited_date": published_at,
                "members": ["しおり"],
                "groups": ["shiori"],
                "group": "shiori",
                "description": f"{title} で訪れた飲食店。",
                "_confidence": "hashtag",
            })

    # 結果表示
    print(f"抽出店舗数: {len(all_shops)}件")
    print()
    for s in all_shops:
        print(f"  {s['name']:20s} | {s['prefecture']}{s['city']:10s} | {s['source_video_title'][:35]}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_shops, f, ensure_ascii=False, indent=2)
    print(f"\n→ {OUTPUT} に保存")


if __name__ == "__main__":
    main()
