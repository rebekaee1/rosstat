import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import { AuthProvider } from '../context/AuthProvider';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ViewModePicker from './ViewModePicker';
import FrequencySwitcher from './FrequencySwitcher';
import VariantGroupPicker from './VariantGroupPicker';
import DeathsViewModePicker from './DeathsViewModePicker';
import PpiViewModePicker from './PpiViewModePicker';
import IndicatorChart from './IndicatorChart';
import DataTable from './DataTable';
import ChartSectionSkeleton from './ChartSectionSkeleton';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => String(key) }),
}));

afterEach(cleanup);

function wrap(ui) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LocaleProvider>
        <AuthProvider>
          <MemoryRouter>{ui}</MemoryRouter>
        </AuthProvider>
      </LocaleProvider>
    </QueryClientProvider>,
  );
}

describe('переключатели режима — единый Chip', () => {
  it('ViewModePicker: группа с подписью, aria-pressed у активного, переключение по клику', () => {
    const onChange = vi.fn();
    wrap(
      <ViewModePicker
        title="Режим"
        modes={[{ mode: 'level', label: 'Уровень' }, { mode: 'yoy', label: 'Год к году' }]}
        currentMode="level"
        onChange={onChange}
      />,
    );
    const group = screen.getByRole('group', { name: 'Режим' });
    const level = within(group).getByRole('button', { name: 'Уровень' });
    const yoy = within(group).getByRole('button', { name: 'Год к году' });
    expect(level.getAttribute('aria-pressed')).toBe('true');
    expect(yoy.getAttribute('aria-pressed')).toBe('false');
    expect(level.className).toContain('fe-chip');
    fireEvent.click(yoy);
    expect(onChange).toHaveBeenCalledWith('yoy');
  });

  it('FrequencySwitcher: чипы-ссылки с aria-current у текущей частоты', () => {
    wrap(
      <FrequencySwitcher
        currentCode="gdp"
        currentFrequency="quarterly"
        alternateFrequencies={{ monthly: 'gdp-monthly' }}
      />,
    );
    const group = screen.getByRole('group');
    const links = within(group).getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links.filter((a) => a.getAttribute('aria-current') === 'page')).toHaveLength(1);
    links.forEach((a) => expect(a.className).toContain('fe-chip'));
  });

  it('VariantGroupPicker (2 среза): ссылки-чипы в группе', () => {
    wrap(
      <VariantGroupPicker
        currentCode="a"
        group={{ label: 'Срез', codes: [{ code: 'a', label: 'А' }, { code: 'b', label: 'Б' }] }}
      />,
    );
    const group = screen.getByRole('group', { name: 'Срез' });
    expect(within(group).getByRole('link', { name: 'А' }).getAttribute('aria-current')).toBe('page');
    expect(within(group).getByRole('link', { name: 'Б' }).getAttribute('aria-current')).toBeNull();
  });

  it('семейные пикеры отдают кнопки с aria-pressed', () => {
    wrap(<DeathsViewModePicker currentMode="year" onChange={vi.fn()} />);
    const pressed = screen.getAllByRole('button').map((b) => b.getAttribute('aria-pressed'));
    expect(pressed.length).toBeGreaterThan(0);
    expect(pressed.every((v) => v === 'true' || v === 'false')).toBe(true);
    cleanup();
    wrap(<PpiViewModePicker currentMode="yoy" onChange={vi.fn()} />);
    expect(screen.getAllByRole('group').length).toBeGreaterThan(0);
    screen.getAllByRole('button').forEach((b) => expect(b.getAttribute('aria-pressed')).not.toBeNull());
  });
});

const SERIES = Array.from({ length: 132 }, (_, i) => ({
  date: `${2021 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}-01`,
  value: 5 + i * 0.1,
}));

