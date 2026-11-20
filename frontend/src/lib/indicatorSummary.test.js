import { describe, expect, it } from 'vitest';
import {
  bestGrowth,
  buildIndicatorSummary,
  isGrowthBaseReliable,
  isSeasonalLevel,
  splitHostCountryNote,
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

describe('круг наблюдателей «Туризм»: сезонные ряды, база роста, пометка принимающей страны', () => {
  const q = [
    { date: '2025-04-01', value: 100 }, { date: '2025-07-01', value: 150 },
    { date: '2026-01-01', value: 60 }, { date: '2026-04-01', value: 138 },
  ];

  it('сезонный квартальный ряд: sameYear считается с тем же кварталом прошлого года', () => {
    const s = buildIndicatorSummary({ points: q, frequency: 'quarterly', unit: 'тыс. поездок' });
    expect(s.seasonal).toBe(true);
    expect(s.sameYear.pct).toBeCloseTo(38, 5);
    expect(s.sameYear.from.date).toBe('2025-04-01');
  });

  it('нет точки год назад: sameYear пуст, а не берётся ближайшая', () => {
    const s = buildIndicatorSummary({
      points: [{ date: '2025-01-01', value: 100 }, { date: '2026-04-01', value: 110 }], frequency: 'quarterly', unit: 'тыс. поездок',
    });
    expect(s.sameYear).toBeNull();
  });

  it('проценты и годовые ряды сезонными не считаются', () => {
    expect(isSeasonalLevel('rate', 'monthly')).toBe(false);
    expect(isSeasonalLevel('level', 'annual')).toBe(false);
    expect(isSeasonalLevel('level', 'monthly')).toBe(true);
  });

  it('isGrowthBaseReliable: почти ноль, рост свыше 1000 %, пропуск рядом с базой', () => {
    const mk = (f) => Array.from({ length: 41 }, (_, i) => ({
      date: `${2016 + Math.floor(i / 4)}-${String(1 + (i % 4) * 3).padStart(2, '0')}-01`, value: f(i),
    }));
    const flat = mk(() => 100);
    expect(isGrowthBaseReliable(flat, bestGrowth(flat), 'quarterly')).toBe(true);
    const nearZero = mk((i) => (i === 0 ? 1 : 100));
    expect(isGrowthBaseReliable(nearZero, bestGrowth(nearZero), 'quarterly')).toBe(false);
    const gap = flat.filter((_, i) => i !== 1);
    expect(isGrowthBaseReliable(gap, bestGrowth(gap), 'quarterly')).toBe(false);
    expect(isGrowthBaseReliable(flat, null, 'quarterly')).toBe(false);
  });

  it('splitHostCountryNote: обе формулировки, остальной текст остаётся', () => {
    expect(splitHostCountryNote('По данным принимающей страны. Число поездок.')).toEqual({ host: true, rest: 'Число поездок.' });
    expect(splitHostCountryNote('Host-country data. Trips.')).toEqual({ host: true, rest: 'Trips.' });
    expect(splitHostCountryNote('Число поездок.')).toEqual({ host: false, rest: 'Число поездок.' });
    expect(splitHostCountryNote(undefined)).toEqual({ host: false, rest: '' });
  });
});

describe('одна точность числа в шапке и плитках (правки 20 и 38)', () => {
  const series = (values) => values.map((value, i) => ({ date: `2025-${String(i + 1).padStart(2, '0')}-01`, value }));

  it('счётная единица: «тыс. поездок» по порядку величины точек, без «847,69»', () => {
    const s = buildIndicatorSummary({ points: series([812.4, 830.1, 847.69]), frequency: 'monthly', unit: 'тыс. поездок', dataDigits: 2 });
    expect(s.shown.text).toBe('848');
    expect(s.prevShown.text).toBe('830');
  });

  it('целые точки: без дроби', () => {
    const s = buildIndicatorSummary({ points: series([410, 420, 435]), frequency: 'monthly', unit: 'тыс. прибытий', dataDigits: 2 });
    expect(s.shown.text).toBe('435');
  });

  it('проценты, рубли, индексы не меняются', () => {
    const pct = buildIndicatorSummary({ points: series([61.25, 62.5, 63.75]), frequency: 'monthly', unit: '%', dataDigits: 2 });
    expect(pct.shown.text).toBe('63,75');
    const rub = buildIndicatorSummary({ points: series([812.4, 830.1, 847.69]), frequency: 'monthly', unit: 'руб.', dataDigits: 2 });
    expect(rub.shown.text).toBe('847,69');
    const idx = buildIndicatorSummary({ points: series([101.2, 102.4, 103.6]), frequency: 'monthly', unit: 'индекс', dataDigits: 1 });
    expect(idx.shown.digits).toBe(1);
  });
});
