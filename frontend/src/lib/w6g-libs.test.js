// Волна 6, зона G: чистая логика сравнения, курсов, калькуляторов и населения.
import { describe, expect, it } from 'vitest';
import { COMPARE_PRESETS, DEFAULT_COMPARE_PRESET, presetIsActive, presetParams } from './comparePresets';
import { compareLabels, conceptShortLabel, joinList, unitHint } from './compareTitle';
import { orderCountryOptions } from './countryOrder';
import { scalesDiffer } from './useCountryComparison';
import {
  buildEdges, convert, convertibleUnits, currencyWindows, formatConverted, pairTab, pairTitle,
  parseAmountInput, parsePair, rateBasis, sortByPopularity, normalizeRateNameEn,
} from './currencyRates';
import { COUNTRY_CURRENCY, currencyForCountry, currencyInPhrase, formatMoney } from './countryCurrency';
import {
  compactPeople, isPeopleUnit, peopleScale, placeOrdinal, populationRank, populationSummary,
  signedPeople, signedPercent,
} from './populationFacts';
import { MESSAGES } from '../i18n/messages';

// Слаги стран каталога (как в slugFlags.js): у каждой должна быть валюта.
const CATALOG_SLUGS = [
  'albania', 'armenia', 'australia', 'austria', 'azerbaijan', 'belgium', 'bosnia', 'brazil', 'bulgaria', 'canada',
  'china', 'croatia', 'cyprus', 'czechia', 'denmark', 'estonia', 'finland', 'france', 'georgia', 'germany', 'greece',
  'hungary', 'iceland', 'india', 'ireland', 'israel', 'italy', 'japan', 'kosovo', 'latvia', 'lithuania', 'luxembourg',
  'malta', 'mexico', 'moldova', 'montenegro', 'netherlands', 'new-zealand', 'north-macedonia', 'norway', 'poland',
  'portugal', 'romania', 'russia', 'serbia', 'slovakia', 'slovenia', 'south-africa', 'south-korea', 'spain', 'sweden',
  'switzerland', 'turkey', 'ukraine', 'united-kingdom', 'united-states',
];

const t = (key, fallback) => {
  const ru = MESSAGES.ru[key];
  return ru == null ? (fallback ?? key) : ru;
};

describe('готовые сравнения', () => {
  it('открываются парой «один показатель, две страны», по умолчанию ВВП США и Китая', () => {
    expect(DEFAULT_COMPARE_PRESET.codes).toEqual(['w:united-states:gdp-usd', 'w:china:gdp-usd']);
    for (const preset of COMPARE_PRESETS) {
      expect(preset.codes).toHaveLength(2);
      const concepts = new Set(preset.codes.map((code) => code.split(':')[2]));
      expect(concepts.size).toBe(1);
      expect(MESSAGES.ru[preset.labelKey]).toBeTruthy();
      expect(MESSAGES.en[preset.labelKey]).toBeTruthy();
    }
  });

  it('параметры адреса: codes и rep; чужие параметры сохраняются, легаси a/b убираются', () => {
    const inflation = COMPARE_PRESETS.find((p) => p.id === 'inflation');
    const params = presetParams(inflation, 'a=cpi&b=key-rate&preview_locale=en&rep=old:yoy');
    expect(params.get('codes')).toBe('w:germany:hicp-index,w:france:hicp-index');
    expect(params.get('rep')).toBe('w:germany:hicp-index:yoy,w:france:hicp-index:yoy');
    expect(params.get('preview_locale')).toBe('en');
    expect(params.has('a')).toBe(false);
    expect(params.has('b')).toBe(false);
    const gdp = presetParams(DEFAULT_COMPARE_PRESET, 'rep=x:yoy');
    expect(gdp.has('rep')).toBe(false);
  });

  it('набор считается активным независимо от порядка', () => {
    expect(presetIsActive(DEFAULT_COMPARE_PRESET, ['w:china:gdp-usd', 'w:united-states:gdp-usd'])).toBe(true);
    expect(presetIsActive(DEFAULT_COMPARE_PRESET, ['w:china:gdp-usd'])).toBe(false);
  });
});

