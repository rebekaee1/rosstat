import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
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

function renderCountry(slug, payload, locale) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [`/world/countries/${slug}`, payload],
  ]);
  return renderPage(<WorldCountry />, {
    path: '/:countrySlug',
    route: `/${slug}`,
    locale,
  });
}

describe('WorldCountry market indicators', () => {
  it('keeps country qualifiers and semantic matches inside the current catalogue', async () => {
    renderCountry('germany', GERMANY);
    await screen.findByRole('heading', { name: 'Рынок труда' });
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'безработица Germany' } });
    expect(await screen.findByRole('link', { name: /Уровень безработицы/ })).toBeTruthy();
    fireEvent.change(input, { target: { value: 'безработица France' } });
    await screen.findByText(/По запросу/);
    expect(screen.queryByRole('link', { name: /Уровень безработицы/ })).toBeNull();
  });

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

describe('WorldCountry category navigation', () => {
  const TWO_CATEGORIES = {
    ...GERMANY,
    categories: [
      ...GERMANY.categories,
      {
        name: 'Цены', name_en: 'Prices', indicators: [{
          code: 'de-cpi', name: 'Индекс цен', frequency: 'monthly',
          last_value: 102, last_date: '2026-06-01',
        }],
      },
    ],
  };

  it('groups US source categories into two levels without changing the country indicator links', async () => {
    renderCountry('united-states', {
      ...US_COUNTRY,
      categories: [
        { name: 'Рынок труда', name_ru: 'Рынок труда', indicators: US_COUNTRY.categories[0].indicators },
        { name: 'Состав ВВП', name_ru: 'Состав ВВП', indicators: [{
          code: 'us-bea-sagdp1-4', name: 'Состав ВВП: Оплата труда',
          name_ru: 'Состав ВВП: Оплата труда', frequency: 'annual', last_value: 10,
        }] },
        { name: 'ВВП по отраслям, текущие цены', name_ru: 'ВВП по отраслям, текущие цены', indicators: [{
          code: 'us-bea-sagdp2-1', name: 'ВВП по отраслям, текущие цены: Все отрасли',
          name_ru: 'ВВП по отраслям, текущие цены: Все отрасли', frequency: 'annual', last_value: 20,
        }] },
      ],
    });

    expect(await screen.findByRole('heading', { name: 'Состав ВВП' })).toBeTruthy();
    expect(screen.getAllByRole('button', { name: /ВВП и производство/ }).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /Оплата труда/ }).getAttribute('href'))
      .toBe('/united-states/indicator/us-bea-sagdp1-4');
    fireEvent.click(screen.getByRole('button', { name: /ВВП по отраслям, текущие цены/ }));
    expect(screen.getByRole('link', { name: /Все отрасли/ }).getAttribute('href'))
      .toBe('/united-states/indicator/us-bea-sagdp2-1');
    fireEvent.click(screen.getByRole('button', { name: /Труд и зарплаты/ }));
    expect(await screen.findByRole('heading', { name: 'Рынок труда' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Уровень безработицы/ })).toBeTruthy();
  });

  it('на десктопе показывает все категории подряд для непрерывной прокрутки', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media,
      addEventListener() {}, removeEventListener() {},
    }));
    renderCountry('germany', TWO_CATEGORIES);

    expect(await screen.findByRole('heading', { name: 'Рынок труда' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Цены' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Индекс цен/ })).toBeTruthy();
  });

  it('ограничивает огромный каталог и оставляет все показатели доступными через разделы и поиск', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media,
      addEventListener() {}, removeEventListener() {},
    }));
    const indicators = Array.from({ length: 220 }, (_, index) => ({
      code: `at-test-${index}`,
      name: `Тестовый показатель ${index}`,
      frequency: 'annual',
      last_value: index,
      last_date: '2025-01-01',
    }));
    renderCountry('austria', {
      ...GERMANY,
      country: { ...GERMANY.country, code: 'AT', slug: 'austria', name: 'Австрия', indicators_count: 221 },
      categories: [
        { name: 'Общество', indicators },
        { name: 'Цены', indicators: [{ code: 'at-cpi', name: 'Индекс цен Австрии', frequency: 'monthly' }] },
      ],
    });

    expect(await screen.findByRole('heading', { name: 'Общество' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Цены' })).toBeTruthy();
    expect(document.querySelectorAll('[data-world-country-category] a[href*="/indicator/"]')).toHaveLength(41);
    fireEvent.click(screen.getByRole('button', { name: /Показать ещё показатели/ }));
    expect(document.querySelectorAll('[data-world-country-category] a[href*="/indicator/"]')).toHaveLength(161);
    fireEvent.click(screen.getByRole('button', { name: /Показать ещё показатели/ }));
    expect(document.querySelectorAll('[data-world-country-category] a[href*="/indicator/"]')).toHaveLength(221);

    fireEvent.click(within(document.querySelector('aside')).getByRole('button', { name: /Цены/ }));
    expect(screen.getByRole('heading', { name: 'Цены' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Индекс цен Австрии/ })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Общество' })).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Поиск по показателям страны'), { target: { value: 'Тестовый показатель' } });
    expect(await screen.findByRole('link', { name: /Тестовый показатель 0/ })).toBeTruthy();
    expect(document.querySelectorAll('[data-world-country-category] a[href*="/indicator/"]')).toHaveLength(120);
  }, 30000);

  it('на десктопе подсвечивает категорию, до которой пользователь прокрутил страницу', async () => {
    const frames = [];
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media,
      addEventListener() {}, removeEventListener() {},
    }));
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      frames.push(cb);
      return frames.length;
    });
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function rect() {
      return { top: this.dataset.worldCountryCategory === 'Рынок труда' ? 100 : -300 };
    });
    renderCountry('germany', TWO_CATEGORIES);
    await screen.findByRole('heading', { name: 'Цены' });

    act(() => { frames.splice(0).forEach((cb) => cb()); });
    fireEvent.scroll(window);
    act(() => { frames.splice(0).forEach((cb) => cb()); });
    const sidebar = document.querySelector('aside');
    // Главные темы идут первыми: «Цены» стоят выше «Рынка труда», прокрутка дошла до второй.
    expect(within(sidebar).getByRole('button', { name: /Рынок труда/ }).getAttribute('aria-current')).toBe('true');
  });

  it('на телефоне сохраняет выбор одной категории через мобильное меню', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: !media.includes('min-width'), media,
      addEventListener() {}, removeEventListener() {},
    }));
    renderCountry('germany', TWO_CATEGORIES);

    // Главные темы идут первыми: сначала «Цены», а не категория, случайно первая по алфавиту.
    expect(await screen.findByRole('heading', { name: 'Цены' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Рынок труда' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Цены\s*1\s*Сменить/ }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Рынок труда/ }));
    expect(screen.getByRole('heading', { name: 'Рынок труда' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Цены' })).toBeNull();
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
    expect(badges.map((b) => b.textContent)).toEqual(['ежемесячно']);
    expect(badges[0].className).not.toContain('opacity-60');
    expect(badges[0].getAttribute('title')).toBe('ежемесячно; также: ежеквартально, ~ежегодно');
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
    expect(badges.map((b) => b.textContent)).toEqual(['ежеквартально']);
    expect(badges[0].getAttribute('title')).toBe('ежеквартально; также: ежегодно');
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
    expect(badges.map((b) => b.textContent)).toEqual(['~ежегодно']);
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

    // Счётчики базы («7964 показателя в 10 разделах») человеку не нужны: hero-абзаца с цифрами покрытия нет совсем.
    const heroParagraphs = Array.from(document.querySelectorAll('p'))
      .filter((node) => /\d+ \S+ в \d+/.test(node.textContent));
    expect(heroParagraphs).toHaveLength(0);
    // Пустой strip несёт альтернативную строку (ключ world.country.coverageAlt;
    // пока словарь параллельной правки не влит, t() отдаёт сырой ключ —
    // принимаем оба состояния, дублирование hero-текста не допускается ни в каком).
    const stripCopy = document.querySelector('div.sm\\:col-span-3')?.textContent || '';
    expect(stripCopy).not.toMatch(/\d+ \S+ в \d+/);
    expect(stripCopy.length).toBeGreaterThan(0);
  });
});

describe('WorldCountry key figures', () => {
  it('shows the unit and the period beside every number and never an indicator code', async () => {
    renderCountry('germany', {
      ...GERMANY,
      overview: [
        {
          concept_slug: 'hicp-index', name: 'Изменение потребительских цен за год', name_en: 'Consumer prices, year over year',
          unit: '%', indicator_code: 'de-prc_hicp_minr', frequency: 'monthly', date: '2026-08-01', value: 2.92,
        },
        {
          concept_slug: 'unemployment-rate', name: 'Уровень безработицы', name_en: 'Unemployment rate',
          unit: '% экономически активного населения', indicator_code: 'de-une', frequency: 'monthly', date: '2026-08-01', value: 4,
        },
      ],
    });
    await screen.findByRole('heading', { name: 'Рынок труда' });
    const cards = document.querySelectorAll('.w2-kpi');
    expect(cards).toHaveLength(2);
    const first = cards[0].textContent.replace(/\u00A0/g, ' ');
    // Название плитки короткое и человеческое; полное официальное название остаётся в подсказке.
    expect(first).toContain('Инфляция');
    expect(cards[0].querySelector('.w2-kpi-name').getAttribute('title')).toBe('Изменение потребительских цен за год');
    expect(first).toContain('2,9');
    // Видимое число сразу итоговое (не «докручивается» от нуля) и округлено до одного знака.
    expect(cards[0].querySelector('.w2-kpi-value [aria-hidden="true"]').textContent).toBe('2,9');
    expect(first).toContain('%');
    expect(first).toContain('август 2026');
    expect(first).not.toContain('prc_hicp');
    const second = cards[1].textContent.replace(/\u00A0/g, ' ');
    expect(second).toContain('4,0');
    expect(second).toContain('% экономически активного населения');
    expect(document.body.textContent).not.toContain('\u00B7');
  });

  it('puts the main themes first and keeps the rest alphabetical', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media, addEventListener() {}, removeEventListener() {},
    }));
    renderCountry('germany', {
      ...GERMANY,
      categories: [
        { name: 'Бизнес и инвестиции', indicators: [{ code: 'de-b', name: 'Инвестиции', frequency: 'annual', last_value: 1, last_date: '2025-01-01' }] },
        { name: 'Население', indicators: [{ code: 'de-p', name: 'Население', frequency: 'annual', last_value: 1, last_date: '2025-01-01' }] },
        { name: 'Национальные счета', indicators: [{ code: 'de-n', name: 'ВВП', frequency: 'annual', last_value: 1, last_date: '2025-01-01' }] },
      ],
    });
    await screen.findByRole('heading', { name: 'Национальные счета' });
    const order = Array.from(document.querySelectorAll('[data-world-country-category]')).map((node) => node.dataset.worldCountryCategory);
    expect(order).toEqual(['Национальные счета', 'Население', 'Бизнес и инвестиции']);
  });

  it('moves a thin topic behind the full ones so the first screen is not poor', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media, addEventListener() {}, removeEventListener() {},
    }));
    const many = (prefix) => Array.from({ length: 6 }, (_, i) => ({
      code: `${prefix}-${i}`, name: `${prefix} ${i}`, frequency: 'annual', last_value: 1, last_date: '2025-01-01',
    }));
    renderCountry('germany', {
      ...GERMANY,
      categories: [
        { name: 'Национальные счета', indicators: [{ code: 'de-n', name: 'ВВП', frequency: 'annual', last_value: 1, last_date: '2025-01-01' }] },
        { name: 'Рынок труда', indicators: many('lab') },
        { name: 'Цены', indicators: many('pr') },
      ],
    });
    await screen.findByRole('heading', { name: 'Цены' });
    const order = Array.from(document.querySelectorAll('[data-world-country-category]')).map((node) => node.dataset.worldCountryCategory);
    expect(order).toEqual(['Цены', 'Рынок труда', 'Национальные счета']);
  });
});

