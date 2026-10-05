// Волна 6, G: калькулятор инфляции: валюта страны, понятные режимы, итог «было / стало», «Смотреть дальше» по стране.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import CalculatorPage from './CalculatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('gsap', () => ({
  default: {
    fromTo: () => ({ kill: () => {} }),
    to: () => ({ kill: () => {} }),
  },
}));

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

function monthlyCpi(fromYear, toYear, value) {
  const out = [];
  for (let y = fromYear; y <= toYear; y += 1) {
    for (let m = 1; m <= 12; m += 1) out.push({ date: `${y}-${String(m).padStart(2, '0')}-01`, value });
  }
  return out;
}
const CPI = { data: monthlyCpi(2020, 2021, 100) };

const CATALOG = {
  items: [
    { code: 'w:united-states:hicp-index', country_slug: 'united-states', country_name: 'США', concept_slug: 'hicp-index', indicator_code: 'us-cpi-all', frequency: 'monthly', unit: 'индекс' },
    { code: 'w:germany:hicp-index', country_slug: 'germany', country_name: 'Германия', concept_slug: 'hicp-index', indicator_code: 'de-hicp', frequency: 'monthly', unit: 'индекс' },
    { code: 'w:australia:hicp-index', country_slug: 'australia', country_name: 'Австралия', concept_slug: 'hicp-index', indicator_code: 'au-cpi', frequency: 'quarterly', unit: 'индекс' },
  ],
  total: 3,
};

function series(slug, name, code) {
  return {
    meta: { country_slug: slug, country_name: name, indicator_code: code, concept_slug: 'hicp-index' },
    data: [
      { date: '2018-12-01', value: 100 },
      { date: '2019-12-01', value: 102 },
      { date: '2020-12-01', value: 106.08 },
    ],
  };
}

