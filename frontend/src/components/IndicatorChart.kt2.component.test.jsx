import { cloneElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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


const q = (y0, n, f = (i) => 100 + i) => Array.from({ length: n }, (_, i) => ({
  date: `${y0 + Math.floor(i / 4)}-${String((i % 4) * 3 + 1).padStart(2, '0')}-01`,
  value: f(i),
}));

function renderChart(props = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LocaleProvider>
        <AuthProvider>
          <MemoryRouter>
            <IndicatorChart
              mode="cpi"
              cpiData={q(2015, 8)}
              forecastData={{ forecast: { values: [] } }}
              showForecast={false}
              cpiChartTitle="Выезд в Египет"
              unit="тыс. поездок"
              indicatorCode="tour-outbound-egypt"
              rangePreset="quarterly"
              defaultChartType="line"
              {...props}
            />
          </MemoryRouter>
        </AuthProvider>
      </LocaleProvider>
    </QueryClientProvider>,
  );
}

const curve = (container) => container.querySelector('.recharts-line-curve, .recharts-area-curve');
const segments = (container) => (curve(container)?.getAttribute('d') || '').split('M').filter(Boolean).length;

describe('IndicatorChart: правки круга «Туризм», z2', () => {
  it('Египет: после 2015 сразу 2019 — линия рвётся, а не соединяет точки через пропуск (правка 10)', () => {
    const gapped = [...q(2015, 4), ...q(2019, 4)];
    const { container } = renderChart({ cpiData: gapped, rangePreset: 'quarterly', defaultChartType: 'line' });
    // Окно по умолчанию может обрезать ряд: берём «Всё».
    fireEvent.click(screen.getByRole('button', { name: 'Всё' }));
    expect(segments(container)).toBe(2);
  });

  it('ряд без пропусков рисуется одной непрерывной линией, как раньше', () => {
    const { container } = renderChart({ cpiData: q(2015, 16) });
    fireEvent.click(screen.getByRole('button', { name: 'Всё' }));
    expect(segments(container)).toBe(1);
  });

  it('выгрузка полного ряда не получает служебных пустых строк', () => {
    const onFullData = vi.fn();
    renderChart({ cpiData: [...q(2015, 4), ...q(2019, 4)], onFullData });
    const rows = onFullData.mock.calls.at(-1)[0];
    expect(rows).toHaveLength(8);
    expect(rows.every((r) => r.actual != null)).toBe(true);
  });

  it('единица стоит у оси; заголовок над графиком скрыт от глаз; тип и «События» за «Изменить вид» (правка 20)', () => {
    const { container } = renderChart();
    expect(screen.getByTestId('chart-axis-unit').textContent).toBe('тыс. поездок');
    expect(container.querySelector('.fe-chart-title').className).toContain('sr-only');
    expect(screen.queryByRole('group', { name: 'Тип графика' })).toBeNull();
    expect(screen.getByRole('group', { name: 'Период графика' })).toBeTruthy();
    fireEvent.click(screen.getByTestId('chart-view-toggle'));
    expect(screen.getByRole('group', { name: 'Тип графика' })).toBeTruthy();
  });

  it('кнопка «События» не показывается, если в окне ряда событий нет (правка 45)', () => {
    renderChart({ cpiData: q(2024, 8) });
    fireEvent.click(screen.getByTestId('chart-view-toggle'));
    expect(screen.queryByTestId('chart-events-toggle')).toBeNull();
    cleanup();
    renderChart({ cpiData: q(2008, 60) });
    fireEvent.click(screen.getByRole('button', { name: 'Всё' }));
    fireEvent.click(screen.getByTestId('chart-view-toggle'));
    expect(screen.getByTestId('chart-events-toggle')).toBeTruthy();
  });
});
