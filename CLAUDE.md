# 推しグルメ巡礼MAP - プロジェクト定義書

## サイト概要
- **サイト名**: 推しグルメ巡礼MAP
- **URL**: https://gourmet.oshikatsu-guide.com
- **目的**: アイドル・芸人・YouTuberが訪れたグルメスポットを地図で探せる聖地巡礼ガイド
- **対象**: アイドルグループに限らず、お笑い芸人・YouTuberも対象に拡大
- **技術**: Jekyll + GitHub Pages（静的サイト、コストゼロ）
- **リポジトリ**: https://github.com/aratakobayashi/oshi-gourmet-map

## 守るルール（全作業共通・最優先）
- **食べログ**: ページへの自動アクセス・スクレイピングをしない。食べログ由来の情報（点数・画像・座標・住所・営業時間・価格帯・電話番号など）を取得・保存・掲載しない。食べログへのリンクを張るのは可（収益化はバリューコマース経由の公式アフィリエイト）。
- 店舗情報の補完は、ホットペッパーグルメの公式API（規約とクレジット表記に従う）か自前の調査で行う。
- 既存のURLは変えない。変える場合は必ず301リダイレクトを設定する。
- アフィリエイトリンクには `rel="sponsored noopener"` を付け、該当ページにPR表記を入れる（ステマ規制対応）。
- 体験談や口コミを捏造しない。
- APIキーなどの秘密情報をリポジトリに入れない（公開リポジトリ）。キーは環境変数から読み、デフォルト値に実キーを書かない。

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
⑤ Python リンク整理（scripts/normalize_links.py）
   tabelog_url / hotpepper_url を正とし affiliate_links の重複を除去
   ※ 食べログの検索・ページ取得はしない（ファンブログ等に載っている食べログURLを使うのは可）
          ↓
⑥ shops.json 自動マージ
          ↓
