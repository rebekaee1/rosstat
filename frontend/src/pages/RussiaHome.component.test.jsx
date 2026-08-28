import { describe, expect, it, vi, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import RussiaHome from './RussiaHome';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const CPI = {
  code: 'cpi', name: 'Индекс потребительских цен', name_en: 'Consumer price index',
  unit: 'индекс', frequency: 'monthly', category: 'Цены', category_ru: 'Цены',
  current_value: 105.4, current_date: '2026-07-01', change: 0.3,
  is_active: true, is_listed: true,
};
const KEY_RATE = {
  code: 'key-rate', name: 'Ключевая ставка', name_en: 'Key rate',
  unit: '%', frequency: 'daily', category: 'Ставки', category_ru: 'Ставки',
  current_value: 17, current_date: '2026-08-25', change: -0.5,
  is_active: true, is_listed: true,
};
const UNEMPLOYMENT = {
  code: 'unemployment', name: 'Уровень безработицы', name_en: 'Unemployment rate',
  unit: '%', frequency: 'monthly', category: 'Рынок труда', category_ru: 'Рынок труда',
  current_value: 2.3, current_date: '2026-06-01', change: -0.1,
  is_active: true, is_listed: true,
};
const WAGES = {
  code: 'wages-nominal', name: 'Средняя номинальная заработная плата', name_en: 'Average nominal wages',
  unit: 'руб.', frequency: 'monthly', category: 'Рынок труда', category_ru: 'Рынок труда',
  current_value: 105000, current_date: '2026-06-01', change: 1500,
  is_active: true, is_listed: true,
};
const HIDDEN = {
  code: 'cpi-yoy', name: 'ИПЦ год к году', name_en: 'CPI YoY',
  unit: '%', frequency: 'monthly', category: 'Цены', category_ru: 'Цены',
  current_value: 5.4, current_date: '2026-07-01', change: 0.2,
  is_active: true, is_listed: false,
};
const NO_VALUE = {
  code: 'population', name: 'Численность населения', name_en: 'Population',
  unit: 'млн чел.', frequency: 'annual', category: 'Население', category_ru: 'Население',
  current_value: null, current_date: null, change: null,
  is_active: true, is_listed: true,
};

function renderRussia(payload) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/indicators', payload],
  ]);
  return renderPage(<RussiaHome />, { path: '/russia', route: '/russia' });
}

async function findChips() {
  const container = await screen.findByTestId('russia-overview-chips');
  return within(container);
}

const LISTING = [WAGES, CPI, KEY_RATE, UNEMPLOYMENT, NO_VALUE];

describe('RussiaHome hero и обзорные чипы', () => {
  it('H1 и intro из PAGE_META (SEO-элементы сохранены)', async () => {
    renderRussia(LISTING);

    expect(await screen.findByRole('heading', { level: 1, name: 'Россия' })).toBeTruthy();
    expect(screen.getByText(/Раздел России объединяет макроэкономические индикаторы/)).toBeTruthy();
  });

  it('тёмная territory-карточка как у WorldCountry: кликабельная карта субъектов', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/indicators', LISTING],
      ['/regions', {
        districts: [{
          code: 'cfo',
          name: 'ЦФО',
          regions: [{ slug: 'moskva', name: 'Москва' }],
        }],
        russia: { slug: 'rossiyskaya-federaciya', name: 'Россия' },
      }],
    ]);
    renderPage(<RussiaHome />, { path: '/russia', route: '/russia' });

    await screen.findByRole('heading', { level: 1, name: 'Россия' });

    const card = await screen.findByLabelText('Карта субъектов Российской Федерации');
    expect(card.className).toContain('bg-[#191A20]');
    expect(card.textContent).toContain('Профиль территории');
    expect(card.textContent).toContain('85 субъектов');
    expect(card.textContent).toContain('RU');

    // Карта монтируется лениво; path + marker города — оба кликабельны.
    const regions = await screen.findAllByRole('button', { name: 'Москва' });
    expect(regions.length).toBeGreaterThanOrEqual(1);
    expect(regions.every((el) => el.getAttribute('data-region-slug') === 'moskva')).toBe(true);
  });

  it('три якорных чипа: ИПЦ (минус 100), ключевая ставка, безработица', async () => {
    renderRussia(LISTING);

    const chips = await findChips();

    const cpiChip = await chips.findByRole('link', { name: /Индекс потребительских цен/ });
    expect(cpiChip.getAttribute('href')).toBe('/russia/indicator/cpi');
    expect(cpiChip.textContent).toContain('5,4');

    const rateChip = chips.getByRole('link', { name: /Ключевая ставка/ });
    expect(rateChip.getAttribute('href')).toBe('/russia/indicator/key-rate');
    expect(rateChip.textContent).toContain('17');

    const uneChip = chips.getByRole('link', { name: /Уровень безработицы/ });
    expect(uneChip.getAttribute('href')).toBe('/russia/indicator/unemployment');
    expect(uneChip.textContent).toContain('2,3');
  });

  it('ряд без текущего значения чип не образует', async () => {
    renderRussia([NO_VALUE]);

    await screen.findByRole('heading', { level: 1, name: 'Россия' });
    expect(screen.queryByRole('link', { name: /Численность населения/ })).toBeNull();
  });
});

