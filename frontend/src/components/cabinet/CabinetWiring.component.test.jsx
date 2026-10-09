// @vitest-environment jsdom
// Круг 11, интеграция: кнопки кабинета подключены к страницам (слот F, сравнение C, калькуляторы E, шапка G)
// и невидимы, пока кабинет выключен на сервере.
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchCabinetConfig: vi.fn(),
  listSaved: vi.fn(),
  saveItem: vi.fn(),
  deleteSavedByKey: vi.fn(),
  listWatches: vi.fn(),
  addWatch: vi.fn(),
  deleteWatchByKey: vi.fn(),
  importSaved: vi.fn(),
}));
const auth = vi.hoisted(() => ({ value: { user: null, isAuthed: false, isLoading: false } }));
vi.mock('../../lib/cabinetApi', () => api);
vi.mock('../../context/authContext', () => ({ useAuth: () => auth.value }));
vi.mock('gsap', () => ({ default: { fromTo: () => ({ kill: () => {} }) } }));
vi.mock('../IndicatorSearch', () => ({ default: () => <div data-testid="indicator-search-stub" /> }));

const store = await import('../../lib/cabinetStore');
const { CabinetSubjectActions, CompareSaveButton } = await import('./CabinetWiring');
const { default: CabinetActionsSlot } = await import('../CabinetActionsSlot');
const { CabinetActionsContext } = await import('../../lib/cabinetActionsContext');
const { default: CalcSaveSlot } = await import('../CalcSaveSlot');
const { default: Navbar } = await import('../Navbar');
const subjects = await import('../../lib/cabinetSubjects');
const { calcSavedPath, comparisonSaveProps } = await import('../../lib/cabinetWiring');
const { buildLanguageSwitchUrl } = await import('../../i18n/locale');

const ENABLED = { enabled: true, features: {}, limits: { saved: 200, watches: 50 } };
const DISABLED = { enabled: false, features: {}, limits: {} };
const guest = { user: null, isAuthed: false, isLoading: false };
const signedIn = { user: { id: 'u1', email: 'a@b.c', display_name: 'Анна' }, isAuthed: true, isLoading: false };
const render$ = (subject) => <CabinetSubjectActions subject={subject} />;

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  store.__resetCabinetStore();
  auth.value = guest;
  api.fetchCabinetConfig.mockResolvedValue(ENABLED);
  api.listSaved.mockResolvedValue({ items: [] });
  api.listWatches.mockResolvedValue({ items: [], limit: 50 });
});
afterEach(cleanup);

const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);
const withContext = (ui) => inRouter(<CabinetActionsContext.Provider value={render$}>{ui}</CabinetActionsContext.Provider>);
const settle = () => new Promise((r) => setTimeout(r, 10));
const guestSaved = () => JSON.parse(window.localStorage.getItem(store.GUEST_KEY) || '[]');

