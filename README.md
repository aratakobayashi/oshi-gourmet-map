# 推しグルメ巡礼MAP

推しが訪れたグルメスポットを地図で巡礼できるサイト。

## 技術スタック

- **ホスティング**: GitHub Pages
- **静的サイト生成**: Jekyll
- **地図**: Leaflet.js + OpenStreetMap
- **データ**: `data/shops.json`（バックエンドなし）

## ローカル開発

```bash
bundle install
bundle exec jekyll serve
# → http://localhost:4000
```

## お店データの追加

`data/shops.json` に以下の形式で追加するだけ。

```json
{
  "id": "shop-xxx",           // 一意のID（kebab-case推奨）
  "name": "お店名",
  "genre": "ラーメン",        // ジャンル
  "prefecture": "東京都",
  "city": "渋谷区",
  "address": "東京都渋谷区...",
  "lat": 35.6595,             // 緯度（Google Mapsで取得）
  "lng": 139.6980,            // 経度
  "youtube_id": "XXXXXXXXXXX", // YouTubeの動画ID
  "members": ["メンバー名"],
  "groups": ["グループ名"],
  "visited_date": "2026-01-01",
  "description": "お店の説明",
  "tags": ["タグ1", "タグ2"],
  "affiliate_links": [
    { "label": "食べログで見る", "url": "https://..." },
    { "label": "Googleマップ", "url": "https://..." }
  ]
}
```

## 記事の追加

`_posts/YYYY-MM-DD-slug.md` を作成してpushするだけ。

```markdown
---
layout: post
title: "記事タイトル"
date: 2026-01-01
prefecture: 東京都
genre: ラーメン
thumbnail: https://img.youtube.com/vi/XXXX/maxresdefault.jpg
shop_ids:
  - shop-001   # 関連店舗ID（複数可）
description: SEO用メタディスクリプション
---

本文をMarkdownで記述...
```

## GitHub Pages へのデプロイ

1. GitHubにリポジトリを作成
2. Settings → Pages → Branch: `main` / folder: `/ (root)` に設定
3. `git push` するだけで自動ビルド＆デプロイ

`_config.yml` の `url` と `baseurl` をリポジトリに合わせて変更してください。

```yaml
url: "https://your-username.github.io"
baseurl: "/your-repo-name"
```
