import { useEffect, useState } from 'react';

/**
 * Круг 11 (D): чтение списка «Вы смотрели» для главной и окна поиска. Список пишет только зона G
 * (`components/RecentPagesTracker.jsx` → `lib/recentPages.js`); здесь тот же ключ и тот же формат, только чтение,
 * поэтому блок не зависит от порядка слияния зон. Всё хранится в этом браузере, на сервер не уходит.
 * Запись: `{ path, title, kind, ts }`; любая ошибка хранилища (приватное окно, запрет) даёт пустой список.
 */
export const RECENT_VISITED_KEY = 'fe:recent-pages:v1';
export const RECENT_VISITED_EVENT = 'fe:recent-pages';

const KINDS = new Set(['country', 'indicator', 'rating', 'compare', 'calculator', 'currency', 'region', 'russia', 'calendar', 'other']);

/** Безопасный внутренний адрес: только путь сайта, без чужих хостов и без двойного слеша. */
function safePath(path) {
  return typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.includes('\\');
}

/** Записи без повреждений, свежие первыми; не больше `limit`. */
export function readRecentVisited(limit = 12) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_VISITED_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && safePath(item.path) && typeof item.title === 'string' && item.title.trim().length >= 2)
      .map((item) => ({
        path: item.path,
        title: item.title.trim().slice(0, 140),
        kind: KINDS.has(item.kind) ? item.kind : 'other',
        ts: Number.isFinite(Number(item.ts)) ? Number(item.ts) : 0,
      }))
      .slice(0, Math.max(0, limit));
  } catch {
    return [];
  }
}

export function clearRecentVisited() {
  try {
    window.localStorage.removeItem(RECENT_VISITED_KEY);
    window.dispatchEvent(new Event(RECENT_VISITED_EVENT));
  } catch {
    /* нечего очищать */
  }
}

/** Список для интерфейса: пуст до монтирования (разметка сервера и клиента совпадают), потом читает хранилище и следит за записями. */
export function useRecentVisited(limit = 12) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    const read = () => setItems(readRecentVisited(limit));
    read();
    window.addEventListener(RECENT_VISITED_EVENT, read);
    window.addEventListener('storage', read);
    return () => {
      window.removeEventListener(RECENT_VISITED_EVENT, read);
      window.removeEventListener('storage', read);
    };
  }, [limit]);
  return items;
}

/**
 * Что показать в блоке «Продолжить»: самые свежие страницы без повторов по названию и без страниц-обёрток.
 * Первая запись — «Продолжить» (самое свежее), остальные — «Вы смотрели».
 */
export function continueItems(items, limit = 6) {
  const seen = new Set();
  const out = [];
  for (const item of items || []) {
    const key = item.title.toLocaleLowerCase();
    if (seen.has(key) || item.path === '/') continue;
    seen.add(key);
    out.push(item);
    if (out.length >= limit) break;
  }
  return out;
}
