import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import RegionProfile from './RegionProfile';
import { mockApiGet, renderPage } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const PROFILE = {
  region: { slug: 'moskva', name: 'г. Москва', district_name: 'Центральный федеральный округ' },
  catalog_total: 495,
  available_total: 474,
  headline: {
    '1.1': { code: 'chislennost-naseleniya', label: 'Население', name: 'Численность населения', value: 13150, prev_value: 13100, unit: 'тысяч человек', year: 2023 },
    '2.10.1': { code: 'uroven-bezrabotitsy', label: 'Безработица', name: 'Уровень безработицы', value: 1, prev_value: 1.8, unit: 'процентов', year: 2024 },
    '8.2': { code: 'inflyatsiya', label: 'Инфляция', name: 'Инфляция', value: 10.1, prev_value: 7.6, unit: 'процентов', year: 2024 },
    '10.1': { code: 'vrp', label: 'ВРП', name: 'Валовой региональный продукт', value: 32339002, prev_value: 30000000, unit: 'миллионов рублей', year: 2023 },
  },
  sections: [
    { num: 1, name: 'Население', indicators: [
      { code: 'bezhentsy', name: 'Численность беженцев', unit: 'человек', value: 10, prev_value: 9, year: 2024 },
      { code: 'chislennost-naseleniya', name: 'Численность населения', unit: 'тысяч человек', value: 13150, prev_value: 13100, year: 2023 },
    ] },
  ],
};

function mount() {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/regions/moskva', PROFILE],
  ]);
  renderPage(<RegionProfile />, { path: '/russia/region/:slug', route: '/russia/region/moskva' });
}

describe('RegionProfile', () => {
  it('без цифр базы данных: «495 показателей» и «474» на странице нет', async () => {
    mount();
    await screen.findByRole('heading', { name: 'г. Москва' });
    expect(document.body.textContent).not.toMatch(/495|474/);
  });

  it('падение безработицы — хорошо (не красное), рост инфляции — плохо (не зелёное)', async () => {
    mount();
    const unemployment = (await screen.findAllByRole('link', { name: /Безработица/ }))[0];
    const badgeU = unemployment.querySelector('.fe-delta-badge');
    expect(badgeU.className).toMatch(/fe-tone--good/);
    const inflation = screen.getAllByRole('link', { name: /Инфляция/ })[0];
    expect(inflation.querySelector('.fe-delta-badge').className).toMatch(/fe-tone--bad/);
  });

  it('единица всегда рядом с числом, проценты с одним знаком, крупные суммы сжаты', async () => {
    mount();
    const unemployment = (await screen.findAllByRole('link', { name: /Безработица/ }))[0];
    expect(unemployment.textContent).toContain('1,0 %');
    const vrp = screen.getAllByRole('link', { name: /ВРП/ })[0];
    expect(vrp.textContent).toContain('32,3 трлн ₽');
  });

  it('в разделе «Население» первой идёт численность населения, а не беженцы', async () => {
    mount();
    await screen.findByRole('heading', { name: 'г. Москва' });
    const links = within(document.getElementById('chart')).getAllByRole('link');
    expect(links[0].textContent).toMatch(/Численность населения/);
    expect(links[1].textContent).toMatch(/Численность беженцев/);
  });
});
