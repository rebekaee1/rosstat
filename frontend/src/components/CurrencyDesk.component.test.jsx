// Волна 6, G: раздел курсов: конвертер, вкладки, поиск валюты, пояснение про разные курсы; верх страницы курса.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import CurrencyDesk from './CurrencyDesk';
import CurrencyTelemetry from './CurrencyTelemetry';
import CurrencyNext from './CurrencyNext';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

/** Список валюты: открыть по подписи и выбрать вариант по названию. */
function pick(label, optionName) {
  fireEvent.click(screen.getByRole('combobox', { name: new RegExp(`^${label}`) }));
  fireEvent.click(screen.getByRole('option', { name: new RegExp(optionName) }));
}

/** Живая лента: доллар на бирже и золото, нефть, биткоин. */
function mockMarket() {
  const snapshots = [
    { code: 'usd-rub-live', price: 85.81, change_pct: 1.1 },
    { code: 'gold-rub-live', price: 11143, change_pct: -0.3 },
    { code: 'brent', price: 113.96, change_pct: -5 },
    { code: 'btc-usd', price: 85276, change_pct: -0.1 },
  ];
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: () => Promise.resolve({ snapshots }) });
}

const INDICATORS = [
  { code: 'btc-usd', name: 'Bitcoin', name_en: 'Bitcoin', current_value: 60000, current_date: '2026-10-05', change: 600, frequency: 'daily', is_active: true },
  { code: 'eur-usd', name: 'EUR/USD', current_value: 1.1, current_date: '2026-10-05', change: -0.01, frequency: 'daily', is_active: true },
  { code: 'usd-rub', name: 'Курс доллара США', current_value: 80, current_date: '2026-10-03', change: 0.4, frequency: 'daily', is_active: true },
  { code: 'eur-rub', name: 'Курс евро', current_value: 100, current_date: '2026-10-03', change: -0.2, frequency: 'daily', is_active: true },
  { code: 'cny-rub', name: 'Курс юаня', current_value: 12, current_date: '2026-10-03', change: 0, frequency: 'daily', is_active: true },
];

const DAILY = {
  data: Array.from({ length: 40 }, (_, i) => ({ date: `2026-08-${String((i % 28) + 1).padStart(2, '0')}`, value: 80 + i * 0.1 })),
};

function mockApis() {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators\/[a-z-]+\/data/, DAILY],
  ]);
}