describe('WorldCountry EN overlay', () => {
  it('при русском payload и locale=en показывает английские имена и единицы', async () => {
    renderCountry('canada', {
      country: {
        code: 'CA',
        slug: 'canada',
        name: 'Канада',
        name_en: 'Canada',
        region: 'Америка',
        region_en: 'Americas',
        indicators_count: 1,
      },
      categories: [{
        name: 'Национальные счета',
        name_en: 'National accounts',
        count: 1,
        indicators: [{
          code: 'ca-weo-ngdpd',
          name: 'Валовой внутренний продукт в текущих ценах',
          name_en: 'Gross domestic product at current prices',
          unit: 'млрд $',
          frequency: 'annual',
          frequencies: ['annual'],
          last_value: 2319.9,
          last_date: '2025-01-01',
        }],
      }],
      overview: [{
        concept_slug: 'gdp-usd',
        name: 'ВВП в текущих ценах',
        name_en: 'GDP at current prices',
        indicator_code: 'ca-weo-ngdpd',
        frequency: 'annual',
        date: '2025-01-01',
        value: 2319.9,
      }],
      coverage: {
        history_start: '1980-01-01',
        history_end: '2025-01-01',
        frequencies: ['annual'],
      },
      market_indicators: [],
    }, 'en');

    const heading = await screen.findByRole('heading', { name: /Canada/ });
    expect(heading.textContent).not.toMatch(/[А-Яа-яЁё]/);
    expect(await screen.findByRole('heading', { name: 'National accounts' })).toBeTruthy();
    expect(screen.getByRole('link', {
      name: /Gross domestic product at current prices/,
    })).toBeTruthy();
    expect(document.body.textContent).toContain('billion $');
    expect(document.body.textContent.replace(/\u00a0/g, ' ')).toContain('2,319.9');
    expect(document.body.textContent).toContain('Americas');
    expect(document.body.textContent).not.toContain('млрд $');
    expect(document.body.textContent).not.toContain('Национальные счета');
    expect(document.body.textContent).not.toContain('Канада');
  });
});

