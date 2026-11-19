import { describe, it, expect } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import RegionIndicatorPage from './RegionIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

// Квартальный ряд региона (цена 1 м² жилья, 19.11.2026): годовой запрос отдаёт frequency='quarterly'.
const q = (year, quarter, value) => ({ year, quarter, value, label: `${['I', 'II', 'III', 'IV'][quarter - 1]} кв. ${year}` });

const PAYLOAD = {
  region: { slug: 'belgorodskaya-oblast', name: 'Белгородская область', kind: 'region' },
  indicator: {
    code: 'cena-m2-zhilya-vtorichnyy',
    name: 'Цена 1 м² жилья, вторичный рынок',
    unit: 'рублей за м²',
    note: null,
    section_num: 20,
    section_name: 'Цены и тарифы',
    table_code: '20.q2',
    macro_code: null,
  },
  frequency: 'quarterly',
  series: [q(2025, 3, 100000), q(2026, 2, 103000), q(2026, 3, 106000)],
  russia_series: [q(2025, 3, 140000), q(2026, 2, 143000), q(2026, 3, 146000)],
  rank: {
    position: 40, total: 82, year: 2026, quarter: 20263, period_label: 'III кв. 2026',
    rank_as_achievement: false, lower_better: false,
    top: [{ slug: 'moskva', name: 'Москва', value: 486000 }], bottom: [], around: [],
  },
  siblings: [],
};

describe('RegionIndicatorPage: квартальный ряд', () => {
  it('подписывает период кварталом и сравнивает с тем же кварталом год назад', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/regions\/belgorodskaya-oblast\/i\/cena-m2-zhilya-vtorichnyy$/, PAYLOAD],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    ]);
    renderPage(<RegionIndicatorPage />, {
      path: '/russia/region/:slug/:code',
      route: '/russia/region/belgorodskaya-oblast/cena-m2-zhilya-vtorichnyy',
    });

    await screen.findByRole('heading', { level: 1, name: /Цена 1 м² жилья/ });
    expect(screen.getAllByText('III кв. 2026').length).toBeGreaterThan(0);
    // +6 % к III кварталу 2025, а не +2,9 % к прошлому кварталу.
    expect(screen.getByText(/6,0\s%\sк тому же кварталу год назад/)).toBeTruthy();
    expect(screen.getByText(/Наибольшие значения по регионам, III кв\. 2026/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /Таблица значений по кварталам/ }));
    const table = screen.getByRole('table');
    expect(within(table).getByText('Квартал')).toBeTruthy();
    expect(within(table).getByText('II кв. 2026')).toBeTruthy();
  });
});
