import { describe, expect, it } from 'vitest';
import { displayCategoryLabel } from './categories';
import { tidyVariantLabel, worldVariantsToPickerGroup } from './worldViewModes';
import { modeSummaryText } from '../components/viewModesContext';
import { buildIndicatorSummary } from './indicatorSummary';
import { suggestedCompareOptions } from './worldCompareSearch';
import { chartCaption } from './chartCaption';
import { localizeWorldUnit } from './worldApi';

describe('displayCategoryLabel', () => {
  it('доходность гособлигаций США показывает «Ставки», а не «Индексы»', () => {
    expect(displayCategoryLabel('ust-10y', 'Индексы')).toBe('Ставки');
    expect(displayCategoryLabel('ust-10y-avg-month', 'Индексы')).toBe('Ставки');
  });
  it('остальные показатели остаются как есть', () => {
    expect(displayCategoryLabel('imoex', 'Индексы')).toBe('Индексы');
    expect(displayCategoryLabel('cpi', 'Цены')).toBe('Цены');
  });
});

describe('tidyVariantLabel', () => {
  it('«Все возраста, % ЭАН» читается как «Все возрасты, % от рабочей силы»', () => {
    expect(tidyVariantLabel('Все возраста, % ЭАН')).toBe('Все возрасты, % от рабочей силы');
  });
  it('возрастные диапазоны с правильным склонением', () => {
    expect(tidyVariantLabel('25–74 лет, тыс. человек')).toBe('25–74 года, тыс. человек');
    expect(tidyVariantLabel('15-24 лет')).toBe('15–24 года');
    expect(tidyVariantLabel('Младше 25 лет')).toBe('Младше 25 лет');
  });
  it('английский текст не трогает', () => {
    expect(tidyVariantLabel('All ages, % of labour force', 'en')).toBe('All ages, % of labour force');
  });
  it('подписи срезов проходят через очистку', () => {
    const group = worldVariantsToPickerGroup(
      [{ code: 'a', label: 'Все возраста, % ЭАН' }, { code: 'b', label: 'Младше 25 лет, % ЭАН' }],
      'Что показать',
    );
    expect(group.codes.map((c) => c.label)).toEqual([
      'Все возрасты, % от рабочей силы',
      'Младше 25 лет, % от рабочей силы',
    ]);
  });
});

describe('modeSummaryText', () => {
  it('значения по умолчанию не удлиняют строку свёрнутой панели', () => {
    expect(modeSummaryText('Значения', 'по месяцам')).toBe('по месяцам');
    expect(modeSummaryText('Values', 'monthly')).toBe('monthly');
  });
  it('другие режимы остаются в строке', () => {
    expect(modeSummaryText('Год к году', 'по месяцам')).toBe('Год к году, по месяцам');
  });
});

describe('localizeWorldUnit', () => {
  it('промилле словами', () => {
    expect(localizeWorldUnit('промилле', 'ru')).toBe('на 1000 жителей');
    expect(localizeWorldUnit('‰', 'en')).toBe('per 1,000 people');
  });
  it('% ЭАН без аббревиатуры', () => {
    expect(localizeWorldUnit('% ЭАН', 'ru')).toBe('% от рабочей силы');
  });
});

describe('buildIndicatorSummary', () => {
  const gdp = [];
  for (let y = 2010; y <= 2026; y += 1) gdp.push({ date: `${y}-01-01`, value: 20000 + (y - 2010) * 700 });

  it('ВВП: оценка года, укрупнённое число и рост за десять лет вместо среднего', () => {
    const s = buildIndicatorSummary({
      points: gdp, frequency: 'annual', unit: 'млрд $', modeType: 'level', locale: 'ru', now: new Date('2026-10-05T00:00:00Z'),
    });
    expect(s.kind).toBe('level');
    expect(s.estimate).toBe(true);
    expect(s.shown.unit).toBe('трлн $');
    expect(s.shown.text).toBe('31,2');
    expect(s.prevShown.text).toBe('30,5');
    expect(s.growth.years).toBe(10);
    expect(s.stats).toBeNull();
  });

  it('процент: максимум и среднее есть, роста нет', () => {
    const pts = Array.from({ length: 24 }, (_, i) => ({
      date: `${2000 + i}-01-01`, value: 2 + (i % 5) * 0.5,
    }));
    const s = buildIndicatorSummary({
      points: pts, frequency: 'annual', unit: '%', modeType: 'level', dataDigits: 1, locale: 'ru', now: new Date('2026-10-05T00:00:00Z'),
    });
    expect(s.kind).toBe('rate');
    expect(s.growth).toBeNull();
    expect(s.stats.years).toBeGreaterThanOrEqual(9);
    expect(s.estimate).toBe(false);
  });

  it('численность: «28,1 млн человек» без «,00»', () => {
    const pts = [
      { date: '2025-01-01', value: 27730356 },
      { date: '2026-01-01', value: 28076986 },
    ];
    const s = buildIndicatorSummary({
      points: pts, frequency: 'annual', unit: 'человек', modeType: 'level', locale: 'ru', now: new Date('2026-10-05T00:00:00Z'),
    });
    expect(s.shown.text).toBe('28,1');
    expect(s.shown.unit).toBe('млн человек');
    expect(s.changePct).toBeCloseTo(1.25, 1);
  });

  it('пустой ряд даёт null', () => {
    expect(buildIndicatorSummary({ points: [], frequency: 'annual', unit: '%' })).toBeNull();
  });
});

describe('suggestedCompareOptions', () => {
  const options = [
    { code: 'average', country_name: 'Среднее' },
    { code: 'a', country_name: 'Албания', country_slug: 'albania' },
    { code: 'b', country_name: 'Китай', country_slug: 'china' },
    { code: 'c', country_name: 'Япония', country_slug: 'japan' },
    { code: 'd', country_name: 'Германия', country_slug: 'germany' },
  ];
  it('популярные страны первыми, без «среднего»', () => {
    const names = suggestedCompareOptions(options, 'ru').map((o) => o.country_name);
    expect(names).toEqual(['Китай', 'Германия', 'Япония', 'Албания']);
  });
  it('предел по количеству', () => {
    expect(suggestedCompareOptions(options, 'ru', 2)).toHaveLength(2);
  });
});

describe('chartCaption', () => {
  const t = (key) => ({ 'w2.mode.level': 'Значения', 'w2.mode.yoy': 'Изменение за год' }[key] || key);
  it('говорит, что показано, а не повторяет название', () => {
    expect(chartCaption({ type: 'level' }, 'млрд $', t)).toBe('Значения, млрд $');
    expect(chartCaption({ type: 'yoy' }, '%', t)).toBe('Изменение за год, %');
    expect(chartCaption(null, '', t)).toBe('Значения');
  });
});