describe('WorldCountry числа одним правилом (RU)', () => {
  it('в списке тем запятая и неразрывный пробел тысяч, как на странице показателя', async () => {
    const payload = {
      ...GERMANY,
      categories: [{
        name: 'Цены',
        indicators: [
          {
            code: 'de-hicp', name: 'Индекс цен', unit: 'индекс', frequency: 'monthly',
            last_value: 132.5, change: 0.1, last_date: '2025-12-01',
          },
          {
            code: 'de-pop', name: 'Население', unit: 'человек', frequency: 'annual',
            last_value: 83400000, last_date: '2025-01-01',
          },
        ],
      }],
    };
    renderCountry('germany', payload, 'ru');
    const row = await screen.findByRole('link', { name: /Индекс цен/ });
    expect(row.textContent).toContain('132,5');
    expect(row.textContent).toContain('+0,10');
    expect(row.textContent).not.toMatch(/\d\.\d/);
    const big = screen.getByRole('link', { name: /Население/ });
    expect(big.textContent).toContain('83 400 000');
  });
});

describe('WorldCountry: волна 6, профиль и список показателей', () => {
  const OVERVIEW = [
    {
      concept_slug: 'hicp-index', name: 'Изменение потребительских цен за год', name_en: 'Consumer prices, year over year',
      unit: '%', indicator_code: 'de-hicp', frequency: 'monthly', date: '2026-08-01', value: 2.9,
    },
    {
      concept_slug: 'budget-balance-gdp', name: 'Сальдо бюджета сектора государственного управления', name_en: 'General government balance',
      unit: '% ВВП', indicator_code: 'de-bud', frequency: 'annual', date: '2025-01-01', value: -2.1,
    },
  ];

  it('заголовок плитки короткий и человеческий, у плитки без ряда есть значок «график недоступен»', async () => {
    renderCountry('germany', { ...GERMANY, overview: OVERVIEW });
    await screen.findByRole('heading', { name: 'Главное' });
    const names = [...document.querySelectorAll('.w2-kpi-name')].map((el) => el.textContent);
    expect(names).toEqual(['Инфляция', 'Баланс бюджета']);
    await waitFor(() => expect(screen.getAllByText('график недоступен')).toHaveLength(2));
  });

  it('кнопка «Сравнить с Россией» ведёт на сравнение двух стран по сопоставимому показателю', async () => {
    renderCountry('germany', { ...GERMANY, overview: OVERVIEW });
    const link = await screen.findByRole('link', { name: /Сравнить с Россией/ });
    expect(link.getAttribute('href')).toBe('/compare?codes=w:germany:hicp-index,w:russia:hicp-index');
  });

  it('без общего с Россией показателя кнопки «Сравнить с Россией» нет', async () => {
    renderCountry('germany', { ...GERMANY, overview: [{ ...OVERVIEW[1], concept_slug: 'activity-rate' }] });
    await screen.findByRole('heading', { name: 'Главное' });
    expect(screen.queryByRole('link', { name: /Сравнить с Россией/ })).toBeNull();
  });

  it('«Мировые рынки» стоят ниже каталога показателей, а не перед ним', async () => {
    renderCountry('united-states', US_COUNTRY);
    const markets = await screen.findByTestId('country-market-indicators');
    const catalog = document.querySelector('[data-world-country-category]');
    expect(catalog.compareDocumentPosition(markets) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('почти-дубли свёрнуты в одну строку, а единица не повторяется в названии', async () => {
    renderCountry('germany', {
      ...GERMANY,
      categories: [{
        name: 'Население',
        indicators: [
          { code: 'de-b1', name: 'Число родившихся по возрасту матери, до 20 лет', unit: 'человек', frequency: 'annual', last_value: 10, last_date: '2025-01-01' },
          { code: 'de-b2', name: 'Число родившихся по возрасту матери, 20-24', unit: 'человек', frequency: 'annual', last_value: 20, last_date: '2025-01-01' },
          { code: 'de-b3', name: 'Число родившихся по месту проживания', unit: 'человек', frequency: 'annual', last_value: 30, last_date: '2025-01-01' },
          { code: 'de-d', name: 'Число умерших, человек', unit: 'человек', frequency: 'annual', last_value: 40, last_date: '2025-01-01' },
        ],
      }],
    });
    await screen.findByRole('heading', { name: 'Население' });
    const group = document.querySelector('.fe-ind-group');
    expect(group).toBeTruthy();
    expect(group.querySelector('.fe-ind-group__name').textContent).toBe('Число родившихся');
    expect(group.querySelector('.fe-ind-group__count').textContent).toBe('3 разреза');
    expect(group.hasAttribute('open')).toBe(false);
    // Одиночный показатель: «, человек» в названии убрано, единица осталась подписью под ним.
    const single = screen.getByRole('link', { name: /Число умерших/ });
    expect(single.textContent).not.toMatch(/Число умерших, человек/);
  });

  it('EN: заголовок «The economy of the United States»', async () => {
    renderCountry('united-states', US_COUNTRY, 'en');
    expect(await screen.findByRole('heading', { level: 1, name: 'The economy of the United States' })).toBeTruthy();
  });
});
