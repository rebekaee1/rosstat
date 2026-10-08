import { describe, expect, it } from 'vitest';
import messagesRu from '../i18n/messages.ru';
import messagesEn from '../i18n/messages.en';
import {
  compactCount,
  compactMoneyAmount,
  typographicMinus,
  describeChange,
  humanizeQualifier,
  indicatorsCountText,
  inflationCaption,
  isMainTopic,
  isPinnedTopic,
  orderKeyFigures,
  scaleMoneyUnit,
  similarCountries,
  splitTechnicalNote,
  topicDisplayName,
  yearAgoPoint,
} from './countryKeyFigures';

const tRu = (key, params = {}) => String(messagesRu[key] ?? key)
  .replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ''));
const tEn = (key, params = {}) => String(messagesEn[key] ?? key)
  .replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ''));

describe('scaleMoneyUnit', () => {
  it('переводит «849 680 млн евро» в «849,7 млрд €» и оставляет пометку про цены отдельно', () => {
    const scaled = scaleMoneyUnit(849680, 'в постоянных ценах 2015 года, млн евро');
    expect(scaled.unit).toBe('млрд €');
    expect(scaled.value).toBeCloseTo(849.68, 2);
    expect(scaled.qualifier).toBe('в постоянных ценах 2015 года');
  });

  it('2 319,9 млрд $ становится 2,3 трлн $, а число без масштаба в единице не трогает', () => {
    const scaled = scaleMoneyUnit(2319.9, 'млрд $');
    expect(scaled.unit).toBe('трлн $');
    expect(scaled.value).toBeCloseTo(2.32, 2);
    expect(scaleMoneyUnit(4, '%')).toBeNull();
    expect(scaleMoneyUnit(83.4, 'человек')).toBeNull();
  });

  it('тысячи человек укрупняются до миллионов, английские единицы тоже', () => {
    expect(scaleMoneyUnit(12345, 'тыс. человек').unit).toBe('млн человек');
    expect(scaleMoneyUnit(1500, 'million euro', 'en').unit).toBe('billion €');
  });
});

describe('humanizeQualifier', () => {
  it('«в постоянных ценах» превращается в «с поправкой на инфляцию»', () => {
    expect(humanizeQualifier('в постоянных ценах 2015 года', tRu)).toBe('с поправкой на инфляцию');
    expect(humanizeQualifier('chain-linked volumes (2015)', tEn)).toBe('adjusted for inflation');
    expect(humanizeQualifier('сезонно скорректировано', tRu)).toBe('сезонно скорректировано');
  });
});

describe('yearAgoPoint', () => {
  const monthly = Array.from({ length: 30 }, (_, i) => {
    const date = new Date(Date.UTC(2024, i, 1)).toISOString().slice(0, 10);
    return { date, value: i + 1 };
  });

  it('находит значение ровно год назад для месячного ряда', () => {
    const point = yearAgoPoint(monthly, 'monthly');
    // последняя точка — июнь 2026, год назад — июнь 2025 (18-я по счёту)
    expect(monthly[monthly.length - 1].date).toBe('2026-06-01');
    expect(point.date).toBe('2025-06-01');
    expect(point.value).toBe(18);
  });

  it('для годового ряда берёт предыдущий год, для короткого ряда ничего не выдумывает', () => {
    const annual = [{ date: '2023-01-01', value: 1 }, { date: '2024-01-01', value: 2 }, { date: '2025-01-01', value: 3 }];
    expect(yearAgoPoint(annual, 'annual').value).toBe(2);
    expect(yearAgoPoint([{ date: '2025-01-01', value: 3 }], 'annual')).toBeNull();
    expect(yearAgoPoint([{ date: '2025-01-01', value: 3 }, { date: '2025-02-01', value: 4 }], 'monthly')).toBeNull();
  });
});

