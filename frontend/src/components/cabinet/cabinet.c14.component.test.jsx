// @vitest-environment jsdom
// 14.11.2026, включение полного кабинета: правки, найденные при проходе всего пути пользователя.
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchCabinetConfig: vi.fn(),
  listSaved: vi.fn(),
  listWatches: vi.fn(),
  fetchCalendarFeed: vi.fn(),
  markFeedSeen: vi.fn(),
  deleteWatchByKey: vi.fn(),
  importSaved: vi.fn(),
  createCalendarFeed: vi.fn(),
  deleteCalendarFeed: vi.fn(),
  calendarFeedLinks: vi.fn(() => ({ https: '', webcal: '' })),
}));
const auth = vi.hoisted(() => ({ user: { id: 'u1', email: 'a@b.c', identities: [] } }));
vi.mock('../../lib/cabinetApi', () => api);
vi.mock('../../context/authContext', () => ({
  useAuth: () => ({ user: auth.user, isAuthed: true, isLoading: false, setUser: vi.fn(), refetch: vi.fn() }),
}));
vi.mock('../../lib/api', () => ({
  logoutUser: vi.fn(), logoutAll: vi.fn(), deleteAccount: vi.fn(), submitFeedback: vi.fn(), updateNewsletter: vi.fn(),
  updateProfile: vi.fn(), fetchAccountExport: vi.fn(), resendVerifyEmail: vi.fn(),
}));
vi.mock('../../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../../i18n', () => ({ useT: () => (key, vars) => (vars ? `${key} ${JSON.stringify(vars)}` : key), useLocale: () => ({ locale: 'ru' }) }));

const store = await import('../../lib/cabinetStore');
const { default: WatchList } = await import('./WatchList');
const { default: ProfilePanel } = await import('./ProfilePanel');
const { default: SavedList } = await import('./SavedList');

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  store.__resetCabinetStore();
  api.fetchCabinetConfig.mockResolvedValue({ enabled: true, features: {}, limits: { saved: 200, watches: 50 } });
  api.listSaved.mockResolvedValue({ items: [] });
  api.fetchCalendarFeed.mockResolvedValue({ active: false });
});
afterEach(cleanup);

const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('«Слежу»: новое не повторяется в общем списке', () => {
  it('ряд с новым значением стоит один раз — в блоке «Что вышло»', async () => {
    api.listWatches.mockResolvedValue({
      items: [
        { id: 'w1', subject_kind: 'indicator', subject_key: 'cpi', title: 'Индекс цен', unit: '%', frequency: 'monthly', available: true, latest_date: '2026-09-01', latest_value: 6.35, value_basis: 'yoy', is_new: true },
        { id: 'w2', subject_kind: 'indicator', subject_key: 'gdp', title: 'ВВП', unit: 'млрд руб.', frequency: 'quarterly', available: true, latest_date: '2026-07-01', latest_value: 50, is_new: false },
      ],
      limit: 50,
    });
    inRouter(<WatchList />);
    await screen.findByText('c11b.feed.title');
    expect(screen.getAllByText('Индекс цен')).toHaveLength(1);
    expect(screen.getAllByText('ВВП')).toHaveLength(1);
    expect(screen.getByText('c11b.watch.title')).toBeTruthy();
    expect(screen.getByText(/c11b\.watch\.count/).textContent).toContain('"n":2');
  });

  it('индекс цен подписан «год к году», обычный ряд — без подписи', async () => {
    api.listWatches.mockResolvedValue({
      items: [
        { id: 'w1', subject_kind: 'indicator', subject_key: 'cpi', title: 'Индекс цен', unit: '%', frequency: 'monthly', available: true, latest_date: '2026-09-01', latest_value: 6.35, value_basis: 'yoy', is_new: false },
        { id: 'w2', subject_kind: 'indicator', subject_key: 'gdp', title: 'ВВП', unit: '%', frequency: 'quarterly', available: true, latest_date: '2026-07-01', latest_value: 1.2, is_new: false },
      ],
      limit: 50,
    });
    inRouter(<WatchList />);
    expect(await screen.findByText(/c11b\.watch\.latestYoy/)).toBeTruthy();
    expect(screen.getAllByText(/c11b\.watch\.latest /)).toHaveLength(1);
  });

  it('всё новое: заголовок общего списка не висит пустым, счётчик остаётся', async () => {
    api.listWatches.mockResolvedValue({
      items: [{ id: 'w1', subject_kind: 'indicator', subject_key: 'cpi', title: 'Индекс цен', available: true, latest_date: '2026-09-01', latest_value: null, is_new: true }],
      limit: 50,
    });
    inRouter(<WatchList />);
    await screen.findByText('c11b.feed.title');
    expect(screen.queryByText('c11b.watch.title')).toBeNull();
    expect(screen.queryByText('c11b.watch.empty')).toBeNull();
    expect(screen.getByText(/c11b\.watch\.count/)).toBeTruthy();
  });
});

describe('Профиль: плашка «Подтвердите почту» только когда письма уходят', () => {
  const base = { id: 'u1', email: 'a@b.c', identities: [], has_password: true, email_verified: false };

  it('почта сайта выключена — плашки нет (письма не было, кнопка «ещё раз» ничего бы не отправила)', () => {
    auth.user = { ...base, mail_available: false };
    inRouter(<ProfilePanel />);
    expect(screen.queryByTestId('account-verify-email')).toBeNull();
  });

  it('почта включена — плашка есть, подложка холодная, без золота', () => {
    auth.user = { ...base, mail_available: true };
    inRouter(<ProfilePanel />);
    const plate = screen.getByTestId('account-verify-email');
    expect(plate.className).not.toMatch(/champagne|gold/);
  });
});

describe('«Избранное»: кабинет полон, в браузере остались записи гостя', () => {
  it('одна понятная подсказка: сколько осталось и что сделать; без повторной плашки «не всё поместилось»', async () => {
    window.localStorage.setItem(store.GUEST_KEY, JSON.stringify([
      { kind: 'country', item_key: 'g1', title: 'G1', created_at: '2026-10-01T00:00:00Z' },
    ]));
    store.__resetCabinetStore();
    api.fetchCabinetConfig.mockResolvedValue({ enabled: true, features: {}, limits: { saved: 1, watches: 50 } });
    api.listSaved.mockResolvedValue({ items: [{ id: 's1', kind: 'country', item_key: 's1', title: 'Турция', created_at: '2026-10-01T00:00:00Z' }] });
    inRouter(<SavedList />);
    expect(await screen.findByText(/c11b\.import\.pendingFull/)).toBeTruthy();
    expect(screen.queryByText(/c11b\.import\.limit/)).toBeNull();
    expect(api.importSaved).not.toHaveBeenCalled();
  });
});