describe('заголовок и подписи линий сравнения', () => {
  const world = (country, slug, concept) => ({
    isWorld: true,
    name: `${concept} — ${country}`,
    ind: { conceptSlug: slug, conceptName: concept, countryName: country },
  });

  it('один показатель, две страны: «Безработица: Германия и Франция», линии подписаны странами', () => {
    const result = compareLabels([
      world('Германия', 'unemployment-rate', 'Уровень безработицы'),
      world('Франция', 'unemployment-rate', 'Уровень безработицы'),
    ], { t, locale: 'ru' });
    expect(result.headline).toBe('Безработица: Германия и Франция');
    expect(result.labels).toEqual(['Германия', 'Франция']);
  });

  it('одна страна, два показателя: заголовок по стране, линии по показателям', () => {
    const result = compareLabels([
      world('США', 'gdp-usd', 'Валовой внутренний продукт'),
      world('США', 'population', 'Численность населения'),
    ], { t, locale: 'ru' });
    expect(result.headline).toBe('США: ВВП, текущие цены и Население');
    expect(result.labels).toEqual(['ВВП, текущие цены', 'Население']);
  });

  it('российские ряды: названия через «и», без повторов «—»', () => {
    const result = compareLabels([
      { name: 'Ключевая ставка', isWorld: false, ind: {} },
      { name: 'Инфляция', isWorld: false, ind: {} },
    ], { t, locale: 'ru' });
    expect(result.headline).toBe('Ключевая ставка и Инфляция');
  });

  it('EN: список через «and»; один ряд: «Показатель: страна»', () => {
    expect(joinList(['Germany', 'France', 'Italy'], 'en')).toBe('Germany, France, and Italy');
    const one = compareLabels([world('Germany', 'population', 'Population')], {
      t: (key, fallback) => MESSAGES.en[key] ?? fallback ?? key, locale: 'en',
    });
    expect(one.headline).toBe('Population: Germany');
  });

  it('короткое название берётся из словаря, иначе из каталога', () => {
    expect(conceptShortLabel('gdp-usd', 'Валовой внутренний продукт в текущих ценах', t)).toBe('ВВП, текущие цены');
    expect(conceptShortLabel('us-unemployment-rate', 'Уровень безработицы', t)).toBe('Уровень безработицы');
  });

  it('пустой набор не ломается', () => {
    expect(compareLabels([], { t, fallback: 'Показатель' })).toEqual({ headline: 'Показатель', labels: [] });
  });
});

describe('порядок стран и разные масштабы', () => {
  it('Россия, США, Китай, Германия, Индия — затем по алфавиту; «average» первым', () => {
    const options = [
      { code: 'a', country_slug: 'albania' },
      { code: 'in', country_slug: 'india' },
      { code: 'avg', code2: 1, country_slug: undefined },
      { code: 'average' },
      { code: 'de', country_slug: 'germany' },
      { code: 'zz', country_slug: 'zimbabwe' },
      { code: 'ru', country_slug: 'russia' },
      { code: 'cn', country_slug: 'china' },
      { code: 'us', country_slug: 'united-states' },
    ];
    const ordered = orderCountryOptions(options).map((o) => o.code);
    expect(ordered.slice(0, 6)).toEqual(['average', 'ru', 'us', 'cn', 'de', 'in']);
    expect(ordered.slice(6)).toEqual(['a', 'avg', 'zz']);
  });

  it('масштабы различаются больше чем вдвое: нужен совет «показать в процентах»', () => {
    const base = [{ value: 28_000_000 }];
    expect(scalesDiffer(base, [{ data: [{ value: 9_000_000 }] }])).toBe(true);
    expect(scalesDiffer(base, [{ data: [{ value: 20_000_000 }] }])).toBe(false);
    expect(scalesDiffer(base, [])).toBe(false);
    expect(scalesDiffer([], [{ data: [{ value: 3 }] }])).toBe(false);
  });
});

