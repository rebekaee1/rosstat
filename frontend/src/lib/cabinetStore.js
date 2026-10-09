/**
 * Круг 11 (зона B): общее состояние кабинета на странице — настройка, сохранённое, слежение.
 *
 * Зачем отдельное хранилище, а не react-query: кнопки `SaveButton` и `WatchButton` подключают пять зон,
 * и в их тестах нет ни провайдера запросов, ни провайдера входа. Хранилище работает без обоих
 * (нет входа = гость, нет ответа настройки = кабинет выключен).
 *
 * Правила:
 *  - кнопки и разделы показываются только если `GET /cabinet/config` вернул `enabled: true`;
 *  - гость сохраняет в браузере (`localStorage`, любая ошибка хранилища проглатывается), при входе записи
 *    переносятся в кабинет пачками по 100 и из браузера удаляются;
 *  - вошедший работает с сервером; изменение показывается сразу и откатывается, если сервер отказал;
 *  - слежение считается сервером на лету, поэтому список читается не чаще раза в 5 минут и при возврате на вкладку;
 *  - данные кабинета не попадают в аналитику и журналы: здесь нет ни одного вызова `track`.
 */
import * as cabinetApi from './cabinetApi';
import { cabinetErrorCode, normalizeSavedInput } from './cabinetItems';

export const GUEST_KEY = 'fe_cab_saved_v1';
const CONFIG_KEY = 'fe_cab_config_v1';
const CONFIG_TTL_MS = 10 * 60 * 1000;
const WATCH_TTL_MS = 5 * 60 * 1000;
const RETRY_AFTER_ERROR_MS = 60 * 1000;
export const GUEST_LIMIT = 200;
export const IMPORT_BATCH = 100;

const DISABLED_CONFIG = Object.freeze({ enabled: false, features: {}, limits: {} });

const SERVER_RESET = Object.freeze({
  saved: [],
  savedStatus: 'idle',
  savedAt: 0,
  watches: [],
  watchStatus: 'idle',
  watchAt: 0,
  watchLimit: 50,
  importResult: null,
});

function freshState() {
  return {
    config: null,
    configStatus: 'idle',
    configAt: 0,
    authKey: null,
    guest: readGuest(),
    ...SERVER_RESET,
  };
}

/** Снимок для сервера и первой отрисовки при гидратации: кабинета нет, ничего не показываем. */
const SERVER_STATE = Object.freeze({
  config: null, configStatus: 'idle', configAt: 0, authKey: null, guest: [], ...SERVER_RESET,
});

let state = null;
const listeners = new Set();
let configPromise = null;
let savedPromise = null;
let watchPromise = null;
let syncing = false;
let wired = false;

function current() {
  if (state === null) state = freshState();
  return state;
}

function set(patch) {
  state = { ...current(), ...patch };
  listeners.forEach((fn) => fn());
}

export function getState() {
  return current();
}

export function getServerState() {
  return SERVER_STATE;
}

export function subscribe(fn) {
  wire();
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** Только для тестов: вернуть хранилище в исходное состояние. */
export function __resetCabinetStore() {
  state = null;
  configPromise = null;
  savedPromise = null;
  watchPromise = null;
  syncing = false;
  listeners.clear();
}

// --- localStorage гостя ----------------------------------------------------------------------------

function readGuest() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(GUEST_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((it) => it && typeof it.kind === 'string' && typeof it.item_key === 'string' && it.item_key)
      .slice(0, GUEST_LIMIT);
  } catch {
    return [];
  }
}

function writeGuest(items) {
  try {
    if (items.length) window.localStorage.setItem(GUEST_KEY, JSON.stringify(items));
    else window.localStorage.removeItem(GUEST_KEY);
    return true;
  } catch {
    return false;
  }
}

function readConfigCache() {
  try {
    const raw = JSON.parse(window.sessionStorage.getItem(CONFIG_KEY) || 'null');
    if (raw && Date.now() - raw.at < CONFIG_TTL_MS && raw.config && typeof raw.config.enabled === 'boolean') return raw.config;
  } catch { /* хранилище недоступно */ }
  return null;
}

function writeConfigCache(config) {
  try { window.sessionStorage.setItem(CONFIG_KEY, JSON.stringify({ at: Date.now(), config })); } catch { /* ничего */ }
}

