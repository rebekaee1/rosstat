import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import ForecastTable from './ForecastTable';
import { renderPage } from '../test/renderPage';

describe('ForecastTable', () => {
  it('не выдаёт последний опубликованный квартал за прогноз', () => {
    renderPage(
      <ForecastTable
        mode="cpi"
        dateFormat="quarterly"
        actualPoints={[{ date: '2026-04-01', value: 6.4 }]}
        forecastData={{ forecast: { values: [
          { date: '2026-04-01', value: 6.4 },
          { date: '2026-07-01', value: 6.3 },
        ] } }}
      />,
      { path: '/', route: '/' },
    );

    expect(screen.queryByRole('row', { name: /^II кв. 2026/ })).toBeNull();
    expect(screen.getByRole('row', { name: /^III кв. 2026/ })).toBeTruthy();
  });

  it('показывает пересчитанный неполный квартал, если API разрешает замену', () => {
    renderPage(
      <ForecastTable
        mode="cpi"
        dateFormat="quarterly"
        actualPoints={[{ date: '2026-04-01', value: 4.2 }]}
        forecastData={{ forecast: {
          replaces_partial_actual: true,
          values: [{ date: '2026-04-01', value: 7.1 }],
        } }}
      />,
      { path: '/', route: '/' },
    );

    expect(screen.getByRole('row', { name: /^II кв. 2026/ })).toBeTruthy();
  });
});

describe('ForecastTable: точность (правки 22, 38)', () => {
  it('прогноз без сотых, когда факт показан без сотых: «9 778 тыс. поездок», а не «9 778,11»', () => {
    renderPage(
      <ForecastTable
        mode="cpi"
        dateFormat="quarterly"
        unit="тыс. поездок"
        actualPoints={[{ date: '2026-04-01', value: 7771 }, { date: '2026-01-01', value: 6500 }]}
        forecastData={{ forecast: { values: [{ date: '2026-07-01', value: 9778.11 }] } }}
      />,
      { path: '/', route: '/' },
    );
    const text = screen.getByRole('row', { name: /^III кв. 2026/ }).textContent;
    expect(text).toContain('9 778');
    expect(text).not.toMatch(/9\s?778,11/);
  });
});