describe('курсы валют: названия, вкладки, конвертер', () => {
  it('пары разбираются, производные ряды нет', () => {
    expect(parsePair('usd-rub')).toEqual({ base: 'USD', quote: 'RUB' });
    expect(parsePair('btc-usd')).toEqual({ base: 'BTC', quote: 'USD' });
    expect(parsePair('usd-rub-eop-month')).toBeNull();
    expect(parsePair('brent')).toBeNull();
  });

  it('названия понятные, без кодов: «Доллар США к рублю», «Биткоин в долларах США»', () => {
    expect(pairTitle('usd-rub', 'ru')).toBe('Доллар США к рублю');
    expect(pairTitle('eur-usd', 'ru')).toBe('Евро к доллару США');
    expect(pairTitle('btc-usd', 'ru')).toBe('Биткоин в долларах США');
    expect(pairTitle('usd-rub', 'en')).toBe('US dollar to ruble');
    expect(pairTitle('btc-usd', 'en')).toBe('Bitcoin in US dollars');
    expect(pairTitle('mystery', 'ru', 'Как есть')).toBe('Как есть');
  });

  it('вкладки: рубль, крипто, мир; порядок по популярности', () => {
    expect(['usd-rub', 'btc-usd', 'eur-usd', 'x-y'].map(pairTab)).toEqual(['rub', 'crypto', 'world', 'world']);
    const sorted = sortByPopularity([{ code: 'sol-usd' }, { code: 'zzz' }, { code: 'usd-rub' }, { code: 'btc-usd' }]);
    expect(sorted.map((i) => i.code)).toEqual(['usd-rub', 'btc-usd', 'sol-usd', 'zzz']);
  });

  it('откуда число: ЦБ, ЕЦБ или закрытие дня', () => {
    expect(rateBasis('usd-rub')).toBe('cb');
    expect(rateBasis('eur-usd')).toBe('ecb');
    expect(rateBasis('btc-usd')).toBe('close');
    expect(rateBasis('brent')).toBeNull();
  });

  const items = [
    { code: 'usd-rub', current_value: 80, current_date: '2026-10-03', is_active: true },
    { code: 'eur-rub', current_value: 100, current_date: '2026-10-03', is_active: true },
    { code: 'btc-usd', current_value: 60000, current_date: '2026-10-05', is_active: true },
    { code: 'gbp-usd', current_value: 0, current_date: '2026-10-05', is_active: true },
  ];

  it('конвертер: прямой, обратный курс и цепочка через несколько пар', () => {
    const edges = buildEdges(items);
    expect(edges.map((e) => e.code)).toEqual(['usd-rub', 'eur-rub', 'btc-usd']);
    expect(convert(100, 'USD', 'RUB', edges).value).toBeCloseTo(8000);
    expect(convert(8000, 'RUB', 'USD', edges).value).toBeCloseTo(100);
    const chain = convert(0.5, 'BTC', 'RUB', edges);
    expect(chain.value).toBeCloseTo(0.5 * 60000 * 80);
    expect(chain.path).toEqual(['btc-usd', 'usd-rub']);
    expect(chain.date).toBe('2026-10-03');
    expect(convert(1, 'EUR', 'USD', edges).value).toBeCloseTo(100 / 80);
    expect(convert(5, 'USD', 'USD', edges).value).toBe(5);
    expect(convert(1, 'USD', 'GBP', edges)).toBeNull();
    expect(convert(NaN, 'USD', 'RUB', edges)).toBeNull();
  });

  it('единицы: рубль первым, затем по списку; нулевой курс не берётся', () => {
    expect(convertibleUnits(buildEdges(items))).toEqual(['RUB', 'USD', 'EUR', 'BTC']);
  });

  it('ввод суммы: пробелы, запятая, мусор', () => {
    expect(parseAmountInput('1 000,5')).toBe(1000.5);
    expect(parseAmountInput('100')).toBe(100);
    expect(parseAmountInput('')).toBeNull();
    expect(parseAmountInput('12a')).toBeNull();
  });

  it('результат: крупное целым, обычное с копейками, доля монеты с точностью', () => {
    expect(formatConverted(8348.4, 'ru')).toBe('8\u00A0348');
    expect(formatConverted(83.4, 'en')).toBe('83.40');
    expect(formatConverted(0.00123456, 'en')).toBe('0.00123456');
  });

  it('английское название курса пишется одинаково', () => {
    expect(normalizeRateNameEn('USD/RUB Exchange Rate')).toBe('USD/RUB exchange rate');
    expect(normalizeRateNameEn('EUR/USD exchange rate')).toBe('EUR/USD exchange rate');
  });
});

