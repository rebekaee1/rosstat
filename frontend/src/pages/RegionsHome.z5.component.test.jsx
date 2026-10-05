import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import RegionsHome from './RegionsHome';
import { mockApiGet, renderPage } from '../test/renderPage';

vi.mock('../components/RegionsMap', () => ({ default: () => <div data-testid="regions-map" /> }));
vi.mock('../components/MapTimeline', () => ({ default: () => null }));
afterEach(() => vi.restoreAllMocks());

function mount(landing) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/regions', landing],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/heatmap/, { values: [] }],
  ]);
  renderPage(<RegionsHome />, { path: '*', route: '/russia/region/map/overview' });
}

describe('Регионы: карта и быстрый выбор', () => {
  it('кнопки показателей — одна горизонтальная лента, а не сетка на шесть строк', async () => {
    mount({ totals: {}, districts: [] });
    const toggle = await screen.findByTestId('map-find-toggle');
    const ribbon = document.querySelector('.z5-metric-ribbon');
    expect(ribbon.getAttribute('role')).toBe('tablist');
    // Показатели и «Найти» стоят рядом с картой, а не вперемешку.
    expect(ribbon.querySelectorAll('button').length).toBeGreaterThanOrEqual(6);
    expect(ribbon.contains(toggle)).toBe(false);
  });

  it('внутри «Найти» стоят чипы Москва, Санкт-Петербург, Татарстан — даже если список регионов ещё не пришёл', async () => {
    mount({ totals: {}, districts: [] });
    fireEvent.click(await screen.findByTestId('map-find-toggle'));
    const panel = await screen.findByTestId('map-find-panel');
    const chips = panel.querySelectorAll('.z5-map-quick .fe-chip');
    expect([...chips].map((el) => el.textContent)).toEqual(['Москва', 'Санкт-Петербург', 'Татарстан']);
    // Быстрые чипы идут первыми, до полей поиска.
    expect(panel.firstElementChild.className).toContain('z5-map-quick');
    fireEvent.click(chips[0]);
    expect(chips[0].getAttribute('aria-pressed')).toBe('true');
  });

  it('когда регионы пришли, подписи берутся из них', async () => {
    mount({
      totals: {},
      districts: [{ slug: 'cfo', name: 'ЦФО', regions: [
        { slug: 'moskva', name: 'г. Москва', stats: {} },
        { slug: 'sankt-peterburg', name: 'г. Санкт-Петербург', stats: {} },
      ] }],
    });
    fireEvent.click(await screen.findByTestId('map-find-toggle'));
    const panel = await screen.findByTestId('map-find-panel');
    await vi.waitFor(() => {
      const labels = [...panel.querySelectorAll('.z5-map-quick .fe-chip')].map((el) => el.textContent);
      expect(labels[0]).toBe('г. Москва');
    });
  });
});
