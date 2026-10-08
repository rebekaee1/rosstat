import { describe, expect, it, vi, afterEach } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import RussiaHome from './RussiaHome';
import { renderPage, mockApiGet } from '../test/renderPage';
import { russiaMainFive } from '../lib/russiaHomeCards';

afterEach(() => vi.restoreAllMocks());

const base = { is_active: true, is_listed: true, name_en: '' };
const CPI = {
  ...base, code: 'cpi', name: 'Индекс потребительских цен', unit: 'индекс', frequency: 'monthly',
  category: 'Цены', category_ru: 'Цены', current_value: 99.92, current_date: '2026-08-01', change: -0.1,
};
const CPI_YOY = {
  ...base, code: 'cpi-yoy', name: 'Инфляция год к году', unit: '%', frequency: 'monthly', is_listed: false,
  category: 'Цены', category_ru: 'Цены', current_value: 5.4, current_date: '2026-08-01',
};
// Листинг после круга 8: у cpi есть годовое hero_value, а cpi-yoy из каталога скрыт.
const CPI_HERO = { ...CPI, hero_value: 6.34, hero_unit: '%', hero_label: 'г/г', hero_change: -0.2 };
const KEY_RATE = {
  ...base, code: 'key-rate', name: 'Ключевая ставка', unit: '%', frequency: 'daily',
  category: 'Ставки', category_ru: 'Ставки', current_value: 14, current_date: '2026-10-02', change: 0,
};
const USD = {
  ...base, code: 'usd-rub', name: 'Курс доллара США', unit: 'руб.', frequency: 'daily',
  category: 'Валюты', category_ru: 'Валюты', current_value: 83.48, current_date: '2026-10-03', change: 0.28,
};
const GDP = {
  ...base, code: 'gdp-nominal', name: 'ВВП номинальный', unit: 'млрд руб.', frequency: 'quarterly',
  category: 'ВВП', category_ru: 'ВВП', current_value: 41250, current_date: '2026-04-01', change: 500,
};
const UNEMPLOYMENT = {
  ...base, code: 'unemployment', name: 'Уровень безработицы', unit: '%', frequency: 'monthly',
  category: 'Рынок труда', category_ru: 'Рынок труда', current_value: 2.2, current_date: '2026-08-01', change: -0.1,
};

describe('russiaMainFive', () => {
  it('главное число инфляции — за год, месячное остаётся мелко', () => {
    const cards = russiaMainFive([CPI, CPI_YOY, KEY_RATE, USD, GDP, UNEMPLOYMENT]);
    expect(cards.map((c) => c.id)).toEqual(['inflation', 'rate', 'usd', 'gdp', 'unemployment']);
    expect(cards[0]).toMatchObject({ code: 'cpi', seriesCode: 'cpi-yoy', value: 5.4, unit: '%' });
    expect(cards[0].monthly.value).toBeCloseTo(-0.08, 2);
  });

  it('cpi-yoy нет в каталоге, но у cpi есть годовое hero_value: число годовое, ряд годовой, месяц мелко', () => {
    const cards = russiaMainFive([CPI_HERO, KEY_RATE]);
    expect(cards[0]).toMatchObject({ code: 'cpi', seriesCode: 'cpi-yoy', value: 6.34, unit: '%' });
    expect(cards[0].monthly.value).toBeCloseTo(-0.08, 2);
    expect(cards[0].noYearAgo).toBeUndefined();
  });

  it('годового числа нет совсем: карточка называется «за месяц» и «год назад» из индекса не берёт', () => {
    const cards = russiaMainFive([CPI, UNEMPLOYMENT]);
    expect(cards.map((c) => c.id)).toEqual(['inflation', 'unemployment']);
    expect(cards[0]).toMatchObject({
      seriesCode: 'cpi', unit: '%', monthly: null, noYearAgo: true, titleKey: 'c8y.ru.main.inflationMonth',
    });
    expect(cards[0].value).toBeCloseTo(-0.08, 2);
  });

  it('месяц годовой карточки не показывается, если период индекса другой', () => {
    const stale = { ...CPI_HERO, current_date: '2026-07-01' };
    const cards = russiaMainFive([stale, { ...CPI_YOY, current_date: '2026-08-01' }]);
    expect(cards[0].monthly).toBeNull();
  });
});

function mount(listing, extra = []) {
  const spy = mockApiGet([
    ['/auth/me', { user: null }],
    ...extra,
    ['/indicators', listing],
  ]);
  renderPage(<RussiaHome />, { path: '/russia', route: '/russia' });
  return spy;
}

