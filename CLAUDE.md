# 推しグルメ巡礼MAP - プロジェクト定義書

## サイト概要
- **サイト名**: 推しグルメ巡礼MAP
- **URL**: https://gourmet.oshikatsu-guide.com
- **目的**: 推しが訪れたグルメスポットを地図で探せる聖地巡礼ガイド
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
- **youtube_idが確認できない店舗は登録しない**
- 1本の動画に複数店舗が登場する場合はそれぞれ別エントリ
- 住所は番地まで取得する（エリア名だけはNG）

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
  ]
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
| equal_love | イコラブ（=LOVE） | 未確認 | - |
| nogizaka46 | 乃木坂46 | 未確認 | - |
| hinatazaka46 | 日向坂46 | 未確認 | - |
| sakurazaka46 | 櫻坂46 | 未確認 | - |

### グループカラー（main.js）
```javascript
yonino:       '#e8537a'  // ピンク
snowman:      '#3b82f6'  // ブルー
sixtones:     '#7c3aed'  // パープル
equal_love:   '#f43f5e'  // レッド
sakurazaka46: '#e11d48'  // 深紅
nogizaka46:   '#0ea5e9'  // 水色
hinatazaka46: '#f59e0b'  // アンバー
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
| `merge_shops.py` | 新規JSONをshops.jsonにマージ（バリデーション含む）※未作成 |
| `geocode_shops.py` | 座標なし店舗のジオコーディング ※未作成 |
| `add_affiliate_links.py` | アフィリエイトURL自動付与 ※未作成 |

---

## 環境変数
```bash
export YOUTUBE_API_KEY="..."   # YouTube Data API v3
export GEMINI_API_KEY="..."    # Gemini API（未取得）
```

---

## 現在の状況
- 総店舗数: 176件
- サムネあり: 120件（68%）
- デプロイ: GitHub Pages + 独自ドメイン済み
- 記事: 5件（よにのちゃんねる）

## ロードマップ
1. ✅ MVP作成・デプロイ
2. ✅ 独自ドメイン設定（gourmet.oshikatsu-guide.com）
3. 🔄 データ収集パイプライン構築
4. ⬜ Gemini API連携・自動化
5. ⬜ アフィリエイトリンク設置
6. ⬜ Google Search Console登録
7. ⬜ データ3000件達成