describe('слот страниц (показатель, страна, регион, рейтинг, календарь)', () => {
  it('кабинет выключен: слот пуст (скрывается по :empty), запросов кроме настройки нет', async () => {
    api.fetchCabinetConfig.mockResolvedValue(DISABLED);
    withContext(<CabinetActionsSlot subject={subjects.russiaIndicatorSubject('cpi', 'Инфляция')} />);
    await waitFor(() => expect(api.fetchCabinetConfig).toHaveBeenCalledTimes(1));
    await settle();
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByTestId('cabinet-actions').innerHTML).toBe('');
    expect(api.listSaved).not.toHaveBeenCalled();
    expect(api.listWatches).not.toHaveBeenCalled();
  });

  it('нет ответа о кабинете: кнопок нет', async () => {
    api.fetchCabinetConfig.mockRejectedValue(new Error('network'));
    withContext(<CabinetActionsSlot subject={subjects.countrySubject('turkey', 'Турция')} />);
    await waitFor(() => expect(api.fetchCabinetConfig).toHaveBeenCalled());
    await settle();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('кабинет включён: звезда и колокольчик у показателя; у события календаря только колокольчик', async () => {
    const { unmount } = withContext(<CabinetActionsSlot subject={subjects.russiaIndicatorSubject('cpi', 'Инфляция')} />);
    expect(await screen.findByRole('button', { name: 'c11b.save.addAria' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'c11b.watch.onAria' })).toBeTruthy();
    unmount();
    withContext(<CabinetActionsSlot subject={subjects.russiaIndicatorSubject('cpi', 'Инфляция', { only: 'watch' })} />);
    expect(await screen.findByRole('button', { name: 'c11b.watch.onAria' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'c11b.save.addAria' })).toBeNull();
  });

  it('у страны и рейтинга только «Сохранить» (за страной не следят)', async () => {
    withContext(<CabinetActionsSlot subject={subjects.countrySubject('turkey', 'Турция')} />);
    expect(await screen.findByRole('button', { name: 'c11b.save.addAria' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /c11b\.watch/ })).toBeNull();
  });

  it.each([
    ['показатель России', () => subjects.russiaIndicatorSubject('cpi', 'Инфляция'), { kind: 'indicator', item_key: 'cpi', path: '/russia/indicator/cpi' }],
    ['мировой ряд', () => subjects.worldIndicatorSubject('turkey', 'tr-cpi', 'Инфляция в Турции'), { kind: 'world', item_key: 'tr-cpi', path: '/turkey/indicator/tr-cpi' }],
    ['страна', () => subjects.countrySubject('turkey', 'Турция'), { kind: 'country', item_key: 'turkey', path: '/turkey' }],
    ['регион', () => subjects.regionSubject('yakutia', 'Якутия'), { kind: 'region', item_key: 'yakutia', path: '/russia/region/yakutia' }],
    ['вид рейтинга', () => subjects.ratingViewSubject({ concept: 'gdp-usd', group: 'g7', cols: ['population'], title: 'ВВП' }), { kind: 'rating_view', item_key: 'gdp-usd|group=g7|cols=population' }],
  ])('ключ записи по договорённости: %s', async (_name, make, expected) => {
    withContext(<CabinetActionsSlot subject={make()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.save.addAria' }));
    await waitFor(() => expect(guestSaved()).toHaveLength(1));
    const [row] = guestSaved();
    expect(row).toMatchObject({ kind: expected.kind, item_key: expected.item_key });
    if (expected.path) expect(row.payload.path).toBe(expected.path);
  });

  it('колокольчик мирового ряда следит по коду ряда', async () => {
    auth.value = signedIn;
    api.addWatch.mockResolvedValue({ item: { id: 'w1', subject_kind: 'world', subject_key: 'tr-cpi' }, created: true });
    withContext(<CabinetActionsSlot subject={subjects.worldIndicatorSubject('turkey', 'tr-cpi', 'Инфляция')} />);
    const bell = await screen.findByRole('button', { name: 'c11b.watch.onAria' });
    await waitFor(() => expect(bell.disabled).toBe(false));
    fireEvent.click(bell);
    await waitFor(() => expect(api.addWatch).toHaveBeenCalled());
    expect(api.addWatch.mock.calls[0].slice(0, 2)).toEqual(['world', 'tr-cpi']);
  });
});

describe('сравнение: «Сохранить сравнение» рядом с картинкой', () => {
  const spec = {
    kind: 'comparison',
    itemKey: 'w:us:gdp,w:cn:gdp|w:cn:gdp:pop',
    title: 'ВВП: США и Китай',
    payload: { codes: 'w:us:gdp,w:cn:gdp', rep: 'w:cn:gdp:pop', names: ['ВВП — США', 'ВВП — Китай'] },
  };

  it('ключ — упорядоченная строка адреса (comparisonKeyFromSearch), адрес и названия в записи', () => {
    const props = comparisonSaveProps(spec);
    expect(props.kind).toBe('comparison');
    expect(props.itemKey).toBe('codes=w%3Aus%3Agdp,w%3Acn%3Agdp&rep=w%3Acn%3Agdp%3Apop');
    expect(props.payload).toEqual({
      path: `/compare?${props.itemKey}`, codes: 'w:us:gdp,w:cn:gdp', rep: 'w:cn:gdp:pop', names: ['ВВП — США', 'ВВП — Китай'],
    });
    expect(comparisonSaveProps({ payload: {} })).toBeNull();
  });

  it('кабинет выключен: кнопки нет', async () => {
    api.fetchCabinetConfig.mockResolvedValue(DISABLED);
    const { container } = inRouter(<CompareSaveButton spec={spec} />);
    await waitFor(() => expect(api.fetchCabinetConfig).toHaveBeenCalled());
    await settle();
    expect(container.innerHTML).toBe('');
  });

  it('кабинет включён: кнопка с подписью, запись вида comparison', async () => {
    inRouter(<CompareSaveButton spec={spec} />);
    const btn = await screen.findByRole('button', { name: /c11i\.compare\.save/ });
    fireEvent.click(btn);
    await waitFor(() => expect(guestSaved()).toHaveLength(1));
    expect(guestSaved()[0]).toMatchObject({ kind: 'comparison', item_key: comparisonSaveProps(spec).itemKey, title: 'ВВП: США и Китай' });
    expect(guestSaved()[0].payload.names).toEqual(['ВВП — США', 'ВВП — Китай']);
  });
});

describe('калькуляторы: «Сохранить расчёт»', () => {
  const payload = { page: 'mortgage', price: 8000000, down: 20, rate: 12.5, years: 20 };

  it('адрес расчёта собирается из параметров страницы', () => {
    expect(calcSavedPath(payload)).toBe('/calculator/mortgage?price=8000000&down=20&rate=12.5&years=20');
    expect(calcSavedPath({ page: 'inflation', amount: 100000, from: 1991, to: 2026, country: 'russia', reversed: true }))
      .toBe('/calculator?amount=100000&from=1991&to=2026&country=russia');
    expect(calcSavedPath({ page: 'compound', initial: 1, monthly: 2, rate: 3, years: 4, inflation: 5, cur: 'USD' }))
      .toBe('/calculator/compound?initial=1&monthly=2&rate=3&years=4&inflation=5&cur=USD');
    expect(calcSavedPath({ page: 'other' })).toBeNull();
  });

  it('кабинет выключен: ни кнопки, ни пустой обёртки с отступом', async () => {
    api.fetchCabinetConfig.mockResolvedValue(DISABLED);
    const { container } = inRouter(<CalcSaveSlot className="mt-4" itemKey="mortgage:8000000:20:12.5:20" title="Ипотека" payload={payload} />);
    await waitFor(() => expect(api.fetchCabinetConfig).toHaveBeenCalled());
    await settle();
    expect(container.innerHTML).toBe('');
  });

  it('кабинет включён: кнопка «Сохранить расчёт», запись calc с нормализованным ключом и адресом', async () => {
    inRouter(<CalcSaveSlot className="mt-4" itemKey="mortgage:8000000:20:12.5:20" title="Ипотека" payload={payload} />);
    fireEvent.click(await screen.findByRole('button', { name: /c11i\.calc\.save/ }));
    await waitFor(() => expect(guestSaved()).toHaveLength(1));
    expect(guestSaved()[0]).toMatchObject({ kind: 'calc', item_key: 'mortgage:8000000:20:12.5:20' });
    expect(guestSaved()[0].payload.path).toBe('/calculator/mortgage?price=8000000&down=20&rate=12.5&years=20');
  });
});

describe('шапка: отметка «Новое» на кнопке «Кабинет»', () => {
  const navAt = (route) => render(<MemoryRouter initialEntries={[route]}><Navbar /></MemoryRouter>);
  const accountLinks = () => screen.getAllByRole('link').filter((a) => a.getAttribute('href') === '/account');

  it('вошедший, кабинет включён, есть новое: отметка в углу кнопки, кнопка position: relative', async () => {
    auth.value = signedIn;
    api.listWatches.mockResolvedValue({
      items: [{ id: 'w1', subject_kind: 'indicator', subject_key: 'cpi', is_new: true, available: true }], limit: 50,
    });
    navAt('/account');
    await waitFor(() => expect(document.querySelector('[data-c11b="feed-badge"]')).not.toBeNull());
    const badge = document.querySelector('[data-c11b="feed-badge"]');
    const link = badge.closest('a');
    expect(link.getAttribute('href')).toBe('/account');
    expect(link.className).toContain('relative');
    expect(badge.className).toContain('c11b-new--corner');
    expect(link.getAttribute('aria-current')).toBe('page');
  });

  it('вошедший, кабинет выключен: отметки нет, список слежения не запрашивается', async () => {
    auth.value = signedIn;
    api.fetchCabinetConfig.mockResolvedValue(DISABLED);
    navAt('/compare');
    await waitFor(() => expect(accountLinks().length).toBeGreaterThan(0));
    await settle();
    expect(document.querySelector('[data-c11b="feed-badge"]')).toBeNull();
    expect(api.listWatches).not.toHaveBeenCalled();
  });

  it('гостю кнопки «Кабинет» и отметки нет, кабинет не спрашивается', async () => {
    navAt('/compare');
    await settle();
    expect(accountLinks()).toHaveLength(0);
    expect(document.querySelector('[data-c11b="feed-badge"]')).toBeNull();
    expect(api.fetchCabinetConfig).not.toHaveBeenCalled();
  });
});

describe('смена языка на калькуляторе сохраняет параметры расчёта', () => {
  it('строка запроса переносится в адрес другого языка', () => {
    const url = buildLanguageSwitchUrl('en', { href: 'https://ru.forecasteconomy.com/calculator/mortgage?price=9000000&rate=11' });
    const parsed = new URL(url);
    expect(parsed.pathname).toBe('/calculator/mortgage');
    expect(parsed.searchParams.get('price')).toBe('9000000');
    expect(parsed.searchParams.get('rate')).toBe('11');
  });
});

describe('стили слота', () => {
  it('пустой слот кнопок не занимает места в ряду (кабинет выключен)', async () => {
    const fs = await import('node:fs');
    const { cwd } = await import('node:process');
    const css = fs.readFileSync(`${cwd()}/src/styles/z4-indicator.css`, 'utf8');
    expect(css).toMatch(/\.fe-cabinet-actions:empty\s*\{\s*display:\s*none;\s*\}/);
  });
});
