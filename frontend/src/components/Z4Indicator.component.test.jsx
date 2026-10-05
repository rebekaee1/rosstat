/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import { ViewModesPanel } from './ViewModesPanel';
import VariantGroupPicker from './VariantGroupPicker';
import ModeGroupsPicker from './ModeGroupsPicker';
import IndicatorHeroValue from './IndicatorHeroValue';
import DataTable from './DataTable';
import { buildIndicatorSummary } from '../lib/indicatorSummary';
import { prepareVariantGroup } from '../lib/viewModeShortLabels';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => String(key) }),
}));

afterEach(cleanup);

const wrap = (ui, { locale = 'ru' } = {}) => render(
  <LocaleProvider locale={locale}><MemoryRouter>{ui}</MemoryRouter></LocaleProvider>,
);

const GROUP = prepareVariantGroup({
  label: 'Что показать',
  codes: [
    { code: 'us-debt', label: 'Государственный долг сектора государственного управления' },
    { code: 'us-gdp', label: 'Валовой внутренний продукт в текущих ценах' },
    { code: 'us-pop', label: 'Численность населения' },
    { code: 'us-bal', label: 'Баланс бюджета сектора государственного управления' },
  ],
});

describe('VariantGroupPicker: короткие названия «Что показать»', () => {
  it('чип показывает короткое имя, полное лежит в title; порядок по важности', () => {
    wrap(<VariantGroupPicker group={GROUP} currentCode="us-gdp" basePath="/united-states/indicator" />);
    const links = screen.getAllByRole('link');
    expect(links.map((a) => a.textContent)).toEqual(['ВВП', 'Население', 'Баланс бюджета', 'Госдолг']);
    const debt = screen.getByRole('link', { name: 'Госдолг' });
    expect(debt.getAttribute('title')).toBe('Государственный долг сектора государственного управления');
    expect(debt.getAttribute('href')).toBe('/united-states/indicator/us-debt');
    // Выбранный отмечен не цветом одним, а aria-current.
    expect(screen.getByRole('link', { name: 'ВВП' }).getAttribute('aria-current')).toBe('page');
    // Название без сокращения не получает лишнего title.
    expect(screen.getByRole('link', { name: 'ВВП' }).getAttribute('title')).toBe('Валовой внутренний продукт в текущих ценах');
  });

  it('группа несёт класс строки полосы выбора', () => {
    const { container } = wrap(<VariantGroupPicker group={GROUP} currentCode="us-gdp" basePath="/x/indicator" />);
    expect(container.querySelector('.fe-pick-card--variant')).toBeTruthy();
  });
});

