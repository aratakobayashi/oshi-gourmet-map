/**
 * map.js
 * Leaflet.js + MarkerCluster による地図表示
 */

let leafletMap = null;
let clusterGroup = null;
let _mapBoundsSet = false; // fitBounds は初回のみ

function initMap() {
  if (leafletMap) return;

  leafletMap = L.map('map').setView([36.5, 136.0], 5);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(leafletMap);

  clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
  });
  leafletMap.addLayer(clusterGroup);
}

function makeGroupIcon(group, solidColor) {
  const color = solidColor || '#b72a65';
  const initial = (typeof GROUP_INITIALS !== 'undefined' && GROUP_INITIALS[group])
    || (typeof GROUP_LABELS !== 'undefined' && GROUP_LABELS[group]
        ? GROUP_LABELS[group].charAt(0)
        : '?');
  const html = `
    <div style="
      background:${color};
      width:28px;height:28px;border-radius:50%;
      border:2px solid #fff;
      box-shadow:0 2px 6px rgba(0,0,0,0.3);
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-size:10px;font-weight:700;
      font-family:'Hiragino Kaku Gothic ProN',sans-serif;
      line-height:1;
    ">${escHtml(String(initial))}</div>`;
  return L.divIcon({
    html,
    className: '',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -16],
  });
}

function renderMapMarkers(shops) {
  if (!leafletMap || !clusterGroup) return;

  clusterGroup.clearLayers();

  const base = typeof SITE_BASEURL !== 'undefined' ? SITE_BASEURL : '';

  shops.forEach(shop => {
    if (!shop.lat || !shop.lng) return;

    const group      = (shop.groups || [])[0] || shop.group || '';
    const solidColor = (typeof GROUP_SOLID_COLORS !== 'undefined' && GROUP_SOLID_COLORS[group]) || '#b72a65';
    const groupLabel = (typeof GROUP_LABELS !== 'undefined' && GROUP_LABELS[group]) || group;

    const icon   = makeGroupIcon(group, solidColor);
    const marker = L.marker([shop.lat, shop.lng], { icon });

    const thumbSrc = shop.youtube_id
      ? `https://img.youtube.com/vi/${shop.youtube_id}/mqdefault.jpg`
      : shop.thumbnail_url || '';
    const thumb = thumbSrc
      ? `<img src="${thumbSrc}" style="width:100%;border-radius:6px;margin-bottom:6px;" loading="eager">`
      : '';

    const shopSlug  = shop.id.replace(/_/g, '-').replace(/-+$/g, '');
    const detailUrl = base + '/shops/' + shopSlug + '/';

    const memberHtml = (shop.members && shop.members.length)
      ? `<p style="font-size:0.78rem;color:#6b7280;margin:2px 0">👤 ${escHtml(shop.members[0])}</p>` : '';
    const stationHtml = shop.nearest_station
      ? `<p style="font-size:0.78rem;color:#6b7280;margin:2px 0">🚉 ${escHtml(shop.nearest_station)}</p>` : '';
    const visitedHtml = shop.visited_date
      ? `<p style="font-size:0.78rem;color:#9ca3af;margin:2px 0">📅 ${formatVisitedMap(shop.visited_date)}</p>` : '';

    const groupBadge = groupLabel
      ? `<span style="font-size:0.72rem;font-weight:700;color:${solidColor};margin-bottom:4px;display:block">${escHtml(groupLabel)}</span>` : '';

    marker.bindPopup(`
      <div class="map-popup">
        ${thumb}
        ${groupBadge}
        <h3>${escHtml(shop.name)}</h3>
        ${memberHtml}
        ${stationHtml}
        ${visitedHtml}
        <p style="margin-top:6px;">
          <a href="${detailUrl}">詳細を見る →</a>
        </p>
      </div>
    `, { maxWidth: 220 });

    clusterGroup.addLayer(marker);
  });

  // fitBounds は初回のみ（以降はユーザーのズーム操作を尊重）
  if (!_mapBoundsSet && clusterGroup.getLayers().length > 0) {
    if (shops.length > 300) {
      // 全件表示のときは東京中心にズーム（fitBoundsすると日本全土になり広すぎる）
      leafletMap.setView([35.68, 139.76], 10);
    } else {
      leafletMap.fitBounds(clusterGroup.getBounds().pad(0.15));
    }
    _mapBoundsSet = true;
  }
}

// 地図を現在地にセンタリング
function centerMapOnUser(lat, lng) {
  if (!leafletMap) return;
  leafletMap.setView([lat, lng], 13);
}

// fitBounds リセット（グループ切り替え等で再フィット）
function resetMapBounds() {
  _mapBoundsSet = false;
}

function formatVisitedMap(dateStr) {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length < 2 || !parts[1]) return parts[0] || dateStr;
  return `${parts[0]}年${parseInt(parts[1])}月`;
}

// escHtml が main.js より先に読まれる場合のフォールバック
if (typeof escHtml === 'undefined') {
  function escHtml(str) {
    if (str == null) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
}
