/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import Breadcrumbs from './Breadcrumbs';
import ForecastControl from './ForecastControl';
import WorldStatTiles, { WorldHeroLine } from './WorldStatTiles';
import WorldChartSection from './WorldChartSection';
import ChartBrush from './ChartBrush';
import { buildIndicatorSummary } from '../lib/indicatorSummary';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, key) => String(key) }),
}));

afterEach(cleanup);

function wrap(ui) {
  return render(
    <LocaleProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </LocaleProvider>,
  );
}

describe('Breadcrumbs: заглушка вместо многоточия', () => {
  it('пока название грузится, в навигации нет «…», а есть заглушка того же размера', () => {
    const { container } = wrap(
      <Breadcrumbs items={[
        { path: '/', name: 'Главная' },
        { path: '/germany', name: '…' },
        { path: '/germany/indicator/x', name: '' },
      ]}
      />,
    );
    expect(container.textContent).not.toContain('…');
    expect(container.querySelectorAll('.fe-crumbs__ghost')).toHaveLength(2);
    expect(container.querySelector('nav').getAttribute('aria-busy')).toBe('true');
  });

  it('когда названия пришли, заглушек нет', () => {
    const { container } = wrap(
      <Breadcrumbs items={[
        { path: '/', name: 'Главная' },
        { path: '/germany', name: 'Германия' },
        { path: '/germany/indicator/x', name: 'Инфляция' },
      ]}
      />,
    );
    expect(container.querySelectorAll('.fe-crumbs__ghost')).toHaveLength(0);
    expect(screen.getByRole('link', { name: 'Германия' })).toBeTruthy();
    expect(container.querySelector('nav').getAttribute('aria-busy')).toBeNull();
  });
});

describe('ForecastControl', () => {
  it('есть прогноз: подписанный переключатель', () => {
    const onToggle = vi.fn();
    wrap(<ForecastControl enabled on onToggle={onToggle} />);
    const sw = screen.getByRole('switch');
    expect(sw.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(sw);
    expect(onToggle).toHaveBeenCalled();
  });

  it('прогноза нет: тумблера нет, вместо него одна понятная фраза', () => {
    wrap(<ForecastControl enabled={false} on={false} onToggle={vi.fn()} />);
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.getByText('Прогноз для этого показателя пока не строится')).toBeTruthy();
  });
});

const NOW = new Date('2026-10-05T00:00:00Z');

function gdpSummary() {
  const points = [];
  for (let y = 2010; y <= 2026; y += 1) points.push({ date: `${y}-01-01`, value: 20000 + (y - 2010) * 700 });
  return buildIndicatorSummary({
    points, frequency: 'annual', unit: 'млрд $', modeType: 'level', locale: 'ru', now: NOW,
  });
}

describe('WorldStatTiles и заголовок со значением', () => {
  it('ВВП: оценка года, укрупнённые числа, рост за 10 лет и место среди стран; нет «В среднем» и «максимума»', () => {
    const { container } = wrap(
      <WorldStatTiles
        summary={gdpSummary()}
        dateFormat="annual"
        frequency="annual"
        previousLabel="Предыдущий год"
        deltaSuffix="к прошлому году"
        rank={{ rank: 2, total: 190 }}
      />,
    );
    const text = container.textContent.replace(/\u00A0/g, ' ');
    expect(text).toContain('Оценка на 2026');
    expect(text).toContain('31,2');
    expect(text).toContain('трлн $');
    expect(text).toContain('+2,3 %');
    expect(text).toContain('к 2025');
    expect(text).toContain('Рост за 10 лет');
    expect(text).toContain('Место среди стран');
    expect(text).toContain('из 190');
    expect(text).not.toMatch(/Исторический максимум|В среднем|Среднее/);
    expect(container.querySelectorAll('.w2-stat')).toHaveLength(4);
  });

  it('плитка без изменения не оставляет пустую строку: примечание идёт сразу под числом', () => {
    const { container } = wrap(
      <WorldStatTiles
        summary={gdpSummary()}
        dateFormat="annual"
        frequency="annual"
        previousLabel="Предыдущий год"
        deltaSuffix="к прошлому году"
      />,
    );
    const tiles = container.querySelectorAll('.w2-stat');
    expect(tiles[1].className).toContain('w2-stat--nodelta');
    expect(tiles[0].className).not.toContain('w2-stat--nodelta');
  });

  it('изменение в процентах и словами: у неподвижного ряда «без изменений»', () => {
    const flat = buildIndicatorSummary({
      points: [{ date: '2025-01-01', value: 3 }, { date: '2026-01-01', value: 3 }],
      frequency: 'annual', unit: '%', modeType: 'level', dataDigits: 1, locale: 'ru', now: NOW,
    });
    const { container } = wrap(
      <WorldStatTiles summary={flat} dateFormat="annual" frequency="annual" previousLabel="Предыдущий год" deltaSuffix="x" />,
    );
    expect(container.textContent).toContain('без изменений');
  });

  it('заголовок: «Германия: 2,3 % за 2025 год» одной строкой, единица рядом с числом', () => {
    const s = buildIndicatorSummary({
      points: [{ date: '2024-01-01', value: 2.5 }, { date: '2025-01-01', value: 2.3 }],
      frequency: 'annual', unit: '%', modeType: 'level', dataDigits: 1, locale: 'ru', now: NOW,
    });
    const { container } = wrap(<WorldHeroLine summary={s} place="Германия" dateFormat="annual" />);
    expect(container.textContent.replace(/\u00A0/g, ' ')).toBe('Германия: 2,3 % за 2025 год');
  });

  it('заголовок: для оценки года так и пишет', () => {
    const { container } = wrap(<WorldHeroLine summary={gdpSummary()} place="США" dateFormat="annual" />);
    expect(container.textContent.replace(/\u00A0/g, ' ')).toContain('31,2 трлн $ оценка на 2026');
  });
});

