# 推しグルメ巡礼MAP - プロジェクト定義書

## サイト概要
- **サイト名**: 推しグルメ巡礼MAP
- **URL**: https://gourmet.oshikatsu-guide.com
- **目的**: アイドル・芸人・YouTuberが訪れたグルメスポットを地図で探せる聖地巡礼ガイド
- **対象**: アイドルグループに限らず、お笑い芸人・YouTuberも対象に拡大
- **技術**: Jekyll + GitHub Pages（静的サイト、コストゼロ）
- **リポジトリ**: https://github.com/aratakobayashi/oshi-gourmet-map

## ゴール
- ファン向け聖地巡礼ガイドとして認知を獲得
- SEO集客からアフィリエイト収益化
- お店データ **3000件以上** を目指す

---

## データ収集パイプライン

```
① YouTube Data API（Python）
   チャンネルの動画一覧を自動取得
   → youtube_id・タイトル・説明文・投稿日を保存
          ↓
② Gemini API（自動）
   動画リストから飲食店訪問動画を選別
   → 店名・住所・メンバー・ジャンルをJSON抽出
   ※ youtube_idはAPIから取得済みのものを使用（捏造防止）
          ↓
③ Python バリデーション
   - youtube_id: 11文字英数字・ユニークチェック
   - 重複店舗の検出（店名の正規化）
   - 必須フィールドの確認
          ↓
④ Python ジオコーディング
   住所 → 緯度・経度（Nominatim OpenStreetMap、無料）
          ↓
⑤ Python アフィリエイトURL付与
   店名で食べログ・ホットペッパーを検索してURL付与
          ↓
⑥ shops.json 自動マージ
```

### データ収集ルール
- **youtube_id または thumbnail_url（TMDB等）のどちらかが必須。サムネイルなし店舗は登録しない**
- 1本の動画に複数店舗が登場する場合はそれぞれ別エントリ
- 住所は番地まで取得する（エリア名だけはNG）
- ドラマ・映画ソースの場合は `source_type: drama` / `tmdb_id` / `tmdb_type` を付与し、TMDBエピソードスチール or ポスターを `thumbnail_url` にセット

---

## データスキーマ（shops.json）

```json
{
  "id": "yonino-xxx",
  "name": "店名",
  "genre": "カフェ",
  "prefecture": "東京都",
  "city": "渋谷区",
  "address": "東京都渋谷区...",
  "lat": 35.6812,
  "lng": 139.7671,
  "youtube_id": "XXXXXXXXXXX",
  "source_video_title": "動画タイトル",
  "source_video_url": "https://www.youtube.com/watch?v=XXXXX",
  "visited_date": "2025-01-15",
  "members": ["二宮和也"],
  "groups": ["yonino"],
  "group": "yonino",
  "description": "説明",
  "nearest_station": "渋谷駅",
  "price_range": "〜3000円",
  "tabelog_url": "https://tabelog.com/...",
  "hotpepper_url": "https://www.hotpepper.jp/...",
  "google_maps_url": "https://maps.google.com/...",
  "tags": ["行列", "朝食"],
  "affiliate_links": [
    {"label": "食べログで見る", "url": "https://tabelog.com/..."},
    {"label": "ホットペッパーで予約", "url": "https://www.hotpepper.jp/..."}
  ],
  "thumbnail_url": "https://image.tmdb.org/t/p/w500/...",
  "source_type": "drama",
  "tmdb_id": 45753,
  "tmdb_type": "tv",
  "ordered_items": ["カフェラテ", "スコーン"],
  "seating_note": "カウンター席あり・テラス席からの眺望が動画のメインシーン"
}
```

### ジャンル一覧
`カフェ` `ラーメン` `焼肉` `食事` `スイーツ` `寿司` `もんじゃ` `居酒屋` `和食` `その他`

---

## 対象グループ・チャンネルID

