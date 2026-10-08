// Страница «Прогнозы»: показывает только то, что отдаёт витрина, честно говорит о границах, ведёт на графики.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import ForecastsPage from './ForecastsPage';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function series(startMonth, count, base, step) {
  const out = [];
  for (let i = 0; i < count; i += 1) {
    const month = startMonth + i;
    const year = 2024 + Math.floor((month - 1) / 12);
    const m = ((month - 1) % 12) + 1;
    out.push({ date: `${year}-${String(m).padStart(2, '0')}-01`, value: base + step * i });
  }
  return out;
}

const SHOWCASE = {
  locale: 'ru',
  themes: [
    { id: 'inflation', name: 'Цены' },
    { id: 'unemployment', name: 'Работа' },
  ],
  items: [
    {
      id: 'russia-inflation',
      scope: 'russia',
      theme: 'inflation',
      kind: 'percent',
      title: 'Россия: инфляция за 12 месяцев',
      country: { slug: 'russia', code: 'RU', name: 'Россия' },
      unit: '% за 12 месяцев',
      frequency: 'monthly',
      source: 'Росстат',
      path: '/russia/indicator/cpi',
      last_actual: { date: '2026-08-01', value: 6.2 },
      forecast_end: { date: '2027-08-01', value: 5.0 },
      change: { unit: 'points', value: -1.2, direction: 'down', horizon_months: 12 },
      history: series(9, 24, 5, 0.05),
      forecast: [
        { date: '2026-09-01', value: 6.0 },
        { date: '2027-08-01', value: 5.0 },
      ],
      updated: '2026-09-05',
      verified: false,
    },
    {
      id: 'united-states-unemployment',
      scope: 'world',
      theme: 'unemployment',
      kind: 'percent',
      title: 'США: безработица',
      country: { slug: 'united-states', code: 'US', name: 'США' },
      unit: '% экономически активного населения',
      frequency: 'monthly',
      source: 'Бюро трудовой статистики США',
      path: '/united-states/indicator/us-unemployment-rate',
      last_actual: { date: '2026-08-01', value: 4.1 },
      forecast_end: { date: '2027-08-01', value: 4.3 },
      change: { unit: 'points', value: 0.2, direction: 'up', horizon_months: 12 },
      history: series(9, 24, 4, 0.0),
      forecast: [
        { date: '2026-09-01', value: 4.1 },
        { date: '2027-08-01', value: 4.3 },
      ],
      updated: '2026-09-05',
      verified: true,
    },
  ],
};

function renderForecasts(payload = SHOWCASE) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/forecasts/showcase', payload],
  ]);
  return renderPage(<ForecastsPage />, { path: '/forecasts', route: '/forecasts' });
}

