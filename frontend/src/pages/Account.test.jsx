// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import Account from './Account';
import { logoutUser, deleteAccount } from '../lib/api';
import { __resetCabinetStore } from '../lib/cabinetStore';
import * as cabinetApi from '../lib/cabinetApi';

const mocks = vi.hoisted(() => ({ setUser: vi.fn(), refetch: vi.fn() }));
vi.mock('../lib/useMeta', () => ({ default: () => {} }));
vi.mock('../context/authContext', () => ({ useAuth: () => ({ user: { id: 'u1', email: 'test@example.com', identities: [] }, isAuthed: true, ...mocks }) }));
vi.mock('../lib/api', () => ({ logoutUser: vi.fn(), deleteAccount: vi.fn(), logoutAll: vi.fn(), submitFeedback: vi.fn(), updateNewsletter: vi.fn(), updateProfile: vi.fn() }));
vi.mock('../lib/cabinetApi', () => ({
  fetchCabinetConfig: vi.fn(),
  listSaved: vi.fn(),
  listWatches: vi.fn(),
  listExports: vi.fn(),
  fetchCalendarFeed: vi.fn(),
  fetchPrefs: vi.fn(),
  savePrefs: vi.fn(),
  deleteSavedById: vi.fn(),
  renameSaved: vi.fn(),
  deleteWatchByKey: vi.fn(),
  markFeedSeen: vi.fn(),
  importSaved: vi.fn(),
  deleteExport: vi.fn(),
  clearExports: vi.fn(),
  createCalendarFeed: vi.fn(),
  deleteCalendarFeed: vi.fn(),
  calendarFeedLinks: vi.fn(() => ({ https: '', webcal: '' })),
}));
vi.mock('../lib/worldApi', () => ({ useWorldCountries: () => ({ data: { countries: [{ slug: 'turkey', name_ru: 'Турция', name_en: 'Türkiye', code: 'TR' }] } }) }));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useT: () => (key, vars) => (vars ? `${key} ${JSON.stringify(vars)}` : key), useLocale: () => ({ locale: 'ru' }) }));

const ENABLED = { enabled: true, features: {}, limits: { saved: 200, watches: 50 } };
const DISABLED = { enabled: false, features: {}, limits: {} };

beforeEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
  window.localStorage.clear();
  __resetCabinetStore();
  cabinetApi.fetchCabinetConfig.mockResolvedValue(DISABLED);
  cabinetApi.listSaved.mockResolvedValue({ items: [] });
  cabinetApi.listWatches.mockResolvedValue({ items: [], limit: 50 });
  cabinetApi.listExports.mockResolvedValue({ items: [] });
  cabinetApi.fetchCalendarFeed.mockResolvedValue({ active: false });
  cabinetApi.fetchPrefs.mockResolvedValue({ data: {}, updated_at: null });
});
afterEach(cleanup);

const renderAccount = (entry = '/account') => render(
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/account" element={<Account />} />
        <Route path="/" element={<p>Home after success</p>} />
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>,
);

describe('account session-ending actions', () => {
  it('account.logout success', async () => {
    logoutUser.mockResolvedValueOnce({});
    renderAccount();
    fireEvent.click(await screen.findByRole('button', { name: 'account.logout' }));
    await waitFor(() => expect(logoutUser).toHaveBeenCalledOnce());
    await screen.findByText('Home after success');
    expect(mocks.setUser).toHaveBeenCalledWith(null);
    expect(mocks.refetch).not.toHaveBeenCalled();
  });

  it('account.logout failure keeps the session and the button', async () => {
    logoutUser.mockRejectedValueOnce(new Error('server unavailable'));
    renderAccount();
    fireEvent.click(await screen.findByRole('button', { name: 'account.logout' }));
    await screen.findByText('account.errorGeneric');
    expect(mocks.setUser).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'account.logout' })).toBeTruthy();
    expect(mocks.refetch).not.toHaveBeenCalled();
  });

  it('удаление аккаунта не срабатывает, пока не введено слово', async () => {
    deleteAccount.mockResolvedValueOnce({});
    renderAccount();
    fireEvent.click(await screen.findByRole('button', { name: 'account.delete' }));
    const confirm = screen.getByRole('button', { name: 'c11b.account.deleteCta' });
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText('c11b.account.deleteWord'), { target: { value: 'c11b.account.deleteWord' } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => expect(deleteAccount).toHaveBeenCalledOnce());
    await screen.findByText('Home after success');
    expect(mocks.setUser).toHaveBeenCalledWith(null);
  });

  it('account.delete failure: аккаунт остаётся, показано сообщение', async () => {
    deleteAccount.mockRejectedValueOnce(new Error('server unavailable'));
    renderAccount();
    fireEvent.click(await screen.findByRole('button', { name: 'account.delete' }));
    fireEvent.change(screen.getByPlaceholderText('c11b.account.deleteWord'), { target: { value: 'c11b.account.deleteWord' } });
    fireEvent.click(screen.getByRole('button', { name: 'c11b.account.deleteCta' }));
    await screen.findByText('account.errorGeneric');
    expect(mocks.setUser).not.toHaveBeenCalled();
  });
});

