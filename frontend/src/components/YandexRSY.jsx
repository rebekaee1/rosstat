import { useEffect, useState } from 'react';

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
 *   R-A-19489903-2 floorAd touch    — мобильные устройства
 *   R-A-19489903-1 floorAd desktop  — десктоп
 *
 * Trap (CONTEXT.md::Yandex.RSY domains CSP): без yandex.ru/an.yandex.ru/
 * *.yandex.net/yastatic.net в CSP (Caddyfile) браузер блокирует context.js
 * + iframe объявлений → реклама молча не загружается.
 */
const RSY_BLOCKS = [
  { blockId: 'R-A-19489903-2', type: 'floorAd', platform: 'touch' },
  { blockId: 'R-A-19489903-1', type: 'floorAd', platform: 'desktop' },
];

export default function YandexRSY() {
  // Пометка «Реклама» над floor-баннером (звонок 2026-06-19): показываем только
  // когда РСЯ реально отрисовалась. Если AdBlock/CSP/сеть блокируют рекламу —
  // блок не рендерится и пометки тоже нет (не висит пустой ярлык).
  const [adShown, setAdShown] = useState(false);

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
          setAdShown(true);
          if (typeof window.ym === 'function') {
            window.ym(107136069, 'reachGoal', 'rsy_floor_render');
          }
        }
      } catch {
        // Не падаем, если РСЯ не загрузилась (CSP/AdBlock/сетевой блок).
      }
    });
  }, []);

  if (!adShown) return null;

  return (
    <div
      aria-hidden="true"
      className="fixed left-1/2 -translate-x-1/2 bottom-[54px] sm:bottom-[96px] pointer-events-none px-2.5 py-0.5 rounded-t-md bg-obsidian/80 backdrop-blur-sm border border-b-0 border-border-subtle text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary"
      style={{ zIndex: 2147483646 }}
    >
      Реклама
    </div>
  );
}