describe('describeChange', () => {
  it('проценты: «на 0,7 пункта ниже, чем в прошлом месяце»', () => {
    const text = describeChange({ change: -0.7, unit: '%', frequency: 'monthly', locale: 'ru', t: tRu });
    expect(text).toBe('на 0,7 пункта ниже, чем в прошлом месяце');
  });

  it('склонение пунктов и «выше» для целых чисел', () => {
    expect(describeChange({ change: 2, unit: '%', frequency: 'annual', locale: 'ru', t: tRu }))
      .toBe('на 2 пункта выше, чем в прошлом году');
    expect(describeChange({ change: 5, unit: 'индекс', frequency: 'quarterly', locale: 'ru', t: tRu }))
      .toBe('на 5 пунктов выше, чем в прошлом квартале');
    expect(describeChange({ change: 21, unit: '%', frequency: 'daily', locale: 'ru', t: tRu }))
      .toBe('на 21 пункт выше, чем вчера');
  });

  it('другие единицы идут после числа, ноль даёт «без изменений»', () => {
    expect(describeChange({ change: 133.63, unit: 'тыс. человек', frequency: 'monthly', locale: 'ru', t: tRu }))
      .toBe('на 134 тыс. человек выше, чем в прошлом месяце');
    expect(describeChange({ change: 0.0001, unit: '%', locale: 'ru', t: tRu })).toBe('без изменений');
    expect(describeChange({ change: null, unit: '%', locale: 'ru', t: tRu })).toBe('');
  });

  it('английский вариант без жаргона', () => {
    expect(describeChange({ change: -0.7, unit: '%', frequency: 'monthly', locale: 'en', t: tEn }))
      .toBe('0.7 points lower than last month');
  });
});

describe('splitTechnicalNote', () => {
  it('прячет «2015 = 100» и «цены 2017» из названия и единицы в подсказку', () => {
    expect(splitTechnicalNote('Индекс цен на жильё (база 2025 = 100)', 'индекс (2025 = 100)')).toEqual({
      name: 'Индекс цен на жильё',
      unit: 'индекс',
      note: '2025 = 100',
    });
    const dollars = splitTechnicalNote('ВВП', 'млрд долларов США (цены 2017)');
    expect(dollars.unit).toBe('млрд долларов США');
    expect(dollars.note).toBe('цены 2017');
  });

  it('название без пометок остаётся как есть', () => {
    expect(splitTechnicalNote('Уровень безработицы', '%')).toEqual({ name: 'Уровень безработицы', unit: '%', note: '' });
  });
});

describe('темы страны', () => {
  it('счётчик: 499 остаётся, 2197 — «2,2 тыс.», слово по числу', () => {
    expect(compactCount(499, 'ru')).toBe('499');
    expect(compactCount(2197, 'ru').replace(/\u00a0/g, ' ')).toBe('2,2 тыс.');
    expect(compactCount(12400, 'ru').replace(/\u00a0/g, ' ')).toBe('12 тыс.');
    expect(compactCount(2197, 'en')).toBe('2.2k');
    expect(indicatorsCountText(1, 'ru', tRu)).toBe('1 показатель');
    expect(indicatorsCountText(24, 'ru', tRu)).toBe('24 показателя');
    expect(indicatorsCountText(499, 'ru', tRu)).toBe('499 показателей');
  });

  it('понятные названия и золотая точка у главных тем', () => {
    const accounts = { name: 'Национальные счета', name_ru: 'Национальные счета', name_en: 'National accounts' };
    expect(topicDisplayName(accounts, 'ru')).toBe('ВВП и рост');
    expect(topicDisplayName(accounts, 'en')).toBe('GDP and growth');
    expect(topicDisplayName({ name: 'Цены', name_en: 'Prices' }, 'en')).toBe('Prices');
    expect(isMainTopic(accounts)).toBe(true);
    expect(isMainTopic({ name: 'Общество' })).toBe(false);
  });

  it('похожие страны: тот же регион, без самой страны, самые полные первыми', () => {
    const catalog = {
      countries: [
        { slug: 'germany', region: 'Европа', indicators_count: 10 },
        { slug: 'france', region: 'Европа', indicators_count: 30 },
        { slug: 'italy', region: 'Европа', indicators_count: 20 },
        { slug: 'japan', region: 'Азия', indicators_count: 99 },
      ],
    };
    expect(similarCountries(catalog, { slug: 'germany', region: 'Европа' }).map((c) => c.slug)).toEqual(['france', 'italy']);
    expect(similarCountries(null, { slug: 'germany', region: 'Европа' })).toEqual([]);
  });
});

