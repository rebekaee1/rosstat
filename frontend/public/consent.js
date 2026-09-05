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
 * Асимметрия Метрика/РСЯ (инцидент fill-rate 2026-08-27, см. `armAdsGate`):
 * Метрика грузится всем — она сама отсекает роботов, и нам нужна полная
 * картина трафика. Запрос объявления РСЯ делаем только за доверенным вводом
 * человека: робот, попросивший рекламу, портит fill rate и оценку качества
 * площадки.
 *
 * Файл подключается одинаково из двух мест (single source of truth):
 *   - frontend/index.html (SPA shell)
 *   - backend/app/services/seo_renderer.py (SSR-страницы, ADR-0003)
 * Раздаётся nginx как /consent.js с no-cache (см. frontend/nginx.conf) —
 * иначе stale-версия пережила бы релиз.
 *
 * Первый hit — с ysclid/yclid/utm_referrer и внешним referer. Иначе после
 * 307 apex→ru. Метрика видит внутренний переход (document.referrer = свой
 * хост), а поисковые фразы в Вебвизоре остаются. После hit — replaceState
 * без меток, чтобы «Страницы входа» не размножались. utm_source/medium
 * в адресной строке не трогаем до hit.
 */
(function () {
  var KEY = 'fe:consent:v1';
  var CURRENT_V = '2026-06-16';
  var COUNTER = 107136069;

  // --- URL hygiene: выполняется всегда, до любых хитов ---
  var STRIP_ALWAYS = ['etext', 'ybaip', '_openstat', 'openstat', 'clid', 'yandex_referrer', '_ga', 'from', 'ref', 'ref_src', 'source', 'mc_cid', 'mc_eid', 'igshid'];
  var ATTRIBUTION = ['yclid', 'ysclid', 'gclid', 'fbclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_referrer'];
  // Часть «меток» совпадает с рабочими параметрами страниц: у калькуляторов
  // from/to — это годы периода. Вырезать их — значит ломать любую
  // расшаренную ссылку, поэтому на таких путях они неприкосновенны.
  var FUNCTIONAL_PARAMS = [
    { prefix: '/calculator', keep: ['from', 'to'] },
  ];
  function stripParams(search, names) {
    if (!search || search.length <= 1) return search || '';
    var path = window.location.pathname;
    var keep = [];
    for (var f = 0; f < FUNCTIONAL_PARAMS.length; f++) {
      if (path.indexOf(FUNCTIONAL_PARAMS[f].prefix) === 0) {
        keep = keep.concat(FUNCTIONAL_PARAMS[f].keep);
      }
    }
    var params = new URLSearchParams(search);
    var changed = false;
    for (var i = 0; i < names.length; i++) {
      if (keep.indexOf(names[i]) !== -1) continue;
      if (params.has(names[i])) { params.delete(names[i]); changed = true; }
    }
    if (!changed) return search;
    var rest = params.toString();
    return rest ? '?' + rest : '';
  }

  var search = window.location.search;
  var hitSearch = stripParams(search, STRIP_ALWAYS);
  var displaySearch = stripParams(hitSearch, ATTRIBUTION);
  var hitPath = window.location.pathname + hitSearch + window.location.hash;
  var cleanPath = window.location.pathname + displaySearch + window.location.hash;

  function firstReferer() {
    var stamped = '';
    try { stamped = new URLSearchParams(search).get('utm_referrer') || ''; } catch (e) { stamped = ''; }
    var ref = document.referrer || '';
    try {
      var host = (location.hostname || '').replace(/^www\./, '');
      var apex = host.replace(/^ru\./, '');
      if (ref) {
        var rh = new URL(ref).hostname.replace(/^www\./, '');
        if (rh === host || rh === apex || rh === 'ru.' + apex) ref = stamped;
      } else {
        ref = stamped;
      }
    } catch (e) {
      if (!ref) ref = stamped;
    }
    return ref;
  }

  var loaded = { analytics: false, ads: false };

  // --- Гейт рекламы: запрос объявления только за живого человека ---
  //
  // Инцидент 2026-08-27..09-03 (данные Партнёрки): запросы рекламы выросли
  // 220 → 4291/день, показы остались ~150–250, fill 97% → 11,5%. Разбивка по
  // гео/браузеру: «Москва» с fill 21% — это YandexBot (город
  // «Moscow (Tsentralnyy administrativnyy okrug)», device_type=bot), США и
  // Сингапур — скрейперы на Chrome-UA. У всех живых браузеров (Safari, Edge,
  // Firefox, YandexBrowser, MobileSafari) fill остался 100%.
  // Робот грузит consent.js на SSR-страницах и просит объявление, которое
  // никогда не покажет. Для РСЯ это нераспроданный инвентарь и приговор
  // качеству площадки (ставки CPM считаются по конверсионности трафика).
  //
  // Правило: рекламу просим после первого доверенного события ввода
  // (isTrusted), а явных роботов не пускаем вовсе. Замер по behavior_events:
  // 96,6% сессий реальных устройств оставляют след ввода, боты — 0%.
  var BOT_UA_RE = /bot|spider|crawl|slurp|headless|phantom|selenium|webdriver|puppeteer|playwright|python-requests|python\/|aiohttp|httpx|curl\/|wget\/|go-http-client|okhttp|java\/|libwww|scrapy|feedfetcher|facebookexternalhit|preview|lighthouse|pagespeed|gtmetrix|yandexmetrika|yandexdirect/i;

  function looksLikeRobot() {
    try {
      if (navigator.webdriver === true) return true;
      if (BOT_UA_RE.test(navigator.userAgent || '')) return true;
    } catch { /* агент недоступен — решаем по вводу */ }
    return false;
  }

  // Скролл включён: на мобильных это первый жест чтения; тач/мышь/клавиатура
  // покрывают остальные случаи. Синтетические события (isTrusted=false)
  // не считаются — ими headless имитирует человека.
  var HUMAN_EVENTS = ['pointerdown', 'pointermove', 'touchstart', 'wheel', 'scroll', 'keydown'];
  var HUMAN_OPTS = { passive: true, capture: true };

  function onFirstHumanSignal(cb) {
    if (looksLikeRobot()) return null;
    var fired = false;
    function fire(e) {
      if (fired) return;
      if (e && e.isTrusted === false) return;
      fired = true;
      for (var i = 0; i < HUMAN_EVENTS.length; i++) {
        window.removeEventListener(HUMAN_EVENTS[i], fire, HUMAN_OPTS);
      }
      cb();
    }
    for (var j = 0; j < HUMAN_EVENTS.length; j++) {
      window.addEventListener(HUMAN_EVENTS[j], fire, HUMAN_OPTS);
    }
    return fire;
  }

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
    window.ym(COUNTER, 'hit', hitPath, { title: document.title, referer: firstReferer() });
    if (displaySearch !== search && typeof history !== 'undefined' && typeof history.replaceState === 'function') {
      try { history.replaceState(history.state, '', cleanPath); } catch { /* ignore */ }
    }
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

  // Метрика грузится сразу (ей нужен весь трафик, роботов она фильтрует сама),
  // РСЯ — только по сигналу человека. Флаг для тестов и отладки.
  window.__feAdsGate = { requested: false, armed: false, robot: false, signal: null };

  function armAdsGate(explicitHuman) {
    if (loaded.ads) return;
    // Клик по баннеру согласия — уже доверенный ввод: ждать второго жеста
    // незачем.
    if (explicitHuman) {
      window.__feAdsGate.armed = true;
      window.__feAdsGate.requested = true;
      loadAds();
      return;
    }
    if (window.__feAdsGate.armed) return;
    window.__feAdsGate.armed = true;
    window.__feAdsGate.robot = looksLikeRobot();
    if (window.__feAdsGate.robot) return;
    // Ссылка на обработчик открыта для тестов: в jsdom у любого
    // dispatchEvent isTrusted=false, живой ввод браузера так не воспроизвести.
    window.__feAdsGate.signal = onFirstHumanSignal(function () {
      window.__feAdsGate.requested = true;
      loadAds();
    });
  }

  window.__feApplyConsent = function (consent, opts) {
    if (!consent) return;
    if (consent.analytics) loadMetrika();
    if (consent.ads) armAdsGate(Boolean(opts && opts.explicit));
  };

  // Подразумеваемое согласие: грузим трекеры по умолчанию. Уважаем только
  // явный отказ в рамках ТЕКУЩЕЙ редакции политики (rec.v === CURRENT_V).
  // На первом заходе не конкурируем с CSS/JS приложения — ждём window.load.
  var IMPLIED = { analytics: true, ads: true };
  var rec = null;
  try {
    var raw = window.localStorage.getItem(KEY);
    if (raw) rec = JSON.parse(raw);
  } catch { rec = null; }
  var consentToApply = rec && rec.v === CURRENT_V ? rec : IMPLIED;
  function applyNow() {
    try { window.__feApplyConsent(consentToApply); }
    catch { window.__feApplyConsent(IMPLIED); }
  }
  if (document.readyState === 'complete') applyNow();
  else window.addEventListener('load', applyNow, { once: true });
})();