describe('ViewModesPanel: строка телефона не повторяет заголовок страницы', () => {
  it('выбранный вариант совпадает с заголовком: в строке «Значения», а не то же название', () => {
    wrap(
      <ViewModesPanel>
        <VariantGroupPicker
          group={GROUP}
          currentCode="us-gdp"
          basePath="/united-states/indicator"
          pageTitle="Валовой внутренний продукт в текущих ценах"
        />
      </ViewModesPanel>,
    );
    const toggle = screen.getByRole('button', { name: /Изменить вид/ });
    expect(toggle.textContent).toContain('Значения');
    expect(toggle.textContent).not.toContain('Валовой внутренний продукт');
    expect(toggle.textContent).not.toContain('ВВП');
  });

  it('вариант отличается от заголовка: в строке короткое имя варианта', () => {
    wrap(
      <ViewModesPanel>
        <VariantGroupPicker
          group={GROUP}
          currentCode="us-debt"
          basePath="/united-states/indicator"
          pageTitle="Государственный долг сектора государственного управления"
        />
      </ViewModesPanel>,
    );
    // Название совпало с заголовком (это он и есть), поэтому тоже «Значения»: не дублируем и короткое имя.
    expect(screen.getByRole('button', { name: /Изменить вид/ }).textContent).toContain('Значения');
  });

  it('все переключатели на значении по умолчанию: панель всё равно сворачивается и показывает его', () => {
    wrap(
      <ViewModesPanel>
        <ModeGroupsPicker
          title="Показать как"
          groups={[{ id: 'values', label: 'Значения', rawLabel: 'Уровень' }, { id: 'yoy', label: 'Год к году', rawLabel: 'Год к году' }]}
          activeGroupId="values"
          onTopClick={() => {}}
          currentMode="level"
          onSubClick={() => {}}
        />
      </ViewModesPanel>,
    );
    const toggle = screen.getByRole('button', { name: /Изменить вид/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(toggle.textContent).toContain('Значения');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
  });

  it('панель получает класс полосы выбора для компьютера', () => {
    const { container } = wrap(<ViewModesPanel><p>Содержимое</p></ViewModesPanel>);
    expect(container.querySelector('.fe-vm-panel').className).toContain('z4-desk');
  });
});

describe('IndicatorHeroValue: главное число в шапке', () => {
  const NOW = new Date('2026-10-05T00:00:00Z');
  const points = Array.from({ length: 16 }, (_, i) => ({ date: `${2010 + i}-01-01`, value: 18000 + i * 800 }));
  const summary = buildIndicatorSummary({
    points, frequency: 'annual', unit: 'млрд $', modeType: 'level', locale: 'ru', now: NOW,
  });

  it('крупное значение с единицей, изменение к прошлому году и период', () => {
    const { container } = wrap(
      <IndicatorHeroValue
        summary={summary}
        points={points}
        dateFormat="annual"
        frequency="annual"
        deltaSuffix="к прошлому году"
      />,
    );
    const text = container.textContent.replace(/\u00A0/g, ' ');
    expect(container.querySelector('[data-testid="indicator-hero-value"]')).toBeTruthy();
    expect(text).toContain('Сейчас');
    expect(text).toContain('30');
    expect(text).toContain('трлн $');
    expect(text).toMatch(/\+\d/);
    expect(text).toContain('к 2024');
    expect(container.querySelector('.z4-hv__value')).toBeTruthy();
  });

  it('оценка текущего года подписана словами', () => {
    const withEstimate = [...points, { date: '2026-01-01', value: 31000 }];
    const estimate = buildIndicatorSummary({
      points: withEstimate, frequency: 'annual', unit: 'млрд $', modeType: 'level', locale: 'ru', now: NOW,
    });
    const { container } = wrap(
      <IndicatorHeroValue summary={estimate} points={withEstimate} dateFormat="annual" frequency="annual" deltaSuffix="x" />,
    );
    expect(container.textContent).toContain('Оценка на 2026');
  });

  it('пока данных нет: скелет той же высоты; без данных и без загрузки ничего не рисует', () => {
    const loading = wrap(<IndicatorHeroValue summary={null} loading />);
    expect(loading.container.querySelector('.z4-hv--loading')).toBeTruthy();
    cleanup();
    const empty = wrap(<IndicatorHeroValue summary={null} />);
    expect(empty.container.firstChild).toBeNull();
  });
});

describe('DataTable: заголовок столбца значения', () => {
  const rows = [{ date: '2024-01-01', value: 1 }, { date: '2025-01-01', value: 2 }];

  it('короткая единица остаётся в заголовке «Значение (млрд $)»', () => {
    const { container } = wrap(<DataTable data={rows} unit="млрд $" dateFormat="annual" />);
    expect(container.querySelector('.fe-histtable__valhead').textContent).toBe('Значение (млрд $)');
  });

  it('длинная единица не растягивает заголовок на шесть строк: она в подсказке', () => {
    const unit = 'индекс, старт периода = 100';
    const { container } = wrap(<DataTable data={rows} unit={unit} dateFormat="annual" />);
    const head = container.querySelector('.fe-histtable__valhead');
    expect(head.textContent).toBe('Значение');
    expect(head.getAttribute('title')).toContain(unit);
  });
});
