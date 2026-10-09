// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchCabinetConfig: vi.fn(),
  listSaved: vi.fn(),
  saveItem: vi.fn(),
  deleteSavedByKey: vi.fn(),
  deleteSavedById: vi.fn(),
  renameSaved: vi.fn(),
  importSaved: vi.fn(),
  listWatches: vi.fn(),
  addWatch: vi.fn(),
  deleteWatchByKey: vi.fn(),
  markFeedSeen: vi.fn(),
}));
vi.mock('./cabinetApi', () => api);

const store = await import('./cabinetStore');

const ENABLED = { enabled: true, features: { saved: true }, limits: { saved: 200, watches: 50 } };
const flush = () => new Promise((r) => setTimeout(r, 0));
const row = (n, extra = {}) => ({
  id: `id${n}`, kind: 'country', item_key: `c${n}`, title: `Страна ${n}`, payload: {}, created_at: `2026-10-0${n}T10:00:00Z`, ...extra,
});

async function boot({ config = ENABLED, auth = 'guest' } = {}) {
  api.fetchCabinetConfig.mockResolvedValue(config);
  await store.ensureConfig();
  store.bindAuth(auth);
  await flush();
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  store.__resetCabinetStore();
  api.listSaved.mockResolvedValue({ items: [] });
  api.listWatches.mockResolvedValue({ items: [], limit: 50 });
});

describe('настройка', () => {
  it('без ответа сервера кабинета нет', async () => {
    api.fetchCabinetConfig.mockRejectedValue(new Error('down'));
    await store.ensureConfig();
    expect(store.getState().config.enabled).toBe(false);
    expect(await store.saveItem({ kind: 'country', itemKey: 'turkey' })).toEqual({ ok: false, reason: 'disabled' });
  });

  it('выключенный кабинет не даёт ни гостю, ни вошедшему ничего записать и не ходит за списками', async () => {
    await boot({ config: { enabled: false, features: {}, limits: {} }, auth: 'u1' });
    expect(api.listSaved).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(store.GUEST_KEY)).toBeNull();
    expect((await store.saveItem({ kind: 'country', itemKey: 'turkey' })).reason).toBe('disabled');
  });

  it('ответ настройки не запрашивается второй раз', async () => {
    await boot();
    await store.ensureConfig();
    expect(api.fetchCabinetConfig).toHaveBeenCalledTimes(1);
  });
});

describe('гость', () => {
  it('сохраняет в браузере, повтор не дублирует, убрать можно', async () => {
    await boot();
    const first = await store.saveItem({ kind: 'country', itemKey: 'turkey', title: 'Турция' });
    expect(first).toMatchObject({ ok: true, local: true, created: true });
    await store.saveItem({ kind: 'country', itemKey: 'turkey' });
    const raw = JSON.parse(window.localStorage.getItem(store.GUEST_KEY));
    expect(raw).toHaveLength(1);
    expect(raw[0].title).toBe('Турция');
    expect(api.saveItem).not.toHaveBeenCalled();
    expect(store.findSavedIn(store.getState(), 'country', 'turkey')).toBeTruthy();
    await store.removeSaved('country', 'turkey');
    expect(window.localStorage.getItem(store.GUEST_KEY)).toBeNull();
  });

  it('предел гостя', async () => {
    await boot();
    for (let i = 0; i < store.GUEST_LIMIT; i += 1) {
      await store.saveItem({ kind: 'country', itemKey: `c${i}` });
    }
    expect((await store.saveItem({ kind: 'country', itemKey: 'extra' })).reason).toBe('limit_reached');
  });

  it('слежение гостю недоступно', async () => {
    await boot();
    expect((await store.addWatch('indicator', 'cpi')).reason).toBe('auth_required');
    expect(api.addWatch).not.toHaveBeenCalled();
  });
});

describe('вошедший', () => {
  it('подгружает сохранённое и сохраняет сразу, откатывая при отказе сервера', async () => {
    api.listSaved.mockResolvedValue({ items: [row(1)] });
    await boot({ auth: 'u1' });
    expect(store.getState().saved).toHaveLength(1);

    api.saveItem.mockResolvedValue({ item: row(2), created: true });
    const ok = await store.saveItem({ kind: 'country', itemKey: 'c2', title: 'Страна 2' });
    expect(ok).toMatchObject({ ok: true, created: true });
    expect(store.getState().saved.map((r) => r.item_key).sort()).toEqual(['c1', 'c2']);

    api.saveItem.mockRejectedValue({ response: { status: 409, data: { detail: { code: 'limit_reached' } } } });
    const bad = await store.saveItem({ kind: 'country', itemKey: 'c3' });
    expect(bad).toEqual({ ok: false, reason: 'limit_reached' });
    expect(store.getState().saved.some((r) => r.item_key === 'c3')).toBe(false);
  });

  it('удаление возвращает строку, если сервер отказал', async () => {
    api.listSaved.mockResolvedValue({ items: [row(1), row(2)] });
    await boot({ auth: 'u1' });
    api.deleteSavedByKey.mockRejectedValue({});
    const res = await store.removeSaved('country', 'c1');
    expect(res.ok).toBe(false);
    expect(store.getState().saved).toHaveLength(2);
    api.deleteSavedByKey.mockResolvedValue({ ok: true });
    await store.removeSaved('country', 'c1');
    expect(store.getState().saved.map((r) => r.item_key)).toEqual(['c2']);
  });

  it('переименование и удаление по номеру записи', async () => {
    api.listSaved.mockResolvedValue({ items: [row(1)] });
    await boot({ auth: 'u1' });
    api.renameSaved.mockResolvedValue({ item: row(1, { title: 'Новое имя' }) });
    expect((await store.renameSaved('id1', ' Новое имя ')).ok).toBe(true);
    expect(store.getState().saved[0].title).toBe('Новое имя');
    expect((await store.renameSaved('id1', '   ')).ok).toBe(false);
    api.deleteSavedById.mockResolvedValue({ ok: true });
    expect((await store.removeSavedById('id1')).ok).toBe(true);
    expect(store.getState().saved).toEqual([]);
  });

  it('смена человека сбрасывает чужие данные', async () => {
    api.listSaved.mockResolvedValue({ items: [row(1)] });
    await boot({ auth: 'u1' });
    api.listSaved.mockResolvedValue({ items: [] });
    store.bindAuth('u2');
    expect(store.getState().saved).toEqual([]);
    await flush();
    expect(api.listSaved).toHaveBeenCalledTimes(2);
  });
});

