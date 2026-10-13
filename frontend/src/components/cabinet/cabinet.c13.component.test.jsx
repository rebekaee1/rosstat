// @vitest-environment jsdom
// Круг 13, зона R-CAB: правки, найденные при проходе по кабинету вошедшим пользователем.
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchCabinetConfig: vi.fn(),
  listSaved: vi.fn(),
  listWatches: vi.fn(),
  listExports: vi.fn(),
  fetchCalendarFeed: vi.fn(),
  fetchPrefs: vi.fn(),
  savePrefs: vi.fn(),
  deleteExport: vi.fn(),
  clearExports: vi.fn(),
  createCalendarFeed: vi.fn(),
  deleteCalendarFeed: vi.fn(),
  calendarFeedLinks: vi.fn(() => ({ https: '', webcal: '' })),
  deleteSavedById: vi.fn(),
  renameSaved: vi.fn(),
  deleteSavedByKey: vi.fn(),
  importSaved: vi.fn(),
  saveItem: vi.fn(),
}));
vi.mock('../../lib/cabinetApi', () => api);
vi.mock('../../context/authContext', () => ({ useAuth: () => ({ user: { id: 'u1', email: 'a@b.c' }, isAuthed: true, isLoading: false }) }));
vi.mock('../../lib/worldApi', () => ({ useWorldCountries: () => ({ data: { countries: [{ slug: 'turkey', name_ru: 'Турция', name_en: 'Türkiye', code: 'TR' }] } }) }));
vi.mock('../../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../../i18n', () => ({ useT: () => (key, vars) => (vars ? `${key} ${JSON.stringify(vars)}` : key), useLocale: () => ({ locale: 'en' }) }));

const store = await import('../../lib/cabinetStore');
const { default: PrefsForm } = await import('./PrefsForm');
const { default: ExportHistory } = await import('./ExportHistory');
const { exportHref } = await import('../../lib/cabinetItems');
const { default: CalendarFeed } = await import('./CalendarFeed');
const { default: SavedList } = await import('./SavedList');
const { CabinetSubjectActions } = await import('./CabinetWiring');
const { russiaIndicatorSubject } = await import('../../lib/cabinetSubjects');

const ENABLED = { enabled: true, features: {}, limits: { saved: 200, watches: 50 } };

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  store.__resetCabinetStore();
  api.fetchCabinetConfig.mockResolvedValue(ENABLED);
  api.listSaved.mockResolvedValue({ items: [] });
  api.listWatches.mockResolvedValue({ items: [], limit: 50 });
  api.listExports.mockResolvedValue({ items: [] });
  api.fetchPrefs.mockResolvedValue({ data: {}, updated_at: null });
  api.fetchCalendarFeed.mockResolvedValue({ active: false });
});
afterEach(cleanup);

