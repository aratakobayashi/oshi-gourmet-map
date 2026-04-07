/**
 * map.js
 * Leaflet.js を使った地図表示
 */

let leafletMap = null;
let markers = [];

function initMap() {
  if (leafletMap) return; // 二重初期化防止

  leafletMap = L.map('map').setView([36.5, 136.0], 5);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(leafletMap);
}

function renderMapMarkers(shops) {
  if (!leafletMap) return;

  // 既存マーカーを削除
  markers.forEach(m => leafletMap.removeLayer(m));
  markers = [];

  shops.forEach(shop => {
    if (!shop.lat || !shop.lng) return;

    const marker = L.marker([shop.lat, shop.lng]).addTo(leafletMap);

    const thumb = shop.youtube_id
      ? `<img src="https://img.youtube.com/vi/${shop.youtube_id}/mqdefault.jpg"
            style="width:100%;border-radius:6px;margin-bottom:6px;" loading="lazy">`
      : '';

    marker.bindPopup(`
      <div class="map-popup">
        ${thumb}
        <h3>${escHtml(shop.name)}</h3>
        <p>${escHtml(shop.prefecture || '')} ${escHtml(shop.genre || '')}</p>
        <p style="margin-top:4px;">
          <a href="javascript:void(0)" onclick="closePopupAndOpenModal('${escHtml(shop.id)}')">詳細を見る →</a>
        </p>
      </div>
    `);

    markers.push(marker);
  });

  // 表示範囲をマーカーに合わせる（マーカーがある場合）
  if (markers.length > 0) {
    const group = L.featureGroup(markers);
    leafletMap.fitBounds(group.getBounds().pad(0.1));
  }
}

function closePopupAndOpenModal(shopId) {
  leafletMap.closePopup();
  openModal(shopId);
}

// escHtml が main.js より先に読まれる場合のフォールバック
if (typeof escHtml === 'undefined') {
  function escHtml(str) {
    if (str == null) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
}