describe('RussiaHome секции категорий', () => {
  it('активная секция с плитками-ссылками в российский каталог', async () => {
    renderRussia(LISTING);

    // jsdom = мобильный вьюпорт: показана только активная (первая) секция.
    expect(await screen.findByRole('heading', { name: 'Цены и инфляция' })).toBeTruthy();

    const section = screen.getByTestId('russia-section');
    const tile = within(section).getByRole('link', { name: /Индекс потребительских цен/ });
    expect(tile.getAttribute('href')).toBe('/russia/indicator/cpi');
    expect(tile.textContent).toContain('5,4');
  });

  it('скрытые из листинга ряды (is_listed=false) не рендерятся', async () => {
    renderRussia([HIDDEN, ...LISTING]);

    await screen.findByRole('heading', { level: 1, name: 'Россия' });
    expect(screen.queryByRole('link', { name: /ИПЦ год к году/ })).toBeNull();
  });
});

describe('RussiaHome навигация по категориям', () => {
  it('sticky aside присутствует с якорными ссылками и счётчиками', async () => {
    renderRussia(LISTING);

    const aside = await screen.findByTestId('russia-aside');
    expect(aside.className).toContain('lg:sticky');
    expect(aside.className).toContain('lg:top-24');
    expect(aside.className).toContain('lg:self-start');

    const anchors = Array.from(aside.querySelectorAll('a[href^="#cat-"]'));
    expect(anchors.length).toBeGreaterThanOrEqual(3);
    // Первая категория CATEGORIES — цены; в фикстуре один listed-ряд.
    expect(anchors[0].textContent).toContain('Цены и инфляция');
    expect(anchors[0].textContent).toContain('1');
    expect(anchors.map((a) => a.textContent).join(' ')).toContain('Рынок труда');
  });

  it('мобильный select-навигатор смонтирован (кнопка выбора раздела)', async () => {
    renderRussia(LISTING);

    const select = await screen.findByRole('button', { name: /Сменить/ });
    expect(select.getAttribute('aria-haspopup')).toBe('dialog');
    expect(select.textContent).toContain('Цены и инфляция');
  });
});

describe('RussiaHome быстрые входы (SEO-требование)', () => {
  it('Сегодня, Регионы, Календарь и Демография доступны ряд ссылок-карточек', async () => {
    renderRussia(LISTING);

    await screen.findByRole('heading', { level: 1, name: 'Россия' });

    const today = screen.getByRole('link', { name: /Сегодня/ });
    expect(today.getAttribute('href')).toBe('/russia/today');
    expect(today.textContent).toContain('Ключевые показатели на текущую дату');

    const regions = screen.getByRole('link', { name: /Регионы/ });
    expect(regions.getAttribute('href')).toBe('/russia/region');

    const calendar = screen.getByRole('link', { name: /Календарь/ });
    expect(calendar.getAttribute('href')).toBe('/russia/calendar');

    const demographics = screen.getByRole('link', { name: /Демография/ });
    expect(demographics.getAttribute('href')).toBe('/russia/demographics');
  });
});

describe('RussiaHome ошибки и пустые состояния', () => {
  it('пустой каталог показывает нейтральный empty state, не падает', async () => {
    renderRussia([]);

    expect(await screen.findByText(/Пока нет опубликованных показателей/)).toBeTruthy();
    expect(screen.queryByTestId('russia-aside')).toBeNull();
  });

  it('десктоп: видны все секции, плитки со значением выше пустых', async () => {
    const mq = (q) => ({ matches: q.includes('min-width'), media: q, addEventListener() {}, removeEventListener() {} });
    const spy = vi.spyOn(window, 'matchMedia').mockImplementation(mq);

    try {
      renderRussia(LISTING);

      const sections = await screen.findAllByTestId('russia-section');
      expect(sections.length).toBeGreaterThanOrEqual(3);
      const tile = screen.getByRole('link', { name: /Средняя номинальная заработная плата/ });
      expect(tile.textContent).toContain('105');
      expect(tile.textContent).toContain('июнь 2026');
      // Пустой ряд тоже отрендерен: вместо значения — прочерк, изменения нет.
      const emptyTile = within(
        sections.find((s) => s.textContent.includes('Численность населения')),
      ).getByRole('link', { name: /Численность населения/ });
      expect(emptyTile.textContent).toContain('—');
      expect(emptyTile.textContent).not.toContain('+');
    } finally {
      spy.mockRestore();
    }
  });

  it('ошибка API: баннер с ретраем, без секций', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/indicators', Promise.reject(Object.assign(new Error('boom'), { response: { status: 500 } }))],
    ]);

    renderPage(<RussiaHome />, { path: '/russia', route: '/russia' });

    expect(await screen.findByText(/Данные о показателях сейчас не подгрузились/)).toBeTruthy();
    expect(screen.queryByTestId('russia-aside')).toBeNull();
  });
});