| group ID | グループ名 | チャンネルID | チャンネルURL |
|---------|----------|------------|------------|
| yonino | よにのちゃんねる | UC2alHD2WkakOiTxCxF-uMAg | https://www.youtube.com/@yoninochannel |
| snowman | すの日常（Snow Man） | UCuFPaemAaMR8R5cHzjy23dQ | https://www.youtube.com/@SnowMan.official.9 |
| sixtones | ストチューブ（SixTONES） | 未確認 | https://www.youtube.com/@SixTONES_st |
| naniwa | なにわ男子 | UCDtVdj7sm41Ysg3XSiSUH3w | https://www.youtube.com/@naniwadanshi_official |
| equal_love | イコラブ（=LOVE） | 未確認 | - |
| nogizaka46 | 乃木坂46（公式MV） | UCUzpZpX2wRYOk3J8QTFGxDg | https://www.youtube.com/@nogizaka46SMEJ |
| nogizaka46 | 乃木坂配信中（乃木坂工事中） | UCfvohDfHt1v5N8l3BzPRsWQ | https://www.youtube.com/@nogizakahaishinchu |
| hinatazaka46 | 日向坂46 | 未確認 | - |
| sakurazaka46 | 櫻坂46 | 未確認 | - |
| ginga | 中丸雄一 銀河チャンネル | - | https://8888-info.hatenablog.com/entry/%E3%83%AD%E3%82%B1%E5%9C%B0%E4%B8%80%E8%A6%A7 |
| shiori | しおりのなんとなく日常 | UCHYa60S50wJ3W-mcTbVQPew | https://www.youtube.com/@nantonakushiori |
| kamaitachi | かまいたち | UCIR2mQ77wHrLMreV45nYhgw | https://www.youtube.com/@kamaitachi |
| kodoku_no_gurume | 孤独のグルメ | - | goro-tablog.com（ファンサイト）/ TMDB ID:45753 |
| heysayjump | Hey! Say! JUMP（いただきハイジャンプ） | UCZgJwFN1PeR8hZZ8A7huuTQ（ファン） | TMDB ID:197002 / e-nini08.hatenadiary.jp |

### グループカラー（main.js）
```javascript
shiori:       '#ec4899'  // ピンク
yonino:       '#e8537a'  // ピンク
snowman:      '#3b82f6'  // ブルー
sixtones:     '#7c3aed'  // パープル
naniwa:       '#f97316'  // オレンジ
equal_love:   '#f43f5e'  // レッド
sakurazaka46: '#e11d48'  // 深紅
nogizaka46:   '#0ea5e9'  // 水色
hinatazaka46: '#f59e0b'  // アンバー
kamenashi:         '#059669'  // グリーン
kodoku_no_gurume:  '#92400e'  // ブラウン
heysayjump:        '#ef4444'  // レッド
```

---

## アフィリエイト戦略

### 対象サービス
| サービス | 報酬形態 | 備考 |
|---------|---------|------|
| 食べログ | クリック報酬 | ASP経由 |
| ホットペッパーグルメ | 予約報酬 | リクルートAP |
| Googleマップ | なし | UX向上目的 |

### 実装方針
- 各店舗に `tabelog_url` `hotpepper_url` を付与
- モーダル内に「予約する」「食べログで見る」ボタンを表示
- アフィリエイトタグはPythonで自動付与

---

## スクリプト一覧（scripts/）

| ファイル | 役割 |
|---------|------|
| `fetch_channel_videos.py` | YouTubeチャンネルの動画一覧取得 |
| `merge_shops.py` | 新規JSONをshops.jsonにマージ（バリデーション含む） |
| `geocode_shops.py` | 座標なし店舗のジオコーディング（Nominatim） |
| `geocode_kamenashi.py` | 住所なし店舗向け強化版ジオコーディング（Overpass API併用） |
| `match_videos.py` | 訪問日付からyoutube_idを紐付け |
| `scrape_naniwa.py` | なにわ男子ロケ地スクレイピング（illmnt.com / hatenablog） |
| `scrape_snowman.py` | Snow Manロケ地スクレイピング（snowman-information.com / hatenablog） |
| `scrape_kamenashi.py` | 亀梨和也ロケ地スクレイピング |
| `scrape_nogizaka.py` | 乃木坂46スクレイピング（senublog.com まとめ + 個別ページ両対応） |
| `scrape_tabelog_matome.py` | 食べログまとめページから乃木坂46店舗取得（tabelog JSON-LDで正確座標取得） |
| `scrape_ginga.py` | 中丸雄一銀河チャンネルスクレイピング（8888-info.hatenablog.com） |
| `scrape_hinatazaka.py` | 日向坂46スクレイピング（せっかくグルメ銚子回ほか） |
| `scrape_kamaitachi.py` | かまいたち動画説明文パース（ロケで行った飲食店まとめ） |
| `scrape_kodoku.py` | 孤独のグルメ スクレイピング（goro-tablog.com）+ TMDB APIでエピソードスチール取得 |
| `build_heysayjump.py` | Hey! Say! JUMP（いただきハイジャンプ）ファンブログ抽出済みデータからJSON生成 |
| `scrape_shiori.py` | しおりのなんとなく日常 YouTubeチャンネル動画取得＋概要欄パース（「店名\nhttps://tabelog...」形式対応） |
| `geocode_shiori.py` | しおり専用ジオコーダー（tabelog JSON-LD優先 + 丁目形式フォールバック） |
| `extract_shiori_hashtags.py` | ハッシュタグから店名候補を抽出（#店名パターン・汎用タグ除外・連結タグ分割対応） |

---

## 環境変数
```bash
export YOUTUBE_API_KEY="..."   # YouTube Data API v3
export GEMINI_API_KEY="..."    # Gemini API（未取得）
export TMDB_API_KEY="..."      # TMDB API（ドラマ・映画サムネイル取得）登録: https://www.themoviedb.org/settings/api
```