describe('круг 8, Y5: сумма без масштаба', () => {
  it('56 459 257 590 евро — «56,5 млрд €»', () => {
    expect(compactMoneyAmount(56459257590, 'евро')).toEqual({ value: 56.45925759, unit: 'млрд €' });
    expect(compactMoneyAmount(56459257590, 'euro', 'en').unit).toBe('billion €');
    expect(compactMoneyAmount(2_500_000, 'евро').unit).toBe('млн €');
  });

  it('малые суммы и обычные единицы остаются как есть', () => {
    expect(compactMoneyAmount(900000, 'евро')).toBeNull();
    expect(compactMoneyAmount(56459257590, 'сделок')).toBeNull();
    expect(compactMoneyAmount(2320, 'млрд $')).toBeNull();
  });

  it('изменение суммы в фразе короткое', () => {
    const text = describeChange({ change: -11898246453, unit: 'евро', frequency: 'quarterly', locale: 'ru', t: tRu });
    expect(text.replace(/\u00a0/g, ' ')).toBe('на 11,9 млрд € ниже, чем в прошлом квартале');
  });

  it('typographicMinus заменяет только ведущий дефис перед цифрой', () => {
    expect(typographicMinus('-0,08')).toBe('−0,08');
    expect(typographicMinus('5-6')).toBe('5-6');
  });
});

describe('orderKeyFigures', () => {
  const item = (slug) => ({ concept_slug: slug });
  it('инфляция, затем ВВП в долларах, безработица, население; остальное в порядке сервера', () => {
    const list = ['gdp-volume-quarterly', 'unemployment-rate', 'hicp-index', 'budget-balance-gdp', 'gdp-usd', 'population'].map(item);
    expect(orderKeyFigures(list).map((x) => x.concept_slug)).toEqual([
      'hicp-index', 'gdp-usd', 'unemployment-rate', 'population', 'gdp-volume-quarterly', 'budget-balance-gdp',
    ]);
  });

  it('ставка и курс, когда они есть, идут сразу после инфляции', () => {
    const list = ['gdp-usd', 'exchange-rate', 'policy-rate', 'hicp-index'].map(item);
    expect(orderKeyFigures(list).map((x) => x.concept_slug)).toEqual(['hicp-index', 'policy-rate', 'exchange-rate', 'gdp-usd']);
  });

  it('не падает на пустом вводе', () => {
    expect(orderKeyFigures(undefined)).toEqual([]);
  });
});

describe('isPinnedTopic', () => {
  it('ВВП, цены и деньги закреплены, рынок труда нет', () => {
    expect(isPinnedTopic({ name: 'Национальные счета' })).toBe(true);
    expect(isPinnedTopic({ name: 'Цены' })).toBe(true);
    expect(isPinnedTopic({ name: 'Финансы' })).toBe(true);
    expect(isPinnedTopic({ name: 'Рынок труда' })).toBe(false);
  });
});

describe('inflationCaption', () => {
  const yoy = { concept_slug: 'hicp-index', unit: 'изменение за год, %', frequency: 'monthly', indicator_code: 'tr-prc_hicp_minr-total-i15' };
  it('месячный ряд: «год к году» и месяц', () => {
    expect(inflationCaption({ item: yoy, period: 'август 2026', t: tRu })).toBe('год к году, август 2026');
    expect(inflationCaption({ item: yoy, period: 'August 2026', t: tEn })).toBe('year over year, August 2026');
  });

  it('годовая оценка МВФ: «в среднем за год, оценка МВФ»', () => {
    const imf = { concept_slug: 'hicp-index', unit: '%', frequency: 'annual', indicator_code: 'tr-weo-pcpipch' };
    expect(inflationCaption({ item: imf, period: '2025', t: tRu })).toBe('в среднем за 2025, оценка МВФ');
  });

  it('не инфляция: пусто', () => {
    expect(inflationCaption({ item: { concept_slug: 'population' }, period: '2025', t: tRu })).toBe('');
  });
});
