/**
 * Круг 11 (зона B): хуки кабинета. Работают без провайдера входа и без провайдера запросов:
 * нет входа = гость, нет ответа настройки = кабинета нет (все хуки отдают `enabled: false`).
 */
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useAuth } from '../context/authContext';
import {
  addWatch, bindAuth, dismissImportResult, ensureConfig, findWatchIn, getServerState, getState,
  loadSaved, loadWatches, markSeen, newCountOf, removeWatch, subscribe,
} from './cabinetStore';

/** Снимок хранилища; перерисовывает при любом изменении. */
export function useCabinetState() {
  return useSyncExternalStore(subscribe, getState, getServerState);
}

/** Вход, если провайдер есть; без него (тесты зон, встраиваемые страницы) человек считается гостем. */
function useOptionalAuth() {
  try { return useAuth(); } catch { return null; }
}

/**
 * Подключает компонент к кабинету: спрашивает настройку (один раз на страницу) и сообщает хранилищу, кто смотрит.
 * Вызывается внутри остальных хуков, отдельно звать не нужно.
 */
export function useCabinetBoot() {
  const auth = useOptionalAuth();
  const loading = Boolean(auth?.isLoading);
  const authed = Boolean(auth?.isAuthed);
  const userId = auth?.user?.id != null ? String(auth.user.id) : (auth?.user?.email || 'user');
  const authKey = loading ? null : (authed ? userId : 'guest');
  useEffect(() => { ensureConfig(); }, []);
  useEffect(() => { bindAuth(authKey); }, [authKey]);
  return { authed, authLoading: loading };
}

/** `{ enabled, ready, features, limits }`. `ready` — ответ получен; пока его нет, `enabled` ложь. */
export function useCabinetConfig() {
  useCabinetBoot();
  const s = useCabinetState();
  return useMemo(() => ({
    enabled: s.config?.enabled === true,
    ready: s.configStatus === 'ready' || s.configStatus === 'error',
    features: s.config?.features || {},
    limits: s.config?.limits || {},
  }), [s.config, s.configStatus]);
}

/**
 * Слежение за рядом: `<WatchButton>` построен на нём.
 * `toggle()` возвращает `{ ok, created?, reason? }`; для гостя слежение не создаётся (`reason: 'auth_required'`).
 */
export function useWatch(subjectKind, subjectKey) {
  const { authed } = useCabinetBoot();
  const s = useCabinetState();
  const enabled = s.config?.enabled === true;
  useEffect(() => {
    if (enabled && authed) loadWatches();
  }, [enabled, authed, s.authKey]);
  const item = enabled ? findWatchIn(s, subjectKind, subjectKey) : null;
  const loaded = s.watchStatus === 'ready' || s.watchStatus === 'error';
  return useMemo(() => ({
    enabled,
    authed,
    watching: Boolean(item),
    item,
    loaded: authed ? loaded : true,
    limit: s.config?.limits?.watches ?? s.watchLimit,
    toggle: () => (item ? removeWatch(subjectKind, subjectKey) : addWatch(subjectKind, subjectKey)),
  }), [enabled, authed, item, loaded, s.config, s.watchLimit, subjectKind, subjectKey]);
}

/**
 * Лента «Что вышло нового»: ряды, у которых появилось значение позже последнего просмотра.
 * Для значка в шапке (`<FeedBadge>`) и раздела «Слежу». Читает список слежения, дополнительных запросов нет.
 */
export function useFeed({ load = true } = {}) {
  const { authed } = useCabinetBoot();
  const s = useCabinetState();
  const enabled = s.config?.enabled === true;
  useEffect(() => {
    if (load && enabled && authed) loadWatches();
  }, [load, enabled, authed, s.authKey]);
  return useMemo(() => {
    const active = enabled && authed;
    const items = active ? s.watches.filter((w) => w.is_new) : [];
    return {
      enabled: active,
      watches: active ? s.watches : [],
      items,
      newCount: active ? newCountOf(s) : 0,
      status: s.watchStatus,
      limit: s.config?.limits?.watches ?? s.watchLimit,
      reload: () => loadWatches({ force: true }),
      markSeen,
    };
  }, [enabled, authed, s]);
}

/** Количество нового для значка; 0, пока кабинет выключен или человек не вошёл. */
export function useFeedCount() {
  return useFeed().newCount;
}

/** Состояние переноса избранного гостя после входа (для разового сообщения в кабинете). */
export function useImportNotice() {
  const s = useCabinetState();
  return { result: s.importResult, dismiss: dismissImportResult };
}

/** Перечитать сохранённое и слежение принудительно (кнопка «Обновить», возврат в кабинет). */
export function reloadCabinet() {
  return Promise.all([loadSaved(true), loadWatches({ force: true })]);
}
