/**
 * Круг 11 (зона B, сведено при интеграции): «Вы смотрели» — последние страницы, которые человек открыл на сайте.
 * Хранятся только в этом браузере (`localStorage`), на сервер не уходят, в аналитику не попадают
 * (решение владельца 09.10.2026). Любая ошибка хранилища (приватное окно, запрет) даёт пустой список.
 *
 * Одно хранилище на весь сайт: это тонкая обёртка над `lib/recentPages.js` (ключ `fe:recent-pages:v1`,
 * запись `{ path, title, kind, ts }`). Пишет одна точка — `components/RecentPagesTracker.jsx` в `App.jsx`
 * (после смены страницы берёт название вкладки); второй трекер не нужен. Читают блок «Вы смотрели» на главной и окно
 * поиска (`lib/homeContinue.js`, тот же ключ и формат) и, при желании, кабинет через `useRecentViews`.
 * Прежний отдельный ключ `fe_recent_views_v1` больше не пишется.
 *
 * Здесь запись в виде `{ kind, key, title, path, at }`: `key` равен адресу страницы, `at` — время открытия.
 */
import { useMemo, useSyncExternalStore } from 'react';
import { safePath } from './cabinetItems';
import {
  RECENT_PAGES_EVENT, RECENT_PAGES_KEY, RECENT_PAGES_LIMIT, clearRecentPages, normalizeRecentPath, readRecentPages, rememberPage,
} from './recentPages';

export const RECENT_VIEWS_KEY = RECENT_PAGES_KEY;
export const RECENT_VIEWS_LIMIT = RECENT_PAGES_LIMIT;

/** Из заголовка вкладки убирает хвост с названием сайта («Инфляция в Турции — Forecast Economy» → «Инфляция в Турции»). */
export function titleFromDocument(raw) {
  const text = String(raw ?? (typeof document !== 'undefined' ? document.title : '') ?? '').trim();
  return text.replace(/\s+[—–|-]\s+Forecast Economy\s*$/i, '').slice(0, 120);
}

function toView(page) {
  const path = safePath(page?.path);
  if (!path) return null;
  return {
    kind: page.kind || 'other',
    key: path,
    title: String(page.title || '').slice(0, 120),
    path,
    at: Number.isFinite(Number(page.ts)) ? Number(page.ts) : 0,
  };
}

/** Последние страницы, новые первыми. */
export function readRecentViews(limit = RECENT_VIEWS_LIMIT) {
  return readRecentPages(RECENT_PAGES_LIMIT).map(toView).filter(Boolean).slice(0, Math.max(0, limit));
}

/**
 * Запоминает страницу первой (в общее хранилище `lib/recentPages.js`); повтор того же адреса поднимается наверх.
 * Якорь отбрасывается, строка запроса остаётся только там, где она задаёт страницу (сравнение, калькуляторы, рейтинг).
 * Главная, вход, кабинет и служебные страницы пропускаются. `kind` и `key` вычисляются по адресу (прежние поля
 * оставлены в подписи для совместимости). Возвращает `true`, если запись сделана.
 */
export function recordView({ title, path } = {}) {
  const safe = safePath(path);
  if (!safe) return false;
  const [beforeHash] = safe.split('#');
  const [pathname, search = ''] = beforeHash.split('?');
  const normalized = normalizeRecentPath(pathname, search);
  if (!normalized) return false;
  return rememberPage({ path: normalized, title: titleFromDocument(title) });
}

export function clearRecentViews() {
  clearRecentPages();
}

function rawStored() {
  try { return window.localStorage.getItem(RECENT_PAGES_KEY) || ''; } catch { return ''; }
}

function subscribe(fn) {
  window.addEventListener(RECENT_PAGES_EVENT, fn);
  window.addEventListener('storage', fn);
  return () => {
    window.removeEventListener(RECENT_PAGES_EVENT, fn);
    window.removeEventListener('storage', fn);
  };
}

/** Хук для блока «Вы смотрели»: пусто на сервере и до первой отрисовки в браузере (гидратация без расхождений). */
export function useRecentViews(limit = 6) {
  const raw = useSyncExternalStore(subscribe, rawStored, () => '');
  return useMemo(() => (raw ? readRecentViews(limit) : []), [raw, limit]);
}
