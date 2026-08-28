import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import WorldCountry from './WorldCountry';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldMap', () => ({
  CountrySilhouette: () => <div data-testid="silhouette-stub">map</div>,
}));

afterEach(() => vi.restoreAllMocks());

const US_COUNTRY = {
  country: {
    code: 'US',
    slug: 'united-states',
    name: 'США',
    name_en: 'United States',
    region: 'Америка',
    indicators_count: 1,
  },
  categories: [
    {
      name: 'Рынок труда',
      count: 1,
      indicators: [
        {
          code: 'us-unemployment',
          name: 'Уровень безработицы',
          unit: '%',
          frequency: 'monthly',
          frequencies: ['monthly'],
          last_value: 4.1,
          last_date: '2026-06-01',
        },
      ],
    },
  ],
  overview: [],
  coverage: {
    history_start: '2024-01-01',
    history_end: '2026-06-01',
    frequencies: ['monthly'],
  },
  market_indicators: [
    {
      code: 'ust-10y',
      name: 'Доходность 10-летних гособлигаций США',
      name_en: 'U.S. 10-year Treasury yield',
      unit: '%',
      last_value: 4.25,
      last_date: '2026-08-21',
      frequency: 'daily',
    },
    {
      code: 'usd-index',
      name: 'Индекс доллара США',
      name_en: 'Broad U.S. Dollar Index',
      unit: 'пунктов',
      last_value: 120.1,
      last_date: '2026-08-21',
      frequency: 'daily',
    },
  ],
};

const GERMANY = {
  ...US_COUNTRY,
  country: {
    code: 'DE',
    slug: 'germany',
    name: 'Германия',
    name_en: 'Germany',
    region: 'Европа',
    indicators_count: 1,
  },
  market_indicators: [],
};

function renderCountry(slug, payload) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [`/world/countries/${slug}`, payload],
  ]);
  return renderPage(<WorldCountry />, {
    path: '/:countrySlug',
    route: `/${slug}`,
  });
}

describe('WorldCountry market indicators', () => {
  it('показывает блок «Мировые рынки» со ссылками в общий каталог', async () => {
    renderCountry('united-states', US_COUNTRY);

    const heading = await screen.findByRole('heading', { name: 'Мировые рынки' });
    expect(heading).toBeTruthy();

    const ust = await screen.findByRole('link', {
      name: /Доходность 10-летних гособлигаций США/,
    });
    expect(ust.getAttribute('href')).toBe('/russia/indicator/ust-10y');

    const usd = screen.getByRole('link', { name: /Индекс доллара США/ });
    expect(usd.getAttribute('href')).toBe('/russia/indicator/usd-index');

    const une = screen.getByRole('link', { name: /Уровень безработицы/ });
    expect(une.getAttribute('href')).toBe('/united-states/indicator/us-unemployment');
  });

  it('не рендерит блок, если привязанных рядов нет', async () => {
    renderCountry('germany', GERMANY);

    await screen.findByRole('heading', { name: 'Рынок труда' });
    expect(screen.queryByRole('heading', { name: 'Мировые рынки' })).toBeNull();
    expect(screen.queryByTestId('country-market-indicators')).toBeNull();
  });
});

