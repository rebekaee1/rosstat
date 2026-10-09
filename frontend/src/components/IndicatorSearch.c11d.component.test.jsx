// @vitest-environment jsdom
// Круг 11 (D): недавние запросы и страницы в пустом окне поиска, фильтры выдачи. Реальный хук useGlobalSearch, ответ сервера подставлен.
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import IndicatorSearch from './IndicatorSearch';
import api from '../lib/api';
import { translate } from '../i18n/messages';

vi.mock('../lib/api', () => ({ default: { get: vi.fn() } }));
vi.mock('../lib/worldApi', () => ({
  useWorldCountries: () => ({ data: { countries: [{ slug: 'russia', code: 'RU' }, { slug: 'turkey', code: 'TR' }, { slug: 'germany', code: 'DE' }] } }),
  useWorldRatingConcepts: () => ({ data: { concepts: [] } }),
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key, vars) => translate(key, vars, 'ru'),
  useLocale: () => ({ locale: 'ru' }),
}));

const row = (over) => ({
  kind: 'world', country_slug: 'turkey', country_name: 'Турция', frequency: 'monthly', unit: '%', navigation: 'spa', score: 100, ...over,
});
const RESULTS = [
  row({ key: 'w:tr-avg', code: 'tr-weo-pcpipch', name: 'Инфляция в среднем за год, оценка МВФ', frequency: 'annual', path: '/turkey/indicator/tr-weo-pcpipch' }),
  row({ key: 'w:tr-yoy', code: 'tr-prc_hicp_manr-cp00', name: 'Инфляция, изменение за год', path: '/turkey/indicator/tr-prc_hicp_manr-cp00' }),
  row({ key: 'w:de-yoy', code: 'de-prc_hicp_manr-cp00', name: 'Инфляция в Германии, изменение за год', country_slug: 'germany', country_name: 'Германия', path: '/germany/indicator/de-prc_hicp_manr-cp00' }),
  row({ key: 'ru:cpi', kind: 'russia', code: 'cpi-yoy', name: 'ИПЦ год к году', country_slug: 'russia', country_name: 'Россия', path: '/russia/indicator/cpi-yoy' }),
];

let client;
beforeEach(() => {
  window.localStorage.clear();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  api.get.mockReset().mockResolvedValue({ data: { results: RESULTS, version: 'federated-v2', intent: { countries: [], regions: [] } } });
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(() => [{ width: 100, height: 30 }]);
});
afterEach(() => { cleanup(); client.clear(); vi.restoreAllMocks(); });

function mount() {
  render(<QueryClientProvider client={client}><MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getAllByRole('button')[0]);
}

describe('окно поиска: недавнее', () => {
  it('пустое окно показывает до шести недавних запросов и до четырёх недавних страниц, потом примеры', () => {
    window.localStorage.setItem('fe_recent_queries', JSON.stringify(['q1 запрос', 'q2 запрос', 'q3 запрос', 'q4 запрос', 'q5 запрос', 'q6 запрос', 'q7 запрос']));
    window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify(
      Array.from({ length: 6 }, (_, i) => ({ path: `/turkey/indicator/x${i}`, title: `Страница ${i}`, kind: 'indicator', ts: 10 - i })),
    ));
    mount();
    const names = screen.getAllByRole('option').map((node) => node.textContent);
    expect(names.filter((text) => /^q\d запрос/.test(text))).toHaveLength(6);
    expect(names.filter((text) => /^Страница \d/.test(text))).toHaveLength(4);
    expect(names.indexOf('Страница 0')).toBeGreaterThan(names.indexOf('q6 запрос'));
    expect(screen.getByText('Вы смотрели')).toBeTruthy();
    expect(screen.getByText('Недавнее')).toBeTruthy();
  });

  it('недавняя страница открывается сразу по адресу, без нового поиска', () => {
    window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify([{ path: '/turkey/indicator/x1', title: 'Недавняя страница Турции', kind: 'indicator', ts: 1 }]));
    mount();
    fireEvent.click(screen.getByRole('option', { name: /Недавняя страница Турции/ }));
    expect(api.get).not.toHaveBeenCalled();
  });

  it('«Очистить» стирает оба списка и оставляет примеры', () => {
    window.localStorage.setItem('fe_recent_queries', JSON.stringify(['инфляция турция']));
    window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify([{ path: '/turkey', title: 'Турция', kind: 'country', ts: 1 }]));
    mount();
    fireEvent.click(screen.getByRole('button', { name: 'Очистить', hidden: true }));
    expect(window.localStorage.getItem('fe_recent_queries')).toBeNull();
    expect(window.localStorage.getItem('fe:recent-pages:v1')).toBeNull();
    expect(screen.queryByText('Вы смотрели')).toBeNull();
    expect(screen.getByText('Популярное')).toBeTruthy();
  });

  it('повреждённое хранилище недавних страниц не ломает окно', () => {
    window.localStorage.setItem('fe:recent-pages:v1', '{oops');
    mount();
    expect(screen.getAllByRole('option').length).toBeGreaterThan(0);
  });
});

