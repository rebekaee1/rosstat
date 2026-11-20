import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import RegionRatingPage from './RegionRatingPage';
import RegionIndicatorPage from './RegionIndicatorPage';
import RegionProfile from './RegionProfile';
import RegionAnnualChart from '../components/RegionAnnualChart';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/RegionsMap', () => ({ default: vi.fn(() => <div data-testid="regions-map-stub">map</div>) }));

beforeEach(() => { Element.prototype.scrollIntoView = vi.fn(); });
afterEach(() => { delete Element.prototype.scrollIntoView; vi.restoreAllMocks(); });

function values(zeroSlugs = []) {
  const rows = [];
  for (let i = 0; i < 12; i += 1) rows.push({ slug: `r${i}`, name: `Регион ${i}`, value: 10 + i, raw: 10 + i, prev: 8 + i });
  for (const s of zeroSlugs) rows.push({ slug: s, name: s === 'moskva' ? 'Москва' : s, value: 0, raw: 0, prev: 0 });
  return rows;
}

function mountRating(code, payload) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [new RegExp(`^/regions/heatmap/${code}`), payload],
  ]);
  return renderPage(<RegionRatingPage />, { path: '/russia/region-rating/:code', route: `/russia/region-rating/${code}` });
}

describe('z5: рейтинг не по ценам', () => {
  it('налог: нейтральные слова, ноль подписан, «−100 %» нет, Москва не «самая дешёвая»', async () => {
    mountRating('tour-nalog-s-nachala-goda', {
      indicator: { code: 'tour-nalog-s-nachala-goda', name: 'Туристический налог: поступило с начала года', unit: 'миллионов рублей с начала года' },
      year: 2026, month: 202609, period_label: 'сентябрь 2026', polarity: 'higher_better', default_sort: 'desc',
      values: values(['moskva', 'bryansk']),
    });
    await screen.findByTestId('rating-mine');
    const text = document.body.textContent;
    expect(text).not.toMatch(/Дешевле|Дороже|Типичная цена|цены по регионам|Цены в|−100/);
    expect(screen.getByText('Наименьшее значение')).toBeTruthy();
    expect(screen.getByTestId('kt5-median')).toBeTruthy();
    const none = screen.getAllByTestId('kt5-none-row');
    expect(none).toHaveLength(2);
    expect(none[0].textContent).toMatch(/налог не введён или сбора не было/);
    // Москва с нулём не стала «наименьшим значением»: минимум — Регион 0 (10).
    const tiles = document.querySelector('.r7c-rate-tiles');
    expect(tiles.textContent).toContain('Регион 0');
    expect(tiles.textContent).not.toContain('Москва');
    expect(text).toMatch(/\(14\)|14 регион/);
  });

  it('ценовой рейтинг остаётся как был: «Дешевле всего», «Типичная цена», подписи цен', async () => {
    mountRating('hleb', {
      indicator: { code: 'hleb', name: 'Средняя цена: хлеб, рублей за кг', unit: 'рублей за кг' },
      year: 2026, month: 202609, period_label: 'сентябрь 2026', polarity: 'lower_better', default_sort: 'asc',
      values: values(),
    });
    await screen.findByTestId('rating-mine');
    expect(screen.getByText('Дешевле всего')).toBeTruthy();
    expect(screen.getByText('Типичная цена')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 2, name: /Цены в 12 регионах/ })).toBeTruthy();
    expect(screen.queryByTestId('kt5-median')).toBeNull();
  });
});

const IND = {
  region: { slug: 'moskva', name: 'Москва', kind: 'region' },
  indicator: { code: 'gosti', name: 'Гости гостиниц', unit: 'тыс. человек', note: 'Число размещённых в гостиницах.', source: 'Росстат, форма 1-КСР', section_num: 6, section_name: 'Туризм', table_code: '6.1', macro_code: null },
  series: [{ year: 2023, value: 1000 }, { year: 2024, value: 1222 }],
  russia_series: [{ year: 2023, value: 9000 }, { year: 2024, value: 10000 }],
  rank: { position: 1, total: 85, year: 2024, rank_as_achievement: false, top: [{ slug: 'moskva', name: 'Москва', value: 1222 }], bottom: [] },
  siblings: [],
};

