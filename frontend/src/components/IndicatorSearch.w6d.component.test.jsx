// @vitest-environment jsdom
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import IndicatorSearch from './IndicatorSearch';
import { translate } from '../i18n/messages';

const ratingState = vi.hoisted(() => ({ concepts: [] }));
const searchState = vi.hoisted(() => ({
  data: { results: [], version: 'v2' }, isPending: false, isDebouncing: false, isError: false, prefetch: vi.fn(), flush: vi.fn(),
}));
vi.mock('../lib/useGlobalSearch', () => ({ default: vi.fn(() => searchState) }));
vi.mock('../lib/worldApi', () => ({
  useWorldCountries: () => ({
    data: { countries: [{ slug: 'germany', code: 'DE' }, { slug: 'united-states', code: 'US' }, { slug: 'russia', code: 'RU' }] },
  }),
  useWorldRatingConcepts: () => ({ data: { concepts: ratingState.concepts } }),
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key, vars) => translate(key, vars, 'ru'),
  useLocale: () => ({ locale: 'ru' }),
}));

beforeEach(() => {
  ratingState.concepts = [];
  Object.assign(searchState, { data: { results: [], version: 'v2' }, isPending: false, isDebouncing: false, isError: false });
  searchState.prefetch.mockClear();
  searchState.flush.mockClear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(() => [{ width: 100, height: 30 }]);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function Probe() {
  const location = useLocation();
  return <output data-testid="loc">{location.pathname}</output>;
}

function mount() {
  render(<MemoryRouter><IndicatorSearch variant="inline" /><Probe /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'Открыть поиск' }));
  return screen.getByRole('combobox');
}

function type(input, value) { fireEvent.change(input, { target: { value } }); }

const row = (key, name, extra = {}) => ({
  key, kind: 'world', code: key, name, country_slug: 'germany', country_name: 'Германия', frequency: 'monthly', unit: '%', path: `/germany/indicator/${key}`, ...extra,
});