describe('WorldCountry frequency badges', () => {
  it('показывает один бейдж самой детальной частоты, остальные — в подсказке', async () => {
    renderCountry('germany', {
      ...GERMANY,
      categories: [{
        name: 'Рынок труда',
        count: 1,
        indicators: [{
          code: 'de-une',
          name: 'Уровень безработицы',
          unit: '%',
          frequency: 'monthly',
          frequencies: ['monthly', 'quarterly'],
          aggregated_frequencies: ['quarterly', 'annual'],
          last_value: 3.1,
          last_date: '2026-06-01',
        }],
      }],
    });

    const row = await screen.findByRole('link', { name: /Уровень безработицы/ });
    const badges = Array.from(row.querySelectorAll('span.rounded-full'));
    // Месячные данные — только «мес.»; кв./год перечислены в подсказке.
    expect(badges.map((b) => b.textContent)).toEqual(['мес.']);
    expect(badges[0].className).not.toContain('opacity-60');
    expect(badges[0].getAttribute('title')).toBe('мес.; также: кв., ~год');
  });

  it('нет месячных среди официальных — показывается квартальный бейдж', async () => {
    renderCountry('germany', {
      ...GERMANY,
      categories: [{
        name: 'Национальные счета',
        count: 1,
        indicators: [{
          code: 'de-gdp',
          name: 'ВВП',
          unit: '%',
          frequency: 'quarterly',
          frequencies: ['quarterly', 'annual'],
          last_value: 0.3,
          last_date: '2026-03-01',
        }],
      }],
    });

    const row = await screen.findByRole('link', { name: /ВВП/ });
    const badges = Array.from(row.querySelectorAll('span.rounded-full'));
    expect(badges.map((b) => b.textContent)).toEqual(['кв.']);
    expect(badges[0].getAttribute('title')).toBe('кв.; также: год');
  });

  it('только расчётная частота — бейдж приглушён с тильдой', async () => {
    renderCountry('germany', {
      ...GERMANY,
      categories: [{
        name: 'Национальные счета',
        count: 1,
        indicators: [{
          code: 'de-gdp-a',
          name: 'ВВП годовой',
          unit: '%',
          frequency: 'annual',
          frequencies: [],
          aggregated_frequencies: ['annual'],
          last_value: 1.2,
          last_date: '2025-12-31',
        }],
      }],
    });

    const row = await screen.findByRole('link', { name: /ВВП годовой/ });
    const badges = Array.from(row.querySelectorAll('span.rounded-full'));
    expect(badges.map((b) => b.textContent)).toEqual(['~год']);
    expect(badges[0].className).toContain('opacity-60');
    expect(badges[0].getAttribute('title')).toBeNull();
  });

  it('без частот бейджей нет', async () => {
    renderCountry('germany', {
      ...GERMANY,
      categories: [{
        name: 'Прочее',
        count: 1,
        indicators: [{
          code: 'de-x',
          name: 'Без частоты',
          unit: '',
          frequency: null,
          frequencies: [],
          aggregated_frequencies: [],
          last_value: 1,
          last_date: '2026-01-01',
        }],
      }],
    });

    const row = await screen.findByRole('link', { name: /Без частоты/ });
    expect(row.querySelectorAll('span.rounded-full').length).toBe(0);
  });
});

describe('WorldCountry empty states', () => {
  it('пустой каталог ведёт к списку стран, а не на /world', async () => {
    renderCountry('germany', {
      ...GERMANY,
      country: { ...GERMANY.country, indicators_count: 0 },
      categories: [],
      overview: [],
      market_indicators: [],
    });

    expect(await screen.findByText(/Пока нет опубликованных показателей/)).toBeTruthy();
    const link = screen.getByRole('link', { name: 'К списку стран' });
    expect(link.getAttribute('href')).toBe('/#countries');
  });

  it('пустой поиск сбрасывается кнопкой из i18n', async () => {
    renderCountry('germany', GERMANY);
    await screen.findByRole('heading', { name: 'Рынок труда' });

    fireEvent.change(screen.getByLabelText('Поиск по показателям страны'), {
      target: { value: 'qqqq' },
    });
    expect(await screen.findByText(/По запросу «qqqq» ничего не найдено/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Сбросить поиск' }));
    expect(await screen.findByRole('heading', { name: 'Рынок труда' })).toBeTruthy();
  });
});

describe('WorldCountry coverage copy', () => {
  it('CTA «Сравнить показатели» на странице ровно один', async () => {
    renderCountry('united-states', US_COUNTRY);

    await screen.findByRole('heading', { name: 'Рынок труда' });
    const cta = screen.getAllByRole('link', {
      name: /Сравнить показатели|Compare indicators/,
    });
    expect(cta).toHaveLength(1);
  });

  it('пустой strip обзорных показателей не повторяет hero-абзац о покрытии', async () => {
    renderCountry('germany', {
      ...GERMANY,
      overview: [],
    });

    await screen.findByRole('heading', { name: 'Рынок труда' });

    // Hero-абзац «{N} в {M} …» на странице один — strip его не дублирует.
    // Скоуп по абзацам: кастомный матчер по textContent в testing-library
    // проходит и по body-обёрткам, что даёт ложные совпадения.
    const heroParagraphs = Array.from(document.querySelectorAll('p'))
      .filter((node) => /\d+ \S+ в \d+/.test(node.textContent));
    expect(heroParagraphs).toHaveLength(1);
    // Пустой strip несёт альтернативную строку (ключ world.country.coverageAlt;
    // пока словарь параллельной правки не влит, t() отдаёт сырой ключ —
    // принимаем оба состояния, дублирование hero-текста не допускается ни в каком).
    const stripCopy = document.querySelector('div.sm\\:col-span-3')?.textContent || '';
    expect(stripCopy).not.toMatch(/\d+ \S+ в \d+/);
    expect(stripCopy.length).toBeGreaterThan(0);
  });
});
