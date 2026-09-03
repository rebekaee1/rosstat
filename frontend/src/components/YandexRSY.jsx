import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
  RSY_BLOCKS,
  destroyBlock,
  forceRemoveShell,
  renderFloorAd,
} from '../lib/rsyFloorAd';

/**
 * Yandex.RTB (РСЯ) floor-ad: React-обвязка. Вся логика блоков, детекции fill
 * и destroy — в `lib/rsyFloorAd.js` (см. контракт и traps там).
 *
 * - Первый рендер — один на документ; дальше на каждой смене маршрута блок
 *   обновляется (`renderFloorAd({ refresh: true })`) с антидребезгом
 *   `REFRESH_COOLDOWN_MS` внутри lib. До 2026-09-03 повторов не было вовсе:
 *   читатель десяти карточек видел одно объявление за визит.
 * - Embed-routes (`/embed/*`) монтируют свой ErrorBoundary без YandexRSY.
 * - `/admin/*`: не инициализируем; уже отрисованный floorAd прячется
 *   классом `rsy-hidden` на <html> (CSS в index.css).
 */
export default function YandexRSY() {
  const { pathname } = useLocation();
  const isAdmin = pathname.startsWith('/admin');

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.classList.toggle('rsy-hidden', isAdmin);
    if (isAdmin) {
      for (const b of RSY_BLOCKS) {
        destroyBlock(b.blockId);
        forceRemoveShell(b.blockId);
      }
    }
  }, [isAdmin]);

  useEffect(() => {
    if (typeof window === 'undefined' || isAdmin) return;

    // Первый маршрут — обычный рендер, последующие — обновление блока.
    const refresh = Boolean(window.__rsyFloorAdRendered);
    window.__rsyFloorAdRendered = true;

    // Очередь разбирает context.js, который грузится только после сигнала
    // человека (public/consent.js). У робота очередь просто не исполнится.
    window.yaContextCb = window.yaContextCb || [];
    window.yaContextCb.push(() => {
      try {
        renderFloorAd({ refresh });
      } catch {
        // Не падаем, если РСЯ не загрузилась (CSP/AdBlock/сетевой блок).
      }
    });
  }, [isAdmin, pathname]);

  return null;
}
