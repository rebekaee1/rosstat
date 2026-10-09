// Круг 11, зона F: рейтинг стран. Разница в п. п. у процентных рядов, фильтр групп стран, набор колонок, скачивание таблицы.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import WorldRatingPage from './WorldRatingPage';
import { renderPage, mockApiGet } from '../test/renderPage';
import * as gridDownload from '../lib/gridDownload';

vi.mock('../components/PlanetView', () => ({
  default: vi.fn(() => <div data-testid="world-map-stub">map</div>),
}));

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); });

const COUNTRIES = [
  ['US', 'США', 'United States', 'united-states'], ['JP', 'Япония', 'Japan', 'japan'], ['DE', 'Германия', 'Germany', 'germany'],
  ['GB', 'Великобритания', 'United Kingdom', 'united-kingdom'], ['FR', 'Франция', 'France', 'france'], ['IT', 'Италия', 'Italy', 'italy'],
  ['CA', 'Канада', 'Canada', 'canada'], ['RU', 'Россия', 'Russia', 'russia'], ['CN', 'Китай', 'China', 'china'],
  ['TR', 'Турция', 'Turkey', 'turkey'], ['PL', 'Польша', 'Poland', 'poland'],
];

function seriesFor(slug, unit, byYear) {
  const years = Object.keys(byYear).map(Number);
  const values_by_year = {};
  for (const year of years) {
    values_by_year[year] = {};
    COUNTRIES.forEach(([code, ru, en, countrySlug], index) => {
      values_by_year[year][code] = {
        country_code: code,
        country_slug: countrySlug,
        country_name: ru,
        country_name_en: en,
        indicator_code: `${code.toLowerCase()}-${slug}`,
        date: `${year}-01-01`,
        value: byYear[year](index),
        unit,
      };
    });
  }
  return { concept: { slug, name: slug, unit }, years, values_by_year };
}

const CONCEPTS = {
  concepts: [
    { slug: 'gdp-usd', name: 'ВВП', unit: 'млрд $', default_sort: 'desc' },
    { slug: 'hicp-index', name: 'Инфляция', unit: 'изменение за год, %', default_sort: 'asc' },
    { slug: 'unemployment-rate', name: 'Безработица', unit: '% экономически активного населения', default_sort: 'asc' },
  ],
  total: 3,
};

function mocks({ user = null } = {}) {
  return [
    ['/auth/me', { user }],
    [/^\/indicators/, []],
    [/^\/world\/countries/, {
      countries: COUNTRIES.map(([code, name, nameEn, slug]) => ({ code, slug, name, name_en: nameEn, indicators_count: 5 })),
      total: COUNTRIES.length,
    }],
    [/^\/world\/rating\/concepts/, CONCEPTS],
    [/^\/world\/compare\/map-series\/gdp-usd/, seriesFor('gdp-usd', 'млрд $', {
      2024: (i) => 5000 - i * 200, 2025: (i) => 5200 - i * 200,
    })],
    // Инфляция: у Китая было 0,1 %, стало 0,8 %: это +0,7 п. п., а не «+700 %».
    [/^\/world\/compare\/map-series\/hicp-index/, seriesFor('hicp-index', 'изменение за год, %', {
      2024: (i) => (i === 8 ? 0.1 : 2 + i * 0.3), 2025: (i) => (i === 8 ? 0.8 : 2.4 + i * 0.3),
    })],
    [/^\/world\/compare\/map-series\/unemployment-rate/, seriesFor('unemployment-rate', '% экономически активного населения', {
      2024: (i) => 3 + i * 0.4, 2025: (i) => 3.2 + i * 0.4,
    })],
  ];
}

function Probe() {
  const location = useLocation();
  return <output data-testid="loc">{location.pathname + location.search}</output>;
}

function renderRating(route, options = {}) {
  mockApiGet(mocks(options));
  return renderPage(
    <><WorldRatingPage /><Probe /></>,
    { path: '/world/rating/:conceptSlug/:year?', route },
  );
}

const flat = (text) => text.replace(/\u00a0/g, ' ');

describe('рейтинг: изменение к прошлому году у процентных рядов', () => {
  it('«было 0,1 %, стало 0,8 %» это +0,7 п. п., а не +700 %; шапка называет меру', async () => {
    renderRating('/world/rating/hicp-index');
    await screen.findByTestId('world-map-stub');
    const row = await waitFor(() => {
      const found = [...document.querySelectorAll('#rating-table tbody tr')].find((tr) => tr.textContent.includes('Китай'));
      expect(found).toBeTruthy();
      return found;
    });
    const text = flat(row.textContent);
    expect(text).toContain('+0,7 п. п.');
    expect(text).not.toMatch(/\+700/);
    const head = [...document.querySelectorAll('#rating-table thead th')].map((th) => th.textContent).join('|');
    expect(head).toContain('п. п.');
    // Подсказка к шапке колонки (текст приходит из словаря, сам ключ не пустой).
    const th = [...document.querySelectorAll('#rating-table thead th')].find((cell) => cell.textContent.includes('п. п.'));
    expect(th.getAttribute('title')).toBeTruthy();
  });

  it('у рядов в долларах изменение остаётся относительным процентом', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    await waitFor(() => {
      const row = [...document.querySelectorAll('#rating-table tbody tr')].find((tr) => tr.textContent.includes('США'));
      expect(flat(row.textContent)).toMatch(/\+4,0 %/);
    });
  });
});