describe('CurrencyDesk', () => {
  it('сверху конвертер: «100 долларов в рубли» по курсу ЦБ с датой', async () => {
    mockApis();
    renderPage(<CurrencyDesk indicators={INDICATORS} />);
    expect(screen.getByRole('heading', { name: 'Конвертер валют' })).toBeTruthy();
    expect(screen.getByLabelText('Сумма').value).toBe('100');
    const out = screen.getByTestId('converter-result');
    expect(out.textContent).toContain('8\u00A0000');
    expect(out.textContent).toContain('Рубль');
    expect(out.textContent).toMatch(/По курсу Банка России на 3 октября 2026/);
  });

  it('поменять местами и пересчитать; сумма с запятой и пробелами; мусор не ломает страницу', () => {
    mockApis();
    renderPage(<CurrencyDesk indicators={INDICATORS} />);
    fireEvent.click(screen.getByRole('button', { name: 'Поменять местами' }));
    fireEvent.change(screen.getByLabelText('Сумма'), { target: { value: '8 000' } });
    expect(screen.getByTestId('converter-result').textContent).toContain('100');
    expect(screen.getByRole('combobox', { name: /^Из/ }).getAttribute('data-value')).toBe('RUB');
    fireEvent.change(screen.getByLabelText('Сумма'), { target: { value: 'abc' } });
    expect(screen.getByTestId('converter-result').textContent).toContain('Введите число');
  });

  it('цепочка: биткоин в рубли идёт через доллар', () => {
    mockApis();
    renderPage(<CurrencyDesk indicators={INDICATORS} />);
    fireEvent.change(screen.getByLabelText('Сумма'), { target: { value: '1' } });
    pick('Из', 'Биткоин');
    expect(screen.getByTestId('converter-result').textContent).toContain('4\u00A0800\u00A0000');
    expect(screen.getByTestId('converter-result').textContent).toMatch(/По последним курсам/);
  });

  it('вкладки «Валюты / Крипто / Мир»: по популярности, в строках значок, график и источник курса', async () => {
    mockApis();
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    const tabs = screen.getByRole('group', { name: 'Разделы курсов' });
    expect(within(tabs).getAllByRole('button').map((b) => b.textContent)).toEqual(['Валюты', 'Крипто', 'Мир']);
    const rows = [...container.querySelectorAll('.fe-w6g-currency-row')];
    expect(rows.map((row) => row.querySelector('.fe-trow__title').textContent)).toEqual([
      'Доллар США к рублю', 'Евро к рублю', 'Китайский юань к рублю',
    ]);
    expect(rows[0].textContent).toContain('курс ЦБ на 3 окт.');
    expect(rows[0].querySelector('.fe-w6g-coin').textContent).toBeTruthy();
    // Мини-график у каждой строки, в том числе у «USD/RUB».
    await waitFor(() => expect(rows[0].querySelector('.fe-tile__spark')).toBeTruthy());

    fireEvent.click(within(tabs).getByRole('button', { name: 'Крипто' }));
    expect(container.querySelector('.fe-trow__title').textContent).toBe('Биткоин в долларах США');
    expect(container.querySelector('.fe-w6g-currency-row').textContent).toContain('закрытие дня, 5 окт.');
    fireEvent.click(within(tabs).getByRole('button', { name: 'Мир' }));
    expect(container.querySelector('.fe-trow__title').textContent).toBe('Евро к доллару США');
  });

  it('«Найти валюту»: по слову, по символу и по коду; пустой результат подсказывает, что ввести', () => {
    mockApis();
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    const search = screen.getByPlaceholderText('Найти валюту');
    fireEvent.change(search, { target: { value: 'бит' } });
    expect([...container.querySelectorAll('.fe-trow__title')].map((n) => n.textContent)).toEqual(['Биткоин в долларах США']);
    fireEvent.change(search, { target: { value: 'eur' } });
    expect(container.querySelectorAll('.fe-w6g-currency-row').length).toBe(2);
    fireEvent.change(search, { target: { value: 'атлантида' } });
    expect(screen.getByRole('status').textContent).toMatch(/Ничего не нашли/);
    fireEvent.click(screen.getByRole('button', { name: 'Сбросить поиск' }));
    expect(container.querySelectorAll('.fe-w6g-currency-row').length).toBe(3);
  });

  it('две плитки рядом: курс ЦБ с золотой отметкой и рыночный курс, пояснение одной строкой', async () => {
    mockApis();
    mockMarket();
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    const tiles = container.querySelector('[data-block="currency-rate-tiles"]');
    expect(tiles.textContent).toContain('Курс ЦБ на 3 окт.');
    expect(tiles.textContent).toContain('80,00');
    expect(tiles.querySelector('.fe-z8-rate--cb .fe-z8-rate__mark')).toBeTruthy();
    await waitFor(() => expect(tiles.textContent).toContain('85,81'));
    expect(tiles.textContent).toContain('Рынок');
    // Пояснение стоит на виду, а не за ссылкой «Почему курс отличается?».
    expect(tiles.querySelector('.fe-z8-why').textContent).toMatch(/официальный курс раз в день/);
    expect(container.querySelector('details.fe-w6g-why')).toBeNull();
  });

  it('справа «Золото, нефть, биткоин» из живой ленты; без ответа сервера блока нет', async () => {
    mockApis();
    mockMarket();
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    await waitFor(() => expect(container.querySelector('[data-block="currency-market-board"]')).toBeTruthy());
    const board = container.querySelector('[data-block="currency-market-board"]');
    expect([...board.querySelectorAll('.fe-z8-board__name')].map((n) => n.textContent)).toEqual(['Золото', 'Нефть', 'Биткоин']);
    expect(board.textContent).toContain('11\u00A0143');
  });

  it('без ответа ленты нет плитки «Рынок» и блока справа, остальное работает', () => {
    mockApis();
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    expect(container.querySelector('.fe-z8-rate--cb')).toBeTruthy();
    expect(container.querySelectorAll('.fe-z8-rate')).toHaveLength(1);
    expect(container.querySelector('[data-block="currency-market-board"]')).toBeNull();
    expect(container.querySelector('.fe-z8-why')).toBeNull();
  });

  it('у доллара значок «$», а не флаг; у евро флаг', () => {
    mockApis();
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    const coins = [...container.querySelectorAll('.fe-w6g-currency-row .fe-w6g-coin')].map((n) => n.textContent);
    expect(coins[0]).toBe('$');
    expect(coins[1]).not.toBe('$');
  });

  it('свой список валюты: открывается, ищет по слову, выбирается клавишей и закрывается по Escape', () => {
    mockApis();
    renderPage(<CurrencyDesk indicators={INDICATORS} />);
    const from = screen.getByRole('combobox', { name: /^Из/ });
    expect(from.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(from);
    expect(from.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getAllByRole('option').length).toBeGreaterThanOrEqual(4);
    const search = document.querySelector('.fe-z8-select__search input');
    fireEvent.change(search, { target: { value: 'евр' } });
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([expect.stringContaining('Евро')]);
    fireEvent.keyDown(search, { key: 'Enter' });
    expect(from.getAttribute('aria-expanded')).toBe('false');
    expect(from.getAttribute('data-value')).toBe('EUR');
    fireEvent.click(from);
    fireEvent.keyDown(screen.getByRole('listbox').parentElement, { key: 'Escape' });
    expect(from.getAttribute('aria-expanded')).toBe('false');
    expect(from.getAttribute('data-value')).toBe('EUR');
  });

  it('график пары за год и строка «1 USD = …»', async () => {
    mockApis();
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    expect(screen.getByTestId('converter-result').textContent).toContain('1 USD = 80,00 RUB');
    await waitFor(() => expect(container.querySelector('[data-block="currency-year-chart"] .fe-z8-chart__title')).toBeTruthy());
    expect(container.querySelector('.fe-z8-chart__title').textContent).toContain('Доллар США → Рубль');
  });
});

describe('CurrencyTelemetry', () => {
  const day = 24 * 60 * 60 * 1000;
  const start = Date.parse('2025-09-01');
  const points = Array.from({ length: 400 }, (_, i) => ({
    date: new Date(start + i * day).toISOString().slice(0, 10),
    value: 70 + i * 0.05,
  }));

  it('вместо «среднего за 28 лет»: сейчас, неделя, месяц, год и размах за год; откуда курс', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/indicators\/usd-rub\/data/, { data: points }]]);
    const { container } = renderPage(<CurrencyTelemetry code="usd-rub" fallback={<p>запасной</p>} />);
    await waitFor(() => expect(container.querySelector('[data-block="currency-telemetry"]')).toBeTruthy());
    const labels = [...container.querySelectorAll('.fe-tele__label')].map((n) => n.textContent);
    expect(labels).toEqual(['Сейчас', 'За неделю', 'За месяц', 'За год']);
    expect(container.textContent).not.toMatch(/Среднее|Исторический максимум/);
    expect(container.querySelector('[data-testid="currency-range"]').textContent).toMatch(/За последний год: от .*\s₽ \(.*\) до .*\s₽ \(.*\)\./);
    expect(container.querySelector('[data-testid="currency-basis"]').textContent).toMatch(/официальный курс Банка России/);
  });

  it('нет данных: показывается запасной верх', async () => {
    mockApiGet([['/auth/me', { user: null }], [/^\/indicators\/usd-rub\/data/, { data: [] }]]);
    renderPage(<CurrencyTelemetry code="usd-rub" fallback={<p>запасной</p>} />);
    expect(await screen.findByText('запасной')).toBeTruthy();
  });
});

describe('CurrencyNext', () => {
  it('ведёт к евро, юаню и нефти и к сравнению вместо тупика', () => {
    renderPage(<CurrencyNext code="usd-rub" />);
    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual([
      '/currencies/indicator/eur-rub', '/currencies/indicator/cny-rub', '/russia/indicator/brent',
      '/compare?codes=usd-rub%2Ceur-rub',
    ]);
    expect(screen.getByText('Нефть Brent')).toBeTruthy();
    expect(screen.getByText('Евро к рублю')).toBeTruthy();
  });
});
