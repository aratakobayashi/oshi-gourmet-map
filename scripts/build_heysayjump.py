"""
build_heysayjump.py
いただきハイジャンプ（Hey! Say! JUMP）データ生成
ソース: e-nini08.hatenadiary.jp + medax.hatenablog.com (ファンブログ手動抽出済み)

使い方:
  python scripts/build_heysayjump.py --output scripts/scraped_heysayjump.json
"""

import json
import re
import os
import argparse

GROUP = 'heysayjump'
TMDB_SHOW_ID = 197002
THUMBNAIL_URL = 'https://image.tmdb.org/t/p/w500/fHu3eQ9wF9NiVUXYBMV5e9VbOob.jpg'

# ファンブログ2ページから手動抽出したデータ
# Source1: https://e-nini08.hatenadiary.jp/entry/2018/07/10/114437
# Source2: https://medax.hatenablog.com/entry/hijump
RAW_SHOPS = [
    # === SOURCE1: e-nini08.hatenadiary.jp ===
    {
        "name": "スパゲッティーのパンチョ",
        "address": "東京都渋谷区道玄坂2-6-2 B1",
        "members": ["山田涼介", "知念侑李"],
        "episode_info": "2015.11.14/11.21 大盛りグルメ特集",
    },
    {
        "name": "ちばチャン",
        "address": "千葉県柏市旭町1-5-4 プラザパスカ B1",
        "members": [],
        "episode_info": "2015.11.14/11.21 大盛りグルメ特集",
    },
    {
        "name": "TOM BOY 池袋2号店",
        "address": "東京都豊島区南池袋3-13-17 MASHITA5 2F",
        "members": ["山田涼介", "知念侑李"],
        "episode_info": "2015.11.14/11.21 大盛りグルメ特集",
    },
    {
        "name": "中華料理 蘭州",
        "address": "東京都中央区銀座6-16-6",
        "members": ["山田涼介", "知念侑李"],
        "episode_info": "2015.11.14/11.21 大盛りグルメ特集",
    },
    {
        "name": "赤ちり亭 渋谷本店",
        "address": "東京都渋谷区宇田川町25 宇田川町センタービルB1",
        "members": ["有岡大貴", "髙木雄也", "八乙女光"],
        "episode_info": "2016.03.03 体を温める食べ物実験",
    },
    {
        "name": "DAIGOMI",
        "address": "東京都豊島区池袋1-1-7 第2伊三美ビルB1",
        "members": ["有岡大貴", "髙木雄也", "八乙女光"],
        "episode_info": "2016.03.03 体を温める食べ物実験",
    },
    {
        "name": "くう",
        "address": "東京都新宿区歌舞伎町1-16-2 富士ビルディングB1～B2",
        "members": ["有岡大貴", "髙木雄也", "八乙女光"],
        "episode_info": "2016.03.03 体を温める食べ物実験",
    },
    {
        "name": "HERO'S ステーキハウス 秋葉原店",
        "address": "東京都千代田区外神田1-6-7 秋葉原センタービル1F",
        "members": ["有岡大貴", "髙木雄也", "八乙女光", "岡本圭人"],
        "episode_info": "2016.04.14 春の大盛りグルメ",
    },
    {
        "name": "深川 つり舟",
        "address": "東京都国立市東1-15-18 白野ビル2F",
        "members": ["有岡大貴", "髙木雄也", "八乙女光", "岡本圭人"],
        "episode_info": "2016.04.14 春の大盛りグルメ",
    },
    {
        "name": "Sun-mi 高松本店 EMU",
        "address": "東京都中央区銀座6-3-9 7F",
        "members": ["薮宏太", "伊野尾慧", "知念侑李"],
        "episode_info": "2016.05.18 高級レストランのランチ特集",
    },
    {
        "name": "赤坂鮨兆",
        "address": "東京都港区赤坂3-6-10 第3セイコービル3F",
        "members": ["薮宏太", "伊野尾慧", "知念侑李"],
        "episode_info": "2016.05.18 高級レストランのランチ特集",
    },
    {
        "name": "銀熊茶寮",
        "address": "東京都中央区銀座6-3-11 西銀座ビル7F",
        "members": ["薮宏太", "伊野尾慧", "知念侑李"],
        "episode_info": "2016.05.18 高級レストランのランチ特集",
    },
    {
        "name": "てんぷら阿部 銀座本店",
        "address": "東京都中央区銀座4丁目3-7 スバルビルB1",
        "members": ["八乙女光"],
        "episode_info": "2016.07.20 グルメ探偵調査",
    },
    {
        "name": "BLTステーキ 銀座",
        "address": "東京都中央区銀座5丁目4-6",
        "members": ["八乙女光"],
        "episode_info": "2016.07.20 グルメ探偵調査",
    },
    {
        "name": "東京銀座フォワグラ",
        "address": "東京都中央区銀座7-3-13 ニューギンザビル1号館",
        "members": ["八乙女光"],
        "episode_info": "2016.07.20 グルメ探偵調査",
    },
    {
        "name": "銀座 楼蘭",
        "address": "東京都中央区銀座5-8-20 銀座コア10F",
        "members": ["八乙女光"],
        "episode_info": "2016.07.20 グルメ探偵調査",
    },
    {
        "name": "爆裂石焼らーめん一兆",
        "address": "茨城県つくば市並木4-17-8",
        "members": ["髙木雄也", "有岡大貴"],
        "episode_info": "2016.10.26 秋のバスツアーおすすめグルメ",
    },
    {
        "name": "New NEW YORK CLUB",
        "address": "東京都目黒区緑が丘2-15-14",
        "members": ["髙木雄也", "有岡大貴"],
        "episode_info": "2016.10.26 秋のバスツアーおすすめグルメ",
    },
    {
        "name": "汁いち",
        "address": "神奈川県横浜市神奈川区鶴屋町2-13-11 7F",
        "members": ["髙木雄也", "有岡大貴"],
        "episode_info": "2016.10.26 秋のバスツアーおすすめグルメ",
    },
    {
        "name": "秀ちゃんラーメン赤坂",
        "address": "東京都港区赤坂2-17-58",
        "members": ["髙木雄也", "有岡大貴"],
        "episode_info": "2016.10.26 秋のバスツアーおすすめグルメ",
    },
    {
        "name": "ダイニングダーツバー Bee 新宿店",
        "address": "東京都新宿区新宿3-18-4 B1・2",
        "members": ["髙木雄也", "八乙女光", "中島裕翔", "知念侑李"],
        "episode_info": "2017.02.01/02.08 女子会向けスイーツ特集",
    },
    {
        "name": "2BOUZE",
        "address": "千葉県船橋市本町5-7-2 1F",
        "members": ["髙木雄也", "八乙女光", "中島裕翔", "知念侑李"],
        "episode_info": "2017.02.01/02.08 女子会向けスイーツ特集",
    },
    {
        "name": "丸子峠鯛焼き屋",
        "address": "静岡県静岡市駿河区丸子5787-1",
        "members": ["髙木雄也", "八乙女光", "中島裕翔", "知念侑李"],
        "episode_info": "2017.02.01/02.08 女子会向けスイーツ特集",
    },
    {
        "name": "創作寿司工房 竜宮城",
        "address": "福岡県糟屋郡志免町志免2-13-4",
        "members": ["髙木雄也", "八乙女光", "中島裕翔", "知念侑李"],
        "episode_info": "2017.02.01/02.08 女子会向けスイーツ特集",
    },
    {
        "name": "パセラリゾーツ 銀座店",
        "address": "東京都中央区銀座6-13-16 1F",
        "members": ["髙木雄也", "八乙女光", "中島裕翔", "知念侑李"],
        "episode_info": "2017.02.01/02.08 女子会向けスイーツ特集",
    },
    {
        "name": "堂ヶ島食堂",
        "address": "静岡県賀茂郡西伊豆町仁科2045-3",
        "members": ["髙木雄也", "有岡大貴", "伊野尾慧", "八乙女光"],
        "episode_info": "2018.01.01 世界の絶景そっくり旅",
    },
    {
        "name": "海鮮茶屋 活き活き亭",
        "address": "千葉県木更津市富士見",
        "members": ["髙木雄也", "八乙女光", "有岡大貴"],
        "episode_info": "2018.08.25/09.01 日帰りサイクリング千葉房総",
    },
    {
        "name": "うな達",
        "address": "東京都豊島区東池袋",
        "members": ["山田涼介", "八乙女光"],
        "episode_info": "2018.09.08 グルメ探偵調査",
    },
    {
        "name": "亀戸餃子",
        "address": "東京都江東区亀戸",
        "members": ["山田涼介", "八乙女光"],
        "episode_info": "2018.09.08 グルメ探偵調査",
    },
    {
        "name": "ひき肉少年",
        "address": "東京都港区白金",
        "members": ["山田涼介", "八乙女光"],
        "episode_info": "2018.09.08 グルメ探偵調査",
    },
    {
        "name": "路地裏",
        "address": "東京都港区港南",
        "members": ["山田涼介", "八乙女光"],
        "episode_info": "2018.09.08 グルメ探偵調査",
    },
    # === SOURCE2: medax.hatenablog.com (川越特集) ===
    {
        "name": "大玉や",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11029624/",
    },
    {
        "name": "松陸製菓",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11024414/",
    },
    {
        "name": "龜屋 本店",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11027752/",
    },
    {
        "name": "鐘撞堂下 田中屋",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11020315/",
    },
    {
        "name": "創作漬物 川越・河村屋",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11025164/",
    },
    {
        "name": "亀屋栄泉",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11005847/",
    },
    {
        "name": "寺子屋本舗 川越店",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11025288/",
    },
    {
        "name": "松本醤油商店",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.10 川越特集",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11038254/",
    },
    {
        "name": "まことや",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11020258/",
    },
    {
        "name": "醤遊王国",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11044505/",
    },
    {
        "name": "東洋堂",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11029625/",
    },
    {
        "name": "餃子菜館 大八",
        "address": "埼玉県川越市",
        "members": ["伊野尾慧", "髙木雄也"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11000929/",
    },
    {
        "name": "近江屋長兵衛商店",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11003518/",
    },
    {
        "name": "龜屋 元町店",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11019660/",
    },
    {
        "name": "cocoro 川越店",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11040808/",
    },
    {
        "name": "松本製菓",
        "address": "埼玉県川越市",
        "members": ["薮宏太", "山田涼介"],
        "episode_info": "2018.11.24 川越特集後編",
        "tabelog_url": "https://tabelog.com/saitama/A1103/A110303/11032418/",
    },
]

GENRE_MAP = [
    (["ラーメン", "汁いち", "爆裂石焼"], "ラーメン"),
    (["ステーキ", "HERO'S"], "焼肉"),
    (["寿司", "竜宮城", "鮨兆"], "寿司"),
    (["カフェ", "パセラ"], "カフェ"),
    (["スイーツ", "製菓", "菓子", "栄泉", "鯛焼き", "大玉や", "寺子屋", "東洋堂"], "スイーツ"),
    (["居酒屋", "Bee", "ダーツ"], "居酒屋"),
    (["天ぷら", "てんぷら", "うな達", "食堂", "茶寮", "海鮮", "活き活き亭", "深川"], "和食"),
    (["餃子", "中華", "蘭州", "楼蘭"], "食事"),
    (["醤油", "醤遊", "漬物"], "その他"),
]


def detect_genre(name):
    for keywords, genre in GENRE_MAP:
        if any(kw in name for kw in keywords):
            return genre
    return "食事"


def make_id(name, idx):
    slug = re.sub(r"[^\w]", "", name, flags=re.UNICODE)
    slug = slug[:15].lower()
    return f"heysayjump-{slug}-{idx:03d}"


def parse_date(ep_info):
    m = re.search(r"(20\d\d)\.(\d\d)\.(\d\d)", ep_info)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def extract_prefecture(address):
    m = re.match(r"(東京都|神奈川県|埼玉県|千葉県|茨城県|静岡県|福岡県|大阪府|京都府|兵庫県)", address)
    return m.group(1) if m else ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="scripts/scraped_heysayjump.json")
    args = parser.parse_args()

    shops = []
    for idx, raw in enumerate(RAW_SHOPS):
        name = raw["name"]
        address = raw.get("address", "")
        members = raw.get("members", [])
        ep_info = raw.get("episode_info", "")
        tabelog_url = raw.get("tabelog_url", "")

        prefecture = extract_prefecture(address)
        genre = detect_genre(name)
        visited_date = parse_date(ep_info)

        affiliate_links = []
        if tabelog_url:
            affiliate_links.append({"label": "食べログで見る", "url": tabelog_url})

        shops.append({
            "id": make_id(name, idx),
            "name": name,
            "genre": genre,
            "prefecture": prefecture,
            "city": "",
            "address": address,
            "lat": None,
            "lng": None,
            "youtube_id": "",
            "thumbnail_url": THUMBNAIL_URL,
            "source_type": "tv",
            "tmdb_id": TMDB_SHOW_ID,
            "tmdb_type": "tv",
            "source_video_title": ep_info,
            "source_video_url": "",
            "visited_date": visited_date,
            "members": members,
            "groups": [GROUP],
            "group": GROUP,
            "description": ep_info,
            "nearest_station": "",
            "price_range": "",
            "tabelog_url": tabelog_url,
            "hotpepper_url": "",
            "google_maps_url": "",
            "tags": ["いただきハイジャンプ", "HeySayJUMP"],
            "affiliate_links": affiliate_links,
        })

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)

    print(f"=== 完了 ===")
    print(f"総件数: {len(shops)}件")
    print(f"thumbnail_urlあり: {sum(1 for s in shops if s['thumbnail_url'])}件")
    print(f"住所あり: {sum(1 for s in shops if len(s['address']) > 5)}件")
    print(f"→ {args.output}")
    print("\n最初の5件:")
    for s in shops[:5]:
        print(f"  [{s['genre']}] {s['name']} / {s['address'][:30]}")


if __name__ == "__main__":
    main()