describe('IndicatorChart', () => {
  const renderChart = (props = {}) => wrap(
    <IndicatorChart
      mode="cpi"
      cpiData={SERIES}
      forecastData={{ forecast: { values: [] } }}
      showForecast={false}
      cpiChartTitle="Ключевая ставка"
      unit="%"
      indicatorCode="key-rate"
      {...props}
    />,
  );

  it('появляется средствами CSS без задержки, а не gsap с задержкой', () => {
    const { container } = renderChart();
    const card = container.querySelector('.fe-chart-card');
    expect(card.className).toContain('fe-reveal');
    expect(card.style.opacity).toBe('');
    const delay = card.style.getPropertyValue('--fe-delay');
    expect(delay === '' || parseFloat(delay) <= 0.1).toBe(true);
  });

  it('плот — role=img с названием и последним значением', () => {
    renderChart();
    const plot = screen.getByRole('img');
    const label = plot.getAttribute('aria-label');
    expect(label).toContain('Ключевая ставка');
    expect(label).toContain('Последнее значение');
    expect(label).toContain('18,10\u00A0%');
  });

  it('периоды и тип графика — группы Chip с aria-pressed', () => {
    renderChart();
    const range = screen.getByRole('group', { name: 'Период графика' });
    const pressed = within(range).getAllByRole('button').filter((b) => b.getAttribute('aria-pressed') === 'true');
    expect(pressed).toHaveLength(1);
    fireEvent.click(within(range).getAllByRole('button')[2]);
    const after = within(range).getAllByRole('button').filter((b) => b.getAttribute('aria-pressed') === 'true');
    expect(after).toHaveLength(1);
    expect(after[0]).toBe(within(range).getAllByRole('button')[2]);
    const type = screen.getByRole('group', { name: 'Тип графика' });
    expect(within(type).getAllByRole('button')).toHaveLength(3);
    within(type).getAllByRole('button').forEach((b) => expect(b.className).toContain('fe-chip'));
  });

  it('период выбирается рамкой с двумя ручками под графиком, а не отдельным ползунком «Раньше / Позже»', () => {
    const { container } = renderChart();
    expect(container.querySelector('input[type="range"]')).toBeNull();
    const brush = container.querySelector('.fe-brush');
    expect(brush).toBeTruthy();
    const handles = within(brush).getAllByRole('slider');
    expect(handles).toHaveLength(2);
    expect(handles.map((h) => h.getAttribute('aria-label'))).toEqual(['Начало периода', 'Конец периода']);
    expect(container.textContent).not.toContain('Раньше');
  });

  it('стрелки на ручке сдвигают границу окна на одну точку', () => {
    const { container } = renderChart();
    const brush = container.querySelector('.fe-brush');
    const [startHandle] = within(brush).getAllByRole('slider');
    const before = Number(startHandle.getAttribute('aria-valuenow'));
    fireEvent.keyDown(startHandle, { key: 'ArrowLeft' });
    const after = Number(within(container.querySelector('.fe-brush')).getAllByRole('slider')[0].getAttribute('aria-valuenow'));
    expect(after).toBe(before - 1);
  });

  it('вид графика подписан словами, периоды короткие и одинаковые', () => {
    renderChart();
    const type = screen.getByRole('group', { name: 'Тип графика' });
    expect(within(type).getAllByRole('button').map((b) => b.textContent)).toEqual(['Область', 'Линия', 'Столбцы']);
    const range = screen.getByRole('group', { name: 'Период графика' });
    expect(within(range).getAllByRole('button').map((b) => b.textContent)).toEqual(['1 г.', '5 л.', '10 л.', 'Всё']);
  });

  it('подсказки «мышью» (Ctrl + scroll) на графике больше нет', () => {
    const { container } = renderChart();
    const plot = container.querySelector('.fe-chart-plot');
    fireEvent.mouseEnter(plot);
    expect(container.textContent).not.toMatch(/Ctrl|scroll/i);
  });


  it('сенсор: тап по плоту открывает подсказку, тап вне закрывает', () => {
    const { container } = renderChart();
    const plot = container.querySelector('.fe-chart-plot');
    expect(plot.getAttribute('data-touch-tooltip')).toBeNull();
    fireEvent.pointerDown(plot, { pointerType: 'touch', pointerId: 1, clientX: 100, clientY: 100 });
    expect(plot.getAttribute('data-touch-tooltip')).toBe('open');
    fireEvent.pointerUp(plot, { pointerType: 'touch', pointerId: 1, clientX: 100, clientY: 100 });
    expect(plot.getAttribute('data-touch-tooltip')).toBe('open');
    fireEvent.pointerDown(document.body, { pointerType: 'touch', pointerId: 2 });
    expect(plot.getAttribute('data-touch-tooltip')).toBeNull();
  });

  it('сенсор: жест, отданный браузеру под прокрутку, не оставляет подсказку', () => {
    const { container } = renderChart();
    const plot = container.querySelector('.fe-chart-plot');
    fireEvent.pointerDown(plot, { pointerType: 'touch', pointerId: 1, clientX: 100, clientY: 100 });
    fireEvent.pointerCancel(plot, { pointerType: 'touch', pointerId: 1 });
    expect(plot.getAttribute('data-touch-tooltip')).toBeNull();
  });

  it('пустой график — видимый текст, а не пустой блок', () => {
    renderChart({ cpiData: [] });
    expect(screen.getByRole('status').textContent).toContain('Нет данных для графика');
  });
});

describe('DataTable', () => {
  const rows = Array.from({ length: 45 }, (_, i) => ({ date: `2024-02-${String((i % 28) + 1).padStart(2, '0')}`, value: i }))
    .map((r, i) => ({ ...r, date: `${2000 + i}-01-01` }));

  it('пагинация отключена, пока таблица грузится', () => {
    wrap(<DataTable data={rows} loading />);
    expect(screen.getByRole('button', { name: 'Назад' }).disabled).toBe(true);
    expect(screen.getByRole('button', { name: 'Вперёд' }).disabled).toBe(true);
  });

  it('кнопки пагинации — общий Button (44px на касании задаёт .fe-btn)', () => {
    wrap(<DataTable data={rows} />);
    const next = screen.getByRole('button', { name: 'Вперёд' });
    expect(next.className).toContain('fe-btn');
    expect(next.disabled).toBe(false);
  });

  it('без данных за период показывает понятный текст', () => {
    wrap(<DataTable data={[]} />);
    expect(screen.getByText('Нет данных за период')).toBeTruthy();
  });

  it('при загрузке без строк — индикатор и текст, контейнер aria-busy', () => {
    const { container } = wrap(<DataTable data={[]} loading />);
    expect(screen.getByText('Таблица загружается…')).toBeTruthy();
    expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
  });

  it('появляется через CSS, без gsap-задержки', () => {
    const { container } = wrap(<DataTable data={rows} />);
    expect(container.firstChild.className).toContain('fe-reveal');
  });
});

describe('ChartSectionSkeleton', () => {
  it('повторяет оболочку и высоту графика (общий класс плота, высота от окна), скрыт от скринридера', () => {
    const { container } = wrap(<ChartSectionSkeleton />);
    const card = container.querySelector('.fe-chart-card');
    expect(card).toBeTruthy();
    // Высоту плота задаёт CSS-класс z4-plot: тот же, что у самого графика, поэтому подмена не сдвигает страницу.
    const plot = container.querySelector('.fe-chart-plot');
    expect(plot.className).toContain('z4-plot');
    expect(plot.style.height).toBe('');
    // Под плотом стоит полоса выбора периода, как у готового графика.
    expect(container.querySelector('.z4-skel-brush')).toBeTruthy();
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();
    expect(screen.getByRole('status').textContent).toBe('График загружается');
  });
});
