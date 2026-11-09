import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderPage } from '../test/renderPage';
import R7PricesBlock from './R7PricesBlock';

const get = vi.fn();
vi.mock('../lib/api', () => ({ default: { get: (...a) => get(...a) } }));

const items = Array.from({ length: 8 }, (_, i) => ({
  code: `ceni-x${i}`, name: `Товар ${i}`, short_name: `Товар ${i}`, unit: 'рублей за литр',
  value: 100 + i, prev_value: 99, period_label: 'сентябрь 2026', yoy_pct: 8.4, spark: [90, 95, 100],
}));

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
  get.mockImplementation((url) => {
    if (url.includes('prices-summary')) {
      return Promise.resolve({ data: { items, groups: [{ group: 'Продукты', label: 'Продукты', count: 40 }], total: 40 } });
    }
    return Promise.resolve({ data: { districts: [{ slug: 'cfo', regions: [{ slug: 'tulskaya-oblast', name: 'Тульская область' }] }] } });
  });
});

describe('R7PricesBlock', () => {
  it('показывает шесть цен со ссылками на ряд России, разворачивается и помнит регион', async () => {
    renderPage(<R7PricesBlock surface="category" />);
    await waitFor(() => expect(screen.getAllByText(/Товар \d/).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/Товар \d/)).toHaveLength(6);
    expect(document.querySelector('a[href="/russia/region/russia/ceni-x0"]')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /ещё 2|more/i }));
    expect(screen.getAllByText(/Товар \d/)).toHaveLength(8);
    const select = await screen.findByRole('combobox');
    await waitFor(() => expect(select.querySelectorAll('option').length).toBe(2));
    fireEvent.change(select, { target: { value: 'tulskaya-oblast' } });
    expect(document.querySelector('a[href="/russia/region/tulskaya-oblast/ceni-x0"]')).toBeTruthy();
    expect(window.localStorage.getItem('fe_r7d_region')).toBe('tulskaya-oblast');
  });

  it('при 404 сводки берёт профиль России', async () => {
    get.mockImplementation((url) => {
      if (url.includes('prices-summary')) return Promise.reject({ response: { status: 404 } });
      if (url === '/regions/russia') {
        return Promise.resolve({ data: { price_headline_codes: ['a'], sections: [{ indicators: [{ code: 'a', name: 'Яйца', unit: 'рублей', value: 5, prev_value: 4, period_label: 'сентябрь 2026' }] }] } });
      }
      return Promise.resolve({ data: { districts: [] } });
    });
    renderPage(<R7PricesBlock surface="hub" />);
    await waitFor(() => expect(screen.getByText('Яйца')).toBeTruthy());
  });
});
