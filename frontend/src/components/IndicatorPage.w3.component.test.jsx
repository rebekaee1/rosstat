/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import TelemetryCard from './TelemetryCard';
import ModeGroupsPicker from './ModeGroupsPicker';
import IndicatorForecastSection from './IndicatorForecastSection';
import Breadcrumbs from './Breadcrumbs';
import RelatedIndicators from './RelatedIndicators';
import GenericViewModePicker from './GenericViewModePicker';
import IndicatorDataTableSection from './IndicatorDataTableSection';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => String(key) }),
}));

afterEach(cleanup);

const wrap = (ui) => render(
  <LocaleProvider locale="ru"><MemoryRouter>{ui}</MemoryRouter></LocaleProvider>,
);

describe('TelemetryCard', () => {
  it('число с единицей, изменение с единицей и смыслом (рост ставки — не зелёный)', () => {
    const { container } = wrap(
      <TelemetryCard label="Текущее значение" value={14} unit="%" change={0.5} polarity="up-bad" meta="на 4 октября 2026" />,
    );
    expect(screen.getByText('14,00')).toBeTruthy();
    const delta = container.querySelector('.fe-delta-badge');
    expect(delta.textContent).toContain('+0,50');
    expect(delta.textContent).toContain('п. п.');
    expect(delta.className).toContain('fe-tone--bad');
    expect(screen.getByText('на 4 октября 2026')).toBeTruthy();
  });

  it('изменение без смысла остаётся нейтральным, а ноль — «Без изменений»', () => {
    const { container, rerender } = wrap(
      <TelemetryCard label="Цена" value={1500} unit="млрд руб." change={12} polarity="neutral" />,
    );
    expect(container.querySelector('.fe-delta-badge').className).toContain('fe-tone--neutral');
    rerender(
      <LocaleProvider locale="ru"><MemoryRouter>
        <TelemetryCard label="Цена" value={1500} unit="млрд руб." change={-0.001} polarity="up-bad" />
      </MemoryRouter></LocaleProvider>,
    );
    expect(screen.getByText('Без изменений')).toBeTruthy();
    expect(container.querySelector('.fe-delta-badge').className).toContain('fe-tone--flat');
    expect(container.textContent).not.toMatch(/0,00/);
  });

  it('подписи не капсом и без сокращений «НАБЛ.»/«ПЕРИОД.»', () => {
    const { container } = wrap(<TelemetryCard label="Максимум за всё время" value={21} unit="%" meta="Достигнут: 15 октября 1993" />);
    expect(container.textContent).not.toMatch(/НАБЛ|ПЕРИОД|ПИК/);
  });
});

describe('ModeGroupsPicker', () => {
  const groups = [
    { id: 'a', label: 'На конец периода', rawLabel: 'На конец периода' },
    { id: 'b', label: 'Год к году', rawLabel: 'К соотв. периоду пред. года' },
  ];

  it('сетка равных ячеек, подсказка под выбранным, детализация со своей подписью', () => {
    const onTop = vi.fn();
    const onSub = vi.fn();
    const { container } = wrap(
      <ModeGroupsPicker
        title="Показать как"
        groups={groups}
        activeGroupId="b"
        onTopClick={onTop}
        subModes={[{ mode: 'm', label: 'По месяцам' }, { mode: 'q', label: 'По кварталам' }]}
        currentMode="m"
        onSubClick={onSub}
      />,
    );
    expect(container.querySelectorAll('.fe-chip-row--grid')).toHaveLength(2);
    expect(screen.getByRole('note').textContent).toMatch(/год назад/);
    expect(screen.getByText('Детализация')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'По кварталам' }));
    expect(onSub).toHaveBeenCalledWith(expect.objectContaining({ mode: 'q' }));
    fireEvent.click(screen.getByRole('button', { name: 'На конец периода' }));
    expect(onTop).toHaveBeenCalledWith(groups[0]);
  });

  it('недоступные подрежимы не занимают место серыми кнопками', () => {
    wrap(
      <ModeGroupsPicker
        title="Показать как"
        groups={groups}
        activeGroupId="a"
        onTopClick={() => {}}
        subModes={[
          { mode: 'm', label: 'По месяцам', disabled: true, hint: 'нет данных' },
          { mode: 'q', label: 'По кварталам' },
          { mode: 'y', label: 'По годам' },
        ]}
        currentMode="q"
        onSubClick={() => {}}
      />,
    );
    expect(screen.queryByRole('button', { name: /По месяцам/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'По годам' })).toBeTruthy();
  });

  it('в подписях нет «соотв.», «пред.», «Режим»', () => {
    const { container } = wrap(
      <GenericViewModePicker
        family={{
          groups: [{ id: 'yoy', label: 'К соотв. периоду пред. года', leaf: true }, { id: 'end', label: 'На конец периода' }],
          modes: [
            { mode: 'level', group: 'end', label: 'По месяцам', code: 'x', isNative: true },
            { mode: 'yoy', group: 'yoy', label: 'Г/г', code: 'x-yoy' },
          ],
          defaultMode: 'level',
        }}
        currentMode="level"
        onChange={() => {}}
      />,
    );
    expect(container.textContent).not.toMatch(/соотв\.|пред\.|Режим|Г\/г/);
  });
});