function wire() {
  if (wired || typeof window === 'undefined') return;
  wired = true;
  // Другая вкладка изменила гостевое избранное.
  window.addEventListener('storage', (event) => {
    if (event.key === GUEST_KEY || event.key === null) set({ guest: readGuest() });
  });
  // Вернулись на вкладку: обновить значок «Новое», но не чаще раза в 5 минут.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    const s = current();
    if (s.watchStatus === 'ready' && Date.now() - s.watchAt > WATCH_TTL_MS) loadWatches();
  });
}

// --- Настройка ---------------------------------------------------------------------------------------

function normalizeConfig(raw) {
  if (!raw || raw.enabled !== true) return DISABLED_CONFIG;
  return { enabled: true, features: raw.features || {}, limits: raw.limits || {} };
}

/** Спросить у сервера, включён ли кабинет. Вызывается один раз на страницу (ответ держится 10 минут в sessionStorage). */
export function ensureConfig() {
  const s = current();
  if (s.configStatus === 'loading' || s.configStatus === 'ready') return configPromise || Promise.resolve();
  if (s.configStatus === 'error' && Date.now() - s.configAt < RETRY_AFTER_ERROR_MS) return Promise.resolve();
  const cached = readConfigCache();
  if (cached) {
    set({ config: normalizeConfig(cached), configStatus: 'ready', configAt: Date.now() });
    configPromise = Promise.resolve();
    maybeLoad();
    return configPromise;
  }
  set({ configStatus: 'loading' });
  configPromise = Promise.resolve()
    .then(() => cabinetApi.fetchCabinetConfig())
    .then((raw) => {
      const config = normalizeConfig(raw);
      writeConfigCache(config);
      set({ config, configStatus: 'ready', configAt: Date.now() });
      maybeLoad();
    })
    .catch(() => {
      // Нет ответа = кабинета нет: ни кнопок, ни разделов, ни пустых заглушек.
      set({ config: DISABLED_CONFIG, configStatus: 'error', configAt: Date.now() });
    });
  return configPromise;
}

/** Связать хранилище с входом: `'guest'` или идентификатор человека; `null` — вход ещё проверяется. */
export function bindAuth(authKey) {
  const s = current();
  if (authKey === null || s.authKey === authKey) return;
  const reset = s.authKey !== null ? SERVER_RESET : {};
  savedPromise = null;
  watchPromise = null;
  set({ authKey, ...reset });
  maybeLoad();
}

export const isEnabled = () => current().config?.enabled === true;
const canUseServer = () => {
  const s = current();
  return s.config?.enabled === true && s.authKey !== null && s.authKey !== 'guest';
};

function maybeLoad() {
  if (canUseServer()) loadSaved();
}

// --- Сохранённое -----------------------------------------------------------------------------------

const same = (row, kind, key) => row.kind === kind && (row.item_key ?? row.itemKey) === key;
const byNewest = (a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''));

/** Есть ли запись: у вошедшего сервер плюс то, что ещё ждёт переноса из браузера; у гостя браузер. */
export function findSavedIn(s, kind, key) {
  if (!kind || !key) return null;
  return s.saved.find((r) => same(r, kind, key)) || s.guest.find((r) => same(r, kind, key)) || null;
}

export function loadSaved(force = false) {
  if (!canUseServer()) return Promise.resolve();
  const s = current();
  if (!force) {
    if (s.savedStatus === 'loading') return savedPromise || Promise.resolve();
    if (s.savedStatus === 'ready') return Promise.resolve();
    if (s.savedStatus === 'error' && Date.now() - s.savedAt < RETRY_AFTER_ERROR_MS) return Promise.resolve();
  }
  const who = s.authKey;
  set({ savedStatus: 'loading' });
  savedPromise = Promise.resolve()
    .then(() => cabinetApi.listSaved())
    .then((res) => {
      if (current().authKey !== who) return undefined;
      set({ saved: Array.isArray(res?.items) ? res.items : [], savedStatus: 'ready', savedAt: Date.now() });
      return syncGuest();
    })
    .catch(() => {
      if (current().authKey === who) set({ savedStatus: 'error', savedAt: Date.now() });
    });
  return savedPromise;
}

