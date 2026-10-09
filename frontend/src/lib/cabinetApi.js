/**
 * Круг 11 (зона B): запросы к `/api/v1/cabinet/*` (контракт — impl4-a.md, раздел 3).
 * Все вызовы идут через общий клиент `api` (сессионная кука, CSRF, язык). Повторять разрешено только то,
 * что безопасно выполнить дважды (`idempotent: true`); выпуск ссылки календаря не повторяется никогда.
 * Сервер при выключенном флаге отвечает 404 на всё, кроме `config`: интерфейс спрашивает `config` первым.
 */
import api from './api';

const data = (promise) => promise.then((r) => r.data);

/** Включён ли кабинет и какие у него лимиты. Открыт гостю, всегда 200. */
export const fetchCabinetConfig = ({ signal } = {}) => data(api.get('/cabinet/config', { signal }));

// --- Сохранённое -------------------------------------------------------------------------------

export const listSaved = ({ kind, key } = {}, { signal } = {}) => {
  const params = {};
  if (kind) params.kind = kind;
  if (key) params.key = key;
  return data(api.get('/cabinet/saved', { params, signal }));
};

/** Добавить или обновить запись по паре (kind, itemKey); пустые title/payload существующее не затирают. */
export const saveItem = ({ kind, itemKey, title, payload }) => {
  const body = { kind, item_key: itemKey };
  if (title) body.title = title;
  if (payload) body.payload = payload;
  return data(api.post('/cabinet/saved', body, { idempotent: true }));
};

export const renameSaved = (id, title) =>
  data(api.patch(`/cabinet/saved/${encodeURIComponent(id)}`, { title }, { idempotent: true }));

export const deleteSavedById = (id) =>
  data(api.delete(`/cabinet/saved/${encodeURIComponent(id)}`, { idempotent: true }));

export const deleteSavedByKey = (kind, key) =>
  data(api.delete('/cabinet/saved', { params: { kind, key }, idempotent: true }));

/** Перенос избранного гостя после входа: до 100 записей за вызов, уже сохранённое не затирается. */
export const importSaved = (items) =>
  data(api.post('/cabinet/saved/import', {
    items: items.map((it) => ({
      kind: it.kind,
      item_key: it.item_key,
      ...(it.title ? { title: it.title } : {}),
      ...(it.payload ? { payload: it.payload } : {}),
    })),
  }, { idempotent: true }));

// --- Слежение и лента ----------------------------------------------------------------------------

export const listWatches = ({ signal } = {}) => data(api.get('/cabinet/watches', { signal }));

export const addWatch = (subjectKind, subjectKey) =>
  data(api.post('/cabinet/watches', { subject_kind: subjectKind, subject_key: subjectKey, channel: 'inapp' }, { idempotent: true }));

export const deleteWatchById = (id) =>
  data(api.delete(`/cabinet/watches/${encodeURIComponent(id)}`, { idempotent: true }));

export const deleteWatchByKey = (subjectKind, subjectKey) =>
  data(api.delete('/cabinet/watches', { params: { subject_kind: subjectKind, subject_key: subjectKey }, idempotent: true }));

export const fetchFeed = ({ signal } = {}) => data(api.get('/cabinet/feed', { signal }));

/** Отметить прочитанным: без `ids` все новые. Ответ — лента после отметки. */
export const markFeedSeen = (ids) =>
  data(api.post('/cabinet/feed/seen', ids && ids.length ? { ids } : {}, { idempotent: true }));

// --- История выгрузок ----------------------------------------------------------------------------

export const listExports = ({ limit } = {}, { signal } = {}) =>
  data(api.get('/cabinet/exports', { params: limit ? { limit } : {}, signal }));

export const deleteExport = (id) =>
  data(api.delete(`/cabinet/exports/${encodeURIComponent(id)}`, { idempotent: true }));

export const clearExports = () => data(api.delete('/cabinet/exports', { idempotent: true }));

// --- Настройки -----------------------------------------------------------------------------------

export const fetchPrefs = ({ signal } = {}) => data(api.get('/cabinet/prefs', { signal }));

/** Сервер заменяет настройки целиком: передавайте полный набор (текущие значения плюс правка). */
export const savePrefs = (prefs) => data(api.put('/cabinet/prefs', prefs, { idempotent: true }));

// --- Личный календарь (.ics) ---------------------------------------------------------------------

export const fetchCalendarFeed = ({ signal } = {}) => data(api.get('/cabinet/calendar-feed', { signal }));

/** Выпуск (или перевыпуск) ссылки. Токен приходит один раз; старая ссылка перестаёт работать. Без повторов. */
export const createCalendarFeed = () => data(api.post('/cabinet/calendar-feed'));

export const deleteCalendarFeed = () => data(api.delete('/cabinet/calendar-feed', { idempotent: true }));

/** Адреса подписки по ответу `createCalendarFeed` (хост берётся у открытой страницы). */
export function calendarFeedLinks(path, host) {
  const h = host || (typeof window !== 'undefined' ? window.location.host : '');
  const proto = typeof window !== 'undefined' && window.location.protocol === 'http:' ? 'http:' : 'https:';
  if (!path || !h) return { https: '', webcal: '' };
  return { https: `${proto}//${h}${path}`, webcal: `webcal://${h}${path}` };
}
