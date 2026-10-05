// «Сравнение»: состояния блока графика — показатели не выбраны, загрузка, сбой с кнопкой «Повторить».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => {
  vi.restoreAllMocks();
});

const INDICATORS = [
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2,
  },
];

const COMMON_ROUTES = [
  ['/auth/me', { user: null }],
  [/^\/indicators\?/, INDICATORS],
  ['/indicators', INDICATORS],
  [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
  ['/regions/catalog', { sections: [] }],
  [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
  [/^\/regions/, { districts: [], sections: [] }],
  ['/world/compare/catalog', { items: [], total: 0 }],
];

describe('ComparePage: состояния графика', () => {
  it('без выбранных показателей — вежливо озвученное состояние «не выбраны», без кнопки «Повторить»', async () => {
    mockApiGet(COMMON_ROUTES);
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const box = await screen.findByTestId('compare-empty');
    expect(box.getAttribute('data-state')).toBe('none');
    expect(box.getAttribute('role')).toBe('status');
    expect(box.textContent).toMatch(/Показатели не выбраны/);
    expect(screen.queryByRole('button', { name: 'Повторить' })).toBeNull();
  });

  it('пока ряд грузится — скелетон с aria-busy той же высоты, что график', async () => {
    const spy = mockApiGet(COMMON_ROUTES);
    const original = spy.getMockImplementation();
    // Запрос ряда не завершается: блок графика остаётся в состоянии загрузки.
    spy.mockImplementation((url) => (/^\/indicators\/cpi\/data/.test(url) ? new Promise(() => {}) : original(url)));
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=cpi' });
    const skeleton = await screen.findByTestId('compare-chart-skeleton');
    expect(skeleton.getAttribute('aria-busy')).toBe('true');
    expect(skeleton.textContent).toMatch(/Загружаем данные/);
    expect(skeleton.querySelector('.skeleton[style]').style.height).toMatch(/^\d+px$/);
    expect(screen.queryByTestId('compare-empty')).toBeNull();
  });

  it('сбой запроса — alert с кнопкой «Повторить», нажатие повторяет запрос', async () => {
    // Маршрута /data нет → 404 (повтор react-query не делается) → состояние ошибки.
    const spy = mockApiGet(COMMON_ROUTES);
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=cpi' });
    const box = await screen.findByTestId('compare-empty');
    await waitFor(() => expect(box.getAttribute('data-state')).toBe('error'));
    expect(box.getAttribute('role')).toBe('alert');
    const dataCalls = () => spy.mock.calls.filter((c) => /^\/indicators\/cpi\/data/.test(String(c[0]))).length;
    const before = dataCalls();
    expect(before).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    await waitFor(() => expect(dataCalls()).toBeGreaterThan(before));
  });

  it('мировой ряд до прихода данных: в карточке название из каталога, внутренний код не виден', async () => {
    const code = 'w:germany:gdp-volume-annual';
    const spy = mockApiGet([
      ...COMMON_ROUTES.filter(([k]) => k !== '/world/compare/catalog'),
      ['/world/compare/catalog', { items: [{
        code, country_slug: 'germany', country_name: 'Германия', country_name_en: 'Germany',
        concept_slug: 'gdp-volume-annual', concept_name: 'ВВП в постоянных ценах', concept_name_en: 'Real GDP',
        frequency: 'annual', unit: 'млн евро',
      }], total: 1 }],
    ]);
    const original = spy.getMockImplementation();
    spy.mockImplementation((url) => (/^\/world\/(germany|compare\/germany)/.test(url) ? new Promise(() => {}) : original(url)));
    renderPage(<ComparePage />, { path: '/compare', route: `/compare?codes=${encodeURIComponent(code)}` });
    await screen.findAllByText(/ВВП в постоянных ценах — Германия/);
    expect(document.body.textContent).not.toContain('w:germany');
  });
});
