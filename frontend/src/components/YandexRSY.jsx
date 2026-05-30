import { useEffect } from 'react';

/**
 * Yandex.RTB (РСЯ) floor-ad: touch + desktop.
 *
 * Контракт:
 * - Loader (`window.yaContextCb` + `https://yandex.ru/ads/system/context.js`)
 *   подключается в `index.html` и в SSR (см. backend/app/services/seo_renderer.py)
 *   — один раз на документ, независимо от количества блоков.
 * - Render двух блоков (touch + desktop) идёт через один push в
 *   `yaContextCb`. Yandex AdvManager сам определяет class устройства и
 *   показывает только соответствующий блок: на iPhone — touch, на desktop —
 *   desktop. Лишних креативов не подгружается.
 * - SPA-навигация (React Router) не вызывает повторный рендер благодаря
 *   `window.__rsyFloorAdRendered` guard. Без guard каждый переход создавал
 *   бы новые экземпляры блоков и счётчики показов в кабинете РСЯ были бы
 *   завышены.
 * - Embed-routes (`/embed/*`) монтируют свой ErrorBoundary без YandexRSY —
 *   подключение происходит в `AppRoutes`, не в `EmbedRoutes`.
 *
 * Активные блоки (см. также CONTEXT.md::Yandex.RSY):
 *   R-A-19133345-1 floorAd touch    — мобильные устройства
 *   R-A-19133345-2 floorAd desktop  — десктоп
 *
 * Trap (CONTEXT.md::Yandex.RSY domains CSP): без yandex.ru/an.yandex.ru/
 * *.yandex.net/yastatic.net в CSP (Caddyfile) браузер блокирует context.js
 * + iframe объявлений → реклама молча не загружается.
 */
const RSY_BLOCKS = [
  { blockId: 'R-A-19133345-1', type: 'floorAd', platform: 'touch' },
  { blockId: 'R-A-19133345-2', type: 'floorAd', platform: 'desktop' },
];

export default function YandexRSY() {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (window.__rsyFloorAdRendered) return;
    window.__rsyFloorAdRendered = true;

    window.yaContextCb = window.yaContextCb || [];
    window.yaContextCb.push(() => {
      try {
        if (window.Ya && window.Ya.Context && window.Ya.Context.AdvManager) {
          for (const cfg of RSY_BLOCKS) {
            window.Ya.Context.AdvManager.render(cfg);
          }
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
