/**
 * favorites.js
 * お気に入り一覧ページ用
 * buildShopCard / restoreFavButtons / toggleFav は main.js で定義済み
 */
document.addEventListener('DOMContentLoaded', async () => {
  const grid     = document.getElementById('fav-grid');
  const countEl  = document.getElementById('fav-count');
  const clearBtn = document.getElementById('fav-clear-btn');
  if (!grid) return;

  const base = typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '';
  const SHOPS_URL = base + '/data/shops-lite.json';
  let allShops = [];

  async function init() {
    try {
      const res = await fetch(SHOPS_URL);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      allShops = await res.json();
    } catch {
      grid.innerHTML = '<p style="text-align:center;padding:2rem;color:#6b7280">データの読み込みに失敗しました。ページを再読み込みしてください。</p>';
      return;
    }
    render();
  }

  function render() {
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem('fav_shops') || '[]'); } catch {}
    const favShops = saved.map(id => allShops.find(s => s.id === id)).filter(Boolean);

    if (countEl) countEl.textContent = favShops.length + '件';
    if (clearBtn) clearBtn.style.display = favShops.length > 0 ? '' : 'none';

    if (favShops.length === 0) {
      grid.innerHTML = `
        <div class="fav-empty">
          <p class="fav-empty__icon">♡</p>
          <p class="fav-empty__text">まだ保存されたお店がありません</p>
          <a href="${base}/shops/" class="fav-empty__link">お店を探す →</a>
        </div>`;
      return;
    }

    grid.innerHTML = favShops.map(s => buildShopCard(s)).join('');
    restoreFavButtons();
  }

  await init();

  // ♡ ボタンで unsave したらカードを消す
  grid.addEventListener('click', e => {
    if (e.target.closest('.shop-card__fav')) {
      setTimeout(render, 0);
    }
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (!confirm('お気に入りをすべて削除しますか？')) return;
      try { localStorage.removeItem('fav_shops'); } catch {}
      render();
    });
  }
});
