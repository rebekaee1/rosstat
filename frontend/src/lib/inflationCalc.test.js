import { describe, expect, it } from 'vitest';
import {
  annualYoyFromIndexPoints,
  buildWorldResult,
  computeFromAnnualYoy,
  defaultCountrySlug,
  formatCalcAmount,
  inflationCountriesFromCatalog,
  normalizePeriod,
  RUSSIA_SLUG,
  US_SLUG,
} from './inflationCalc';

describe('annualYoyFromIndexPoints', () => {
  it('берёт последнюю точку года и считает I_t / I_{t-1}', () => {
    const yoy = annualYoyFromIndexPoints([
      { date: '2018-06-01', value: 99 },
      { date: '2018-12-01', value: 100 },
      { date: '2019-12-01', value: 102 },
      { date: '2020-12-01', value: 106.08 },
    ]);
    expect(yoy).toHaveLength(2);
    expect(yoy[0].year).toBe(2019);
    expect(yoy[0].value).toBeCloseTo(2);
    expect(yoy[1].year).toBe(2020);
    expect(yoy[1].value).toBeCloseTo(4);
  });
});

describe('computeFromAnnualYoy', () => {
  const points = [
    { date: '2019-12-01', year: 2019, value: 2 },
    { date: '2020-12-01', year: 2020, value: 4 },
    { date: '2021-12-01', year: 2021, value: 5 },
  ];

  it('множитель — произведение (1 + yoy/100) по годам периода', () => {
    const out = computeFromAnnualYoy(points, 2019, 2021, 100000);
    expect(out.product).toBeCloseTo(1.02 * 1.04 * 1.05);
    expect(out.clamped).toBe(false);
    expect(out.breakdown).toHaveLength(3);
    expect(out.breakdown[2].equivalent).toBe(Math.round(100000 * 1.02 * 1.04 * 1.05));
  });

  it('короткий ряд клэмпит период и не экстраполирует', () => {
    const out = computeFromAnnualYoy(points, 2010, 2025, 100000);
    expect(out.clamped).toBe(true);
    expect(out.effectiveFrom).toBe(2019);
    expect(out.effectiveTo).toBe(2021);
    expect(out.minYear).toBe(2019);
    expect(out.product).toBeCloseTo(1.02 * 1.04 * 1.05);
  });
});

describe('buildWorldResult', () => {
  it('считает обесценивание по индексу и помечает короткий ряд', () => {
    const result = buildWorldResult({
      amount: 100000,
      fromYear: 2010,
      toYear: 2020,
      indexPoints: [
        { date: '2018-12-01', value: 100 },
        { date: '2019-12-01', value: 102 },
        { date: '2020-12-01', value: 106.08 },
      ],
    });
    expect(result.kind).toBe('world');
    expect(result.hasCategories).toBe(false);
    expect(result.clamped).toBe(true);
    expect(result.seriesStartYear).toBe(2018);
    expect(result.effectiveFrom).toBe(2019);
    expect(result.effectiveTo).toBe(2020);
    expect(result.multiplier).toBeCloseTo(1.02 * 1.04);
    expect(result.equivalent).toBe(Math.round(100000 * 1.02 * 1.04));
  });
});

describe('inflationCountriesFromCatalog', () => {
  it('берёт только hicp-index и не хардкодит список', () => {
    const countries = inflationCountriesFromCatalog({
      items: [
        {
          country_slug: 'germany',
          country_name: 'Германия',
          concept_slug: 'hicp-index',
          indicator_code: 'de-hicp',
        },
        {
          country_slug: 'france',
          country_name: 'Франция',
          concept_slug: 'unemployment-rate',
          indicator_code: 'fr-une',
        },
        {
          country_slug: RUSSIA_SLUG,
          country_name: 'Россия',
          concept_slug: 'hicp-index',
          indicator_code: 'ru-hicp',
        },
      ],
    });
    expect(countries.map((c) => c.slug)).toEqual(['germany']);
    expect(countries[0].name).toBe('Германия');
  });
});

describe('formatCalcAmount', () => {
  it('для России добавляет рубль, для мира — нет', () => {
    expect(formatCalcAmount(100000, { withRuble: true })).toMatch(/₽/);
    expect(formatCalcAmount(100000, { withRuble: false })).not.toMatch(/₽/);
  });
});

describe('defaultCountrySlug', () => {
  it('EN-витрина по умолчанию считает США, русская — Россию', () => {
    expect(defaultCountrySlug('en')).toBe(US_SLUG);
    expect(defaultCountrySlug('en')).toBe('united-states');
    expect(defaultCountrySlug('ru')).toBe(RUSSIA_SLUG);
  });
});

describe('normalizePeriod', () => {
  it('переставляет перепутанные границы URL (from > to)', () => {
    expect(normalizePeriod(2020, 2010, 1991, 2026)).toEqual({ from: 2010, to: 2020 });
  });

  it('клэмпит период к доступному диапазону данных', () => {
    expect(normalizePeriod(1980, 2100, 1991, 2026)).toEqual({ from: 1991, to: 2026 });
  });

  it('валидный период не меняет', () => {
    expect(normalizePeriod(2000, 2015, 1991, 2026)).toEqual({ from: 2000, to: 2015 });
  });

  it('однолетний период сохраняется, а не схлопывается до перестановки', () => {
    expect(normalizePeriod(2020, 2020, 1991, 2026)).toEqual({ from: 2020, to: 2020 });
  });
});
