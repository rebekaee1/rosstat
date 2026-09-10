import { describe, expect, it } from 'vitest';
import {
  codeMatchesTargets,
  damerauLevenshtein,
  expandSearchQuery,
  filterSearchIndicators,
  normalizeSearchQuery,
  resolveSynonymTargets,
} from './searchSynonyms';

const CATALOG = [
  { code: 'cpi', name: 'Индекс потребительских цен', name_en: 'Consumer price index', category: 'Цены', seo_keywords: 'инфляция, рост цен' },
  { code: 'cpi-food', name: 'Продовольственные товары', name_en: 'CPI food', category: 'Цены' },
  { code: 'inflation-annual', name: 'Годовая инфляция', name_en: 'Annual inflation', category: 'Цены' },
  { code: 'fuel-ai95', name: 'АИ-95', name_en: 'AI-95', category: 'Цены' },
  { code: 'fuel-ai92', name: 'АИ-92', name_en: 'AI-92', category: 'Цены' },
  { code: 'fuel-diesel', name: 'Дизельное топливо', name_en: 'Diesel', category: 'Цены' },
  { code: 'unemployment', name: 'Уровень незанятости', name_en: 'Jobless rate', category: 'Труд' },
  { code: 'wages-nominal', name: 'Средняя оплата труда', name_en: 'Average wage', category: 'Труд' },
  { code: 'brent', name: 'Нефть марки Brent', name_en: 'Brent crude', category: 'Сырьё' },
  { code: 'gold-price', name: 'Учётная цена золота', name_en: 'Gold price', category: 'Сырьё' },
  { code: 'btc-usd', name: 'Курс BTC', name_en: 'Bitcoin', category: 'Крипто' },
  { code: 'key-rate', name: 'Ставка Банка России', name_en: 'Bank of Russia rate', category: 'Деньги' },
  { code: 'mortgage-rate', name: 'Средневзвешенная жилищная ставка', name_en: 'Housing loan rate', category: 'Деньги' },
  { code: 'usd-rub', name: 'Пара USD/RUB', name_en: 'USD RUB', category: 'Валюты' },
  { code: 'gdp-real', name: 'Реальный выпуск', name_en: 'Real output', category: 'Нацсчета' },
  { code: 'gdp-per-capita-usd', name: 'Выпуск на человека, $', name_en: 'Output per person', category: 'Нацсчета', concept_slug: 'gdp-per-capita-usd' },
  { code: 'pensioners', name: 'Численность получателей', name_en: 'Recipients', category: 'Социум' },
  { code: 'natural-gas', name: 'Henry Hub', name_en: 'Henry Hub', category: 'Сырьё' },
  { code: 'noise', name: 'Магазин розничных продаж', name_en: 'Store turnover', category: 'Торговля' },
  { code: 'budget-deficit', name: 'Дефицит федерального бюджета', name_en: 'Budget deficit', category: 'Бюджет' },
  { code: 'government-debt-gdp', name: 'Долг сектора госуправления к ВВП', name_en: 'General government debt', category: 'Бюджет', concept_slug: 'government-debt-gdp' },
];

function codes(query) {
  return filterSearchIndicators(CATALOG, query).map((ind) => ind.code);
}

describe('normalizeSearchQuery', () => {
  it('lowercases, maps ё→е, trim и схлопывает пробелы', () => {
    expect(normalizeSearchQuery('  ИПЦ  ')).toBe('ипц');
    expect(normalizeSearchQuery('Жильё   ЦБ')).toBe('жилье цб');
    expect(normalizeSearchQuery('Oil')).toBe('oil');
  });
});

describe('damerauLevenshtein', () => {
  it('считает замену, вставку и соседнюю транспозицию как 1', () => {
    expect(damerauLevenshtein('инфляция', 'инфляцая')).toBe(1);
    expect(damerauLevenshtein('brent', 'bernt')).toBe(1);
    expect(damerauLevenshtein('инфляция', 'инфляция')).toBe(0);
    expect(damerauLevenshtein('инфляция', 'дефляция')).toBeGreaterThan(1);
  });
});

describe('resolveSynonymTargets', () => {
  it('раскрывает русские и английские ключи', () => {
    expect(resolveSynonymTargets('ИПЦ')).toContain('cpi');
    expect(resolveSynonymTargets('oil')).toContain('brent');
    expect(resolveSynonymTargets('ставка цб')).toContain('key-rate');
    expect(resolveSynonymTargets('ввп на душу')).toEqual(
      expect.arrayContaining(['gdp-per-capita', 'gdp-per-capita-usd']),
    );
  });

  it('не цепляет «газ» внутри «магазин»', () => {
    expect(resolveSynonymTargets('магазин')).not.toContain('natural-gas');
  });
});

