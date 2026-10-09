import { useEffect, useState } from 'react';

/**
 * Круг 11, G: «Вы смотрели» (недавно открытые страницы). Хранится только в этом браузере (`localStorage`), на сервер не уходит, в события
 * аналитики не попадает (приватность: PLAN3, раздел 5). Любая ошибка хранилища (приватное окно, запрет) даёт пустой список.
 *
 * Пишет один компонент, `components/RecentPagesTracker.jsx` (смонтирован в App.jsx); читают блок «Продолжить» на главной (зона D)
 * и кабинет (зона B: `lib/recentViews.js` берёт данные отсюда: `readRecentPages`, `useRecentPages`).
 *
 * Запись: `{ path, title, kind, ts }`
 *   path   адрес со строкой запроса только там, где она задаёт страницу (сравнение, калькуляторы, рейтинг), без служебных параметров;
 *   title  название страницы без хвоста «— Forecast Economy» (то, что стоит во вкладке);
 *   kind   'country' | 'indicator' | 'rating' | 'compare' | 'calculator' | 'currency' | 'region' | 'russia' | 'calendar' | 'other';
 *   ts     время последнего открытия, мс.
 * Повторное открытие той же страницы поднимает запись наверх, дублей нет. Лимит 12 записей.
 */
export const RECENT_PAGES_KEY = 'fe:recent-pages:v1';
export const RECENT_PAGES_LIMIT = 12;
export const RECENT_PAGES_EVENT = 'fe:recent-pages';

/** Адреса, которые «просмотром» не считаются: главная, вход и кабинет, служебное, виджеты. */
const EXCLUDED = [/^\/$/, /^\/admin(\/|$)/, /^\/login(\/|$)/, /^\/register(\/|$)/, /^\/account(\/|$)/, /^\/embed(\/|$)/, /^\/widgets(\/|$)/];
/** Где строка запроса — часть страницы (набор рядов сравнения, исходные числа калькулятора, год рейтинга). */
const KEEP_SEARCH = [/^\/compare$/, /^\/calculator(\/|$)/, /^\/world\/rating(\/|$)/];
const DROP_PARAMS = /^(utm_|yclid|gclid|fbclid|_ym|preview_locale$|locale_pref$|ref$)/i;

/** Адрес для записи или null, если страницу запоминать не нужно. */
export function normalizeRecentPath(pathname, search = '') {
  const path = String(pathname || '').replace(/\/+$/, '') || '/';
  if (EXCLUDED.some((re) => re.test(path))) return null;
  if (!KEEP_SEARCH.some((re) => re.test(path))) return path;
  const params = new URLSearchParams(search || '');
  for (const key of [...params.keys()]) if (DROP_PARAMS.test(key)) params.delete(key);
  const rest = params.toString();
  const full = rest ? `${path}?${rest}` : path;
  return full.length > 300 ? path : full;
}

/** Вид страницы по адресу (для значка и подписи в списке). */
export function recentPageKind(path) {
  const p = String(path || '').split('?')[0];
  if (p.startsWith('/compare')) return 'compare';
  if (p.startsWith('/calculator')) return 'calculator';
  if (p.startsWith('/world/rating')) return 'rating';
  if (p.startsWith('/currencies')) return 'currency';
  if (p.startsWith('/russia/calendar')) return 'calendar';
  if (/^\/russia\/region/.test(p) || /\/region\//.test(p) || /\/regions$/.test(p)) return 'region';
  if (/\/indicator\//.test(p)) return 'indicator';
  if (p.startsWith('/russia')) return 'russia';
  if (/^\/[^/]+$/.test(p)) return 'country';
  return 'other';
}

/** Название без хвоста с именем сайта и без лишних пробелов. */
export function cleanRecentTitle(title) {
  return String(title || '')
    .replace(/\s*[|—–-]\s*Forecast Economy.*$/i, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 140);
}

export function readRecentPages(limit = RECENT_PAGES_LIMIT) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_PAGES_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.path === 'string' && typeof item.title === 'string' && item.title && item.path.startsWith('/'))
      .slice(0, limit);
  } catch {
    return [];
  }
}

/** Запоминает страницу первой. Возвращает true, если запись сделана. */
export function rememberPage({ path, title, now = Date.now() }) {
  const clean = cleanRecentTitle(title);
  if (!path || !String(path).startsWith('/') || clean.length < 2) return false;
  try {
    const next = [
      { path, title: clean, kind: recentPageKind(path), ts: now },
      ...readRecentPages(RECENT_PAGES_LIMIT).filter((item) => item.path !== path),
    ].slice(0, RECENT_PAGES_LIMIT);
    window.localStorage.setItem(RECENT_PAGES_KEY, JSON.stringify(next));
    window.dispatchEvent(new Event(RECENT_PAGES_EVENT));
    return true;
  } catch {
    return false;
  }
}

export function clearRecentPages() {
  try {
    window.localStorage.removeItem(RECENT_PAGES_KEY);
    window.dispatchEvent(new Event(RECENT_PAGES_EVENT));
  } catch {
    /* нечего очищать */
  }
}

/** Список для интерфейса: пуст до монтирования (разметка сервера и клиента совпадают), потом читает хранилище и следит за новыми записями. */
export function useRecentPages(limit = RECENT_PAGES_LIMIT) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    const read = () => setItems(readRecentPages(limit));
    read();
    window.addEventListener(RECENT_PAGES_EVENT, read);
    window.addEventListener('storage', read);
    return () => {
      window.removeEventListener(RECENT_PAGES_EVENT, read);
      window.removeEventListener('storage', read);
    };
  }, [limit]);
  return items;
}
