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
| `migrate_guidebook.py` | 旧 推し活ガイドブック（oshikatsu-guide.com）の記事を _guides/ へ移行。301用の対応表を redirects/ に出力 |

**食べログにアクセスするため使用禁止のスクリプト**（削除予定）: `fetch_tabelog_thumbnails.py` `retry_arashi_thumbnails.py` `scrape_tabelog_details.py` `check_closed_shops.py` `scrape_tabelog_matome.py` `geocode_missing.py` `geocode_shiori.py`。`scrape_arashi.py` `scrape_kinpri.py` `pipeline_naniwa.py` `pipeline_timelesz.py` の食べログ取得関数は無効化済み。

---

## 推し活ガイド（/guide/）
- 旧 推し活ガイドブック（WordPress）の記事41本を `_guides/` コレクションに移行（2026-10）。レイアウトは `_layouts/guide.html`
- カテゴリ: `_data/guide_categories.json`（venue / travel / basics / profile）
- 会場ガイドの「会場周辺の聖地グルメ」は `_data/venues.json` の座標から build_site_data.py が近い順に計算（_data/venue_nearby.json）し、ページ生成時に表示
- 旧URL→新URLの対応表: `redirects/guidebook_redirects.csv`（旧サイト側で301を設定する）

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
- 推し活ガイド41本（/guide/）・特集記事42本（/articles/）
- 運営者情報 /about/・お問い合わせ /contact/・プライバシーポリシー /privacy/・広告表記 /disclosure/ あり
- 食べログ由来データ（点数・画像・価格帯・営業時間）は削除済み。画像なし店舗 465件（2026-10-09 に fetch_program_thumbnails.py で番組・ドラマのTMDB画像を976件補完。「なにわ男子のどっち派」「なにわ男子のなんでやねん」はめざましテレビ内のコーナー。残りはYouTube企画（match_youtube_videos.py の対象）・MV・SNS投稿などTMDBにない出典）。2026-10-09 に match_youtube_videos.py で43件に youtube_id（残りの確認待ち74件は scripts/youtube_match_review.json）、fetch_hotpepper_photos.py で94件に hotpepper_photo を付与し、画像なし店舗は 421件
- TMDB_API_KEY は v4 の読み取りトークン（eyJ...）。Authorization: Bearer で送る（fetch_program_thumbnails.py は両対応）。TMDBのクレジットは /about/ に記載
- アフィリエイトは仕組みのみ導入済み（_config.yml の affiliate に sid/pid を入れると有効化）

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