⑦ ページ生成（必須）
   bash scripts/build_pages.sh --push
   → generate_shop_pages.py + generate_list_pages.py + build_site_data.py を実行
   → _shop_pages/ と _list_pages/、_data/（カード・近くの店・グループ集計）、data/explore.json を再生成・コミット・push
   ※ shops-lite.json は scripts/generate_lite.py で再生成する
   ※ データ追加後は必ずこのスクリプトを実行すること
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
  "tabelog_url": "https://tabelog.com/...",
  "hotpepper_url": "https://www.hotpepper.jp/...",
  "google_maps_url": "https://maps.google.com/...",
  "tags": ["行列", "朝食"],
  "affiliate_links": [
    {"label": "公式サイト", "url": "https://..."},
    {"label": "一休で予約", "url": "https://restaurant.ikyu.com/..."}
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
genre は英語コードで保存し、表示名・アイコンは `_data/genres.json` が正（Liquid / JS / Python から参照）。
`shokuji`（食事） `washoku`（和食） `cafe`（カフェ） `ramen`（ラーメン） `sweets`（スイーツ） `izakaya`（居酒屋） `yakiniku`（焼肉） `chuka`（中華） `others`（その他）

### リンク項目のルール
- 食べログは `tabelog_url`、ホットペッパーは `hotpepper_url` だけに入れる（店舗トップURL・追跡パラメータなし）
- `affiliate_links` には公式サイト・一休など、それ以外のリンクだけを入れる
- `tabelog_url_alt` は食い違いの確認用の一時フィールド（確認後に削除）
- アフィリエイト変換は `_includes/affiliate-link.html` が `_config.yml` の `affiliate.valuecommerce` の sid/pid を見て行う。空の間は通常リンク
- `tabelog_score` / `price_range` / `business_hours` / 食べログ画像の `thumbnail_url` は食べログ由来のため持たない

### グループ名
表示名は `_data/groups.json` が正（_group_pages の group_label と同じ）。新グループ追加時はここにも追加する。

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
| kingprince | King & Prince（当たり前レストラン） | - | tsuzuki-fam.com（ファンブログ）8エピソード（2022-08〜2023-05） |

### グループカラー（_group_pages の group_color が正。build_site_data.py が _data/group_ix.json に写す。下は参考）
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
kingprince:        '#f472b6'  // ピンク
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
| `scrape_kinpri.py` | King & Prince「当たり前レストラン」スクレイピング（tsuzuki-fam.com / ValueCommerce経由tabelog URL対応） |
| `fetch_program_thumbnails.py` | 画像なし店舗に、出典のテレビ番組・ドラマのTMDB画像を補完（番組名→TMDB IDの対応表 PROGRAMS。回が特定できればエピソード画像、なければポスター）。新しい番組はPROGRAMSに追加 |
| `fetch_hotpepper_photos.py` | hotpepper_url のある店にホットペッパーAPIの店舗写真を hotpepper_photo として付ける（HOTPEPPER_API_KEY）。表示は 動画 → hotpepper_photo → thumbnail_url の順。写真を出すページとフッターに「Powered by ホットペッパー Webサービス」 |
| `match_youtube_videos.py` | youtube_id のない店のうち、公式YouTube企画（すのちゅーぶ・Aぇちゅ〜ぶ・乃木坂配信中など）が出典の店をチャンネルの動画一覧と照合して youtube_id を付ける（YOUTUBE_API_KEY）。自信のないものは scripts/youtube_match_review.json に候補を出し、確認後 --apply-review |
| `normalize_links.py` | 外部リンクの正規化（重複削除・食べログURLの店舗トップ化・ホットペッパーの追跡パラメータ除去）。何度実行しても同じ結果 |
| `generate_lite.py` | shops.json から shops-lite.json / shops-lite/*.json を生成（リニューアル後の画面では未使用） |
| `build_site_data.py` | 画面用データを生成: _data/shop_cards・group_meta・group_ix・group_detail・nearby・venue_nearby・site_stats と data/explore.json（/shops/ の絞り込み用） |
| `geocode_gsi.py` | 住所から座標を取り直す（国土地理院アドレス検索API・キー不要）。番地まで一致したとき等だけ更新。既定は試算のみ、--write で書き込み |
| `clean_orphan_pages.py` | shops.json にない店舗の _shop_pages（孤立ページ）から指定フィールドを除去（URLは残す） |
| `check_articles.py` | 特集記事（_posts/）の shop_ids と本文の inline-shop-card/grid のIDを shops.json と照合。--fix で、IDの付け替え（REMAP）・ないIDの削除・shop_ids を本文の店と一致させる。build_pages.sh で確認だけ実行 |
| `merge_candidates.py` | 調べた店の候補JSON（{"new":[...],"attach":[...]}）を確かめて shops.json に足す。採用は confidence high/mid・店に行った回・住所が国土地理院で番地まで一致・youtube_id 11文字だけ（地方の大字までの high は location_unverified）。attach は既存店に動画を付ける。group に - で候補ごとの group |
| `weekly/run.py` | 週1回の自動更新（情報源ごとのアダプタ→merge_candidates.py）。GitHub Actions の weekly-update.yml が実行。`--dry-run` で書き込みなし |
| `add_group.py` | 新しいグループを足す（_data/groups.json と _group_pages/<id>.md）。`python scripts/add_group.py <id> <表示名> <色>` |
| `refresh_group_titles.py` | グループページのタイトル・説明・店数を店のデータから書き直す（build_pages.sh で実行） |
| `migrate_guidebook.py` | 旧 推し活ガイドブック（oshikatsu-guide.com）の記事を _guides/ へ移行。301用の対応表を redirects/ に出力 |

**食べログにアクセスするため使用禁止のスクリプト**（削除予定）: `fetch_tabelog_thumbnails.py` `retry_arashi_thumbnails.py` `scrape_tabelog_details.py` `check_closed_shops.py` `scrape_tabelog_matome.py` `geocode_missing.py` `geocode_shiori.py`。`scrape_arashi.py` `scrape_kinpri.py` `pipeline_naniwa.py` `pipeline_timelesz.py` の食べログ取得関数は無効化済み。

---

## 推し活ガイド（/guide/）
- 旧 推し活ガイドブック（WordPress）の記事41本を `_guides/` コレクションに移行（2026-10）。レイアウトは `_layouts/guide.html`
- カテゴリ: `_data/guide_categories.json`（venue / travel / basics / profile）
- 会場ガイドの「会場周辺の聖地グルメ」は `_data/venues.json` の座標から build_site_data.py が近い順に計算（_data/venue_nearby.json）し、ページ生成時に表示。3km以内が3軒未満の会場は10kmまで広げる（r に半径）
- 旧URL→新URLの対応表: `redirects/guidebook_redirects.csv`（旧サイト側で301を設定する）
- 会場ガイドの新しい型（2026-10 東京ドームから）: 冒頭の要点 → 基本情報 → アクセス → ゲートと座席 → 持ち込み・ルール → お金・荷物・当日 → 泊まる → 周辺の聖地グルメ（自動）→ よくある質問。公式サイトで確かめた事実だけを書き、体験談風の内容（参戦ファッション・撮影スポットなど）は書かない。front matter: `summary`（要点）・`checked_at`（確認日）・`sources`（label/url の出典）・`faq`（FAQPage の構造化データにもなる）・`thumbnail_note`（画像の注記）。新しい会場は `_data/venues.json` に名前と座標を足す
- 会場ガイドの見出し画像（サムネイル）は写真を使わず、SVG で描いた写真風のイラストに、会場名・「ライブ参戦ガイド」・記事の中身（最寄り駅・座席・持ち込み・周辺グルメ○軒など）を大きく載せて、一覧でひと目で見たくなるものにする（元データ `assets/img/guide/src/`、1200px と 600px の webp）。画像の下に「イラスト」と注記する
- 会場ガイドの本文には図を3枚以上入れる（駅との位置関係・座席のつくり・持ち込めないもの・当日の準備など）。図とサムネイルは会場データ `scripts/venue_data/<slug>.json`（駅・座席・持ち込み禁止・当日の準備・サムネイルの札。形は tokyo-dome.json を参照）から `python scripts/venue_guide_images.py <slug>` で作る（`assets/img/guide/<slug>/*.svg` と `<slug>.webp`。Chromium が要る: 環境変数 PW_CHROME と NODE_PATH、scripts/render_png.js）。記事の図の width/height も自動で合わせる。会場を足すときは `_data/venues.json` にも名前と座標を入れて build_site_data.py を先に実行（サムネイルの「周辺の聖地グルメ○軒」に使う）。`<figure class="fig">` で載せ、alt に図の中身を文章で書く。図の内容も公式情報で確かめた事実だけにし、出典をキャプションに書く
- 会場の type は dome / arena / hall / budokan / messe / stadium（屋根なし）。2026-10-10 に旧型の会場ガイド18本も新しい型に書き直した（URLはそのまま）。名称変更: 日本ガイシホール→クロコくんホール、さいたまスーパーアリーナ→GMOアリーナさいたま、武蔵野の森総合スポーツプラザ→京王アリーナTOKYO、札幌ドーム→大和ハウス プレミストドーム、マリンメッセ福岡→マリンメッセ福岡A館、神戸ワールド記念ホール→ワールド記念ホール（_data/venues.json の name も新しい名前。slug は旧名のまま）
- 回遊: build_site_data.py が _data/article_rel.json（キー `p:<記事slug>` / `g:<ガイドslug>` → posts・guides のサムネイル付きカード）を作り、`_includes/rel-cards.html` で記事・ガイドの末尾に出す（特集→近くの会場のガイド・あわせて読みたい／会場ガイド→近くの会場・会場の近くの店が載っている特集）。会場ガイドの周辺グルメは card.html に会場からの距離（`from`/`m`）を出し、推しごとのチップと「地図で近くのお店を見る」は /shops/?near=緯度,経度&nl=会場名（explore.js が近い順に並べ、地図をその場所に寄せる）
- 会場ガイド以外のガイド（メンバー紹介など）も、書き直すときは同じく checked_at・sources・summary・faq を付け、公式か大手報道で確かめた事実だけを書く（ファンの声・SNSの埋め込み・噂・年齢は書かない。生年月日だけ）。見出し画像は写真を使わず `python scripts/guide_text_thumbs.py <slug>`（文字だけのサムネイル。中身は scripts/guide_thumbs.json）。2026-10-10 にメンバー・グループ・番組紹介9本とtimeleszツアー記事を書き直し（猪俣周杜は2026-09-30付でSTARTOとの契約解除、timeleszは10月から7人。少年忍者は2025-11-30に活動終了）
- メンバー紹介の新しい型（2026-10 寺西拓人で試作）: 本人の言葉（公式インタビュー・会見の短い引用＋出典リンク。`.pf-quote`）・ひと目でわかるカード（`.pf-card`）・数字で見る（`.pf-nums`）・歩みの年表図・出演作（`.pf-works`）・はじめて見るなら（公式チャンネルの動画。`.pf-videos`）・推しと「食」（食の発言＋訪れたお店のジャンル図＋inline-shop-grid＋地図へのボタン `.pf-cta` → /shops/?g=<group>&m=<group>:<名前>）。本文を `<div class="pf" style="--pc:<メンバーカラー>">` で囲む。図と見出し画像は `python scripts/profile_figures.py <slug>`（データ scripts/profile_data/<slug>.json）。ファンの声は作らない。編集部の意見は編集部の意見として書く
- お役立ちガイド（遠征準備・推し活の基本）の新しい型（2026-10 遠征準備3本・推し活の基本10本）: 本文を `.pf` で囲み、ひと目でわかるまとめ（.pf-card/.pf-nums）・図4〜5枚（記事ごとに手で描いたSVG、幅420・背景 #F7F3EC・12px未満の文字なし。assets/img/guide/<slug>/）・編集部のメモ（.pf-quote、事実にもとづく助言。架空の体験談は書かない）・会場ガイドやお店探しへの .pf-cta。値段は書かず公式へ。見出し画像は `python scripts/howto_thumbs.py <slug>`（データ scripts/howto_data/<slug>.json。アイコンのイラスト）。A8リンクは行き先と表示名が一致するものだけ（旧記事は表示名と行き先が食い違うものが多かった）
- 「近くの店」（会場ガイド・店舗ページ）には、住所が番地まであり座標がほかの店と重なっていない店だけを出す（区役所あたりの座標になっている店を除くため）。場所が怪しい店は shops.json で `location_unverified: true` を付けると除外される

## 特集記事（/articles/）の新しい型（2026-10 全42本）
- お手本 `_posts/2026-04-01-yonino-gourmet-matome-2025-2026.md`。本文はHTMLで `.pf` に包み、ひと目でわかるカード・数字で見る・年表図／ジャンルと場所の図（`python scripts/post_figures.py <slug> --color '<色>' --title '<…の年表>'`。assets/img/posts/<slug>/）・テーマ別の .pf-works（回・動画タイトル・注文したもの）＋inline-shop-grid・公式動画・エリアで巡る・地図への .pf-cta
- 事実の土台は店舗データと公式（YouTube oEmbed・TMDB・番組公式）。data/shops.json の description の評判（行列・名店・ミシュランなど）は書き写さない
- 動画タイトルが空の店は `python scripts/fill_video_titles.py --write`（YouTube oEmbed。source_video_title と source_video_channel）
- 食べログボタンは、`tabelog_verified: true` を付けた店だけ店のページへ。ほかは「店名＋市区町村」の食べログ検索（集めた tabelog_url に別の店が多かったため）。ホットペッパーは `scripts/add_hotpepper_urls.py`（名前が完全一致なら1.5km以内、部分一致なら300m以内だけ採用。迷うものは scripts/hotpepper_match_review.json）

## デザイン（2026-10 リニューアル「1a 巡礼帳」）
- CSS は `assets/css/app.css` の1ファイル（色・文字・余白はファイル先頭の変数）。JS は `assets/js/app.js`（全ページ共通: 保存・動画・地図・共有・目次・店舗の行の組み立て）と `assets/js/explore.js`（/shops/ の絞り込み・地図）だけ。どちらも素のJS
- 店舗カードの部品: `_includes/card.html`（グリッド）・`row.html`（行）・`mini.html`（小）・`thumb.html`。中身は `_data/shop_cards.json` から引く。JSで作る行は app.js の shopUI.row（row.html と同じ形に保つ）
- include の中で使う変数は `_c` `_gi` のように _ を付ける（Jekyll の include は変数を呼び出し元と共有するため、付けないとページ側の値を上書きする）
- 写真のない店はグループ色の面＋ジャンル印（`_data/genres.json` の mark）で表す
- 一覧は `.rows`（スマホは行）に `.rows--grid` を付けるとPC（1024px以上）で写真カードのグリッドになる（`.rows--4` で4列）。グループ・一覧ページの並び替え・メンバー絞り込み・もっと見るは `assets/js/listpage.js`
- PCの記事・ガイドは1200px以上で「目次｜本文｜サイド」の3列。/shops/ は body_class: page-wide で画面いっぱいに広げる
- レイアウトの front matter の body_class は default.html が layout.body_class として読む
- スマホの下部ナビは「ホーム・探す・特集（/articles/）・ガイド（/guide/）・保存」。ランキングはトップの「人気のお店ランキングを見る」とフッターのサイト内リンクから
- ヘッダーのメニューは1024px以上（それ未満は下部ナビ）。ヘッダーの検索欄は1180px以上（1024〜1179pxは虫めがねボタン）
- /shops/ のスマホの「一覧／地図」切り替えは画面下に浮かぶボタン（#fab）
- /shops/ のPC（1024px以上）は、一覧の店を押すと地図の上に詳細パネルを開く（explore.js。店舗ページを fetch して .shop を差し込む。URLは ?shop=<slug>、戻る・Escで閉じる）。スマホや ?shop= 付きURLをスマホで開いたときは店舗ページへ移る
- 店舗ページのルート案内・Googleマップは「店名＋住所」で検索（座標が地域の中心になっている店があるため）。住所がない店だけ座標
- 存在しないURLは 404.html（検索欄と主要ページへの導線）
- トップ（index.html）だけはリニューアル前のデザイン（写真コラージュ・マスキングテープ・ピンク）。CSSは `_includes/top.css`（旧 style.css からトップで使うルールだけを `.lp` の中に閉じ込めたもの）を head に埋め込む（front matter の inline_css）。「推し活ガイド」の黒いブロックだけ新デザインのまま残している。新着は site_stats.latest / latest_video からページ生成時に書き出す
- トップのコラージュ・カードのグループ写真は assets/images/groups/<id>_480.webp / _120.webp（元の800px JPEGから作成）
- 店舗ページの「この店に行くなら」はリンクがある行だけ出す。「予約する」はホットペッパー・一休など予約できるリンクがあるときだけ（食べログは「食べログで見る」）。PR表記は提携IDが入っているリンクがあるときに自動で出る
- 「泊まる」リンクは じゃらん（検索語は Shift_JIS。build_site_data.py でエンコード）と楽天トラベル。提携後に `_config.yml` の affiliate.valuecommerce.jalan_pid / affiliate.rakuten.id を入れると変換される
- URL は Jekyll が :name を変換したもの（`_` → `-`、`--` → `-`）。リンクは `_data/group_ix.json` の u や shop_cards の u を使い、自分で組み立てない

## 表示速度のルール（PageSpeed Insights スマホ90点以上を維持）
- Webフォントは読み込まない（端末標準フォント。見出しは明朝、本文はゴシック。app.css の --serif / --sans）
- AdSense は使わない（2026-10 に削除。地図・一覧に広告が重なり操作を妨げていたため）
- Leaflet は地図を表示するときに app.js が読み込む（店舗ページは「地図を表示」を押したとき・PCは画面に近づいたとき。/shops/ は地図表示またはPC）
- 一覧はページ生成時に最初の20件を書き出す。/shops/ の絞り込み用データ data/explore.json（約160KB圧縮後）は表示が落ち着いてから読む。shops-lite.json は画面では使っていない
- 特集記事の店数は shop_ids から出す（front matter に shop_count を書かない）。本文に「全○店」などグループ全体の店数を書かない（データが増えると食い違うため）。グループ全体の数が要るときは `{{ site.data.group_ix.<group>.n }}` を使う。グループの記事には、グループ全体の店数と記事の店数を並べた案内（post.html の .livecount）が自動で出る
- 特集記事に値段・営業時間・電話番号を書かない（変わりやすく出典が残らないため）
- 複数グループを扱う記事（ジャンル横断のまとめ）には group を付けない
- 記事内の店舗カードは `{% include inline-shop-card.html shop_id="..." %}` / `{% include inline-shop-grid.html ids="a,b" %}` でページ生成時に描画する
- Google アナリティクスはページ表示完了の1.5秒後に読み込む（head.html）
- ガイドの見出し画像は 600px 版（*_600.webp）を用意して srcset で出し分ける。新しいガイドを追加したら 600px 版も作る
- 描画前にレイアウト計算をさせない（offsetTop / offsetHeight などの読み取りは load 後に）

## 環境変数
```bash
export YOUTUBE_API_KEY="..."   # YouTube Data API v3
export GEMINI_API_KEY="..."    # Gemini API（未取得）
export TMDB_API_KEY="..."      # TMDB API（ドラマ・映画サムネイル取得）登録: https://www.themoviedb.org/settings/api
export HOTPEPPER_API_KEY="..." # ホットペッパーグルメ Webサービス 登録: https://webservice.recruit.co.jp/
```

---

## 現在の状況（2026-10-07時点）
- 総店舗数: 2,328件（42グループ）。店舗ページ 2,360（うち孤立ページ32）・一覧ページ111・グループページ42
- 推し活ガイド50本（/guide/。2026-10-10 に旧型の会場ガイド18本を新しい型へ書き直し。2026-10-09 に新しい型の会場ガイド10本: 東京ドーム・京セラドーム大阪・バンテリンドーム ナゴヤ・みずほPayPayドーム福岡・日本武道館・Kアリーナ横浜・東京ガーデンシアター・ベルーナドーム・幕張メッセ・LaLa arena TOKYO-BAY）・特集記事42本（/articles/）
- 運営者情報 /about/・お問い合わせ /contact/・プライバシーポリシー /privacy/・広告表記 /disclosure/ あり
- 食べログ由来データ（点数・画像・価格帯・営業時間）は削除済み。画像なし店舗 465件（2026-10-09 に fetch_program_thumbnails.py で番組・ドラマのTMDB画像を976件補完。「なにわ男子のどっち派」「なにわ男子のなんでやねん」はめざましテレビ内のコーナー。残りはYouTube企画（match_youtube_videos.py の対象）・MV・SNS投稿などTMDBにない出典）。2026-10-09 に match_youtube_videos.py で43件に youtube_id（残りの確認待ち74件は scripts/youtube_match_review.json）、fetch_hotpepper_photos.py で94件に hotpepper_photo を付与し、画像なし店舗は 421件
- TMDB_API_KEY は v4 の読み取りトークン（eyJ...）。Authorization: Bearer で送る（fetch_program_thumbnails.py は両対応）。TMDBのクレジットは /about/ に記載
- アフィリエイト（2026-10-12〜）: バリューコマースのサイトID 3784026。LinkSwitch（_config.yml の affiliate.valuecommerce.linkswitch_pid）で、食べログ・じゃらん・ホットペッパー・一休へのリンクをクリック時に自動変換。提携済み: 食べログ・一休.comレストラン・じゃらん（2026-10-12 に変換を確認）。ホットペッパーは2026-10-17に提携を断られた（リンクは通常リンク・rel="noopener" で残す。予約ボタンは利用者のため残す）。楽天アフィリエイト（楽天トラベルの「泊まる」）は affiliate.rakuten.id で変換。A8は未設定
- PR表記: 広告リンクのあるページはタイトルのすぐ下に「#アフィリエイト広告 本ページはプロモーションを含みます」（.pr-note--top。ホットペッパー・じゃらんの規約で、ページ上部に分かる大きさで出す）
- 記事の収益動線: 特集記事の front matter に `stay_area: "鎌倉"`（＋`stay_note`）を書くと本文の後に「○○周辺に泊まる」（じゃらん・楽天トラベル）が出る。まとめ記事は `stay_inline: true` を付け、本文の「半日で巡るなら」のあとに `{% include stay-inline.html %}` を置く（コースの出発地の近くの街。stay_note はコースと路線の事実だけ）（じゃらんの Shift_JIS は build_site_data.py が _data/stay_kw.json に作る）。ガイドの商品は `{% include buy-box.html title=… note=… kw="検索語,…" %}`（楽天市場の検索）や `links="表示名|URL;…"`。使った感想・おすすめ順位・値段は書かない。広告リンクを足したガイドは front matter に `pr: true`
- 食べログの報酬は「ネット予約できる店のページ」からの予約だけ（検索結果・エリアページ経由は対象外）。tabelog_verified の店を増やすほど効く

## データ追加の方針（2026-10-12 決定）
- 次にデータを集める順: SixTONESの抜けている回 → WEST.・乃木坂配信中 → 亀梨・しおりの続き → ジュニアCHANNEL。Search Console では「グループ名＋聖地巡礼／ロケ地＋東京／ご飯」で探されている
- timelesz は Sexy Zone 時代（2024年3月以前）の回は載せない。番組のスタジオで料理が出ただけの店は残し、記事では訪問と分けて書く
- 出典が確かめられない店・どの店舗か分からない店（差し入れ・インスタの写真だけ等）は載せない
- グループを広げる範囲（2026-10-12 決定）: アイドルを優先しつつ、芸人・タレントが出るグルメ番組（酒場放浪記・町中華で飲ろうぜ・オモウマい店・せっかくグルメ など。番組ごとに1グループ）も足す。食べ歩き系YouTuber（SUSURU TV. など）は後回し。目標はグループ数・店数とも今の2倍以上

## 週1回の自動更新（2026-10-13〜。.github/workflows/weekly-update.yml）
- 毎週月曜 日本時間5:50ごろ（手動は Actions → Weekly update → Run workflow。dry_run にチェックで書き込みなし）。`scripts/weekly/run.py` が情報源ごとに新しい回の店を候補にし、`scripts/merge_candidates.py`（国土地理院で番地まで一致・同じグループの重複なし・画像あり）を通った店だけ data/shops.json に足す → `build_pages.sh --no-commit` → `check_articles.py --strict`（エラーなら commit しない）→ main に commit・push → 同じワークフローでサイトを作って公開（GITHUB_TOKEN の push では deploy-site.yml が動かないため）。足した店が0件なら commit しない
- 情報源は `scripts/weekly/sources.json`（1情報源＝`scripts/weekly/<adapter>.py`。`collect(cfg, state, log)` が `{"new":[候補], "skipped":[(理由, 名前)], "state":{...}}` を返す）。今あるもの: 町中華で飲ろうぜ（公式XML）・吉田類の酒場放浪記（店ページ番号の続き。未放送ページで止まる）・ぶらり途中下車の旅（articles.js）・食彩の王国（api/shop.json。ジャンルは公式の見出し優先）・オモウマい店（feed/onair-1.json。紹介メニューは ordered_items にしない）・YouTube（乃木坂配信中の「撮影協力」をホットペッパーAPIで1軒に決める）。どこまで読んだかは `scripts/weekly/state.json`（`--init-state` で今の shops.json の最新回から作り直せる）。lookback_days 分は読み直す（足し済みは merge_candidates が重複として外す）
- 情報源を足すとき: 店名と住所が決まった形で載る公式ページだけ。robots.txt を守り1.2秒以上あける（common.fetch）。食べログ・テレビ東京系・名古屋テレビにはアクセスしない。飲食店でないもの（物販・施設・工房）は外す。YouTube の食べ歩きチャンネルは sources.json の youtube の channels に足す（format: name_address＝説明文に「店名：」「住所：」がある／credit_hotpepper。group は先に add_group.py で作る）。手元で `python scripts/weekly/run.py --dry-run [--only <id>]` で確かめる
- secrets（Settings → Secrets and variables → Actions）: `YOUTUBE_API_KEY`・`HOTPEPPER_API_KEY`（TMDB_API_KEY は今は使わない）。キーはログに出さない（common.redact）
- Summary の見方: 表の「候補」＝新しい回で拾った店、「足した」＝shops.json に入った店、「見送り（確認で）」＝merge_candidates が外した店（住所が国土地理院と食い違う・番地まで確かめられない など。理由別の件数と一覧）、「見送り（読んだ段階）」＝飲食店でない・閉店・ホットペッパーで1軒に決まらない など。「登録済みで外した」は前回までに足した店（正常）。状態が「失敗」の情報源はサイトの形が変わった可能性があるので、アダプタを直す

## 載せる店の決まり（2026-10-13 決定）
- 有名人（グループ・番組の出演者）と結びつかない店は載せない。情報番組の特集・リポーターだけの紹介・ナレーションだけの番組（食彩の王国・せやねん！・news every.・よんチャンTV・オモウマい店・あさパラS）は外した（URLは転送ページ）。スイッチ！・シューイチ・news おかえり は出演者の記録がある店だけ
- 食べ歩き系YouTuberは登録者1万人以上
- グループの店は1軒ずつ確かめる（5グループ済み: SixTONES・King & Prince・WEST.・Snow Man・なにわ男子）。外すもの: 差し入れ・ケータリング・取り寄せだけ／他人の話／メンバーが出ていない場面のロケ地／推測だけ／飲食店でない／重複。members は実際に行った・出たメンバーだけ
- 店の種類 `visit_kind`: youtube / own_tv（冠番組）/ guest_tv（出演番組）/ drama（出演ドラマのロケ地）/ magazine / other。`program` に番組・作品名、`with` に一緒にいた人。スタジオに料理が出ただけの店は `studio_only: true`（残すが「行った」とは書かない）。確かめきれない点は `qa_note`。ドラマのロケ地・スタジオの店はページの題名が変わる（generate_shop_pages.py）

## グループのまとめ記事の型（2026-10-13〜）
- 「<グループ>の聖地巡礼・ロケ地まとめ｜<主な出典>で行った東京のご飯ほか<N>軒」。そのグループの店（閉店を除く）を全部 shop_ids に入れる
- 章は 公式YouTube → 冠番組 → 出演した番組 → ドラマのロケ地 → スタジオに料理が出た店 の順。そのあと 年表・ジャンルと場所の図 → はじめて見るなら → エリアで巡る（東京の聖地マップ）→ 地図へ
- お店は「お店の行」（`<ul class="wrs"><li class="wr">{% include wr-open.html id="…" %}<span class="wr__k">年.月</span><b class="wr__name">店名</b><span class="wr__t">回／メンバー／食べた物（場所）</span>{% include wr-close.html id="…" %}</li></ul>`）。写真・押すとお店のページ・「お店の詳細を見る」・予約／食べログのボタン（hotpepper_url と tabelog_verified の店だけ。front matter に pr: true）。同じ店を文字とカードで2回並べない
- 冒頭（ひと目でわかるの前）に「出典で選ぶ」（.cnav。章へのリンクとアイコン {% include chico.html kind="yt|tv|guest|drama|studio|other" %}）と {% include matome-members.html group="…" %}（メンバー別に /shops/ の絞り込みへ）
- 書いた記事は `python scripts/matome_rows.py <slug> --color '<色>'` で上の形にそろう（.pf-works＋grid → .wrs、章の id とアイコン、冒頭の案内、図の章の移動、東京23区のタイル地図 `scripts/ward_tilemap.py`（2026-10-18 に山手線の地図 post_map.py から切り替え）、ジャンルの図 `post_figures.py --only-genre`。何度実行しても同じ）
- グループページの上部に、そのグループのまとめ記事（article_type: matome。URLに gourmet-matome を含むものを優先）へのリンクが出る
- 巡礼帳の見た目（2026-10-13 SixTONES で試作）: front matter `techo: true` と `cover_ids`（写真3枚の店ID）・`cover_title`・`cover_sub` で、表紙（写真をテープで留めたコラージュ＋題の札 `_includes/techo-cover.html`）。本文は `<div class="pf pf--techo">`（見出しにマスキングテープ・付箋の編集部メモ・紙の行）。「ひと目でわかる」の箱と数字の箱は使わず、「はじめての3軒」（`{% include pick.html id=… no="其の一" why="選んだ理由（回・頼んだ物など事実だけ）" %}` を `.picks` に）と「半日で巡るなら」（front matter `courses` → `python scripts/course_stops.py <slug>` で道順のリスト `<ol class="stops">`（番号・店名・場所／メンバー・次への移動と直線距離）。場所は市区町村＋町名まで（丁目のない町があるので丁目・番地は書かない）。移動は確かな事実だけ。2026-10-18 に手描き風のコース図 post_course.py から切り替え）。店の行の写真には訪れた年月の判子（.hanko）。掲載時点・確認元の注記は本文のあと。データの出どころの言い回し（「推しグルメ巡礼MAPのデータより」など）は本文に何度も書かない
- 済み（店の見直し＋全店のまとめ記事＋巡礼帳）: SixTONES・Snow Man・King & Prince・WEST.・なにわ男子・よにの・Hey! Say! JUMP・timelesz・乃木坂46・=LOVE・嵐（新規）・亀梨和也・かまいたち・中丸銀河ちゃんねる・櫻坂46（新規）・日向坂46・KinKi Kids（新規）・Aぇ! group（新規）・≠ME・≒JOY（2026-10-15）。番組: 町中華で飲ろうぜ（2026-10-17）・吉田類の酒場放浪記（2026-10-18。寺・折り紙会館の2件を外した）・人生最高レストラン（2026-10-18。ゲストがトークで紹介した店。`--talk` で行は「#回／○○が紹介」、冒頭に「ゲストで選ぶ」）・ぶらり途中下車の旅（2026-10-18。`--people 旅人` で「旅人で選ぶ」。横尾渉・塚田僚一・伊野尾慧などアイドルの旅人の回あり）。アイドル9グループ（2026-10-18）: HiHi Jets・超特急・Number_i・Travis Japan・Kis-My-Ft2（横尾渉の『ぶらり』23軒ほかをグループにも足した）・関ジャニ∞・BTS・Stray Kids の見直し＋まとめ記事（SMAP は在籍中の店が1軒だけなので記事なし。Number_i の King & Prince 在籍中の放送の店は kingprince へ）。番組の店をアイドルのグループにも足すときは、その日にそのグループのメンバーだったかを確かめる（build_site_data.py の「メンバーで選ぶ」は、グループが主の店に出てくる人だけを数える）。次は 店の少ないグループ（10軒未満）と、番組・YouTuber のグループ
- STARTOの店を増やす（2026-10-18）: 公式YouTubeの説明文には店名がほとんど載らない（超特急・乃木坂配信中は例外）。番組公式で店名と出演者が読めるのは日テレの articles.js（ゴチ・ヒルナンデス！・メシドラ・沸騰ワード10）。TBS・フジ・テレ朝の番組公式は店名が載らないか過去回が残っていない。ゴチの増田貴久で NEWS（news）を作った。ヒルナンデス！は `scripts/weekly/hirunan.py`（コーナーの出演者にSTARTOメンバーがいるコーナーだけ。放送日にグループにいたか期間表で確かめる。住所がないのでホットペッパーAPIで地域の中の1軒に決める。週1回の更新は名前が完全一致（high）だけ。過去分は --backfill で出し、一部一致（mid）は1軒ずつ見直してから merge_candidates）。同じ名前・住所の店がほかのグループにあれば、新しい店にせずグループを付ける
- 2026-10-19: STARTO公式YouTube18チャンネル（約1万5千本）の説明文を全部読んだが、「撮影協力」は施設・観光局だけで飲食店は0軒（この方法は使わない）。木村拓哉の店は公式YouTube「木村さ〜〜ん！」の公開日と登録日が一致したので youtube_id を付けた（【過去回】は撮影がそれより前）。K-POP 10組（kpop-idol-gourmet-matome）・STARTOのジュニア・ユニット（starto-juniors-gourmet-matome）は複数グループの記事（group なし）。V6 は店0軒になったので /groups/v6/ は 20th Century へ転送
- 食べログURLの確認（2026-10-19）: アイドルの店の出典ページ（ファンブログ）で、その店の見出しの区画の中・店名の後にある最初の食べログリンク（ValueCommerce の vc_url などはデコード。食べログ・包んだURLにはアクセスしない）が登録URLと同じなら tabelog_verified（tabelog_source に出典ページ）。564軒中 270軒一致・22軒は1つ前の店のURLを付けていたずれを直した・4軒は別の店のURLだったので外した。食べログのリンクを貼らないサイト（chiicrane・fananablog・jwest など）と、出典ページの記録がない731軒は確かめられない。同じページから、メンバーが頼んだ物（162軒・304品）と座った席（20軒の seating_note）を、本文に書いてあるものだけ足した（ブロガー自身の注文・番組の紹介メニュー・推測は入れない）
- 出典ページの記録がなかったアイドルの店731軒（2026-10-19）: 店ごとにファンのロケ地ブログ・番組公式を探して source_url を付けた（703軒）。同じ方法で食べログURLを照合し338軒一致・34軒を出典ページのURLに直した（支店違いの疑いは直さない）。乃木坂など食べログにリンクしないブログの店は確かめられない（乃木坂の tabelog_url は禁止スクリプトの食べログまとめ由来なので確認済みにしない）。スタジオ試食（嵐にしやがれのデスマッチ・当たり前レストラン）の品は ordered_items に入れない。嵐の取り寄せだけの6軒を外した。アイドルの店 1,890軒中 確認済み食べログ 664・頼んだ物 714・席 62
- まとめ記事のお店の行には `scripts/enrich_rows.py` が「🍴頼んだ物（行の文にない品を最大3つ）」「🪑席」（.wr__more）を書き足す（build_pages.sh で毎回実行。studio_only の店・ほかのグループが主の店には足さない）。食べログのボタンは shop_cards の tb（tabelog_verified の店）から wr-close.html が自動で出す
- 複数グループに入っている店の見直し（scratchpad の apply_qa）では、主グループでないグループの判定で members・説明を上書きしない（メンバーを足すだけ）。店のデータの visited_date・回は主グループのもの（ほかのグループの回の日付は記事・年表で手で書く）
- 見直しの手順: 店ごとの判定を JSON にまとめてから data/shops.json に反映する（RULES.md 相当: 残す・外す・members・visit_kind・program・with・description・qa_note・studio_only）。外す店はURLを転送ページに。ほかのグループにも入っている店は、そのグループから外すだけにして店は消さない
- アフィリエイト動線のQA（2026-10-16）: 食べログ店ページ・じゃらん・一休は LinkSwitch で変換されることを本番で確認。ホットペッパーは提携を断られた（2026-10-17。広告扱いをやめた）。ホットペッパーAPIでのリンクは2026-10-16に1,311軒へ。まとめ記事の食べログボタンは tabelog_verified の店だけなのでほぼ無い（アイドルの店の未確認URL 1,593軒が課題）
- 番組グループのまとめ記事（2026-10-17 町中華で飲ろうぜ から）: 出典が1つなので章は地域ごと（東京23区を4つに分けて区ごと → 東京の市部 → 神奈川・埼玉・千葉 → そのほか）。冒頭の「エリアで選ぶ」・行・shop_ids は `python scripts/program_matome_rows.py <slug> <group> --prefix '<番組名>'` が作る（本文の <!-- nav:start/end --> と <!-- rows:start/end --> を書き換え。何度実行しても同じ）。23区の外の「そのほか」が60軒を超えると地方→都道府県ごとに分け、全店で出演者が同じ（吉田類など）なら行に出演者を書かない。放送回の「店名」は行から外す。店が数百軒あるので、区・地域ごとに閉じた <details data-lazy> に店のデータ（JSON）を入れ、開いたときに app.js が写真なしの行（.wr__link--lite）を作る。店名だけは本文に並べる（.wrd__names）。はじめての3軒・半日コース・編集部メモ・FAQ は手で書く（番組公式のデータにある事実だけ）。場所の図は山手線の地図ではなく東京23区のタイル地図（`python scripts/ward_tilemap.py <slug> --color … --title …` → wards.svg。1区＝1マス＋23区の外の棒）。半日コースは手描き風の図ではなく `<ol class="stops">`（番号・店名・場所／出演者・次までの直線距離）。表紙・はじめての3軒は店の写真（hotpepper_photo など）がある店から選ぶ（番組ポスターしかない店は看板風になる）
- 店の多い記事でも速さを保つため、.hscroll と .pf-works は content-visibility: auto（画面に近づいてから描く）

## 過去の状況（2026-05-26時点）
- 総店舗数: 820件（kodoku_no_gurume:176 / equal_love:117 / yonino:97 / nogizaka46:79 / snowman:59 / sixtones:49 / heysayjump:48 / notme:39 / kingprince:22 / kamenashi:32 / shiori:29 / neajoy:25 / ginga:12 / naniwa:10 / kamaitachi:10 / hinatazaka46:7 / timelesz:6 / sakurazaka46:3）
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
- King & Prince（当たり前レストラン）: tsuzuki-fam.comスクレイピング。リンクがValueCommerce経由（vc_urlパラメータをdecodeするとtabelog URL取得可能）。住所なし店舗はtabelog JSON-LDで補完。8エピソード（2022-08-13〜2023-05-20）から22件。0903分（4件）はリンクも住所もなく取得不可。

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
