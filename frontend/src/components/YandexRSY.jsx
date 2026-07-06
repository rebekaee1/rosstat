import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

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
 * - Служебные страницы `/admin/*` без рекламы (BI 2.1, этап 4а): на них
 *   реклама не инициализируется, а floorAd, отрисованный до перехода,
 *   прячется классом `rsy-hidden` на <html> (CSS в index.css).
 *
 * Маркировка «Реклама»: её несёт сам креатив РСЯ (Yandex как рекламная
 * система ставит метку «Реклама» + домен/erid рекламодателя — это её зона
 * ответственности в RTB). Свой оверлей-ярлык мы НЕ рисуем: floorAd имеет
 * переменную высоту (картинка + текст + кнопка закрытия), и отдельный
 * фиксированный элемент с захардкоженным `bottom` попадал в середину
 * объявления (баг 2026-06-24). Дубль был и избыточен, и ломал вёрстку.
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
  const { pathname } = useLocation();
  const isAdmin = pathname.startsWith('/admin');

  // Служебный раздел /admin/*: рекламу не инициализируем, а уже отрисованный
  // floorAd прячем CSS-классом (этап 4а BI 2.1) — SDK РСЯ живёт глобально
  // и переживает SPA-навигацию, поэтому unmount недостаточно.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.classList.toggle('rsy-hidden', isAdmin);
  }, [isAdmin]);

  useEffect(() => {
    if (typeof window === 'undefined' || isAdmin) return;
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
  }, [isAdmin]);

  return null;
}