/** Перенос избранного гостя в кабинет после входа. При сбое записи остаются в браузере до следующей попытки. */
export async function syncGuest() {
  const s = current();
  if (syncing || !canUseServer() || !s.guest.length) return;
  syncing = true;
  const who = s.authKey;
  const batch = s.guest.slice();
  let imported = 0;
  let skipped = 0;
  let limitReached = false;
  let failed = false;
  try {
    for (let i = 0; i < batch.length; i += IMPORT_BATCH) {
      const res = await cabinetApi.importSaved(batch.slice(i, i + IMPORT_BATCH));
      imported += res?.imported || 0;
      skipped += res?.skipped || 0;
      if (res?.limit_reached) { limitReached = true; break; }
    }
  } catch {
    failed = true;
  }
  syncing = false;
  if (current().authKey !== who || failed) return;
  const left = current().guest.filter((g) => !batch.some((b) => same(b, g.kind, g.item_key)));
  writeGuest(left);
  set({ guest: left, importResult: { imported, skipped, limitReached } });
  await loadSaved(true);
}

export function dismissImportResult() {
  set({ importResult: null });
}

/** Сохранить. Ответ: `{ ok, local?, created?, reason? }`; причины: disabled, invalid, limit_reached, network и коды сервера. */
export async function saveItem(raw) {
  const input = normalizeSavedInput(raw);
  if (!input) return { ok: false, reason: 'invalid' };
  if (!isEnabled()) return { ok: false, reason: 'disabled' };
  const now = new Date().toISOString();

  if (!canUseServer()) {
    const list = current().guest;
    const at = list.findIndex((r) => same(r, input.kind, input.itemKey));
    if (at < 0 && list.length >= GUEST_LIMIT) return { ok: false, reason: 'limit_reached' };
    const row = {
      kind: input.kind,
      item_key: input.itemKey,
      title: input.title || (at >= 0 ? list[at].title : '') || '',
      payload: input.payload || (at >= 0 ? list[at].payload : null) || null,
      created_at: at >= 0 ? list[at].created_at : now,
    };
    const next = at < 0 ? [row, ...list] : list.map((r, i) => (i === at ? row : r));
    const persisted = writeGuest(next);
    set({ guest: next });
    return { ok: true, local: true, created: at < 0, persisted };
  }

  const tempId = `tmp-${Math.random().toString(36).slice(2)}`;
  const known = current().saved.some((r) => same(r, input.kind, input.itemKey));
  if (!known) {
    const temp = {
      id: tempId, kind: input.kind, item_key: input.itemKey, title: input.title || '',
      payload: input.payload || {}, created_at: now, updated_at: now, pending: true,
    };
    set({ saved: [temp, ...current().saved] });
  }
  try {
    const res = await cabinetApi.saveItem(input);
    const item = res?.item;
    const rest = current().saved.filter((r) => r.id !== tempId && !(item && same(r, item.kind, item.item_key)));
    set({ saved: item ? [item, ...rest].sort(byNewest) : rest });
    return { ok: true, created: res?.created !== false };
  } catch (err) {
    set({ saved: current().saved.filter((r) => r.id !== tempId) });
    return { ok: false, reason: cabinetErrorCode(err) };
  }
}

/** Убрать по виду и ключу. У вошедшего убирает и запись, ещё не перенесённую из браузера. */
export async function removeSaved(kind, key) {
  if (!isEnabled()) return { ok: false, reason: 'disabled' };
  const s = current();
  const guestLeft = s.guest.filter((r) => !same(r, kind, key));
  if (guestLeft.length !== s.guest.length) {
    writeGuest(guestLeft);
    set({ guest: guestLeft });
  }
  if (!canUseServer()) return { ok: true, local: true };
  const removed = current().saved.filter((r) => same(r, kind, key));
  if (!removed.length) return { ok: true };
  set({ saved: current().saved.filter((r) => !same(r, kind, key)) });
  try {
    await cabinetApi.deleteSavedByKey(kind, key);
    return { ok: true };
  } catch (err) {
    set({ saved: [...removed, ...current().saved].sort(byNewest) });
    return { ok: false, reason: cabinetErrorCode(err) };
  }
}

