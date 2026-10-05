import { cloneElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocaleProvider } from '../i18n';
import { AuthProvider } from '../context/AuthProvider';
import IndicatorChart from './IndicatorChart';

// В jsdom у контейнера нет размеров, и Recharts ничего не рисует: отдаём графику фиксированный размер.
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

const SERIES = Array.from({ length: 36 }, (_, i) => {
  const d = new Date(Date.UTC(2023, i, 1));
  return { date: d.toISOString().slice(0, 10), value: 10 + Math.sin(i / 4) * 3 + i * 0.1 };
});

const FORECAST = {
  forecast: {
    values: Array.from({ length: 6 }, (_, i) => {
      const d = new Date(Date.UTC(2026, i, 1));
      return {
        date: d.toISOString().slice(0, 10), value: 13 + i * 0.2, lower_bound: 12 + i * 0.1, upper_bound: 14 + i * 0.4,
      };
    }),
  },
};

function renderChart(props = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LocaleProvider>
        <AuthProvider>
          <MemoryRouter>
            <IndicatorChart
              mode="cpi"
              cpiData={SERIES}
              forecastData={FORECAST}
              showForecast
              cpiChartTitle="Ключевая ставка"
              unit="%"
              indicatorCode="key-rate"
              {...props}
            />
          </MemoryRouter>
        </AuthProvider>
      </LocaleProvider>
    </QueryClientProvider>,
  );
}

describe('IndicatorChart: стеклянная лента (K4.1, K4.4)', () => {
  it('основная линия — градиент ленты 3 px, поверх неё блик-штрих', () => {
    const { container } = renderChart();
    const ribbon = container.querySelector('.k4-ribbon .recharts-area-curve');
    expect(ribbon).not.toBeNull();
    expect(ribbon.getAttribute('stroke')).toMatch(/^url\(#k4-.+-ribbon\)$/);
    expect(ribbon.getAttribute('stroke-width')).toBe('3');
    expect(container.querySelector('.k4-gloss .recharts-curve')).not.toBeNull();
    const gradientId = ribbon.getAttribute('stroke').slice(5, -1);
    expect(container.querySelector(`[id="${gradientId}"]`)).not.toBeNull();
  });

  it('на графике нет пунктира: ни линия прогноза, ни сетка, ни граница «сейчас»', () => {
    const { container } = renderChart();
    expect(container.querySelector('.recharts-wrapper')).not.toBeNull();
    expect(container.querySelectorAll('[stroke-dasharray]:not([stroke-dasharray="none"]):not([stroke-dasharray="0"])')).toHaveLength(0);
    const forecast = container.querySelector('.k4-forecast .recharts-curve');
    expect(forecast.getAttribute('stroke')).toMatch(/^url\(#k4-.+-forecast\)$/);
  });

  it('прогноз: коридор-призма и луч света на границе факта и прогноза', () => {
    const { container } = renderChart();
    const prism = container.querySelector('.k4-prism .recharts-area-area');
    expect(prism).not.toBeNull();
    expect(prism.getAttribute('fill')).toMatch(/^url\(#k4-.+-prism\)$/);
    expect(container.querySelector('.k4-beam')).not.toBeNull();
  });

  it('сетка — чередующиеся полосы, а не линии с пунктиром', () => {
    const { container } = renderChart();
    expect(container.querySelector('.recharts-cartesian-gridstripes-horizontal')).not.toBeNull();
  });

  it('последняя точка — бусина с гало и стеклянная плашка значения без обводки', () => {
    const { container } = renderChart({ showForecast: false });
    const marker = container.querySelector('.k4-lastpoint');
    expect(marker).not.toBeNull();
    expect(marker.querySelector('.k4-lastpoint__halo')).not.toBeNull();
    const tag = marker.querySelector('.k4-lastpoint__tag');
    expect(tag.getAttribute('stroke')).toBeNull();
  });

  it('тип «Столбцы» рисует столбцы градиентом без обводки', () => {
    const { container } = renderChart({ showForecast: false });
    const type = screen.getByRole('group', { name: 'Тип графика' });
    fireEvent.click(within(type).getByRole('button', { name: /Столбцы/ }));
    const bar = container.querySelector('.recharts-bar-rectangle path, .recharts-bar-rectangle rect');
    expect(bar).not.toBeNull();
    expect(bar.getAttribute('fill')).toMatch(/^url\(#k4-.+-bar\)$/);
  });
});

describe('IndicatorChart: сегмент вида графика (K4.2)', () => {
  it('бегунок общего жёлоба едет под выбранную кнопку через переменную --seg-i', () => {
    const { container } = renderChart({ showForecast: false });
    const group = container.querySelector('.fe-seg');
    expect(group.querySelector('.fe-seg__thumb')).not.toBeNull();
    expect(group.style.getPropertyValue('--seg-i')).toBe('0');
    expect(group.style.getPropertyValue('--seg-n')).toBe('3');
    fireEvent.click(within(group).getByRole('button', { name: /Столбцы/ }));
    expect(container.querySelector('.fe-seg').style.getPropertyValue('--seg-i')).toBe('2');
    // Кнопки остаются нажимаемыми Chip: бегунок не перехватывает клики.
    expect(within(group).getAllByRole('button')).toHaveLength(3);
  });
});