describe('перенос избранного гостя при входе', () => {
  const seedGuest = (n) => window.localStorage.setItem(store.GUEST_KEY, JSON.stringify(
    Array.from({ length: n }, (_, i) => ({ kind: 'country', item_key: `g${i}`, title: `G${i}`, payload: null, created_at: '2026-10-01T00:00:00Z' })),
  ));

  it('отправляет пачками по 100, чистит браузер и запоминает итог', async () => {
    seedGuest(150);
    store.__resetCabinetStore();
    api.importSaved.mockResolvedValue({ imported: 100, skipped: 0, limit_reached: false });
    await boot({ auth: 'u1' });
    await flush();
    expect(api.importSaved).toHaveBeenCalledTimes(2);
    expect(api.importSaved.mock.calls[0][0]).toHaveLength(100);
    expect(api.importSaved.mock.calls[1][0]).toHaveLength(50);
    expect(window.localStorage.getItem(store.GUEST_KEY)).toBeNull();
    expect(store.getState().guest).toEqual([]);
    expect(store.getState().importResult).toMatchObject({ imported: 200, limitReached: false });
  });

  it('при сбое записи остаются в браузере для следующей попытки', async () => {
    seedGuest(3);
    store.__resetCabinetStore();
    api.importSaved.mockRejectedValue(new Error('offline'));
    await boot({ auth: 'u1' });
    await flush();
    expect(JSON.parse(window.localStorage.getItem(store.GUEST_KEY))).toHaveLength(3);
    expect(store.getState().importResult).toBeNull();
  });

  it('гостю ничего не отправляется', async () => {
    seedGuest(2);
    store.__resetCabinetStore();
    await boot({ auth: 'guest' });
    await flush();
    expect(api.importSaved).not.toHaveBeenCalled();
  });
});

describe('слежение', () => {
  const watch = (n, extra = {}) => ({
    id: `w${n}`, subject_kind: 'indicator', subject_key: `k${n}`, title: `Ряд ${n}`, is_new: false, available: true, latest_date: '2026-09-01', ...extra,
  });

  it('читает список один раз за 5 минут и считает новое', async () => {
    api.listWatches.mockResolvedValue({ items: [watch(1, { is_new: true }), watch(2)], limit: 50 });
    await boot({ auth: 'u1' });
    await store.loadWatches();
    await store.loadWatches();
    expect(api.listWatches).toHaveBeenCalledTimes(1);
    expect(store.newCountOf(store.getState())).toBe(1);
    await store.loadWatches({ force: true });
    expect(api.listWatches).toHaveBeenCalledTimes(2);
  });

  it('добавляет, убирает с откатом и отмечает прочитанным', async () => {
    api.listWatches.mockResolvedValue({ items: [watch(1, { is_new: true })], limit: 50 });
    await boot({ auth: 'u1' });
    await store.loadWatches();

    api.addWatch.mockResolvedValue({ item: watch(2), created: true });
    expect((await store.addWatch('indicator', 'k2')).ok).toBe(true);
    expect(store.findWatchIn(store.getState(), 'indicator', 'k2')).toBeTruthy();

    api.addWatch.mockRejectedValue({ response: { status: 409, data: { detail: { code: 'limit_reached' } } } });
    expect((await store.addWatch('indicator', 'k9')).reason).toBe('limit_reached');

    api.deleteWatchByKey.mockRejectedValue({});
    expect((await store.removeWatch('indicator', 'k2')).ok).toBe(false);
    expect(store.findWatchIn(store.getState(), 'indicator', 'k2')).toBeTruthy();
    api.deleteWatchByKey.mockResolvedValue({ ok: true });
    await store.removeWatch('indicator', 'k2');
    expect(store.findWatchIn(store.getState(), 'indicator', 'k2')).toBeNull();

    api.markFeedSeen.mockResolvedValue({ new_count: 0 });
    await store.markSeen();
    expect(store.newCountOf(store.getState())).toBe(0);
    expect(api.markFeedSeen).toHaveBeenCalledWith(undefined);
  });

  it('при отказе отметка «прочитано» возвращается', async () => {
    api.listWatches.mockResolvedValue({ items: [watch(1, { is_new: true })], limit: 50 });
    await boot({ auth: 'u1' });
    await store.loadWatches();
    api.markFeedSeen.mockRejectedValue({});
    expect((await store.markSeen(['w1'])).ok).toBe(false);
    expect(store.newCountOf(store.getState())).toBe(1);
  });
});