it('ru: примеры мировые, а ставка ФРС, нефть и ключевая ставка открываются сразу по своему адресу', async () => {
  mount();
  const options = screen.getAllByRole('option').map((o) => o.textContent);
  expect(options.slice(0, 4)).toEqual(['Инфляция в Турции', 'ВВП Индии', 'Безработица в Испании', 'Ставка ФРС США']);
  fireEvent.click(screen.getByRole('option', { name: 'Ставка ФРС США' }));
  await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/united-states/indicator/us-policy-rate'));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});

it('подсказка без готового адреса ищет сразу и открывает лучший показатель сама, показывая «Открываем»', async () => {
  searchState.data = { version: 'v2', results: [
    { key: 'country:turkey', kind: 'country', name: 'Турция', country_slug: 'turkey', path: '/turkey' },
    row('tr-cpi', 'Инфляция', { country_slug: 'turkey', country_name: 'Турция', path: '/turkey/indicator/tr-cpi' }),
  ] };
  mount();
  fireEvent.click(screen.getByRole('option', { name: 'Инфляция в Турции' }));
  expect(searchState.flush).toHaveBeenCalledWith('Инфляция в Турции');
  await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/turkey/indicator/tr-cpi'));
});

it('наведение на подсказку без адреса подгружает её выдачу заранее', () => {
  mount();
  fireEvent.mouseEnter(screen.getByRole('option', { name: 'ВВП Индии' }));
  expect(searchState.prefetch).toHaveBeenCalledWith('ВВП Индии');
  searchState.prefetch.mockClear();
  fireEvent.mouseEnter(screen.getByRole('option', { name: 'Ставка ФРС США' }));
  expect(searchState.prefetch).not.toHaveBeenCalled();
});

it('после выбора панель остаётся с полосой «Открываем: …», пока страница не открылась', () => {
  const assign = vi.fn();
  const original = window.location;
  Object.defineProperty(window, 'location', { configurable: true, value: { ...original, assign } });
  try {
    searchState.data = { version: 'v2', results: [row('de-un', 'Безработица', { navigation: 'document', path: '/germany/indicator/de-un/2024' })] };
    const input = mount();
    type(input, 'безработица германии');
    fireEvent.click(screen.getByRole('option', { name: /Безработица/ }));
    expect(assign).toHaveBeenCalledWith('/germany/indicator/de-un/2024');
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByTestId('search-opening').textContent).toContain('Открываем: Безработица');
  } finally {
    Object.defineProperty(window, 'location', { configurable: true, value: original });
  }
});

it('крестик сначала очищает запрос и только потом закрывает окно', () => {
  const input = mount();
  type(input, 'ввп');
  fireEvent.click(screen.getByRole('button', { name: 'Очистить запрос' }));
  expect(screen.getByRole('combobox').value).toBe('');
  expect(screen.getByRole('dialog')).toBeTruthy();
  fireEvent.click(document.querySelector('.fe-search-field button[aria-label="Закрыть"]'));
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('«gdp»: раздел «Рейтинги» с «ВВП: рейтинг стран» первым, дальше «Показатели»', () => {
  ratingState.concepts = [{ slug: 'gdp-usd', name: 'ВВП' }, { slug: 'population', name: 'Население' }];
  searchState.data = { version: 'v2', intent: { countries: [], regions: [] }, results: [
    row('ru-gdp', 'ВВП номинальный', { kind: 'russia', country_slug: 'russia', country_name: 'Россия', frequency: 'quarterly', unit: 'млрд руб.', path: '/russia/indicator/gdp' }),
  ] };
  const input = mount();
  type(input, 'gdp');
  const titles = [...document.querySelectorAll('.w6d-sr-title')].map((p) => p.textContent);
  expect(titles).toEqual(['Рейтинги', 'Показатели']);
  const options = screen.getAllByRole('option');
  expect(options[0].textContent).toContain('ВВП: рейтинг стран');
});

it('«Курс доллара»: одна строка и переключатель день, неделя, месяц; кнопка открывает свой вариант', async () => {
  const base = { kind: 'russia', country_slug: 'russia', country_name: 'Россия', unit: 'руб.' };
  searchState.data = { version: 'v2', intent: { countries: [], regions: [] }, results: [
    row('usd-d', 'Курс доллара США', { ...base, frequency: 'daily', path: '/currencies/indicator/usd-rub' }),
    row('usd-m', 'Курс доллара США (средняя за месяц)', { ...base, frequency: 'monthly', path: '/currencies/indicator/usd-rub-avg-month' }),
    row('usd-w', 'Курс доллара США (средняя за неделю)', { ...base, frequency: 'weekly', path: '/currencies/indicator/usd-rub-avg-week' }),
  ] };
  const input = mount();
  type(input, 'курс доллара');
  expect(screen.getAllByRole('option')).toHaveLength(1);
  const group = screen.getByRole('group', { name: 'Как часто обновляются данные' });
  expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['День', 'Неделя', 'Месяц']);
  fireEvent.click(within(group).getByRole('button', { name: 'Месяц' }));
  await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/currencies/indicator/usd-rub-avg-month'));
});

it('«population»: одна строка с кнопками стран вместо десятков строк, популярные страны первыми, есть рейтинг', async () => {
  ratingState.concepts = [{ slug: 'population', name: 'Население' }];
  const slugs = ['albania', 'armenia', 'australia', 'austria', 'germany', 'united-states', 'china', 'brazil'];
  searchState.data = { version: 'v2', intent: { countries: [], regions: [] }, results: slugs.map((slug, i) =>
    row(`pop-${slug}`, 'Численность населения', { country_slug: slug, country_name: slug.toUpperCase(), frequency: 'annual', unit: 'человек', path: `/${slug}/indicator/pop-${i}` })) };
  const input = mount();
  type(input, 'population');
  const options = screen.getAllByRole('option');
  // Рейтинг и одна строка показателя
  expect(options.map((o) => o.textContent).filter((text) => text.includes('Численность населения'))).toHaveLength(1);
  expect(document.body.textContent).not.toMatch(/по годам, человек/);
  const chips = [...document.querySelectorAll('.w6d-sr-chip')].map((b) => b.textContent);
  expect(chips[0]).toContain('Рейтинг стран');
  expect(chips[1]).toContain('UNITED-STATES');
  expect(chips.at(-1)).toBe('Ещё 2');
  fireEvent.click(screen.getByRole('button', { name: 'Ещё 2' }));
  expect([...document.querySelectorAll('.w6d-sr-chip')].map((b) => b.textContent)).toContain('ALBANIA');
  fireEvent.click(screen.getByRole('button', { name: /Рейтинг стран/ }));
  await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/world/rating/population'));
});

it('в строке видно последнее значение с месяцем и мини-график; индексы и методика убраны из названия', () => {
  searchState.data = { version: 'v2', intent: { countries: ['germany'], regions: [] }, results: [
    row('de-un', 'Уровень безработицы (2015 = 100)', {
      frequency: 'monthly', unit: '%', latest: { value: 4.0, date: '2026-08-01' }, spark: [3.6, 3.7, 3.9, 4.0],
    }),
  ] };
  const input = mount();
  type(input, 'безработица германии');
  const option = screen.getByRole('option');
  expect(option.textContent).toContain('Уровень безработицы');
  expect(option.textContent).not.toContain('2015');
  expect(option.textContent).toMatch(/4,00\s%, август 2026/);
  expect(option.querySelector('svg.w6d-spark')).not.toBeNull();
});

it('мировая цена получает значок глобуса, а не российский флаг', () => {
  searchState.data = { version: 'v2', intent: { countries: [], regions: [] }, results: [
    row('brent', 'Нефть марки Brent', { kind: 'russia', country_slug: 'russia', country_name: 'Мировой рынок', frequency: 'daily', unit: 'USD/баррель', path: '/russia/indicator/brent' }),
  ] };
  const input = mount();
  type(input, 'нефть');
  const option = screen.getByRole('option');
  expect(option.querySelector('.w6d-sr-globe')).not.toBeNull();
  expect(option.querySelector('.fe-search-row__badge')).toBeNull();
  expect(option.textContent).toContain('$ за баррель');
});

it('подсказка про клавиши видна только там, где есть мышь и клавиатура', () => {
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  const kbd = document.querySelector('kbd');
  expect(kbd.className).toContain('hidden');
  expect(kbd.className).toContain('pointer-fine:inline');
});

it('нерелевантное после точных совпадений уходит под «Ещё варианты»', () => {
  searchState.data = { version: 'v2', intent: { countries: ['germany'], regions: [] }, results: [
    row('un-m', 'Уровень безработицы', { frequency: 'monthly' }),
    row('un-y', 'Уровень безработицы', { frequency: 'annual' }),
    row('pop', 'Население, %'),
    row('kids', 'Дети в домохозяйствах без работающих, %'),
  ] };
  const input = mount();
  type(input, 'безработица германии');
  expect(screen.getAllByRole('option')).toHaveLength(1);
  const more = screen.getByRole('button', { name: /Ещё варианты \(2\)/ });
  fireEvent.click(more);
  expect(screen.getAllByRole('option')).toHaveLength(3);
});