describe('окно поиска: фильтры выдачи', () => {
  async function typeQuery() {
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'инфляция' } });
    await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0));
  }
  const optionNames = () => screen.getAllByRole('option').map((node) => node.textContent);

  it('кнопка «Фильтры» раскрывает страну, периодичность, источник и способ счёта; выбор сужает выдачу сразу, без нового запроса', async () => {
    mount();
    await typeQuery();
    expect(optionNames().length).toBe(4);
    const calls = api.get.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /Фильтры/ }));
    for (const label of ['Страна', 'Как часто', 'Источник', 'Как считать']) expect(screen.getByRole('group', { name: label })).toBeTruthy();
    fireEvent.click(within(screen.getByRole('group', { name: 'Страна' })).getByRole('button', { name: 'Германия' }));
    await waitFor(() => expect(optionNames().length).toBe(1));
    expect(optionNames()[0]).toMatch(/Германии/);
    expect(screen.getByText('Показано 1 из 4')).toBeTruthy();
    expect(api.get.mock.calls.length).toBe(calls);
  });

  it('«в среднем за год» и «год к году» разделяют ряды одного смысла', async () => {
    mount();
    await typeQuery();
    fireEvent.click(screen.getByRole('button', { name: /Фильтры/ }));
    const basis = within(screen.getByRole('group', { name: 'Как считать' }));
    fireEvent.click(basis.getByRole('button', { name: 'В среднем за год' }));
    await waitFor(() => expect(optionNames().length).toBe(1));
    expect(optionNames()[0]).toMatch(/по годам/);
    fireEvent.click(basis.getByRole('button', { name: 'Год к году' }));
    await waitFor(() => expect(optionNames().length).toBeGreaterThan(1));
  });

  it('если под фильтры ничего не подошло, окно говорит об этом и даёт сбросить', async () => {
    mount();
    await typeQuery();
    fireEvent.click(screen.getByRole('button', { name: /Фильтры/ }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Источник' })).getByRole('button', { name: 'МВФ' }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Страна' })).getByRole('button', { name: 'Германия' }));
    expect(await screen.findByTestId('search-filtered-out')).toBeTruthy();
    fireEvent.click(within(screen.getByTestId('search-filtered-out')).getByRole('button', { name: 'Сбросить' }));
    await waitFor(() => expect(optionNames().length).toBe(4));
  });

  it('новый запрос сбрасывает прежние фильтры', async () => {
    mount();
    await typeQuery();
    fireEvent.click(screen.getByRole('button', { name: /Фильтры/ }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Страна' })).getByRole('button', { name: 'Германия' }));
    await waitFor(() => expect(optionNames().length).toBe(1));
    expect(screen.getByLabelText('выбрано: 1')).toBeTruthy();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'инфляция турция' } });
    await waitFor(() => expect(screen.queryByLabelText('выбрано: 1')).toBeNull());
  });
});
