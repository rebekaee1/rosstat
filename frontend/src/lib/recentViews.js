/**
 * Круг 11 (зона B): «Вы смотрели» — последние страницы, которые человек открыл на сайте.
 * Хранятся только в этом браузере (`localStorage`), на сервер не уходят, в аналитику не попадают
 * (решение владельца 09.10.2026). Любая ошибка хранилища (приватное окно, запрет) даёт пустой список.
 *
 * Запись: одна точка (трекер в оболочке, зона G) зовёт `recordView({ kind, key, title, path })` после открытия страницы.
 * Чтение: `readRecentViews(limit)` или хук `useRecentViews(limit)` (блок «Продолжить» на главной, зона D).
 */
import { useMemo, useSyncExternalStore } from 'react';
import { safePath } from './cabinetItems';

export const RECENT_VIEWS_KEY = 'fe_recent_views_v1';
export const RECENT_VIEWS_LIMIT = 12;
const CHANGE_EVENT = 'fe:recent-views';
const KIND_RE = /^[a-z][a-z_]{0,23}$/;
/** Служебные страницы в «Вы смотрели» не нужны. */
const SKIP_PATH = /^\/(?:login|register|account|admin|embed|widgets)(?:[/?#]|$)/;

/** Из заголовка вкладки убирает хвост с названием сайта («Инфляция в Турции — Forecast Economy» → «Инфляция в Турции»). */
export function titleFromDocument(raw) {
  const text = String(raw ?? (typeof document !== 'undefined' ? document.title : '') ?? '').trim();
  return text.replace(/\s+[—–|-]\s+Forecast Economy\s*$/i, '').slice(0, 120);
}

function clean(entry) {
  if (!entry || typeof entry !== 'object') return null;
  const path = safePath(entry.path);
  const title = typeof entry.title === 'string' ? entry.title.trim().slice(0, 120) : '';
  if (!path || !title || !KIND_RE.test(String(entry.kind || ''))) return null;
  const at = Number.isFinite(entry.at) ? entry.at : 0;
  return { kind: entry.kind, key: String(entry.key ?? '').slice(0, 200), title, path, at };
}

function parse(raw) {
  try {
    const list = JSON.parse(raw || '[]');
    return Array.isArray(list) ? list.map(clean).filter(Boolean).slice(0, RECENT_VIEWS_LIMIT) : [];
  } catch {
    return [];
  }
}

function rawStored() {
  try { return window.localStorage.getItem(RECENT_VIEWS_KEY) || ''; } catch { return ''; }
}

/** Последние страницы, новые первыми. */
export function readRecentViews(limit = RECENT_VIEWS_LIMIT) {
  return parse(rawStored()).slice(0, Math.max(0, limit));
}

/**
 * Запоминает страницу первой; повтор того же адреса (без якоря) поднимается наверх, а не дублируется.
 * Возвращает `true`, если запись сделана. Служебные страницы и страницы без названия пропускаются.
 */
export function recordView({ kind, key = '', title, path } = {}) {
  const entry = clean({ kind, key, title, path, at: Date.now() });
  if (!entry || entry.path === '/' || SKIP_PATH.test(entry.path)) return false;
  const bare = (p) => p.split('#')[0];
  try {
    const next = [entry, ...parse(rawStored()).filter((it) => bare(it.path) !== bare(entry.path))].slice(0, RECENT_VIEWS_LIMIT);
    window.localStorage.setItem(RECENT_VIEWS_KEY, JSON.stringify(next));
    window.dispatchEvent(new Event(CHANGE_EVENT));
    return true;
  } catch {
    return false;
  }
}

export function clearRecentViews() {
  try {
    window.localStorage.removeItem(RECENT_VIEWS_KEY);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  } catch { /* ничего */ }
}

function subscribe(fn) {
  window.addEventListener(CHANGE_EVENT, fn);
  window.addEventListener('storage', fn);
  return () => {
    window.removeEventListener(CHANGE_EVENT, fn);
    window.removeEventListener('storage', fn);
  };
}

/** Хук для блока «Вы смотрели»: пусто на сервере и до первой отрисовки в браузере (гидратация без расхождений). */
export function useRecentViews(limit = 6) {
  const raw = useSyncExternalStore(subscribe, rawStored, () => '');
  return useMemo(() => parse(raw).slice(0, Math.max(0, limit)), [raw, limit]);
}
