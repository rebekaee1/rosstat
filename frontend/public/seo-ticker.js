/*
 * Бегущая строка курсов для чистых SSR-страниц (годовые страницы, 404): они отдаются без React-бандла,
 * поэтому приложение со своей лентой здесь не загружается. Тот же источник данных и тот же набор курсов,
 * что у приложения (`/api/v1/ticker/live`, `components/LiveTicker.jsx`); разметка и стили ленты — в
 * `seo_renderer.py` (`.seo-ticker`). Файл не хэшируется Vite, поэтому nginx отдаёт его с no-cache.
 * Любой сбой (сеть, 429, пустой ответ) оставляет строку скрытой: страница остаётся рабочей без неё.
 */
(function () {
  'use strict';
  var root = document.getElementById('seo-ticker');
  if (!root || !window.fetch) return;

  var en = (document.documentElement.lang || 'ru').slice(0, 2) === 'en';
  var lane = root.getAttribute('data-lane') || 'world';

  var META = {
    'usd-rub-live': { l: 'USD/RUB', p: 'usd-rub', d: 2 },
    'eur-rub-live': { l: 'EUR/RUB', p: 'eur-rub', d: 2 },
    'cny-rub-live': { l: 'CNY/RUB', p: 'cny-rub', d: 2 },
    'eur-usd': { l: 'EUR/USD', p: 'eur-usd', d: 2 },
    'gbp-usd': { l: 'GBP/USD', p: 'gbp-usd', d: 2 },
    'usd-cny': { l: 'USD/CNY', p: 'usd-cny', d: 2 },
    'btc-usd': { l: 'BTC/USD', p: 'btc-usd', d: 0 },
    'brent': { l: 'Brent', p: 'brent', d: 2 },
    'gold-rub-live': { l: en ? 'Gold ₽/g' : 'Золото ₽/г', p: 'gold-price', d: 0 }
  };
  var SRC = en ? { market: 'exchange', cb: 'central bank' } : { market: 'биржа', cb: 'ЦБ' };
  var tag = en ? 'en-US' : 'ru-RU';

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function num(v, d) {
    return v.toLocaleString(tag, { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function srcKind(s) {
    s = String(s || '');
    if (/moex|мосбирж/i.test(s)) return 'market';
    if (/cbr|банк россии|цб/i.test(s)) return 'cb';
    return null;
  }

  function cell(s) {
    var m = META[s.code];
    if (!m || !(s.price > 0)) return '';
    var html = '<span class="seo-tk-l">' + esc(m.l) + '</span><b class="seo-tk-v">' + esc(num(s.price, m.d)) + '</b>';
    var kind = srcKind(s.source);
    if (kind) html += '<span class="seo-tk-s">' + esc(SRC[kind]) + '</span>';
    var pct = s.change_pct;
    if (typeof pct === 'number' && Math.abs(pct) >= 0.005) {
      var up = pct > 0;
      var body = (up ? '+' : '−') + num(Math.abs(pct), 2) + '%';
      html += '<span class="seo-tk-d ' + (up ? 'seo-tk-up' : 'seo-tk-down') + '"><i aria-hidden="true">' +
        (up ? '↗' : '↘') + '</i>' + esc(body) + '</span>';
    }
    return '<a class="seo-tk" href="/russia/indicator/' + m.p + '">' + html + '</a>';
  }

  function render(data) {
    var rows = (data && data.snapshots) || [];
    var items = rows.map(cell).filter(Boolean).join('');
    if (!items) return;
    // Две одинаковые половины дают бесшовную петлю: анимация сдвигает дорожку ровно на половину.
    root.innerHTML = '<div class="seo-tk-view"><div class="seo-tk-track">' +
      '<div class="seo-tk-set">' + items + '</div>' +
      '<div class="seo-tk-set" aria-hidden="true">' + items.replace(/<a /g, '<a tabindex="-1" ') + '</div></div></div>';
    root.hidden = false;
    var track = root.firstChild.firstChild;
    var half = track.firstChild.getBoundingClientRect().width;
    // Скорость примерно 40 px/с: читаемо, но не отвлекает.
    if (half > 0) track.style.setProperty('--seo-tk-run', Math.max(20, Math.round(half / 40)) + 's');
  }

  fetch('/api/v1/ticker/live?lane=' + encodeURIComponent(lane), { cache: 'no-store', credentials: 'same-origin' })
    .then(function (r) { if (!r.ok) throw new Error('ticker ' + r.status); return r.json(); })
    .then(render)
    .catch(function () { /* строка остаётся скрытой */ });
})();