describe('изменение курса за неделю, месяц и год', () => {
  const day = 24 * 60 * 60 * 1000;
  const start = Date.parse('2025-09-01');
  const points = Array.from({ length: 400 }, (_, i) => ({
    date: new Date(start + i * day).toISOString().slice(0, 10),
    value: 100 + i * 0.1,
  }));

  it('считает проценты и размах за последний год', () => {
    const windows = currencyWindows(points);
    const last = points[points.length - 1];
    expect(windows.last.date).toBe(last.date);
    expect(windows.week).toBeCloseTo(((last.value / points[points.length - 8].value) - 1) * 100, 4);
    expect(windows.month).toBeGreaterThan(windows.week);
    expect(windows.year).toBeGreaterThan(windows.month);
    expect(windows.max.value).toBe(last.value);
    expect(windows.min.value).toBeGreaterThan(100);
  });

  it('короткая история: года нет, а неделя есть', () => {
    const windows = currencyWindows(points.slice(-20));
    expect(windows.week).not.toBeNull();
    expect(windows.year).toBeNull();
    expect(currencyWindows([{ date: '2026-01-01', value: 1 }])).toBeNull();
  });
});

describe('валюта страны для калькулятора инфляции', () => {
  it('есть у всех стран каталога сравнения', () => {
    for (const slug of CATALOG_SLUGS) {
      expect(currencyForCountry(slug), slug).toBeTruthy();
    }
  });

  it('австралийские доллары, американские и евро', () => {
    expect(currencyInPhrase(currencyForCountry('australia'), 'ru')).toBe('в австралийских долларах');
    expect(currencyInPhrase(currencyForCountry('australia'), 'en')).toBe('in Australian dollars');
    expect(formatMoney(100000, currencyForCountry('united-states'), 'en')).toBe('$100,000');
    expect(formatMoney(100000, currencyForCountry('australia'), 'en')).toBe('A$100,000');
    expect(formatMoney(71827, currencyForCountry('germany'), 'ru')).toBe('71\u00A0827\u00A0€');
    expect(formatMoney(100000, currencyForCountry('poland'), 'en')).toBe('100,000\u00A0zł');
    expect(formatMoney(100000, COUNTRY_CURRENCY.russia, 'ru')).toBe('100\u00A0000\u00A0₽');
    expect(formatMoney(null, null)).toBe('—');
    expect(currencyForCountry('atlantis')).toBeNull();
  });
});

