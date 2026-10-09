#!/bin/bash
# build_pages.sh
# データ更新後に実行するページ生成パイプライン
#
# 使い方:
#   bash scripts/build_pages.sh
#   bash scripts/build_pages.sh --push   # git pushまで自動実行

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "=== ① お店個別ページ生成 ==="
python scripts/generate_shop_pages.py

echo ""
echo "=== ② グループ×ジャンル一覧ページ生成 ==="
python scripts/generate_list_pages.py

echo ""
echo "=== ③ 一覧・近くの店・検索用データ生成（_data/*.json と data/explore.json） ==="
python scripts/build_site_data.py

echo ""
echo "=== ③' 特集記事の店舗IDの確認（shops.json にないIDがあれば表示。直すときは --fix） ==="
python scripts/check_articles.py

echo ""
echo "=== ④ git add ==="
git add _shop_pages/ _list_pages/ _data/ data/explore.json

# 変更がある場合のみコミット
if git diff --cached --quiet; then
  echo "変更なし。コミットをスキップします。"
else
  echo ""
  echo "=== ⑤ git commit ==="
  git commit -m "build: ページ自動生成（shop_pages + list_pages）

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

  if [[ "$1" == "--push" ]]; then
    echo ""
    echo "=== ⑥ git push ==="
    git push
    echo ""
    echo "✓ 完了: ビルド＆プッシュしました"
  else
    echo ""
    echo "✓ 完了: コミットしました（pushはまだです）"
    echo "  push するには: git push"
  fi
fi
