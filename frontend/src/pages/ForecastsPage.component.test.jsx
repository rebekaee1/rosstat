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
      forecast_end: { date: '2027-08-01', value: 5.0, lower: 3.9, upper: 6.1 },
      change: { unit: 'points', value: -1.2, direction: 'down', horizon_months: 12 },
      history: series(9, 24, 5, 0.05),
      forecast: [
        { date: '2026-09-01', value: 6.0, lower: 5.8, upper: 6.2 },
        { date: '2027-08-01', value: 5.0, lower: 3.9, upper: 6.1 },
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
      forecast_end: { date: '2027-08-01', value: 4.3, lower: 3.8, upper: 4.8 },
      change: { unit: 'points', value: 0.2, direction: 'up', horizon_months: 12 },
      history: series(9, 24, 4, 0.0),
      forecast: [
        { date: '2026-09-01', value: 4.1, lower: 4.0, upper: 4.2 },
        { date: '2027-08-01', value: 4.3, lower: 3.8, upper: 4.8 },
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
    expect(russia.textContent).toContain('Коридор: от 3,9');
    expect(within(russia).getByRole('link', { name: /Открыть график/ }).getAttribute('href')).toBe('/russia/indicator/cpi');
    // Мини-график читается скринридером и содержит факт, пунктир и коридор.
    expect(within(russia).getByRole('img').getAttribute('aria-label')).toContain('через год');
    expect(russia.querySelector('.zb-fc__hist')).toBeTruthy();
    expect(russia.querySelector('.zb-fc__fore')).toBeTruthy();
    expect(russia.querySelector('.zb-fc__band')).toBeTruthy();

    const us = cards[1];
    expect(us.textContent).toContain('выше на 0,2 пункта');
    expect(us.textContent).toContain('Проверен на истории');
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

  it('без жаргона на виду', async () => {
    const { container } = renderForecasts();
    await screen.findAllByTestId('forecast-card');
    expect(container.textContent).not.toMatch(/API|SDMX|MASE|gate|парсер/i);
  });
});
