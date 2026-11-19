import { cloneElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocaleProvider } from '../i18n';
import { AuthProvider } from '../context/AuthProvider';
import RegionAnnualChart from './RegionAnnualChart';
import { track } from '../lib/track';

// В jsdom у контейнера нет размеров, и Recharts ничего не рисует: отдаём графику фиксированный размер.
// onClick графика запоминаем — нажатие на точку в jsdom через координаты не воспроизводится.
const clickRef = { current: null };
vi.mock('recharts', async (importOriginal) => {
  const original = await importOriginal();
  const Composed = original.ComposedChart;
  return {
    ...original,
    ResponsiveContainer: ({ children }) => cloneElement(children, { width: 800, height: 300 }),
    ComposedChart: (props) => {
      clickRef.current = props.onClick;
      return <Composed {...props} />;
    },
  };
});

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => (key === 'CHART_PICK' ? 'chart_pick' : String(key)) }),
}));

beforeEach(() => {
  clickRef.current = null;
  track.mockClear();
});
afterEach(cleanup);

const SERIES = [
  { year: 2020, value: 1.21 },
  { year: 2021, value: 1.35 },
  { year: 2022, value: 1.42 },
  { year: 2023, value: 1.38 },
];

function renderChart(props = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LocaleProvider>
        <AuthProvider>
          <MemoryRouter>
            <RegionAnnualChart series={SERIES} regionName="Республика Калмыкия" unit="" height={300} {...props} />
          </MemoryRouter>
        </AuthProvider>
      </LocaleProvider>
    </QueryClientProvider>,
  );
}

describe('RegionAnnualChart — значение по нажатию на точку (Пульс 19.11.2026)', () => {
  it('плот помечен как управление: поток поведения не пишет нажатие кликом в пустоту', () => {
    renderChart();
    const plot = screen.getByRole('img');
    expect(plot.hasAttribute('data-interactive')).toBe(true);
    expect(plot.getAttribute('data-picked')).toBeNull();
    expect(typeof clickRef.current).toBe('function');
  });

  it('нажатие закрепляет точку: вертикаль, точка и плашка «год значение», событие chart_pick с источником', () => {
    const { container } = renderChart();
    act(() => clickRef.current({ activeLabel: 2021 }));
    const plot = screen.getByRole('img');
    expect(plot.getAttribute('data-picked')).toBe('true');
    const marker = container.querySelector('.k4-picked');
    expect(marker).not.toBeNull();
    expect(marker.querySelector('line')).not.toBeNull();
    expect(marker.textContent).toContain('2021');
    expect(marker.textContent).toContain('1,35');
    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith('chart_pick', { source: 'region' });
  });

  it('повторное нажатие на ту же точку снимает выбор, нажатие мимо точек ничего не делает', () => {
    const { container } = renderChart();
    act(() => clickRef.current({ activeLabel: 2022 }));
    act(() => clickRef.current({ activeLabel: 2022 }));
    expect(container.querySelector('.k4-picked')).toBeNull();
    act(() => clickRef.current({}));
    expect(container.querySelector('.k4-picked')).toBeNull();
    expect(track).toHaveBeenCalledTimes(1);
  });

  it('месячный ряд: плашка подписывает месяц', () => {
    const monthly = [
      { year: 2024, month: 1, label: '2024-01', value: 52.1 },
      { year: 2024, month: 2, label: '2024-02', value: 52.6 },
      { year: 2024, month: 3, label: '2024-03', value: 53.0 },
    ];
    const { container } = renderChart({ series: monthly, frequency: 'monthly' });
    act(() => clickRef.current({ activeLabel: '2024-02' }));
    const marker = container.querySelector('.k4-picked');
    expect(marker).not.toBeNull();
    expect(marker.textContent).toContain('фев 2024');
  });
});