describe('RussiaHome: главная пятёрка', () => {
  it('пять крупных карточек с человеческими названиями, ссылки ведут в показатели', async () => {
    mount([CPI, CPI_YOY, KEY_RATE, USD, GDP, UNEMPLOYMENT]);
    const box = await screen.findByTestId('russia-overview-chips');
    const cards = await within(box).findAllByRole('link');
    expect(cards).toHaveLength(5);
    const names = [...box.querySelectorAll('.z5-key__name')].map((el) => el.firstChild.textContent);
    expect(names).toEqual(['Инфляция за год', 'Ключевая ставка', 'Курс доллара', 'ВВП', 'Безработица']);
    const inflation = cards[0];
    expect(inflation.getAttribute('href')).toBe('/russia/indicator/cpi');
    const text = inflation.textContent.replace(/\u00a0/g, ' ');
    expect(text).toContain('5,4');
    expect(text).toContain('за месяц: \u22120,08 %');
    // ВВП в трлн, а не «41 250 млрд»
    expect(cards[3].textContent.replace(/\u00a0/g, ' ')).toContain('41,3');
    expect(cards[3].textContent).toContain('трлн ₽');
    // Жаргона нет, полное название читается скринридером.
    expect(inflation.querySelector('.sr-only').textContent).toContain('Индекс потребительских цен');
    expect(document.body.textContent).not.toContain('\u00B7');
  });
});

describe('RussiaHome: годовая инфляция и «год назад»', () => {
  const YOY_ROWS = [
    { date: '2025-08-01', value: 8.14 },
    { date: '2026-07-01', value: 6.5 },
    { date: '2026-08-01', value: 6.34 },
  ];

  it('число, «год назад» и график берутся из годового ряда, а не из индекса около 100', async () => {
    const spy = mount([CPI_HERO, KEY_RATE, USD, GDP, UNEMPLOYMENT], [
      [/\/indicators\/cpi-yoy\/data/, { data: YOY_ROWS }],
    ]);
    const box = await screen.findByTestId('russia-overview-chips');
    const inflation = (await within(box).findAllByRole('link'))[0];
    await vi.waitFor(() => {
      expect(inflation.textContent.replace(/\u00a0/g, ' ')).toContain('год назад: 8,14 %');
    });
    const text = inflation.textContent.replace(/\u00a0/g, ' ');
    expect(text).toContain('6,34');
    expect(text).not.toContain('99,6');
    const urls = spy.mock.calls.map((c) => c[0]);
    expect(urls).toContain('/indicators/cpi-yoy/data');
    expect(urls).not.toContain('/indicators/cpi/data');
  });

  it('без годового числа плитка «за месяц» не выдумывает «год назад»', async () => {
    mount([CPI, KEY_RATE, USD, GDP, UNEMPLOYMENT], [
      [/\/indicators\/cpi\/data/, { data: [{ date: '2025-08-01', value: 99.6 }, { date: '2026-08-01', value: 99.92 }] }],
    ]);
    const box = await screen.findByTestId('russia-overview-chips');
    const inflation = (await within(box).findAllByRole('link'))[0];
    expect(inflation.querySelector('.z5-key__name').firstChild.textContent).toBe('Инфляция за месяц');
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(inflation.textContent).not.toContain('год назад');
  });
});

describe('RussiaHome: компактные разделы', () => {
  const wages = Array.from({ length: 9 }, (_, i) => ({
    ...base,
    code: `wage-${i}`,
    name: `Показатель труда ${i}`,
    unit: 'руб.',
    frequency: 'monthly',
    category: 'Рынок труда',
    category_ru: 'Рынок труда',
    current_value: 100 + i,
    current_date: '2026-06-01',
    change: 1,
  }));

  it('сначала шесть строк (две колонки без пустой ячейки), остальное по кнопке «Показать ещё», и обратно', async () => {
    mount(wages);
    const section = await screen.findByTestId('russia-section');
    expect(within(section).getAllByRole('link')).toHaveLength(6);
    const more = within(section).getByRole('button', { name: /Показать ещё 3/ });
    expect(more.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(more);
    expect(within(section).getAllByRole('link')).toHaveLength(9);
    const less = within(section).getByRole('button', { name: /Свернуть/ });
    fireEvent.click(less);
    expect(within(section).getAllByRole('link')).toHaveLength(6);
  });

  it('раздел из семи строк кнопки не требует', async () => {
    mount(wages.slice(0, 7));
    const section = await screen.findByTestId('russia-section');
    expect(within(section).getAllByRole('link')).toHaveLength(7);
    expect(within(section).queryByRole('button')).toBeNull();
  });

  it('строка: значение с единицей, изменение со смыслом словами в подсказке', async () => {
    mount(wages.slice(0, 2));
    const section = await screen.findByTestId('russia-section');
    const row = within(section).getAllByRole('link')[0];
    expect(row.querySelector('.z5-ru-row__value small').textContent).toBe('руб.');
    expect(row.querySelector('.z5-ru-row__delta').getAttribute('title')).toMatch(/выше, чем в прошлом месяце/);
  });
});
