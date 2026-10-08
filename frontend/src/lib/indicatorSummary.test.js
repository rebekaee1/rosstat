import { describe, expect, it } from 'vitest';
import {
  bestGrowth,
  formatPercentChange,
  formatTileValue,
  growthOverYears,
  isEstimateDate,
  rankAmongCountries,
  tidyDigits,
  isPercentChangeUnit,
  preferPercentUnit,
  unitKind,
  windowStats,
} from './indicatorSummary';

const yearly = (from, to, f) => Array.from({ length: to - from + 1 }, (_, i) => ({
  date: `${from + i}-01-01`,
  value: f(i),
}));

describe('unitKind', () => {
  it('отличает проценты, индексы и обычные величины', () => {
    expect(unitKind('%')).toBe('rate');
    expect(unitKind('на 1000 жителей')).toBe('rate');
    expect(unitKind('индекс 2015 = 100')).toBe('index');
    expect(unitKind('Index, 2015 = 100')).toBe('index');
    expect(unitKind('млрд $')).toBe('level');
    expect(unitKind('человек')).toBe('level');
  });

  it('изменения за год и к прошлому периоду всегда считаются темпом', () => {
    expect(unitKind('индекс', 'yoy')).toBe('rate');
    expect(unitKind('млрд $', 'step')).toBe('rate');
  });
});

describe('growthOverYears / bestGrowth', () => {
  it('считает рост за 10 лет по годовому ряду', () => {
    const points = yearly(2010, 2025, (i) => 100 + i * 10);
    const growth = growthOverYears(points, 10);
    expect(growth.from.date).toBe('2015-01-01');
    expect(growth.pct).toBeCloseTo(((250 / 150) - 1) * 100, 6);
  });

  it('берёт окно покороче, когда истории мало', () => {
    const points = yearly(2019, 2025, (i) => 10 + i);
    const growth = bestGrowth(points);
    expect(growth.years).toBe(5);
  });

  it('не выдумывает рост, если ряд начинается позже нужной даты', () => {
    expect(growthOverYears(yearly(2023, 2025, () => 5), 10)).toBeNull();
  });

  it('не считает рост от нуля или отрицательного значения', () => {
    const points = yearly(2010, 2025, (i) => (i === 5 ? 0 : 5));
    expect(growthOverYears(points, 10)).toBeNull();
  });
});

describe('windowStats', () => {
  it('даёт максимум, минимум и среднее за десять лет', () => {
    const points = yearly(2000, 2025, (i) => i);
    const stats = windowStats(points, 10);
    expect(stats.highest.value).toBe(25);
    expect(stats.lowest.value).toBe(15);
    expect(stats.average).toBeCloseTo(20, 6);
  });

  it('молчит, если точек меньше трёх', () => {
    expect(windowStats(yearly(2024, 2025, () => 1))).toBeNull();
  });
});

describe('isEstimateDate', () => {
  const now = new Date('2026-10-05T00:00:00Z');
  it('годовое значение за текущий год считается оценкой', () => {
    expect(isEstimateDate('2026-01-01', 'annual', now)).toBe(true);
    expect(isEstimateDate('2025-01-01', 'annual', now)).toBe(false);
  });
  it('месячное значение оценкой не считается, пока дата не в будущем', () => {
    expect(isEstimateDate('2026-10-01', 'monthly', now)).toBe(false);
    expect(isEstimateDate('2026-12-01', 'monthly', now)).toBe(true);
  });
});

describe('formatTileValue', () => {
  it('укрупняет миллиарды до триллионов', () => {
    const r = formatTileValue(30767.08, 'млрд $', { locale: 'ru' });
    expect(r.text).toBe('30,8');
    expect(r.unit).toBe('трлн $');
  });

  it('численность населения показывает в миллионах, без «,00»', () => {
    const r = formatTileValue(28076986, 'человек', { locale: 'ru' });
    expect(r.text).toBe('28,1');
    expect(r.unit).toBe('млн человек');
  });

  it('тысячи человек тоже укрупняет', () => {
    const r = formatTileValue(5200, 'тыс. человек', { locale: 'ru' });
    expect(r.text).toBe('5,2');
    expect(r.unit).toBe('млн человек');
  });

  it('по-английски триллионы и миллионы людей', () => {
    expect(formatTileValue(30767.08, 'billion $', { locale: 'en' })).toMatchObject({ text: '30.8', unit: 'trillion $' });
    expect(formatTileValue(28076986, 'people', { locale: 'en' })).toMatchObject({ text: '28.1', unit: 'million people' });
  });

  it('малые числа не трогает, а у тысяч убирает дробную часть', () => {
    expect(formatTileValue(2.3, '%', { dataDigits: 1, locale: 'ru' }).text).toBe('2,3');
    expect(formatTileValue(1469.05, '$', { dataDigits: 2, locale: 'ru' }).text).toMatch(/^1\s469,05$/);
  });

  it('пустое значение — тире', () => {
    expect(formatTileValue(null, '%').text).toBe('—');
  });
});

describe('formatPercentChange', () => {
  it('ставит знак и неразрывный пробел', () => {
    expect(formatPercentChange(5.04)).toBe('+5,0 %');
    expect(formatPercentChange(-1.26)).toBe('−1,3 %');
  });
  it('нулевое после округления изменение даёт null', () => {
    expect(formatPercentChange(0.02)).toBeNull();
    expect(formatPercentChange(null)).toBeNull();
  });
});

describe('tidyDigits', () => {
  it('знаков столько, сколько в данных ряда: шапка и таблица показывают одно и то же число', () => {
    expect(tidyDigits(12345, 0)).toBe(0);
    expect(tidyDigits(113.96, 2)).toBe(2);
    expect(tidyDigits(150.5, 1)).toBe(1);
    expect(tidyDigits(5.25, 2)).toBe(2);
    expect(tidyDigits(5.25, 5)).toBe(2);
  });
});

describe('rankAmongCountries', () => {
  const items = [
    { country_code: 'US', value: 30 },
    { country_code: 'CN', value: 20 },
    { country_code: 'DE', value: 5 },
    { country_code: 'FR', value: 4 },
  ];
  it('находит место своей страны', () => {
    expect(rankAmongCountries(items, 'DE', 5)).toEqual({ rank: 3, total: 4 });
  });
  it('встраивает страну, которой нет в снимке', () => {
    expect(rankAmongCountries(items, 'JP', 6)).toEqual({ rank: 3, total: 5 });
  });
  it('молчит, если стран мало', () => {
    expect(rankAmongCountries(items.slice(0, 2), 'US', 30)).toBeNull();
  });
});

describe('проценты изменения не считаются индексом (круг 8, D2)', () => {
  it('«изменение за год, %» уже темп', () => {
    expect(isPercentChangeUnit('изменение за год, %')).toBe(true);
    expect(isPercentChangeUnit('annual change, %')).toBe(true);
    expect(isPercentChangeUnit('индекс 2015=100')).toBe(false);
    expect(unitKind('изменение за год, %')).toBe('rate');
    expect(unitKind('индекс 2015=100')).toBe('index');
  });
  it('единица из описания показателя перебивает «индекс», пришедший с данными', () => {
    expect(preferPercentUnit('индекс 2015=100', 'изменение за год, %')).toBe('изменение за год, %');
    expect(preferPercentUnit('индекс 2015=100', 'индекс 2015=100')).toBe('индекс 2015=100');
    expect(preferPercentUnit('%', 'изменение за год, %')).toBe('%');
  });
});