describe('ForecastsPage', () => {
  it('рисует карточки витрины с числами, изменением и ссылкой на график', async () => {
    renderForecasts();
    const cards = await screen.findAllByTestId('forecast-card');
    expect(cards).toHaveLength(2);

    const russia = cards[0];
    expect(within(russia).getByRole('heading', { level: 3, name: 'Россия: инфляция за 12 месяцев' })).toBeTruthy();
    expect(russia.textContent).toContain('6,2');
    expect(russia.textContent).toContain('5,0');
    expect(russia.textContent).toContain('ниже на 1,2 пункта');
    expect(within(russia).getByRole('link', { name: /Открыть график/ }).getAttribute('href')).toBe('/russia/indicator/cpi');
    // Мини-график читается скринридером и содержит линию факта и линию прогноза, без диапазона.
    expect(within(russia).getByRole('img').getAttribute('aria-label')).toContain('через год');
    expect(russia.querySelector('.zb-fc__hist')).toBeTruthy();
    expect(russia.querySelector('.zb-fc__fore')).toBeTruthy();
    expect(russia.querySelector('.zb-fc__band')).toBeNull();

    const us = cards[1];
    expect(us.textContent).toContain('выше на 0,2 пункта');
    expect(us.textContent).toContain('Проверен на прошлых данных');
  });

  it('диапазона прогноза нет нигде: ни в тексте, ни в легенде, ни на графике, даже если сервер прислал границы', async () => {
    const withBounds = JSON.parse(JSON.stringify(SHOWCASE));
    for (const item of withBounds.items) {
      item.forecast_end = { ...item.forecast_end, lower: 1, upper: 99 };
      item.forecast = item.forecast.map((row) => ({ ...row, lower: 1, upper: 99 }));
    }
    const { container } = renderForecasts(withBounds);
    await screen.findAllByTestId('forecast-card');
    expect(container.textContent).not.toMatch(/коридор|диапазон|интервал|доверитель/i);
    expect(container.textContent).not.toContain('99');
    expect(container.querySelector('.zb-fc__band')).toBeNull();
    expect(container.querySelector('.zb-fc__key--range')).toBeNull();
    // Графика высотой в рамку: границы 1 и 99 не растягивают ось (линия остаётся в пределах значений прогноза).
    const nums = container.querySelector('.zb-fc__fore').getAttribute('d').match(/-?\d+(\.\d+)?/g).map(Number);
    expect(Math.min(...nums)).toBeGreaterThanOrEqual(0);
  });

  it('метод остаётся второй ссылкой, границы витрины названы вслух', async () => {
    renderForecasts();
    await screen.findAllByTestId('forecast-card');
    const method = screen.getByRole('link', { name: /Как мы считаем/ });
    expect(method.getAttribute('href')).toBe('/methodology#read');
    expect(screen.getByRole('heading', { level: 2, name: 'Чего здесь нет' })).toBeTruthy();
    expect(screen.getByText(/не пересказываем и не подменяем/)).toBeTruthy();
  });

  it('фильтр по теме оставляет только нужные карточки', async () => {
    renderForecasts();
    await screen.findAllByTestId('forecast-card');
    fireEvent.click(screen.getByRole('button', { name: 'Работа' }));
    const cards = screen.getAllByTestId('forecast-card');
    expect(cards).toHaveLength(1);
    expect(cards[0].textContent).toContain('США: безработица');
    fireEvent.click(screen.getByRole('button', { name: 'Все' }));
    expect(screen.getAllByTestId('forecast-card')).toHaveLength(2);
  });

  it('пустая витрина: честная фраза вместо выдуманных прогнозов', async () => {
    renderForecasts({ locale: 'ru', themes: [], items: [] });
    expect(await screen.findByText(/Прогнозы появятся здесь/)).toBeTruthy();
    expect(screen.queryAllByTestId('forecast-card')).toHaveLength(0);
  });

  it('K5.4: карточки без blur (fe-glass-lite), стрелка-грань между цифрами, луч «сейчас», лента лениво', async () => {
    const { container } = renderForecasts();
    const cards = await screen.findAllByTestId('forecast-card');
    for (const card of cards) {
      expect(card.className).toContain('fe-glass-lite');
      expect(card.className).not.toContain('fe-panel');
      expect(card.querySelector('.zb-fc__arrow')).toBeTruthy();
      expect(card.querySelector('.zb-fc__ray')).toBeTruthy();
      expect(card.querySelector('.zb-fc__split')).toBeNull();
    }
    expect(cards[1].querySelector('.zb-fc__badge').getAttribute('data-verified')).toBe('true');
    const ribbon = container.querySelector('.zb-fc__ribbon img');
    expect(ribbon.getAttribute('src')).toBe('/brand/ribbon.webp');
    expect(ribbon.getAttribute('loading')).toBe('lazy');
    expect(ribbon.getAttribute('alt')).toBe('');
    expect(ribbon.getAttribute('width')).toBe('1114');
    expect(ribbon.getAttribute('height')).toBe('631');
  });

  it('без жаргона на виду', async () => {
    const { container } = renderForecasts();
    await screen.findAllByTestId('forecast-card');
    expect(container.textContent).not.toMatch(/API|SDMX|MASE|gate|парсер/i);
  });

  it('круг 8: единица стоит рядом с числами, на мини-графике подписаны начало, «сейчас» и конец', async () => {
    const level = JSON.parse(JSON.stringify(SHOWCASE));
    level.items[0] = {
      ...level.items[0],
      id: 'germany-inflation',
      kind: 'level',
      unit: 'индекс 2015=100',
      title: 'Германия: потребительские цены',
      last_actual: { date: '2026-08-01', value: 136.34 },
      forecast_end: { date: '2027-08-01', value: 140.08 },
    };
    const { container } = renderForecasts(level);
    const cards = await screen.findAllByTestId('forecast-card');
    const card = cards[0];
    expect(card.querySelector('.zb-fc__unit').textContent).toBe('индекс 2015=100');
    // Две отметки значений и три подписи под графиком; прогноз по-прежнему одна линия без диапазона.
    expect(card.querySelectorAll('.zb-fc__tag')).toHaveLength(2);
    const axis = card.querySelector('.zb-fc__axis');
    expect(axis.querySelector('.zb-fc__axis-now').textContent).toBe('Сейчас');
    expect(axis.querySelector('.zb-fc__axis-start').textContent).not.toBe('');
    expect(axis.querySelector('.zb-fc__axis-end').textContent).not.toBe('');
    expect(container.querySelector('.zb-fc__dot-spark')).toBeNull();
    expect(container.querySelector('.zb-fc__meta')).toBeNull();
    // Бейдж стоит над названием и не сдвигает значения соседних карточек.
    const head = card.querySelector('.zb-fc__card-head');
    expect(head.firstElementChild.className).toContain('zb-fc__badge');
    expect(head.lastElementChild.tagName).toBe('H3');
  });

  it('круг 8: запрос витрины ждёт не дольше 10 с и не уходит в тихие повторы перехватчика', async () => {
    const spy = mockApiGet([
      ['/auth/me', { user: null }],
      ['/forecasts/showcase', SHOWCASE],
    ]);
    renderPage(<ForecastsPage />, { path: '/forecasts', route: '/forecasts' });
    await screen.findAllByTestId('forecast-card');
    const call = spy.mock.calls.find(([url]) => url === '/forecasts/showcase');
    expect(call[1].timeout).toBe(10000);
    expect(call[1].__retryCount).toBeGreaterThanOrEqual(3);
  });
});

