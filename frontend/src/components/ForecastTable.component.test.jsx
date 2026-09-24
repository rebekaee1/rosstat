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
