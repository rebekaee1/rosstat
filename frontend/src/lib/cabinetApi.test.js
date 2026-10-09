// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const http = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(),
}));
vi.mock('./api', () => ({ default: http }));

const cabinet = await import('./cabinetApi');

beforeEach(() => {
  vi.clearAllMocks();
  for (const fn of Object.values(http)) fn.mockResolvedValue({ data: { ok: true } });
});

describe('cabinetApi', () => {
  it('пути и тела совпадают с контрактом сервера', async () => {
    await cabinet.fetchCabinetConfig();
    expect(http.get).toHaveBeenCalledWith('/cabinet/config', expect.anything());

    await cabinet.saveItem({ kind: 'country', itemKey: 'turkey', title: 'Турция', payload: { path: '/turkey' } });
    expect(http.post).toHaveBeenCalledWith(
      '/cabinet/saved',
      { kind: 'country', item_key: 'turkey', title: 'Турция', payload: { path: '/turkey' } },
      { idempotent: true },
    );

    await cabinet.deleteSavedByKey('country', 'turkey');
    expect(http.delete).toHaveBeenCalledWith('/cabinet/saved', { params: { kind: 'country', key: 'turkey' }, idempotent: true });

    await cabinet.addWatch('indicator', 'cpi_yoy');
    expect(http.post).toHaveBeenCalledWith(
      '/cabinet/watches',
      { subject_kind: 'indicator', subject_key: 'cpi_yoy', channel: 'inapp' },
      { idempotent: true },
    );

    await cabinet.deleteWatchByKey('world', 'x');
    expect(http.delete).toHaveBeenCalledWith('/cabinet/watches', { params: { subject_kind: 'world', subject_key: 'x' }, idempotent: true });

    await cabinet.markFeedSeen();
    expect(http.post).toHaveBeenCalledWith('/cabinet/feed/seen', {}, { idempotent: true });
    await cabinet.markFeedSeen(['a']);
    expect(http.post).toHaveBeenCalledWith('/cabinet/feed/seen', { ids: ['a'] }, { idempotent: true });
  });

  it('пустые название и данные в запрос не попадают (сервер не затрёт существующее)', async () => {
    await cabinet.saveItem({ kind: 'country', itemKey: 'turkey' });
    expect(http.post.mock.calls[0][1]).toEqual({ kind: 'country', item_key: 'turkey' });
  });

  it('перенос гостя шлёт только поля записи', async () => {
    await cabinet.importSaved([{ kind: 'country', item_key: 'a', title: '', payload: null, created_at: 'x', extra: 1 }]);
    expect(http.post.mock.calls[0][1]).toEqual({ items: [{ kind: 'country', item_key: 'a' }] });
  });

  it('выпуск ссылки календаря не повторяется автоматически', async () => {
    await cabinet.createCalendarFeed();
    expect(http.post).toHaveBeenCalledWith('/cabinet/calendar-feed');
  });

  it('адреса подписки строятся из пути ответа и хоста страницы', () => {
    const links = cabinet.calendarFeedLinks('/api/v1/cabinet/calendar.ics?token=abc', 'ru.example.com');
    expect(links.webcal).toBe('webcal://ru.example.com/api/v1/cabinet/calendar.ics?token=abc');
    expect(links.https.endsWith('//ru.example.com/api/v1/cabinet/calendar.ics?token=abc')).toBe(true);
    expect(cabinet.calendarFeedLinks('', 'x')).toEqual({ https: '', webcal: '' });
  });

  it('настройки передаются целиком', async () => {
    await cabinet.savePrefs({ locale: 'ru' });
    expect(http.put).toHaveBeenCalledWith('/cabinet/prefs', { locale: 'ru' }, { idempotent: true });
  });
});