describe('filterSearchIndicators', () => {
  it('«ипц» находит инфляцию', () => {
    const found = codes('ипц');
    expect(found).toContain('cpi');
    expect(found).toContain('cpi-food');
    expect(found).toContain('inflation-annual');
  });

  it('«бензин» находит топливо', () => {
    const found = codes('бензин');
    expect(found).toEqual(expect.arrayContaining(['fuel-ai95', 'fuel-ai92', 'fuel-diesel']));
  });

  it('«безработица» находит unemployment', () => {
    expect(codes('безработица')).toContain('unemployment');
  });

  it('опечатка «инфляцая» находит инфляцию', () => {
    expect(codes('инфляцая')).toContain('cpi');
  });

  it('английский «oil» находит brent', () => {
    expect(codes('oil')).toEqual(['brent']);
  });

  it('русский запрос находит по name_en, английский — по name', () => {
    expect(codes('bitcoin')).toContain('btc-usd');
    expect(codes('учётная')).toContain('gold-price');
  });

  it('ставит точные совпадения раньше синонимов и fuzzy', () => {
    const ranked = codes('инфляция');
    expect(ranked[0]).toBe('cpi');
    expect(ranked.indexOf('cpi')).toBeLessThan(ranked.indexOf('cpi-food'));
  });

  it('не дублирует один код в разных слоях', () => {
    const found = codes('cpi');
    expect(found.filter((c) => c === 'cpi')).toHaveLength(1);
  });

  it('«магазин» не приводит к natural-gas через ложный «газ»', () => {
    expect(codes('магазин')).not.toContain('natural-gas');
  });

  it('пустой запрос не вываливает каталог', () => {
    expect(filterSearchIndicators(CATALOG, '')).toEqual([]);
    expect(filterSearchIndicators(CATALOG, '   ')).toEqual([]);
  });

  it('«госдолг» находит бюджет и долг', () => {
    const found = codes('госдолг');
    expect(found).toEqual(expect.arrayContaining(['budget-deficit', 'government-debt-gdp']));
  });
});

describe('codeMatchesTargets / expandSearchQuery', () => {
  it('префикс cpi ловит семейство, но не чужой код', () => {
    expect(codeMatchesTargets('cpi-food', ['cpi'])).toBe(true);
    expect(codeMatchesTargets('noise', ['cpi'])).toBe(false);
  });

  it('короткий синоним раскрывается в латинский код для world-search', () => {
    expect(expandSearchQuery('ипц')).toBe('cpi');
    expect(expandSearchQuery('oil')).toBe('brent');
    expect(expandSearchQuery('что угодно')).toBe('что угодно');
  });
});

describe('intent ranking with noisy metadata and hidden siblings', () => {
  const noisy = [
    { code: 'fuel-yoy', name: 'Бензин', category: 'Инфляция', is_listed: false },
    { code: 'gold-reserves', name: 'Резервы', seo_keywords: 'gold золото' },
    { code: 'cpi-food-yoy', name: 'Продукты', category: 'Инфляция', is_listed: false },
    { code: 'cpi', name: 'Индекс потребительских цен', category: 'Цены' },
    { code: 'gold-price', name: 'Учётная цена золота', name_en: 'Gold price' },
  ];
  it('puts CPI before category-only inflation matches without dropping any match', () => {
    const found = filterSearchIndicators(noisy, 'инфляция', { limit: 0 }).map(x => x.code);
    expect(found[0]).toBe('cpi');
    expect(new Set(found)).toEqual(new Set(['fuel-yoy', 'cpi-food-yoy', 'cpi']));
  });
  it('puts gold price before gold in reserve metadata', () => {
    expect(filterSearchIndicators(noisy, 'gold')[0].code).toBe('gold-price');
  });
  it('keeps a hidden sibling directly accessible by exact code', () => {
    expect(filterSearchIndicators(noisy, 'cpi-food-yoy')[0].code).toBe('cpi-food-yoy');
  });
  it('exact name beats a broad canonical synonym', () => {
    const found = filterSearchIndicators([...noisy, { code: 'specific', name: 'Инфляция' }], 'инфляция');
    expect(found[0].code).toBe('specific');
  });
  it('retains the full matching catalogue when explicitly unlimited', () => {
    const many = Array.from({ length: 700 }, (_, i) => ({ code: `item-${i}`, category: 'Инфляция' }));
    expect(filterSearchIndicators([...many, noisy[3]], 'инфляция', { limit: 0 })).toHaveLength(701);
  });
});
