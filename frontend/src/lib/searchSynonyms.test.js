import { describe, expect, it } from 'vitest';
import {
  codeMatchesTargets,
  damerauLevenshtein,
  expandSearchQuery,
  filterSearchIndicators,
  filterSearchOptions,
  correctSearchKeyboardLayout,
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
  { code: 'ipi', name: 'Индекс промышленного производства', name_en: 'Industrial production', category: 'Бизнес' },
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

describe('shared scoped ranking and required qualifiers', () => {
  const scoped = [
    { code: 'cpi', name: 'Индекс потребительских цен', country_slug: 'russia', frequency: 'monthly' },
    { code: 'de-cpi', name: 'Индекс потребительских цен', country_slug: 'germany', frequency: 'monthly' },
    { code: 'us-cpi', name: 'Consumer Price Index', country_slug: 'united-states', frequency: 'monthly' },
    { code: 'wages-nominal', name: 'Средняя заработная плата', country_slug: 'russia' },
    { code: 'minimum-wage', name: 'Минимальный размер оплаты труда', country_slug: 'russia' },
    { code: 'deposit-rate-avg-quarter', name: 'Ставка по вкладам', country_slug: 'russia', frequency: 'quarterly' },
    { code: 'key-rate', name: 'Ключевая ставка', country_slug: 'russia', frequency: 'daily' },
  ];

  it('retains the country qualifier after resolving an economic alias', () => {
    expect(filterSearchOptions(scoped, 'инфляция Германия').map((item) => item.code)).toEqual(['de-cpi']);
    expect(filterSearchOptions(scoped, 'cpi USA').map((item) => item.code)).toEqual(['us-cpi']);
    expect(filterSearchOptions(scoped, 'инфляция Марс')).toEqual([]);
  });

  it('keeps frequency and deposit qualifiers instead of selecting the key rate', () => {
    expect(filterSearchOptions(scoped, 'средняя ставка по вкладам по кварталам').map((item) => item.code))
      .toEqual(['deposit-rate-avg-quarter']);
    expect(filterSearchOptions(scoped, 'ставка по вкладам ежедневно')).toEqual([]);
  });

  it.each(['МРОТ', 'минимальная зарплата', 'minimum wage'])('does not substitute average pay for %s', (q) => {
    expect(filterSearchOptions(scoped, q).map((item) => item.code)).toEqual(['minimum-wage']);
    expect(filterSearchOptions(scoped.filter((item) => item.code !== 'minimum-wage'), q)).toEqual([]);
  });

  it('corrects layout only after literal matching fails', () => {
    expect(correctSearchKeyboardLayout('byakzwbz')).toBe('инфляция');
    expect(filterSearchOptions(scoped, 'byakzwbz')[0].code).toBe('cpi');
    const literal = { code: 'byakzwbz', name: 'Source identifier' };
    expect(filterSearchOptions([literal, ...scoped], 'byakzwbz')).toEqual([literal]);
  });

  it('corrects keyboard punctuation before tokenization within the eligible pool', () => {
    const bread = { code: 'bread', name: 'Производство хлебных изделий', frequency: 'annual', country_slug: 'russia' };
    const wages = { code: 'wages', name: 'Средняя зарплата', frequency: 'annual', country_slug: 'russia' };
    expect(correctSearchKeyboardLayout('[kt,ys[')).toBe('хлебных');
    expect(filterSearchOptions([bread, wages], '[kt,ys[')).toEqual([bread]);
    expect(filterSearchOptions([wages], '[kt,ys[')).toEqual([]);
    expect(filterSearchOptions([bread], '[kt,ys[ vtczwfv')).toEqual([]);
    expect(filterSearchOptions([bread], '[kt,ys[ %')).toEqual([]);
    const literal = { code: '[kt,ys[', name: 'Literal identifier' };
    expect(filterSearchOptions([literal, bread], '[kt,ys[')).toEqual([literal]);
    expect(filterSearchOptions([bread], '[]')).toEqual([]);
  });

  it('accepts an unfinished letter only for a long literal native title prefix', () => {
    const roads = { code: 'road-density', name: 'Плотность автомобильных дорог общего пользования с твердым покрытием', country_slug: 'russia', frequency: 'annual', unit: 'км на 1000 км²' };
    const railway = { code: 'rail-density', name: 'Плотность железных дорог общего пользования', country_slug: 'russia', frequency: 'annual', unit: 'км на 1000 км²' };
    const q = 'Плотность автомобильных дорог общего пользования с твердым п';
    expect(filterSearchOptions([roads, railway], q)).toEqual([roads]);
    expect(filterSearchOptions([railway], q)).toEqual([]);
    expect(filterSearchOptions([roads], `${q} %`)).toEqual([]);
    expect(filterSearchOptions([roads], `${q} Германия`)).toEqual([]);
    expect(filterSearchOptions([roads], `${q} monthly`)).toEqual([]);
    expect(filterSearchOptions([roads], 'Плотность а')).toEqual([]);
  });

  it('matches count vocabulary and bounded Russian inflection without dropping the subject', () => {
    const students = { code: 'students', name: 'Численность студентов' };
    const roads = { code: 'roads', name: 'Протяженность автомобильных дорог' };
    expect(filterSearchOptions([students, roads], 'количество студентов')).toEqual([students]);
    expect(filterSearchOptions([students, roads], 'дороги')).toEqual([roads]);
    expect(filterSearchOptions([students, roads], 'численность дорог')).toEqual([]);
  });

  it('retains all options and original object identity without inventing a result cap', () => {
    const items = Array.from({ length: 701 }, (_unused, i) => ({ value: String(i), label: `Запас топлива ${i}` }));
    expect(filterSearchOptions(items, '')).toBe(items);
    expect(filterSearchOptions(items, 'топлива')).toHaveLength(701);
    expect(filterSearchOptions(items, 'топлива')[0]).toBe(items[0]);
    expect(filterSearchOptions(items, 'топлива', { limit: 25 })).toHaveLength(25);
  });

  it('uses actual country/region identity for convenience aliases', () => {
    const spb = { value: 'sankt-peterburg', label: 'г. Санкт-Петербург' };
    const metric = { value: 'housing', label: 'Стоимость жилья в Санкт-Петербурге' };
    expect(filterSearchOptions([spb], 'СПб', { searchKind: 'region' })).toEqual([spb]);
    expect(filterSearchOptions([metric], 'СПб')).toEqual([]);
    expect(filterSearchOptions([spb], 'СПб Москва', { searchKind: 'region' })).toEqual([]);
  });

  it('preserves literal numeric percentages and actual percentage units', () => {
    const items = [
      { code: 'base-1000', name: 'Индекс базовый 1000', unit: '%' },
      { code: 'base-100', name: 'Индекс базовый 100', unit: 'баллы' },
      { code: 'percent-100', name: 'Индекс базовый 100 %', unit: '%' },
      { code: 'cpi', name: 'Инфляция', unit: '%', country_slug: 'russia' },
      { code: 'gdp', name: 'Валовой выпуск', unit: 'рубли', country_slug: 'russia' },
    ];
    expect(filterSearchOptions(items, '100%')).toEqual([items[2]]);
    expect(filterSearchOptions(items, 'инфляция %')).toEqual([items[3]]);
    expect(filterSearchOptions(items, 'ВВП %')).toEqual([]);
    expect(filterSearchOptions(items, '100% Germany')).toEqual([]);
  });

  it('does not discard a meaningful residual token after a longest intent phrase', () => {
    const items = [
      { code: 'gdp-real', name: 'Реальный выпуск', country_slug: 'germany' },
      { code: 'gdp-per-capita-usd', name: 'Выпуск на человека', country_slug: 'germany' },
    ];
    expect(filterSearchOptions(items, 'ввп на душу Германии').map((item) => item.code)).toEqual(['gdp-per-capita-usd']);
    expect(filterSearchOptions(items, 'ввп на душу Германии женщины')).toEqual([]);
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

  it.each(['зарплата', 'зпл', 'з/п'])('«%s» находит зарплату', (query) => {
    expect(codes(query)).toContain('wages-nominal');
  });

  describe('поиск стали без подмены общими индексами', () => {
    const broadIndices = [
      CATALOG.find(ind => ind.code === 'ipi'),
      { code: 'ppi', name: 'Индекс цен производителей', name_en: 'Producer price index' },
      { code: 'ipi-manufacturing', name: 'Обрабатывающая промышленность', name_en: 'Manufacturing production' },
      { code: 'ppi-manufacturing', name: 'Цены производителей обрабатывающей промышленности' },
    ];
    const steel = { code: 'fixture-commodity-001', name: 'Сталь — объём производства', name_en: 'Crude steel production' };

    it.each(['steel', 'сталь', 'ste', 'стал', 'прокат', 'металл'])(
      '«%s» не выдаёт общие индексы, если профильного ряда нет', (query) => {
        expect(filterSearchIndicators(broadIndices, query)).toEqual([]);
        expect(resolveSynonymTargets(query)).toEqual([]);
      },
    );

    it.each(['steel', 'сталь', 'ste', 'стал', 'Crude steel production', 'Сталь — объём производства'])(
      '«%s» находит профильное название, включая частичное совпадение', (query) => {
        expect(filterSearchIndicators([...broadIndices, steel], query)).toEqual([steel]);
      },
    );

    it.each(['steel', 'сталь'])(
      '«%s» сохраняет точное совпадение имени без нерелевантных индексов', (query) => {
        const exact = { code: 'fixture-exact', name: query };
        expect(filterSearchIndicators([...broadIndices, steel, exact], query)).toEqual([exact, steel]);
      },
    );
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

  it.each(['steel', 'сталь', 'прокат', 'металл', 'steel production'])(
    'сохраняет исходный запрос «%s» для мирового поиска', (query) => {
      expect(expandSearchQuery(query)).toBe(query);
    },
  );

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

describe('measure synonyms reach rows without a federal code (2026-10-02)', () => {
  // Real dead end: a region page shows an «Инфляция» tile, yet the scoped search
  // for «инфляция» answered «не найдено» because regional CPI rows have their own codes.
  const regional = [
    { code: 'indeksy-potrebitelskih-tsen', name: 'Индексы потребительских цен' },
    { code: 'indeksy-potrebitelskih-tsen-na-uslugi', name: 'Индексы потребительских цен (тарифов) на услуги' },
    { code: 'indeksy-tsen-proizvoditeley', name: 'Индексы цен производителей промышленных товаров' },
    { code: 'srednyaya-zarplata', name: 'Среднемесячная заработная плата' },
  ];
  it.each(['инфляция', 'ипц', 'инфл'])('finds consumer price rows for «%s» and nothing else', (query) => {
    expect(filterSearchOptions(regional, query).map((item) => item.code)).toEqual([
      'indeksy-potrebitelskih-tsen', 'indeksy-potrebitelskih-tsen-na-uslugi',
    ]);
  });
  it('still requires every other word of the query', () => {
    expect(filterSearchOptions(regional, 'инфляция услуги').map((item) => item.code)).toEqual([
      'indeksy-potrebitelskih-tsen-na-uslugi',
    ]);
    expect(filterSearchOptions(regional, 'инфляция зарплата')).toEqual([]);
  });
});
