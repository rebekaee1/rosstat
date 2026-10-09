// Круг 11, зона F: страница России. Изменение в строках раздела называет, к чему оно, а у карточек «Главного» одно название.
import { describe, expect, it, vi, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import RussiaHome from './RussiaHome';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const base = { is_active: true, is_listed: true, name_en: '' };
const CPI = {
  ...base, code: 'cpi', name: 'Индекс потребительских цен', name_en: 'Consumer Price Index', unit: 'индекс', frequency: 'monthly',
  category: 'Цены', category_ru: 'Цены', current_value: 99.92, current_date: '2026-08-01', change: -0.1,
  hero_value: 6.34, hero_unit: '%', hero_label: 'г/г', hero_change: -0.2,
};
const KEY_RATE = {
  ...base, code: 'key-rate', name: 'Ключевая ставка', unit: '%', frequency: 'daily',
  category: 'Ставки', category_ru: 'Ставки', current_value: 14, current_date: '2026-10-02', change: 0.5,
};
const GDP = {
  ...base, code: 'gdp-nominal', name: 'ВВП номинальный', unit: 'млрд руб.', frequency: 'quarterly',
  category: 'ВВП', category_ru: 'ВВП', current_value: 41250, current_date: '2026-04-01', change: 500,
};

function mount(listing) {
  mockApiGet([['/auth/me', { user: null }], ['/indicators', listing]]);
  renderPage(<RussiaHome />, { path: '/russia', route: '/russia' });
}

describe('RussiaHome: круг 11 (F)', () => {
  it('стрелка изменения в строке раздела называет основание: «к прошлому месяцу / кварталу», у дневного ряда «к прошлому значению»', async () => {
    mount([CPI, KEY_RATE, GDP]);
    const section = await screen.findByTestId('russia-section');
    const rows = [...section.querySelectorAll('.z5-ru-row')];
    expect(rows.length).toBeGreaterThan(0);
    const cpiRow = rows.find((row) => row.textContent.includes('Индекс потребительских цен'));
    expect(cpiRow.querySelector('.z5-ru-row__vs').textContent).toBe('к прошлому месяцу');
  });

  it('карточка «Главного» называется одним словом и не несёт второго имени в подсказке или скрытом тексте', async () => {
    mount([CPI, KEY_RATE, GDP]);
    const box = await screen.findByTestId('russia-overview-chips');
    const inflation = (await within(box).findAllByRole('link'))[0];
    expect(inflation.querySelector('.z5-key__name').textContent).toBe('Инфляция за год');
    expect(inflation.querySelector('.z5-key__name').getAttribute('title')).toBeNull();
    expect(inflation.querySelector('.sr-only')).toBeNull();
    expect(inflation.textContent).not.toContain('Consumer Price Index');
  });
});