---

## 現在の状況（2026-05-26時点）
- 総店舗数: 798件（kodoku_no_gurume:176 / equal_love:117 / yonino:97 / nogizaka46:79 / snowman:59 / sixtones:49 / heysayjump:48 / notme:39 / kamenashi:32 / shiori:29 / neajoy:25 / ginga:12 / naniwa:10 / kamaitachi:10 / hinatazaka46:7 / timelesz:6 / sakurazaka46:3）
- youtube_idあり: ~372件（50%）
- thumbnail_urlあり: 0件（孤独のグルメ追加後に増える予定）
- サムネイルなし: 42件（nogizaka46:12 / sixtones:6 / hinatazaka46:6 / naniwa:5 / ginga:4 / sakurazaka46:3 / snowman:2 / yonino:2 / equal_love:2）← ファンブログ由来で動画特定困難
- QA実施済み（2026-05-25）: description全件あり / 重複なし / 海外店舗6件（意図的）
- デプロイ: GitHub Pages + 独自ドメイン済み（gourmet.oshikatsu-guide.com）
- GA4: 設定済み（G-PFYMG6S0Q1）
- Search Console: 設定済み
- 記事: 9件（よにのちゃんねる中心、浅草クロスグループ記事含む）

## データ収集パイプライン（実績）
- よにのちゃんねる: YouTube API → Gemini抽出 → ジオコーディング → マージ
- Snow Man / なにわ男子: ファンブログスクレイピング → ジオコーディング → マージ
- 亀梨和也: ファンブログスクレイピング → 強化ジオコーディング → マージ
- 乃木坂46: Senu Blog（senublog.com）スクレイピング → 30件 + tabelog matome（matome/3277/ + matome/7804/）+ senublog個別ページ → 計79件
  - tabelog matomeはscrape_tabelog_matome.pyで取得（tabelog JSON-LDから座標取得）
  - senublog個別ページはscrape_nogizaka.py（scrape_senublog_individual関数）で対応
- 中丸雄一銀河チャンネル: hatenablog（8888-info.hatenablog.com）スクレイピング → 12件
- Snow Man（追加）: mom-eat.com スクレイピング（scrape_mom_eat.py）→ +9件（計59件）。29件既存店補完（seating_note/ordered_items付与）
- かまいたち: 動画説明文パース（ロケで行った飲食店まとめ 関西・関東編） + rascalブログ → 10件
- =LOVE / ≠ME / ≒JOY: miruwz7.blog.jp スクレイピング（scrape_miruwz.py） → 181件（equal_love:66 / notme:26 / neajoy:12 + 食品フィルタ補完分77件）
- 孤独のグルメ: goro-tablog.com スクレイピング（scrape_kodoku.py）+ TMDB APIエピソードスチール → 176件
- しおり（なんとなく日常）: 概要欄パース（tabelog URL形式）→ 9件 + ハッシュタグ抽出（extract_shiori_hashtags.py）→ 20件 = 計29件
- **重要**: しおりは概要欄にtabelog URLを入れる動画が少ない。ハッシュタグ抽出（#店名パターン）が主軸。新着動画でも継続抽出可能。
- **重要**: Gemini APIはYouTubeタイトルからの飲食店抽出に向かない。ファンブログスクレイピングが主軸。
- **重要**: miruwz7.blog.jpはJS描画のため CSS セレクタ不可。regex で記事URLを収集すること。
- **重要**: サムネイルなし店舗は登録しない。youtube_id または TMDB等のthumbnail_urlが必須。
- **重要**: ginga（銀河チャンネル）のvisited_dateはファンブログ日付をそのまま使用。scrape_ginga.pyで--year 2025を使うと実際は2024年動画にずれる。日付はチャンネル動画一覧で確認すること（channelId: UCYTrZoOfDgoQo7Bdbttv9qw）。

## ロードマップ
1. ✅ MVP作成・デプロイ
2. ✅ 独自ドメイン設定（gourmet.oshikatsu-guide.com）
3. ✅ データ収集パイプライン構築（スクレイピング中心）
4. ✅ GA4 + Google Search Console設定
5. ✅ 対象をアイドルから芸人・YouTuberに拡大（ginga・kamaitachi追加）
6. ✅ ランキングページ新設（/ranking/）
7. 🔄 データ拡充（目標3000件）
8. ✅ ドラマ・映画ソース対応（thumbnail_url / source_type / tmdb_id フィールド追加）
9. 🔄 孤独のグルメ データ収集（scrape_kodoku.py 完成・TMDB_API_KEY取得待ち）
10. ⬜ アフィリエイトリンク整備（食べログ直URL・ホットペッパー）
11. ⬜ 乃木坂46 / 日向坂46 追加ファンブログ発掘
12. ⬜ データ3000件達成