describe('кабинет выключен', () => {
  it('остаётся прежняя страница без вкладок и заглушек', async () => {
    renderAccount('/account?tab=watches');
    await screen.findByText('account.profile');
    expect(screen.queryByRole('tablist')).toBeNull();
    expect(screen.queryByText('c11b.tabs.saved')).toBeNull();
    expect(screen.getByText('account.intro')).toBeTruthy();
    expect(cabinetApi.listSaved).not.toHaveBeenCalled();
    expect(cabinetApi.listWatches).not.toHaveBeenCalled();
  });

  it('у неактивной «Отправить» есть подсказка', async () => {
    renderAccount();
    const send = await screen.findByRole('button', { name: 'account.feedbackSend' });
    expect(send.disabled).toBe(true);
    expect(send.getAttribute('title')).toBe('c11b.account.feedbackHint');
  });
});

describe('кабинет включён', () => {
  beforeEach(() => { cabinetApi.fetchCabinetConfig.mockResolvedValue(ENABLED); });

  it('по умолчанию открывает «Избранное» и показывает все разделы', async () => {
    cabinetApi.listSaved.mockResolvedValue({
      items: [{ id: 's1', kind: 'country', item_key: 'turkey', title: 'Турция', payload: { path: '/turkey' }, created_at: '2026-10-01T10:00:00Z' }],
    });
    renderAccount();
    expect(await screen.findByText('Турция')).toBeTruthy();
    const tabs = screen.getAllByRole('tab').map((el) => el.textContent);
    expect(tabs).toEqual(['c11b.tabs.saved', 'c11b.tabs.compare', 'c11b.tabs.watches', 'c11b.tabs.exports', 'c11b.tabs.prefs', 'c11b.tabs.profile']);
    expect(screen.getByRole('tab', { name: 'c11b.tabs.saved' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText('Турция').closest('a').getAttribute('href')).toBe('/turkey');
    expect(screen.queryByText('account.profile')).toBeNull();
  });

  it('вкладка берётся из адреса, переключение меняет адрес и содержимое', async () => {
    renderAccount('/account?tab=exports');
    await screen.findByText('c11b.export.empty');
    fireEvent.click(screen.getByRole('tab', { name: 'c11b.tabs.profile' }));
    await screen.findByText('account.profile');
  });

  it('ссылка /account#feedback ведёт в профиль', async () => {
    renderAccount('/account#feedback');
    await screen.findByText('account.feedback');
    expect(screen.getByRole('tab', { name: 'c11b.tabs.profile' }).getAttribute('aria-selected')).toBe('true');
  });

  it('«Слежу»: новое отдельным блоком, значок на вкладке, можно отметить прочитанным и перестать следить', async () => {
    cabinetApi.listWatches.mockResolvedValue({
      items: [
        { id: 'w1', subject_kind: 'indicator', subject_key: 'cpi_yoy', title: 'Инфляция', unit: '%', frequency: 'monthly', available: true, latest_date: '2026-09-01', latest_value: 6.3, is_new: true },
        { id: 'w2', subject_kind: 'indicator', subject_key: 'gdp', title: 'ВВП', available: false, latest_date: null, is_new: false },
      ],
      limit: 50,
    });
    cabinetApi.markFeedSeen.mockResolvedValue({ new_count: 0 });
    cabinetApi.deleteWatchByKey.mockResolvedValue({ ok: true });
    renderAccount('/account?tab=watches');
    await screen.findByText('c11b.feed.title');
    expect(screen.getByRole('tab', { name: /c11b\.tabs\.watches/ }).textContent).toContain('1');
    expect(screen.getByText(/c11b\.watch\.gone/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'c11b.feed.seenAll' }));
    await waitFor(() => expect(cabinetApi.markFeedSeen).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText('c11b.feed.title')).toBeNull());
    fireEvent.click(screen.getAllByRole('button', { name: /c11b\.watch\.stopAria/ })[1]);
    await waitFor(() => expect(cabinetApi.deleteWatchByKey).toHaveBeenCalledWith('indicator', 'gdp'));
  });

  it('«Выгрузки»: строка со ссылкой на страницу и очисткой по подтверждению', async () => {
    cabinetApi.listExports.mockResolvedValue({
      items: [{ id: 'e1', source: 'table', subject_key: 'cpi', format: 'csv', rows_count: 120, created_at: '2026-10-02T10:00:00Z', params: { filename: 'cpi_yoy_all.csv', href: '/russia/indicator/cpi_yoy' } }],
    });
    cabinetApi.clearExports.mockResolvedValue({ ok: true, removed: 1 });
    renderAccount('/account?tab=exports');
    expect(await screen.findByText('cpi yoy all')).toBeTruthy();
    expect(screen.getByRole('link', { name: /c11b\.export\.openAria/ }).getAttribute('href')).toBe('/russia/indicator/cpi_yoy');
    fireEvent.click(screen.getByRole('button', { name: 'c11b.export.clear' }));
    fireEvent.click(screen.getByRole('button', { name: 'c11b.export.clearYes' }));
    await waitFor(() => expect(cabinetApi.clearExports).toHaveBeenCalled());
    await screen.findByText('c11b.export.empty');
  });

  it('«Мои сравнения»: показывает только сравнения, можно переименовать', async () => {
    cabinetApi.listSaved.mockResolvedValue({
      items: [
        { id: 's1', kind: 'comparison', item_key: 'codes=a,b', title: 'Россия и Турция', payload: { names: ['Россия', 'Турция'] }, created_at: '2026-10-01T10:00:00Z' },
        { id: 's2', kind: 'country', item_key: 'turkey', title: 'Турция', payload: {}, created_at: '2026-10-01T10:00:00Z' },
      ],
    });
    cabinetApi.renameSaved.mockResolvedValue({ item: { id: 's1', kind: 'comparison', item_key: 'codes=a,b', title: 'Моё', payload: {}, created_at: '2026-10-01T10:00:00Z' } });
    renderAccount('/account?tab=compare');
    await screen.findByText('Россия и Турция');
    expect(screen.queryByText('Турция', { selector: '.c11b-row__title' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /c11b\.row\.renameAria/ }));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Моё' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(cabinetApi.renameSaved).toHaveBeenCalledWith('s1', 'Моё'));
    await screen.findByText('Моё');
  });

  it('«Настройки»: сохраняет только допустимые поля', async () => {
    cabinetApi.fetchPrefs.mockResolvedValue({ data: { locale: 'ru' }, updated_at: null });
    cabinetApi.savePrefs.mockResolvedValue({ data: { locale: 'ru', currency: 'EUR' }, updated_at: '2026-10-09T10:00:00Z' });
    renderAccount('/account?tab=prefs');
    await screen.findByText('c11b.prefs.intro');
    fireEvent.click(screen.getByRole('button', { name: 'EUR' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));
    await waitFor(() => expect(cabinetApi.savePrefs).toHaveBeenCalledWith({ locale: 'ru', currency: 'EUR' }));
    await screen.findByText('c11b.prefs.saved');
  });
});