describe('WorldChartSection', () => {
  const props = {
    code: 'de-x',
    indicator: { name: 'Население', unit: 'человек', frequency: 'annual', category: 'Демография' },
    modeMeta: { id: 'level-annual', type: 'level', freq: 'annual', unit: 'человек' },
    dataPoints: Array.from({ length: 30 }, (_, i) => ({ date: `${1996 + i}-01-01`, value: 80000000 + i * 100000 })),
    forecastEnabled: false,
    showForecast: true,
    onToggleForecast: vi.fn(),
    frequency: 'annual',
    unit: 'человек',
    country: { slug: 'germany', name: 'Германия', code: 'DE' },
    conceptSlug: 'population',
    comparisonPeers: [
      { code: 'peer:china:pop', country_slug: 'china', country_name: 'Китай', country_code: 'CN', indicator_code: 'cn-pop' },
      { code: 'peer:japan:pop', country_slug: 'japan', country_name: 'Япония', country_code: 'JP', indicator_code: 'jp-pop' },
    ],
    onFullData: vi.fn(),
    onDownloadCsv: vi.fn(),
    onDownloadExcel: vi.fn(),
  };

  function renderSection(extra = {}) {
    mockApiGet([['/auth/me', { user: null }]]);
    return renderPage(<WorldChartSection {...props} {...extra} />, { path: '/', route: '/' });
  }

  it('нет прогноза: тумблера нет, написано что прогноз не строится, дальше есть куда идти', () => {
    renderSection();
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.getByText('Прогноз для этого показателя пока не строится')).toBeTruthy();
    const next = screen.getByRole('navigation', { name: 'Что посмотреть дальше' });
    expect(within(next).getByRole('link', { name: /Рейтинг стран/ }).getAttribute('href')).toContain('/world/rating/population');
    expect(within(next).getByRole('link', { name: /Все показатели: Германия/ })).toBeTruthy();
  });

  it('сравнение стран стоит выше графика, а чипы стран нажимаются одним касанием', () => {
    const { container } = renderSection();
    const compare = container.querySelector('#compare');
    const plot = container.querySelector('.fe-chart-plot');
    expect(compare).toBeTruthy();
    expect(plot).toBeTruthy();
    // DOCUMENT_POSITION_FOLLOWING: график идёт после блока сравнения.
    expect(compare.compareDocumentPosition(plot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(compare).getByRole('button', { name: 'Китай' })).toBeTruthy();
  });

  it('название показателя не повторяется над графиком: один заголовок секции и подпись «что показано»', () => {
    const { container } = renderSection();
    expect(container.textContent).not.toContain('Население');
    expect(container.querySelector('h2').textContent).toBe('Динамика показателя');
    expect(container.querySelector('.fe-chart-title').textContent).toContain('Значения');
  });

  it('есть прогноз: переключатель включён по умолчанию', () => {
    renderSection({ forecastEnabled: true, forecastGateStatus: 'passed' });
    expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('true');
    expect(screen.queryByText('Прогноз для этого показателя пока не строится')).toBeNull();
  });

  it('одна кнопка «Скачать» вместо россыпи кнопок', () => {
    renderSection();
    expect(screen.getAllByRole('button', { name: /Скачать/ })).toHaveLength(1);
  });
});

describe('ChartBrush', () => {
  const rows = Array.from({ length: 40 }, (_, i) => ({ date: `${2000 + i}-01-01`, actual: i }));

  it('две ручки: стрелками двигается начало и конец окна', () => {
    const onChange = vi.fn();
    wrap(
      <ChartBrush
        rows={rows}
        start={10}
        end={30}
        minWindow={5}
        onChange={onChange}
        labels={{ group: 'Период', from: 'Начало', to: 'Конец' }}
      />,
    );
    const [from, to] = screen.getAllByRole('slider');
    fireEvent.keyDown(from, { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenLastCalledWith(9, 30);
    fireEvent.keyDown(to, { key: 'ArrowRight', shiftKey: true });
    expect(onChange).toHaveBeenLastCalledWith(10, 40);
  });

  it('окно не сжимается меньше минимума', () => {
    const onChange = vi.fn();
    wrap(
      <ChartBrush
        rows={rows}
        start={10}
        end={15}
        minWindow={5}
        onChange={onChange}
        labels={{ group: 'Период', from: 'Начало', to: 'Конец' }}
      />,
    );
    const [from] = screen.getAllByRole('slider');
    fireEvent.keyDown(from, { key: 'ArrowRight' });
    expect(onChange).not.toHaveBeenCalled();
  });
});