/** Убрать по идентификатору записи (кнопка «Убрать» в кабинете). */
export async function removeSavedById(id) {
  const row = current().saved.find((r) => r.id === id);
  if (!row || !canUseServer()) return { ok: false, reason: 'not_found' };
  set({ saved: current().saved.filter((r) => r.id !== id) });
  try {
    await cabinetApi.deleteSavedById(id);
    return { ok: true };
  } catch (err) {
    const code = cabinetErrorCode(err);
    if (code === 'not_found') return { ok: true };
    set({ saved: [row, ...current().saved].sort(byNewest) });
    return { ok: false, reason: code };
  }
}

export async function renameSaved(id, title) {
  const name = String(title || '').trim().slice(0, 200);
  const row = current().saved.find((r) => r.id === id);
  if (!row || !name || !canUseServer()) return { ok: false, reason: 'invalid' };
  set({ saved: current().saved.map((r) => (r.id === id ? { ...r, title: name } : r)) });
  try {
    const res = await cabinetApi.renameSaved(id, name);
    if (res?.item) set({ saved: current().saved.map((r) => (r.id === id ? res.item : r)) });
    return { ok: true };
  } catch (err) {
    set({ saved: current().saved.map((r) => (r.id === id ? row : r)) });
    return { ok: false, reason: cabinetErrorCode(err) };
  }
}

// --- Слежение -----------------------------------------------------------------------------------------

export const findWatchIn = (s, kind, key) =>
  s.watches.find((w) => w.subject_kind === kind && w.subject_key === key) || null;

export const newCountOf = (s) => s.watches.filter((w) => w.is_new).length;

export function loadWatches({ force = false } = {}) {
  if (!canUseServer()) return Promise.resolve();
  const s = current();
  if (!force) {
    if (s.watchStatus === 'loading') return watchPromise || Promise.resolve();
    if (s.watchStatus === 'ready' && Date.now() - s.watchAt < WATCH_TTL_MS) return Promise.resolve();
    if (s.watchStatus === 'error' && Date.now() - s.watchAt < RETRY_AFTER_ERROR_MS) return Promise.resolve();
  }
  const who = s.authKey;
  set({ watchStatus: 'loading' });
  watchPromise = Promise.resolve()
    .then(() => cabinetApi.listWatches())
    .then((res) => {
      if (current().authKey !== who) return;
      set({
        watches: Array.isArray(res?.items) ? res.items : [],
        watchLimit: res?.limit || 50,
        watchStatus: 'ready',
        watchAt: Date.now(),
      });
    })
    .catch(() => {
      if (current().authKey === who) set({ watchStatus: 'error', watchAt: Date.now() });
    });
  return watchPromise;
}

export async function addWatch(kind, key) {
  if (!canUseServer()) return { ok: false, reason: isEnabled() ? 'auth_required' : 'disabled' };
  try {
    const res = await cabinetApi.addWatch(kind, key);
    const item = res?.item;
    if (item) {
      const rest = current().watches.filter((w) => !(w.subject_kind === item.subject_kind && w.subject_key === item.subject_key));
      set({ watches: [item, ...rest], watchStatus: current().watchStatus === 'idle' ? 'ready' : current().watchStatus, watchAt: current().watchAt || Date.now() });
    }
    return { ok: true, created: res?.created !== false, item };
  } catch (err) {
    return { ok: false, reason: cabinetErrorCode(err) };
  }
}

export async function removeWatch(kind, key) {
  if (!canUseServer()) return { ok: false, reason: 'auth_required' };
  const removed = current().watches.filter((w) => w.subject_kind === kind && w.subject_key === key);
  set({ watches: current().watches.filter((w) => !(w.subject_kind === kind && w.subject_key === key)) });
  try {
    await cabinetApi.deleteWatchByKey(kind, key);
    return { ok: true };
  } catch (err) {
    set({ watches: [...removed, ...current().watches] });
    return { ok: false, reason: cabinetErrorCode(err) };
  }
}

/** Отметить новое прочитанным (без `ids` — всё). Значок гаснет сразу. */
export async function markSeen(ids) {
  if (!canUseServer()) return { ok: false, reason: 'auth_required' };
  const before = current().watches;
  const hit = (w) => !ids || !ids.length || ids.includes(w.id);
  set({ watches: before.map((w) => (hit(w) ? { ...w, is_new: false, last_seen_date: w.latest_date || w.last_seen_date } : w)) });
  try {
    await cabinetApi.markFeedSeen(ids);
    return { ok: true };
  } catch (err) {
    set({ watches: before });
    return { ok: false, reason: cabinetErrorCode(err) };
  }
}