describe('z5: страница показателя региона', () => {
  function mount(slug, payload) {
    mockApiGet([
      ['/auth/me', { user: null }],
      [new RegExp(`^/regions/${slug}/i/gosti$`), payload],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: {} }],
      [/^\/regions\/heatmap\/gosti/, { indicator: { code: 'gosti', name: 'Гости', unit: 'тыс. человек' }, year: 2024, values: values() }],
    ]);
    return renderPage(<RegionIndicatorPage />, { path: '/russia/region/:slug/:code', route: `/russia/region/${slug}/gosti` });
  }

  it('абсолютный показатель: доля в России и место вместо «в России выше на N %»', async () => {
    mount('moskva', IND);
    const share = await screen.findByTestId('kt5-share');
    expect(share.textContent).toMatch(/Доля в России, 2024: 12,2\s%/);
    expect(share.textContent).toMatch(/место 1 из 85 регионов/);
    expect(screen.queryByTestId('r6c-russia')).toBeNull();
    expect(document.body.textContent).not.toMatch(/выше на|ниже на/);
  });

  it('есть блок источника, методологии и строка цитирования', async () => {
    mount('moskva', IND);
    const box = await screen.findByTestId('kt5-source');
    expect(within(box).getByText(/Источник: Росстат, форма 1-КСР/)).toBeTruthy();
    expect(within(box).getByText('Число размещённых в гостиницах.')).toBeTruthy();
    expect(screen.getByTestId('kt5-cite').textContent).toMatch(/^Forecast Economy\. Гости гостиниц — Москва: источник данных — Росстат, форма 1-КСР/);
  });

  it('страница «Российская Федерация»: строки сравнения РФ с собой нет, «Все регионы →» ведёт на рейтинг', async () => {
    mount('russia', { ...IND, region: { slug: 'russia', name: 'Российская Федерация', kind: 'country' }, rank: null });
    const link = await screen.findByTestId('kt5-all-regions');
    expect(link.getAttribute('href')).toBe('/russia/region-rating/gosti');
    expect(screen.queryByTestId('kt5-share')).toBeNull();
    expect(screen.queryByTestId('r6c-russia')).toBeNull();
  });

  it('процентный показатель сохраняет прежнее сравнение с Россией', async () => {
    mount('moskva', { ...IND, indicator: { ...IND.indicator, unit: '%' }, series: [{ year: 2023, value: 5 }, { year: 2024, value: 6 }], russia_series: [{ year: 2023, value: 4 }, { year: 2024, value: 4.5 }] });
    expect(await screen.findByTestId('r6c-russia')).toBeTruthy();
    expect(screen.queryByTestId('kt5-share')).toBeNull();
  });
});

describe('z5: страница региона из раздела «Туризм»', () => {
  const PROFILE = {
    region: { slug: 'moskva', name: 'Москва', district_name: 'ЦФО' },
    headline: {},
    sections: [
      { num: 1, name: 'Население', indicators: [{ code: 'naselenie', name: 'Численность населения', unit: 'тыс. человек', value: 1, prev_value: 1, year: 2024 }] },
      { num: 6, name: 'Культура, отдых и туризм', indicators: [{ code: 'gosti', name: 'Гости гостиниц', unit: 'тыс. человек', value: 1, prev_value: 1, year: 2024 }] },
    ],
  };
  const mount = (route) => {
    mockApiGet([['/auth/me', { user: null }], ['/regions/moskva', PROFILE]]);
    return renderPage(<RegionProfile />, { path: '/russia/region/:slug', route });
  };

  it('?topic=tourism открывает туристские показатели', async () => {
    mount('/russia/region/moskva?topic=tourism');
    await screen.findByRole('heading', { name: 'Москва' });
    const chart = document.getElementById('chart');
    expect(await within(chart).findByRole('link', { name: /Гости гостиниц/ })).toBeTruthy();
    expect(within(chart).queryByRole('link', { name: /Численность населения/ })).toBeNull();
  });

  it('без параметра по-прежнему первая тема', async () => {
    mount('/russia/region/moskva');
    await screen.findByRole('heading', { name: 'Москва' });
    expect(within(document.getElementById('chart')).getByRole('link', { name: /Численность населения/ })).toBeTruthy();
  });
});

describe('z5: график сравнения регионов', () => {
  const mk = (k) => [{ year: 2020, value: 10 * k }, { year: 2021, value: 12 * k }, { year: 2022, value: 15 * k }];
  const draw = (props) => renderPage(<RegionAnnualChart series={mk(1)} regionName="Тыва" compareName="Москва" {...props} />);

  it('разница масштабов больше 10 раз: подпись про рост в % от начала периода', () => {
    draw({ compareSeries: mk(50) });
    expect(screen.getByTestId('rebase-note').textContent).toMatch(/больше чем в 10 раз.*от начала периода/);
  });

  it('близкие масштабы: график как раньше', () => {
    draw({ compareSeries: mk(3) });
    expect(screen.queryByTestId('rebase-note')).toBeNull();
  });
});
