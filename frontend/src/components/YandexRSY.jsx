import { useEffect } from 'react';

/**
 * Yandex.RTB (РСЯ) floor-ad для мобильных устройств.
 *
 * Контракт:
 * - Loader (`window.yaContextCb` + `https://yandex.ru/ads/system/context.js`)
 *   подключается в `index.html` и в SSR (см. backend/app/services/seo_renderer.py).
 * - Сам блок рендерится **один раз** на сессию через push в `yaContextCb`.
 * - SPA-навигация (React Router) не вызывает повторный рендер благодаря
 *   `window.__rsyFloorAdRendered` guard.
 * - `platform: "touch"` означает: Yandex покажет блок только на мобильных
 *   устройствах. На десктопе AdvManager сам не рендерит блок — лишних
 *   запросов не будет.
 * - Embed-routes (`/embed/*`) монтируют свой ErrorBoundary без YandexRSY —
 *   подключение происходит в `AppRoutes`, не в `EmbedRoutes`.
 *
 * Trap (CONTEXT.md::Yandex.RSY domains CSP): без yandex.ru/an.yandex.ru/
 * yastatic.net в CSP (Caddyfile) браузер блокирует context.js + iframe
 * объявления → реклама молча не загружается.
 */
export default function YandexRSY() {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (window.__rsyFloorAdRendered) return;
    window.__rsyFloorAdRendered = true;

    window.yaContextCb = window.yaContextCb || [];
    window.yaContextCb.push(() => {
      try {
        if (window.Ya && window.Ya.Context && window.Ya.Context.AdvManager) {
          window.Ya.Context.AdvManager.render({
            blockId: 'R-A-19133345-1',
            type: 'floorAd',
            platform: 'touch',
          });
          if (typeof window.ym === 'function') {
            window.ym(107136069, 'reachGoal', 'rsy_floor_render');
          }
        }
      } catch {
        // Не падаем, если РСЯ не загрузилась (CSP/AdBlock/сетевой блок).
      }
    });
  }, []);

  return null;
}
