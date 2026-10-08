import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import IndicatorTelemetryGrid from './IndicatorTelemetryGrid';
vi.mock('./TelemetryCard', () => ({ default: ({ label, value, deltaSuffix }) => <div>{label}: {value}{deltaSuffix ? ` | ${deltaSuffix}` : ''}</div> }));
describe('indicator summary names the displayed transformation', () => {
  it.each(['inflation', 'inflation-quarter', 'inflation-year'])('labels %s as a year-on-year change, not a generic current value', (mode) => {
    render(<LocaleProvider locale="ru"><IndicatorTelemetryGrid indicator={{ frequency: 'monthly', unit: '%' }}
      isPriceCategory chartMode="inflation" safeViewMode={mode}
      viewStats={{ currentValue: 6.34, previousValue: 6, currentDate: '2026-08-01' }} adj={x => x} />
    </LocaleProvider>);
    expect(screen.getByText(/Год к году.*6.34/)).toBeTruthy();
    expect(screen.queryByText(/Текущее значение/)).toBeNull();
  });
});

describe('круг 9 (Y10): подписи сравнения и окно статистики', () => {
  const mount = (props) => render(
    <LocaleProvider locale="ru">
      <IndicatorTelemetryGrid indicator={{ frequency: 'monthly', unit: '%' }} isPriceCategory adj={(x) => x} {...props} />
    </LocaleProvider>,
  );

  it('«по годам»: предыдущее значение это прошлый год, а не прошлый месяц', () => {
    mount({
      chartMode: 'inflation',
      safeViewMode: 'inflation-year',
      viewStats: { currentValue: 5.6, previousValue: 9.5, currentDate: '2025-12-01', previousDate: '2024-12-01' },
    });
    expect(screen.getByText(/Предыдущий год: 9\.5/)).toBeTruthy();
    expect(screen.queryByText(/Предыдущий месяц/)).toBeNull();
  });

  it('максимум и среднее за последние 10 лет вместо всей истории с девяностых', () => {
    const points = [];
    for (let year = 1995; year <= 2026; year += 1) {
      points.push({ date: `${year}-01-01`, value: year < 2000 ? 2000 : 6 });
    }
    mount({
      chartMode: 'inflation',
      safeViewMode: 'inflation',
      viewStats: { currentValue: 6, previousValue: 6, currentDate: '2026-01-01', highest: { value: 2000, date: '1995-01-01' }, average: 400 },
      firstDate: '1995-01-01',
      windowPoints: points,
    });
    expect(screen.getByText(/Максимум за 10 лет: 6/)).toBeTruthy();
    expect(screen.getByText(/Среднее за 10 лет: 6/)).toBeTruthy();
    expect(screen.queryByText(/Исторический максимум/)).toBeNull();
  });
});
