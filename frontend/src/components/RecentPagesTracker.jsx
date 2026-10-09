import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { normalizeRecentPath, rememberPage } from '../lib/recentPages';

/** Сколько ждать после перехода: страница успевает поставить своё название во вкладку (`useMeta`) и показать содержимое. */
export const RECENT_SETTLE_MS = 1500;
/** Если страница ещё не сменила название (медленный чанк), проверяем ещё столько раз и только потом отказываемся от записи. */
export const RECENT_RETRIES = 3;

/**
 * Круг 11, G: единственное место, где запоминаются открытые страницы («Вы смотрели»). Ничего не рисует.
 * Через 1,5 с после перехода берёт название вкладки и пишет его в `lib/recentPages.js`. «Не найдено» не запоминается; быстрый проход
 * по ссылкам (страница сменилась раньше срока) записи не оставляет; если после перехода на другой адрес во вкладке всё ещё название
 * прежней страницы (медленная загрузка), запись откладывается, а не получает чужое название. Эффект только на клиенте.
 */
export default function RecentPagesTracker() {
  const { pathname, search } = useLocation();
  const previousPathname = useRef(pathname);
  useEffect(() => {
    const changedPage = previousPathname.current !== pathname;
    previousPathname.current = pathname;
    const path = normalizeRecentPath(pathname, search);
    if (!path) return undefined;
    const titleAtStart = document.title;
    let timer = 0;
    let attempt = 0;
    const settle = () => {
      attempt += 1;
      if (document.querySelector('.z2-nf')) return;
      if (changedPage && document.title === titleAtStart && attempt <= RECENT_RETRIES) {
        timer = window.setTimeout(settle, RECENT_SETTLE_MS);
        return;
      }
      if (changedPage && document.title === titleAtStart) return;
      rememberPage({ path, title: document.title });
    };
    timer = window.setTimeout(settle, RECENT_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [pathname, search]);
  return null;
}
