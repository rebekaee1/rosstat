/**
 * Consent-bootstrap — единственная точка загрузки Яндекс.Метрики и РСЯ.
 *
 * Модель согласия (152-ФЗ, подразумеваемое согласие): продолжая пользоваться
 * сайтом, посетитель соглашается на cookie. По умолчанию трекеры (Метрика +
 * РСЯ) грузятся сразу — баннер CookieConsent.jsx лишь информирует. Явный
 * отказ текущей редакции политики (analytics/ads=false при v==CURRENT_V)
 * уважаем: трекеры не грузим. Запись хранится в localStorage (`fe:consent:v1`).
 * CURRENT_V обязан совпадать с CONSENT_VERSION в frontend/src/lib/consent.js.
 *
 * Файл подключается одинаково из двух мест (single source of truth):
 *   - frontend/index.html (SPA shell)
 *   - backend/app/services/seo_renderer.py (SSR-страницы, ADR-0003)
 * Раздаётся nginx как /consent.js с no-cache (см. frontend/nginx.conf) —
 * иначе stale-версия пережила бы релиз.
 *
 * Внутри сохранена логика очистки URL от служебных меток (ybaip/etext/...):
 * defer:true отключает автоматический первый hit Метрики, вручную шлём
 * очищенный URL — «Страницы входа» не дублируются. utm_* НЕ удаляем — они
 * нужны Метрике для атрибуции source/medium/campaign.
 */
(function () {
  var KEY = 'fe:consent:v1';
  var CURRENT_V = '2026-06-16';
  var COUNTER = 107136069;

  // --- URL hygiene: выполняется всегда, до любых хитов ---
  var TRACKING = ['etext', 'ybaip', 'yclid', 'ysclid', 'gclid', 'fbclid', '_openstat', 'openstat', 'clid', 'yandex_referrer', '_ga', 'utm_referrer', 'from', 'ref', 'ref_src', 'source', 'mc_cid', 'mc_eid', 'igshid'];
  var search = window.location.search;
  var cleanedSearch = search;
  if (search && search.length > 1) {
    var params = new URLSearchParams(search);
    var changed = false;
    for (var i = 0; i < TRACKING.length; i++) {
      if (params.has(TRACKING[i])) { params.delete(TRACKING[i]); changed = true; }
    }
    if (changed) {
      var rest = params.toString();
      cleanedSearch = rest ? '?' + rest : '';
    }
  }
  var cleanPath = window.location.pathname + cleanedSearch + window.location.hash;
  if (cleanedSearch !== search && typeof history !== 'undefined' && typeof history.replaceState === 'function') {
    try { history.replaceState(history.state, '', cleanPath); } catch { /* ignore */ }
  }

  var loaded = { analytics: false, ads: false };

  function loadMetrika() {
    if (loaded.analytics) return;
    loaded.analytics = true;
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (var j = 0; j < document.scripts.length; j++) { if (document.scripts[j].src === r) { return; } }
      k = e.createElement(t); a = e.getElementsByTagName(t)[0]; k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
    })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js?id=' + COUNTER, 'ym');
    // Webvisor 2 + form analytics: triggerEvent — JS-события в Webvisor;
    // childIframe — записи внутри embed-виджета; trackHash — deeplink-якоря.
    window.ym(COUNTER, 'init', {
      defer: true,
      webvisor: true,
      clickmap: true,
      accurateTrackBounce: true,
      trackLinks: true,
      trackHash: true,
      triggerEvent: true,
      childIframe: true
    });
    window.ym(COUNTER, 'hit', cleanPath, { title: document.title, referer: document.referrer });
  }

  function loadAds() {
    if (loaded.ads) return;
    loaded.ads = true;
    // Очередь yaContextCb наполняется компонентом YandexRSY.jsx независимо
    // от согласия; context.js при загрузке разбирает её и рендерит блоки.
    window.yaContextCb = window.yaContextCb || [];
    var s = document.createElement('script');
    s.src = 'https://yandex.ru/ads/system/context.js';
    s.async = true;
    document.head.appendChild(s);
  }

  window.__feApplyConsent = function (consent) {
    if (!consent) return;
    if (consent.analytics) loadMetrika();
    if (consent.ads) loadAds();
  };

  // Подразумеваемое согласие: грузим трекеры по умолчанию. Уважаем только
  // явный отказ в рамках ТЕКУЩЕЙ редакции политики (rec.v === CURRENT_V).
  var IMPLIED = { analytics: true, ads: true };
  var rec = null;
  try {
    var raw = window.localStorage.getItem(KEY);
    if (raw) rec = JSON.parse(raw);
  } catch { rec = null; }
  try {
    window.__feApplyConsent(rec && rec.v === CURRENT_V ? rec : IMPLIED);
  } catch { window.__feApplyConsent(IMPLIED); }
})();