const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('C2: настройки кабинета', () => {
  it('в форме только то, что сайт применяет: формат чисел, валюта конвертера, главная страна', async () => {
    inRouter(<PrefsForm />);
    await screen.findByText('c12u.prefs.intro');
    expect(screen.getByText('c11b.prefs.numbers')).toBeTruthy();
    expect(screen.getByText('c11b.prefs.currency')).toBeTruthy();
    expect(screen.getByText('c11b.prefs.country')).toBeTruthy();
    // язык (его задаёт адрес страницы), единицы и темы рассылки из формы убраны: они ничего не меняли
    for (const gone of ['c11b.prefs.locale', 'c11b.prefs.units', 'c11b.prefs.topics', 'c11b.prefs.topicsNote']) {
      expect(screen.queryByText(gone)).toBeNull();
    }
    // рубль не предлагается: конвертер и так открывается парой USD → RUB
    expect(screen.queryByRole('button', { name: 'RUB' })).toBeNull();
    for (const code of ['USD', 'EUR', 'CNY']) expect(screen.getByRole('button', { name: code })).toBeTruthy();
  });

  it('сохранение не стирает ранее сохранённые язык, единицы и темы', async () => {
    api.fetchPrefs.mockResolvedValue({ data: { locale: 'ru', units: 'short', newsletter_topics: ['rates'] }, updated_at: null });
    api.savePrefs.mockResolvedValue({ data: { locale: 'ru', units: 'short', newsletter_topics: ['rates'], currency: 'EUR' }, updated_at: 'x' });
    inRouter(<PrefsForm />);
    await screen.findByText('c12u.prefs.intro');
    fireEvent.click(screen.getByRole('button', { name: 'EUR' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));
    await waitFor(() => expect(api.savePrefs).toHaveBeenCalledWith({
      locale: 'ru', units: 'short', newsletter_topics: ['rates'], currency: 'EUR',
    }));
  });
});

describe('история выгрузок: куда ведёт строка', () => {
  it('адрес, записанный при выгрузке, главнее', () => {
    expect(exportHref({ source: 'compare', params: { href: '/compare?codes=a', codes: ['b'] } })).toBe('/compare?codes=a');
  });

  it('старая запись сравнения без адреса восстанавливается по кодам рядов', () => {
    expect(exportHref({ source: 'compare', params: { codes: ['w:united-states:us-cpi-all', 'brent'], rep: 'x' } }))
      .toBe('/compare?codes=w%3Aunited-states%3Aus-cpi-all,brent&rep=x');
  });

  it('старая запись рейтинга ведёт на рейтинг за тот год', () => {
    expect(exportHref({ source: 'rating', subject_key: 'gdp-usd:2025', params: {} })).toBe('/world/rating/gdp-usd/2025');
  });

  it('чужой адрес и запись без источника ссылки не получают', () => {
    expect(exportHref({ source: 'table', params: { href: '//evil.test/x' } })).toBeNull();
    expect(exportHref({ source: 'table', params: {} })).toBeNull();
    expect(exportHref({ source: 'rating', subject_key: 'a b:2025', params: {} })).toBeNull();
  });

  it('в строке есть кнопка «Открыть страницу»', async () => {
    api.listExports.mockResolvedValue({ items: [{
      id: 'e1', source: 'rating', subject_key: 'gdp-usd:2025', format: 'csv', rows_count: 55, created_at: '2026-10-12T10:00:00Z',
      params: { title: 'GDP by country, 2025', filename: 'rating_gdp-usd_2025.csv' },
    }] });
    inRouter(<ExportHistory />);
    const open = await screen.findByRole('link', { name: /c11b\.export\.openAria/ });
    expect(open.getAttribute('href')).toBe('/world/rating/gdp-usd/2025');
  });
});

describe('личный календарь', () => {
  it('без российских слежений подсказывает, что календарь пока пуст', async () => {
    inRouter(<CalendarFeed hasRussian={false} />);
    await screen.findByText('c11b.cal.noRussian');
  });

  it('с российским слежением подсказки нет', async () => {
    inRouter(<CalendarFeed hasRussian />);
    await screen.findByText('c11b.cal.intro');
    expect(screen.queryByText('c11b.cal.noRussian')).toBeNull();
  });
});

describe('«Мои сравнения»: счётчик', () => {
  it('показывает и число сравнений, и общий предел с избранным', async () => {
    api.listSaved.mockResolvedValue({ items: [
      { id: 'c1', kind: 'comparison', item_key: 'codes=a', title: 'Сравнение', payload: { path: '/compare?codes=a' }, created_at: '2026-10-12T10:00:00Z' },
      { id: 'i1', kind: 'indicator', item_key: 'brent', title: 'Brent', payload: {}, created_at: '2026-10-12T10:00:00Z' },
      { id: 'i2', kind: 'country', item_key: 'turkey', title: 'Turkey', payload: {}, created_at: '2026-10-12T10:00:00Z' },
    ] });
    inRouter(<SavedList mode="comparisons" />);
    await screen.findByText('c11b.saved.countShared {"n":1,"total":3,"max":200}');
  });
});

describe('карточка события календаря', () => {
  it('колокольчик с подписью «Следить»: одинокая иконка не поясняла, что она делает', async () => {
    inRouter(<CabinetSubjectActions subject={russiaIndicatorSubject('key_rate', 'Ключевая ставка', { only: 'watch', variant: 'button' })} />);
    await screen.findByText('c11b.watch.off');
    expect(screen.queryByRole('button', { name: /c11b\.save/ })).toBeNull();
  });

  it('без variant остаётся иконкой (шапка показателя)', async () => {
    inRouter(<CabinetSubjectActions subject={russiaIndicatorSubject('key_rate', 'Ключевая ставка', { only: 'watch' })} />);
    await screen.findByRole('button', { name: /c11b\.watch\.onAria/ });
    expect(screen.queryByText('c11b.watch.off')).toBeNull();
  });
});
