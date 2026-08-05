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
 * - SPA-навигация не вызывает повторный рендер (`window.__rsyFloorAdRendered`).
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
    if (window.__rsyFloorAdRendered) return;
    window.__rsyFloorAdRendered = true;

    window.yaContextCb = window.yaContextCb || [];
    window.yaContextCb.push(() => {
      try {
        renderFloorAd();
      } catch {
        // Не падаем, если РСЯ не загрузилась (CSP/AdBlock/сетевой блок).
      }
    });
  }, [isAdmin]);

  return null;
}