function mockApis(overrides = []) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ...overrides,
    ['/indicators/cpi/data', CPI],
    ['/indicators/cpi-food/data', CPI],
    ['/indicators/cpi-nonfood/data', CPI],
    ['/indicators/cpi-services/data', CPI],
    ['/world/compare/catalog', CATALOG],
    [/^\/world\/compare\/series\/germany\//, series('germany', 'Германия', 'de-hicp')],
    [/^\/world\/compare\/series\/united-states\//, series('united-states', 'США', 'us-cpi-all')],
    [/^\/world\/compare\/series\/australia\//, series('australia', 'Австралия', 'au-cpi')],
    [/^\/world\/indicators\//, { indicator: { source: 'Статистическое ведомство', code: 'x' }, country: { slug: 'germany', name: 'Германия' } }],
  ]);
}

const collapse = (text) => String(text || '').replace(/\u00A0/g, ' ').replace(/\s+/g, ' ').trim();

function setPreviewLocale(locale) {
  const url = new URL(window.location.href);
  if (locale) url.searchParams.set('preview_locale', locale);
  else url.searchParams.delete('preview_locale');
  window.history.pushState({}, '', url.toString());
}

describe('CalculatorPage: волна 6', () => {
  it('сумма подписана валютой страны, итог с валютой, а не «нац. валюта»', async () => {
    mockApis();
    renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2019&to=2020&country=germany' });
    expect(await screen.findByLabelText(/Сумма в евро/)).toBeTruthy();
    await waitFor(() => expect(collapse(document.body.textContent)).toMatch(/106 080 €/));
    expect(document.body.textContent).not.toMatch(/нац\. валюта/);
  });

  it('австралийские доллары называются по-русски', async () => {
    mockApis();
    renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2019&to=2020&country=australia' });
    expect(await screen.findByLabelText(/Сумма в австралийских долларах/)).toBeTruthy();
  });

  it('EN: США по умолчанию, «Amount in US dollars», итог «$106,080»', async () => {
    mockApis();
    setPreviewLocale('en');
    try {
      renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2019&to=2020' });
      expect(await screen.findByLabelText(/Amount in US dollars/)).toBeTruthy();
      await waitFor(() => expect(collapse(document.body.textContent)).toMatch(/\$106,080/));
      expect(document.body.textContent).not.toMatch(/local currency/i);
    } finally {
      setPreviewLocale(null);
    }
  });

  it('пока каталог стран грузится, выбранная страна не подменяется Россией и слаг не виден', async () => {
    mockApiGet([['/auth/me', { user: null }]]);
    // Каталог стран «висит»: перехватываем сам запрос.
    const api = (await import('../lib/api')).default;
    api.get.mockImplementation((url) => (url === '/world/compare/catalog'
      ? new Promise(() => {})
      : Promise.reject(Object.assign(new Error('x'), { response: { status: 404 } }))));
    setPreviewLocale('en');
    try {
      renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2019&to=2020' });
      const picker = await screen.findByRole('button', { name: 'Country' });
      expect(picker.textContent).not.toMatch(/Россия|Russia/);
      expect(document.body.textContent).not.toContain('united-states');
    } finally {
      setPreviewLocale(null);
    }
  });

  it('направление: «Сколько стоит сегодня» и «Сколько стоило тогда» вместо «Прямой расчёт»', async () => {
    mockApis();
    renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2020&to=2021' });
    const today = await screen.findByRole('button', { name: /Сколько стоит сегодня/ });
    const then = screen.getByRole('button', { name: /Сколько стоило тогда/ });
    expect(today.getAttribute('aria-pressed')).toBe('true');
    expect(then.getAttribute('aria-pressed')).toBe('false');
    expect(document.body.textContent).not.toMatch(/Прямой расчёт/);
    fireEvent.click(then);
    expect(then.getAttribute('aria-pressed')).toBe('true');
    expect(today.getAttribute('aria-pressed')).toBe('false');
  });

  it('итог сопровождается картинкой «было / стало» и витриной калькуляторов', async () => {
    mockApis();
    const { container } = renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2020&to=2021' });
    await waitFor(() => expect(container.querySelector('.fe-w6g-ba')).toBeTruthy());
    expect(container.querySelectorAll('.fe-w6g-ba__bar')).toHaveLength(2);
    const showcase = container.querySelector('[data-block="calc-showcase"]');
    expect(showcase).toBeTruthy();
    const links = [...showcase.querySelectorAll('a')];
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/calculator', '/calculator/mortgage', '/calculator/compound']);
    expect(links[0].getAttribute('aria-current')).toBe('page');
    expect(showcase.textContent).toContain('Россия и десятки стран');
    expect(showcase.textContent).toContain('Для любой валюты');
  });

  it('«Смотреть дальше» следует за выбранной страной', async () => {
    mockApis();
    renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2019&to=2020&country=germany' });
    const link = await screen.findByRole('link', { name: 'Экономика: Германия' });
    expect(link.getAttribute('href')).toBe('/germany');
    expect(screen.getByRole('link', { name: 'Инфляция в странах мира' }).getAttribute('href')).toBe('/world/rating/hicp-index');
    expect(screen.getByRole('link', { name: 'Сравнить с другой страной' }).getAttribute('href')).toContain('w%3Agermany%3Ahicp-index');
    expect(screen.queryByRole('link', { name: 'Демография' })).toBeNull();
  });

  it('для России «Смотреть дальше» прежнее: регионы, демография, экономика', async () => {
    mockApis();
    renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2020&to=2021' });
    expect(await screen.findByRole('link', { name: 'Демография' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Регионы России' })).toBeTruthy();
  });

  it('сбой загрузки: понятный текст без «ряд» и кнопка «Повторить»', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/compare/catalog', CATALOG],
    ]);
    const api = (await import('../lib/api')).default;
    const original = api.get.getMockImplementation();
    api.get.mockImplementation((url) => (String(url).startsWith('/world/compare/series/')
      ? Promise.reject(Object.assign(new Error('boom'), { response: { status: 500 } }))
      : original(url)));
    renderPage(<CalculatorPage />, { path: '/calculator', route: '/calculator?amount=100000&from=2019&to=2020&country=germany' });
    // Хук один раз повторяет запрос сам (с паузой), поэтому ждём чуть дольше обычного.
    const alert = await screen.findByRole('alert', {}, { timeout: 5000 });
    expect(alert.textContent).toMatch(/Не получилось загрузить данные о ценах/);
    expect(alert.textContent).not.toMatch(/ряд/);
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
  });
});