describe('IndicatorForecastSection без прогноза', () => {
  it('компактная доброжелательная плашка с действием, без пунктира и жаргона', () => {
    const { container } = wrap(
      <IndicatorForecastSection
        indicator={{ code: 'x' }}
        chartMode="cpi"
        safeViewMode="level"
        forecastEnabled={false}
        showForecast
        hasForecastData={false}
      />,
    );
    const card = container.querySelector('[data-block="forecast-empty"]');
    expect(card).toBeTruthy();
    expect(card.className).not.toContain('border-dashed');
    expect(card.textContent).not.toMatch(/режим|ряд|переключател/i);
    expect(within(card).getByRole('link').getAttribute('href')).toContain('/russia/category');
  });
});

describe('Breadcrumbs', () => {
  it('обычный регистр: нет капса и моноширинного шрифта, текущая страница помечена', () => {
    const { container } = wrap(
      <Breadcrumbs
        variant="mono"
        items={[
          { path: '/', name: 'Главная' },
          { path: '/russia', name: 'Россия' },
          { path: '/russia/indicator/key-rate', name: 'Ключевая ставка ЦБ РФ' },
        ]}
      />,
    );
    expect(container.querySelector('nav').className).not.toMatch(/uppercase|font-mono|tracking/);
    expect(container.querySelector('[aria-current="page"]').textContent).toBe('Ключевая ставка ЦБ РФ');
    expect(container.querySelectorAll('.fe-crumbs__sep')).toHaveLength(2);
  });
});

describe('RelatedIndicators', () => {
  it('три «До 1 года» получают разные понятные названия, у каждого значение с единицей', () => {
    wrap(
      <RelatedIndicators
        code="key-rate"
        items={[
          { code: 'credit-rate-corp-short', name: 'До 1 года', unit: '%', frequency: 'monthly', current_value: 17.5, current_date: '2026-08-01' },
          { code: 'credit-rate-ind-short', name: 'До 1 года', unit: '%', frequency: 'monthly', current_value: 21.2, current_date: '2026-08-01' },
          { code: 'deposit-rate', name: 'До 1 года', unit: '%', frequency: 'monthly', current_value: 15.1, current_date: '2026-08-01' },
        ]}
      />,
    );
    const titles = screen.getAllByRole('link').map((a) => a.querySelector('.fe-rel-card__title')?.textContent).filter(Boolean);
    expect(new Set(titles).size).toBe(3);
    expect(titles.every((t) => t !== 'До 1 года')).toBe(true);
    expect(screen.getByText('17,50%')).toBeTruthy();
  });
});

describe('IndicatorDataTableSection на странице года', () => {
  const points = [
    { date: '2023-12-15', value: 16 },
    { date: '2024-01-03', value: 16 },
    { date: '2024-07-26', value: 18 },
    { date: '2025-02-14', value: 21 },
  ];

  function renderAt(route) {
    return render(
      <LocaleProvider locale="ru">
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route
              path="/russia/indicator/:code/:year?"
              element={(
                <IndicatorDataTableSection
                  indicator={{ code: 'key-rate', frequency: 'daily', unit: '%', name: 'Ключевая ставка' }}
                  chartMode="cpi"
                  safeViewMode="level"
                  dataPoints={points}
                />
              )}
            />
          </Routes>
        </MemoryRouter>
      </LocaleProvider>,
    );
  }

  it('показывает только строки выбранного года и называет год в заголовке', () => {
    renderAt('/russia/indicator/key-rate/2024');
    expect(screen.getByRole('heading', { level: 3 }).textContent).toMatch(/, 2024$/);
    expect(screen.getAllByRole('row')).toHaveLength(3);
  });

  it('без года таблица показывает всю историю', () => {
    renderAt('/russia/indicator/key-rate');
    expect(screen.getAllByRole('row')).toHaveLength(5);
  });
});