describe('население человеческими числами', () => {
  it('кратко: 28,1 млн, 812 тыс., 1,41 млрд', () => {
    expect(compactPeople(28_076_986, 'ru')).toBe('28,1\u00A0млн');
    expect(compactPeople(5_500_000, 'ru')).toBe('5,50\u00A0млн');
    expect(compactPeople(812_400, 'ru')).toBe('812\u00A0тыс.');
    expect(compactPeople(1_408_280_000, 'en')).toBe('1.41\u00A0billion');
    expect(compactPeople(28_076_986, 'en')).toBe('28.1\u00A0million');
  });

  it('прибавка и проценты со знаком и без «,00»', () => {
    expect(signedPeople(346_630, 'ru')).toBe('+347\u00A0тыс.');
    expect(signedPeople(-12_000, 'ru')).toBe('−12\u00A0тыс.');
    expect(signedPeople(0)).toBeNull();
    expect(signedPercent(1.2345, 'ru')).toBe('+1,2\u00A0%');
    expect(signedPercent(0.01, 'ru')).toBe('0 %');
  });

  it('место: «5-е» и «5th»', () => {
    expect(placeOrdinal(5, 'ru')).toBe('5-е');
    expect(['1st', '2nd', '3rd', '4th', '11th', '12th', '21st'].map((_, i) => placeOrdinal([1, 2, 3, 4, 11, 12, 21][i], 'en')))
      .toEqual(['1st', '2nd', '3rd', '4th', '11th', '12th', '21st']);
  });

  it('место среди стран снимка', () => {
    const items = [
      { country_slug: 'china', value: 1400 },
      { country_slug: 'india', value: 1390 },
      { country_slug: 'australia', value: 28 },
      { country_slug: 'austria', value: 9 },
    ];
    expect(populationRank(items, 'australia')).toEqual({ rank: 3, total: 4 });
    expect(populationRank(items, 'nowhere')).toBeNull();
  });

  it('единицы ряда: люди, тысячи, миллионы', () => {
    expect(peopleScale('человек')).toBe(1);
    expect(peopleScale('тыс. чел.')).toBe(1e3);
    expect(peopleScale('млн чел.')).toBe(1e6);
    expect(isPeopleUnit('человек')).toBe(true);
    expect(isPeopleUnit('persons')).toBe(true);
    expect(isPeopleUnit('% ВВП')).toBe(false);
  });

  it('сводка: оценка текущего года, прирост и рост за десять лет', () => {
    const points = [];
    for (let year = 2014; year <= 2026; year += 1) {
      points.push({ date: `${year}-01-01`, value: 25_000_000 + (year - 2014) * 250_000 });
    }
    const summary = populationSummary(points, 'человек', { now: new Date('2026-10-05') });
    expect(summary.year).toBe(2026);
    expect(summary.estimate).toBe(true);
    expect(summary.delta).toBe(250_000);
    expect(summary.deltaPct).toBeCloseTo((250_000 / 27_750_000) * 100, 6);
    expect(summary.decadePct).toBeCloseTo(((28_000_000 / 25_500_000) - 1) * 100, 6);
    const old = populationSummary(points.slice(0, 5), 'человек', { now: new Date('2026-10-05') });
    expect(old.estimate).toBe(false);
    expect(old.decadePct).toBeNull();
    expect(populationSummary([], 'человек')).toBeNull();
  });
});

describe('единицы словами в списке показателей', () => {
  it('«‰» и «USD/баррель» читаются без расшифровки', () => {
    expect(unitHint('‰', 'ru')).toBe('на 1000 жителей');
    expect(unitHint('USD/баррель', 'en')).toBe('$ per barrel');
    expect(unitHint('%', 'ru')).toBe('%');
  });
});

describe('тексты зоны G', () => {
  it('ключи w6g.* есть в обоих языках, в английских нет кириллицы, нет средней точки', () => {
    const ruKeys = Object.keys(MESSAGES.ru).filter((key) => key.startsWith('w6g.'));
    const enKeys = Object.keys(MESSAGES.en).filter((key) => key.startsWith('w6g.'));
    expect(ruKeys.length).toBeGreaterThan(100);
    expect(enKeys.sort()).toEqual(ruKeys.sort());
    for (const key of enKeys) {
      expect(MESSAGES.en[key], key).not.toMatch(/[А-Яа-яЁё]/);
    }
    for (const key of ruKeys) {
      expect(MESSAGES.ru[key], key).not.toContain('·');
      expect(MESSAGES.en[key], key).not.toContain('·');
    }
  });

  it('подписи настроек сравнения человеческие', () => {
    expect(MESSAGES.ru['w6g.compare.scale.values']).toBe('Как есть');
    expect(MESSAGES.ru['w6g.compare.scale.index']).toBe('Рост от начала (старт = 100)');
    expect(MESSAGES.ru['w6g.compare.step.auto']).toBe('Как в источнике');
    expect(MESSAGES.ru['w6g.compare.saveImage']).toBe('Сохранить как картинку');
  });
});
