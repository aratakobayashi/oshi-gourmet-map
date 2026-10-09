/* グループページ・グループ×ジャンル一覧: その場での並び替え・メンバー絞り込み・もっと見る。
   最初の一覧はHTMLにある。操作されたときに data/explore.json を読む */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';
  var root = document.querySelector('[data-listpage]');
  if (!root || !window.shopUI) return;
  var ui = window.shopUI, I = ui.I;
  var group = root.dataset.group, genre = root.dataset.genre || '';
  var rowsEl = root.querySelector('[data-rows]'), moreBtn = root.querySelector('[data-more]');
  var countEl = root.querySelector('[data-count]'), sortEl = root.querySelector('[data-sort]');
  var mapLink = root.querySelector('[data-maplink]');
  var mapBase = mapLink ? mapLink.getAttribute('href') : '';
  var PAGE = rowsEl.children.length || 24;
  var state = { member: '', sort: 'new', shown: PAGE }, list = null;

  function compute(data) {
    list = ui.sort(data.filter(function (r) {
      if (r[I.gr].indexOf(group) < 0) return false;
      if (genre && r[I.g] !== genre) return false;
      if (state.member && r[I.m].indexOf(state.member) < 0) return false;
      return true;
    }), state.sort);
  }
  function draw() {
    rowsEl.innerHTML = list.slice(0, state.shown).map(ui.row).join('') || '<p class="empty">お店が見つかりませんでした。</p>';
    if (countEl) countEl.textContent = list.length;
    if (moreBtn) {
      moreBtn.hidden = list.length <= state.shown;
      moreBtn.textContent = 'さらに表示（' + Math.min(state.shown, list.length) + ' / ' + list.length + '）';
    }
    if (mapLink) {
      mapLink.href = mapBase + (state.member ? '&m=' + encodeURIComponent(group + ':' + state.member) : '');
      mapLink.textContent = list.length + '軒を地図で見る';
    }
    window.paintFavs(rowsEl);
  }
  function update() { ui.load().then(function (data) { compute(data); draw(); }); }

  if (sortEl) sortEl.addEventListener('change', function () { state.sort = sortEl.value; state.shown = PAGE; update(); });
  if (moreBtn) moreBtn.addEventListener('click', function () { state.shown += PAGE; update(); });
  document.querySelectorAll('[data-member]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      state.member = a.dataset.member; state.shown = PAGE;
      document.querySelectorAll('[data-member]').forEach(function (x) { x.classList.toggle('chip--on', x === a); });
      update();
      var top = root.getBoundingClientRect().top;
      if (top < 0 || top > innerHeight) root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
});
