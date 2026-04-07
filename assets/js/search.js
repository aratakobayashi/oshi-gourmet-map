/**
 * search.js
 * 記事ページ内の関連店舗カード埋め込み用
 * （メインのフィルター処理は main.js に集約済み）
 */

// 記事ページで呼ばれる関連店舗カードの埋め込み
// post.html の <script> から buildShopCard() を呼ぶため、
// このファイルは main.js より先に読み込まれることを想定しない。
// buildShopCard は main.js で定義済み。
