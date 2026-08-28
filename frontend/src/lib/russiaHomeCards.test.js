import { describe, expect, it } from 'vitest';
import { CATEGORIES } from './categories';
import {
  groupRussiaCategories,
  russiaIndicatorChange,
  russiaIndicatorDisplay,
  russiaOverviewChips,
  sortRussiaTiles,
} from './russiaHomeCards';

const CPI = {
  code: 'cpi', name: 'Индекс потребительских цен', unit: 'индекс',
  category: 'Цены', category_ru: 'Цены', current_value: 105.4, current_date: '2026-07-01',
  change: 0.3, is_active: true, is_listed: true,
};
const KEY_RATE = {
  code: 'key-rate', name: 'Ключевая ставка', unit: '%',
  category: 'Ставки', category_ru: 'Ставки', current_value: 17, current_date: '2026-08-25',
  is_active: true, is_listed: true,
};
const UNEMPLOYMENT = {
  code: 'unemployment', name: 'Уровень безработицы', unit: '%',
  category: 'Рынок труда', category_ru: 'Рынок труда', current_value: 2.3,
  current_date: '2026-06-01', change: -0.1, is_active: true, is_listed: true,
};
const WAGES_NOMINAL = {
  code: 'wages-nominal', name: 'Средняя номинальная заработная плата', unit: 'руб.',
  category: 'Рынок труда', category_ru: 'Рынок труда', current_value: 105000,
  current_date: '2026-06-01', is_active: true, is_listed: true,
};
const CPI_FOOD = {
  code: 'cpi-food', name: 'Индекс потребительских цен на продовольственные товары', unit: 'индекс',
  category: 'Цены', category_ru: 'Цены', current_value: 104.9, current_date: '2026-07-01',
  is_active: true, is_listed: true,
};
const BRENT = {
  code: 'brent', name: 'Нефть Brent', unit: '$/барр.',
  category: 'Товарные рынки', category_ru: 'Товарные рынки', current_value: 65.4,
  current_date: '2026-08-26', change: -1.2, is_active: true, is_listed: true,
};

const INDICATORS = [WAGES_NOMINAL, CPI_FOOD, CPI, KEY_RATE, UNEMPLOYMENT, BRENT];

describe('sortRussiaTiles', () => {
  it('ряды со значением идут первыми, внутри группы — по имени', () => {
    const noValueRow = { ...KEY_RATE, current_value: null, name: 'Ясно последний ряд' };
    const sorted = sortRussiaTiles([noValueRow, CPI_FOOD, CPI, UNEMPLOYMENT, BRENT]);
    // Ряд без значения — в самом конце; внутри группы с значениями — по имени.
    expect(sorted[sorted.length - 1].code).toBe('key-rate');
    const names = sorted.slice(0, -1).map((i) => i.name);
    const sortedNames = [...names].sort((a, b) => a.localeCompare(b, 'ru'));
    expect(names).toEqual(sortedNames);
  });

  it('не мутирует входной список', () => {
    const input = [WAGES_NOMINAL, CPI];
    const snapshot = [...input];
    sortRussiaTiles(input);
    expect(input).toEqual(snapshot);
  });
});

describe('groupRussiaCategories', () => {
  it('группирует по apiCategory в порядке CATEGORIES, считает плитки', () => {
    const grouped = groupRussiaCategories(INDICATORS, CATEGORIES);
    const labor = grouped.find((g) => g.category.slug === 'labor');
    const prices = grouped.find((g) => g.category.slug === 'prices');
    // Внутри секции — сортировка по имени (Средняя… < Уровень… в ru-коллаторе).
    expect(labor.indicators.map((i) => i.code)).toEqual(['wages-nominal', 'unemployment']);
    expect(labor.count).toBe(2);
    expect(prices.indicators.map((i) => i.code)).toEqual(['cpi', 'cpi-food']);
  });

  it('категории без рядов пропускаются', () => {
    const grouped = groupRussiaCategories(INDICATORS, CATEGORIES);
    expect(grouped.some((g) => g.category.slug === 'science')).toBe(false);
  });

  it('не listed ряды не попадают в группировку', () => {
    const grouped = groupRussiaCategories(
      [{ ...CPI, is_listed: false }, KEY_RATE],
      CATEGORIES,
    );
    expect(grouped.map((g) => g.category.slug)).toEqual(['rates']);
  });
});

describe('russiaIndicatorDisplay', () => {
  it('hero-ряд: значение и единица из hero', () => {
    expect(russiaIndicatorDisplay({
      code: 'ipi', hero_value: 1.2, hero_unit: '%', current_value: 105.3, unit: 'индекс',
    })).toEqual({ value: 1.2, unit: '%', isHero: true });
  });

  it('сырой ИПЦ без hero — минус 100, единица ряда', () => {
    expect(russiaIndicatorDisplay(CPI)).toEqual({ value: 5.4, unit: 'индекс', isHero: false });
  });

  it('обычный ряд — уровень и единица', () => {
    expect(russiaIndicatorDisplay(KEY_RATE)).toEqual({ value: 17, unit: '%', isHero: false });
  });

  it('ряд без значения — null', () => {
    expect(russiaIndicatorDisplay({ ...KEY_RATE, current_value: null })).toBeNull();
  });
});

describe('russiaIndicatorChange', () => {
  it('hero-ряд — hero_change, обычный — дельта уровня', () => {
    expect(russiaIndicatorChange({ hero_value: 1.2, hero_change: 0.2, change: 0.9 })).toBe(0.2);
    expect(russiaIndicatorChange({ change: -1.2 })).toBe(-1.2);
  });

  it('нулевое и отсутствующее изменение — null', () => {
    expect(russiaIndicatorChange({ change: 0 })).toBeNull();
    expect(russiaIndicatorChange({})).toBeNull();
  });
});

describe('russiaOverviewChips', () => {
  it('три якорных чипа: ИПЦ (минус 100), ключевая ставка, безработица', () => {
    const chips = russiaOverviewChips(INDICATORS);
    expect(chips.map((c) => c.code)).toEqual(['cpi', 'key-rate', 'unemployment']);
    expect(chips[0].value).toBeCloseTo(5.4);
    expect(chips[1].value).toBe(17);
    expect(chips[2].value).toBe(2.3);
  });

  it('отсутствующий ряд пропускается, но остальные чипы рендерятся', () => {
    const chips = russiaOverviewChips(INDICATORS.filter((i) => i.code !== 'key-rate'));
    expect(chips.map((c) => c.code)).toEqual(['cpi', 'unemployment']);
  });

  it('ряд без значения чип не образует', () => {
    const chips = russiaOverviewChips([{ ...UNEMPLOYMENT, current_value: null }]);
    expect(chips).toEqual([]);
  });
});
