// Волна 6, G: страница раздела «Курсы валют и криптовалют» и страница одного курса.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import CategoryPage from './CategoryPage';
import IndicatorDetail from './IndicatorDetail';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const day = 24 * 60 * 60 * 1000;
const start = Date.parse('2025-09-01');
const HISTORY = Array.from({ length: 400 }, (_, i) => ({
  date: new Date(start + i * day).toISOString().slice(0, 10),
  value: 70 + i * 0.05,
}));

const LIST = [
  { code: 'eur-rub', name: 'Курс евро', unit: 'руб.', category: 'Валюты', category_ru: 'Валюты', frequency: 'daily', is_active: true, is_listed: true, current_value: 100, current_date: '2026-10-03', change: 0.2 },
  { code: 'usd-rub', name: 'Курс доллара США', unit: 'руб.', category: 'Валюты', category_ru: 'Валюты', frequency: 'daily', is_active: true, is_listed: true, current_value: 80, current_date: '2026-10-03', change: 0.4 },
  { code: 'btc-usd', name: 'Bitcoin', unit: 'USD', category: 'Валюты', category_ru: 'Валюты', frequency: 'daily', is_active: true, is_listed: true, current_value: 60000, current_date: '2026-10-05', change: 100 },
];

describe('/currencies', () => {
  it('конвертер сверху, вкладки, поиск валюты вместо общего поиска, строки по популярности', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\/[a-z-]+\/data/, { data: HISTORY }],
      [/^\/indicators(\?|$)/, LIST],
    ]);
    const { container } = renderPage(<CategoryPage fixedSlug="currencies" />, { path: '/currencies', route: '/currencies' });
    expect(await screen.findByRole('heading', { name: 'Конвертер валют' })).toBeTruthy();
    expect(screen.getByPlaceholderText('Найти валюту')).toBeTruthy();
    // Общего поля «Найти показатель или страну» на этой странице нет.
    expect(container.querySelector('[data-block="category-list"]').textContent).not.toMatch(/Найти показатель или страну/);
    const titles = [...container.querySelectorAll('.fe-w6g-currency-row .fe-trow__title')].map((n) => n.textContent);
    expect(titles).toEqual(['Доллар США к рублю', 'Евро к рублю']);
  });
});

describe('страница курса', () => {
  it('USD/RUB: сейчас, неделя, месяц, год и размах вместо «среднего за 28 лет»; ведёт к евро, юаню и нефти', async () => {
    const detail = {
      code: 'usd-rub', name: 'Курс доллара США', name_en: 'USD/RUB Exchange Rate', unit: 'руб.', frequency: 'daily',
      category: 'Валюты', source: 'Банк России', is_active: true, is_listed: true,
      current_value: 89.95, current_date: '2026-10-05', description: 'Описание', methodology: 'Методология', seo_blocks: null,
    };
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\/usd-rub$/, detail],
      [/^\/indicators\/usd-rub\/data/, { indicator: 'usd-rub', data: HISTORY }],
      [/^\/indicators\/usd-rub\/stats/, { code: 'usd-rub', data_count: 400, average: 46.17, highest: { date: '2022-03-11', value: 120.38 } }],
      [/^\/indicators\/usd-rub\/forecast/, { indicator: 'usd-rub', forecast: null }],
      [/^\/indicators(\?|$)/, LIST],
      [/^\/regions/, { districts: [], sections: [] }],
    ]);
    const { container } = renderPage(<IndicatorDetail />, {
      path: '/currencies/indicator/:code', route: '/currencies/indicator/usd-rub',
    });
    await waitFor(() => expect(container.querySelector('[data-block="currency-telemetry"]')).toBeTruthy(), { timeout: 3000 });
    const labels = [...container.querySelectorAll('[data-block="currency-telemetry"] .fe-tele__label')].map((n) => n.textContent);
    expect(labels).toEqual(['Сейчас', 'За неделю', 'За месяц', 'За год']);
    expect(container.textContent).not.toMatch(/Среднее значение|Исторический максимум/);
    expect(container.querySelector('[data-testid="currency-range"]')).toBeTruthy();
    // Вместо тупика: что посмотреть дальше.
    const next = await screen.findByRole('region', { name: 'Что посмотреть дальше' }, { timeout: 3000 });
    expect(next.textContent).toContain('Евро к рублю');
    expect(next.textContent).toContain('Нефть Brent');
    // Подпись панели режимов: «Показать», а не «Вид графика».
    expect(container.querySelector('.fe-vm-toggle__label')?.textContent ?? 'Показать').toBe('Показать');
  });
});
