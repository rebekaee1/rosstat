import { cloneElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocaleProvider } from '../i18n';
import { AuthProvider } from '../context/AuthProvider';
import IndicatorChart from './IndicatorChart';

vi.mock('recharts', async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    ResponsiveContainer: ({ children }) => cloneElement(children, { width: 800, height: 360 }),
  };
});

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => String(key) }),
}));

afterEach(cleanup);

const YEARS = Array.from({ length: 40 }, (_, i) => ({ date: `${1985 + i}-01-01`, value: 100 + i * 4 }));
const OTHER = YEARS.map((p, i) => ({ date: p.date, value: 50 + i * 2 }));

function chart(props = {}) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LocaleProvider>
        <AuthProvider>
          <MemoryRouter>
            <IndicatorChart
              mode="cpi"
              cpiData={YEARS}
              cpiChartTitle="ВВП"
              unit="млрд $"
              indicatorCode="gdp-usd-test"
              rangePreset="annual"
              comparisonSeries={[{ data: OTHER, dataKey: 'comparison_0', label: 'Китай', color: '#397C8C' }]}
              {...props}
            />
          </MemoryRouter>
        </AuthProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}

const pressed = (name) => screen.getByRole('button', { name }).getAttribute('aria-pressed');

describe('IndicatorChart: период при сравнении от общей базы (круг 10, Ср2)', () => {
  it('без свойства rebaseRange период не меняется: годовой ряд открыт на 10 лет', () => {
    const { rerender } = render(chart({ rebaseVisible: false }));
    expect(pressed('10 л.')).toBe('true');
    rerender(chart({ rebaseVisible: true }));
    expect(pressed('10 л.')).toBe('true');
  });

  it('включили «старт периода = 100»: окно 25 лет, выключили: прежнее окно', () => {
    const { rerender } = render(chart({ rebaseVisible: false, rebaseRange: '25y' }));
    expect(pressed('10 л.')).toBe('true');
    rerender(chart({ rebaseVisible: true, rebaseRange: '25y' }));
    expect(pressed('25 л.')).toBe('true');
    rerender(chart({ rebaseVisible: false, rebaseRange: '25y' }));
    expect(pressed('10 л.')).toBe('true');
  });

  it('у ряда без пункта «25 лет» берётся «Всё»', () => {
    const { rerender } = render(chart({ rebaseVisible: false, rebaseRange: '25y', rangePreset: 'default' }));
    rerender(chart({ rebaseVisible: true, rebaseRange: '25y', rangePreset: 'default' }));
    expect(pressed('Всё')).toBe('true');
  });
});
