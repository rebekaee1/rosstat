// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import RegionsHome from './RegionsHome';
import { renderPage, mockApiGet } from '../test/renderPage';

describe('R7-C: «Мой регион» в рейтинге хаба', () => {
  const landing = { totals: { points: 3, indicators: 2, regions: 3 }, districts: [] };
  const heat = {
    year: 2024, default_sort: 'desc', indicator: { code: 'x', name: 'Зарплата', unit: '₽' },
    values: [
      { slug: 'ryazanskaya-oblast', name: 'Рязанская область', value: 60000, raw: 60000 },
      { slug: 'moskva', name: 'Москва', value: 150000, raw: 150000 },
      { slug: 'tulskaya-oblast', name: 'Тульская область', value: 70000, raw: 70000 },
    ],
  };
  beforeEach(() => { try { localStorage.removeItem('fe-my-region'); } catch { /* нет хранилища */ } });

  it('выбор региона показывает карточку с местом и серединой, и запоминается', async () => {
    mockApiGet([['/auth/me', { user: null }], ['/regions', landing], ['/regions/catalog', { sections: [] }], [/^\/regions\/heatmap\//, heat]]);
    renderPage(<RegionsHome />, { path: '/russia/region', route: '/russia/region' });
    const select = await screen.findByTestId('ranking-mine');
    expect(screen.queryByTestId('ranking-mine-card')).toBeNull();
    fireEvent.change(select, { target: { value: 'tulskaya-oblast' } });
    const card = await screen.findByTestId('ranking-mine-card');
    expect(card.textContent).toContain('Тульская область');
    expect(card.textContent).toContain('2-е место из 3');
    expect(card.textContent).toContain('середина по регионам');
    await waitFor(() => expect(localStorage.getItem('fe-my-region')).toBe('tulskaya-oblast'));
  });
});
