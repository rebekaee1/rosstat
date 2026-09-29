/**
 * Standalone-сборка для ЧИСТЫХ SSR-страниц — быстрых ссылок
 * (/today*, /russia/region-rating/*, /russia/region-vs/*, /calendar/*, годовые landing'и) —
 * там React-бандл не грузится, и без этого файла ~43k URL SEO-программы были
 * слепой зоной собственного счётчика (их видела только Метрика) и шли без
 * рекламы.
 *
 * Один исходник — два бандла: SPA импортирует behavior.js и rsyFloorAd.js как
 * модули, а этот entry собирается отдельным чанком с фиксированным именем
 * /assets/behavior-standalone.js и подключается строкой в SSR-хроме
 * (seo_renderer.py). Полный паритет сбора: session_start с портретом,
 * pageview, клики, dwell, scroll, vitals, ошибки. Consent уважается так же.
 *
 * Реклама (2026-09-29): тот же floorAd РСЯ, что рисует YandexRSY.jsx в SPA.
 * Кладём рендер в очередь `yaContextCb`; context.js грузит consent.js только
 * за доверенным вводом человека (гейт fill-rate), у робота очередь не
 * исполнится. Страница без рекламы (брендовая 404) помечена `data-no-ads`.
 */
import { behaviorInit } from './lib/behavior';
import { renderFloorAd } from './lib/rsyFloorAd';

function queueFloorAd() {
  if (document.body?.hasAttribute('data-no-ads')) return;
  window.yaContextCb = window.yaContextCb || [];
  window.yaContextCb.push(() => {
    try {
      renderFloorAd();
    } catch {
      // Не падаем, если РСЯ не загрузилась (CSP/AdBlock/сетевой блок).
    }
  });
}

function init() {
  behaviorInit();
  queueFloorAd();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true });
} else {
  init();
}