describe('рейтинг: группы стран', () => {
  it('«G7» оставляет семь стран с местами внутри группы, «Все» возвращает список; группа живёт в адресе', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const groups = await screen.findByTestId('rating-groups');
    expect(within(groups).getAllByRole('button').map((b) => b.textContent)).toEqual(['Все', 'G7', 'БРИКС', 'СНГ']);
    fireEvent.click(within(groups).getByRole('button', { name: 'G7' }));
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(7));
    expect(screen.getByTestId('loc').textContent).toContain('group=g7');
    const places = [...document.querySelectorAll('#rating-table tbody tr td:first-child')].map((td) => td.textContent);
    expect(places).toEqual(['1', '2', '3', '4', '5', '6', '7']);
    expect(document.querySelector('#rating-table h2').textContent).toContain('G7');
    fireEvent.click(within(groups).getByRole('button', { name: 'Все' }));
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr').length).toBeGreaterThan(7));
    expect(screen.getByTestId('loc').textContent).not.toContain('group=');
  });

  it('группа из адреса применяется сразу; СНГ в каталоге из одной России показывается', async () => {
    renderRating('/world/rating/gdp-usd?group=cis');
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(1));
    expect(document.querySelector('#rating-table tbody tr').textContent).toContain('Россия');
  });
});

describe('рейтинг: колонки', () => {
  it('добавленная колонка стоит в таблице с признаком прокрутки, набор можно запомнить и он вернётся без адреса', async () => {
    renderRating('/world/rating/gdp-usd?cols=unemployment-rate');
    await screen.findByTestId('world-map-stub');
    const card = await waitFor(() => {
      const found = document.querySelector('.z6-table-card[data-scroll]');
      expect(found).toBeTruthy();
      return found;
    });
    expect(card.getAttribute('data-extra')).toBe('1');
    expect(card.querySelector('th[data-col="unemployment-rate"]')).toBeTruthy();
    const save = screen.getByTestId('rating-save-cols');
    expect(save.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(save);
    expect(JSON.parse(window.localStorage.getItem('fe:rating-cols'))).toEqual(['unemployment-rate']);
    expect(save.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(save);
    expect(window.localStorage.getItem('fe:rating-cols')).toBeNull();
  });

  it('запомненный набор открывается сам, если в адресе колонок нет', async () => {
    window.localStorage.setItem('fe:rating-cols', JSON.stringify(['unemployment-rate']));
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toContain('cols=unemployment-rate'));
  });
});

describe('рейтинг: скачать таблицу', () => {
  it('гостю — окно регистрации, файл не строится', async () => {
    const spy = vi.spyOn(gridDownload, 'downloadGrid').mockResolvedValue({ remaining: null });
    const limit = vi.fn();
    window.addEventListener('fe:download-limit', limit);
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    fireEvent.click(await screen.findByRole('button', { name: /Скачать/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: /CSV/ }));
    expect(limit).toHaveBeenCalled();
    expect(spy).not.toHaveBeenCalled();
    window.removeEventListener('fe:download-limit', limit);
  });

  it('вошедшему уходит вся таблица как на экране: места, страны, значение, изменение и добавленная колонка', async () => {
    const spy = vi.spyOn(gridDownload, 'downloadGrid').mockResolvedValue({ remaining: null });
    renderRating('/world/rating/gdp-usd?cols=unemployment-rate&group=g7', { user: { id: 1, email: 'u@x.ru', is_admin: false } });
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(7));
    await waitFor(() => expect(screen.getByRole('button', { name: /Скачать/ })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Скачать/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: /Excel/ }));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const payload = spy.mock.calls[0][0];
    expect(payload.format).toBe('xlsx');
    expect(payload.filename).toMatch(/^rating_gdp-usd_2025_g7\.xlsx$/);
    expect(payload.rows).toHaveLength(7);
    expect(payload.columns.map((c) => c.key)).toEqual(['rank', 'country', 'value', 'change', 'x_unemployment-rate']);
    expect(payload.rows[0]).toMatchObject({ rank: 1, country: 'США' });
    expect(JSON.stringify(payload)).not.toMatch(/lower|upper/i);
  });
});
