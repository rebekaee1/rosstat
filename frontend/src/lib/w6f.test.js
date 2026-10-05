// Волна 6, зона F: чистые функции календаря, 404, карты регионов, штатов США и подачи чисел.
import { describe, it, expect } from 'vitest';
import { suggestForPath } from './notFoundSuggest';
import { pickDefaultDay, findDailyRecurring } from './calendarGrouping';
import { plainEventText, shortEventTitle } from './calendarText';
import { bubbleLayout, pathCentroid } from './regionsBubbles';
import { MAP_SCALE, buildQuantiles } from './regionsMapColors';
import { formatDeltaWithUnit } from './deltaText';
import { plainUsIndicatorName, plainUsSectionTitle } from './usCatalogTopics';
import { explainIndicator } from './regionUi';
import mapData from './regionsMap.json';

describe('404: подсказка «Возможно, вы искали»', () => {
  it('рейтинг по ВВП и калькуляторы угадываются по словам адреса', () => {
    expect(suggestForPath('/ranking/gdp')[0]).toMatchObject({ to: '/world/rating/gdp-usd', labelKey: 'w6f.nf.guess.rating' });
    expect(suggestForPath('/rankings')[0].to).toBe('/world/rating/gdp-usd');
    expect(suggestForPath('/calculators')[0].to).toBe('/calculator');
    expect(suggestForPath('/russia/regions')[0].to).toBe('/russia/region');
  });

  it('незнакомый адрес — пустой список, подсказок не больше трёх', () => {
    expect(suggestForPath('/zzz')).toEqual([]);
    expect(suggestForPath('/')).toEqual([]);
    expect(suggestForPath('/rating/calculator/region/compare/today').length).toBeLessThanOrEqual(3);
  });
});

describe('календарь: день по умолчанию', () => {
  const rate = (date) => ({ title: 'Официальный курс доллара', source: 'cbr', scheduled_date: date, importance: 1 });
  const dailyRates = Array.from({ length: 12 }, (_u, i) => rate(`2026-10-${String(i + 1).padStart(2, '0')}`));
  const cpi = { title: 'Индекс потребительских цен', source: 'rosstat', scheduled_date: '2026-10-09', importance: 3 };
  const minor = { title: 'Бюллетень', source: 'rosstat', scheduled_date: '2026-10-07', importance: 1 };

  it('ежедневные курсы не считаются: открывается ближайшее важное событие, а не пятница с курсами', () => {
    const recurring = findDailyRecurring([...dailyRates, cpi, minor]);
    expect(recurring.keys.size).toBe(1);
    expect(pickDefaultDay([...dailyRates, cpi, minor], '2026-10-05', recurring.keys)).toBe('2026-10-09');
  });

  it('если в сегодняшнем дне есть разовое событие, открывается сегодня', () => {
    const recurring = findDailyRecurring([...dailyRates, cpi, minor]);
    expect(pickDefaultDay([...dailyRates, cpi, minor], '2026-10-09', recurring.keys)).toBe('2026-10-09');
  });

  it('важное событие выбирается раньше рядового, а без событий результат пустой', () => {
    const recurring = findDailyRecurring(dailyRates);
    expect(pickDefaultDay([...dailyRates, minor, cpi], '2026-10-01', findDailyRecurring([...dailyRates, minor, cpi]).keys)).toBe('2026-10-09');
    expect(pickDefaultDay(dailyRates, '2026-10-01', recurring.keys)).toBeNull();
  });
});

describe('календарь: тексты без жаргона', () => {
  it('сокращения расшифрованы, остаётся одна первая фраза', () => {
    expect(plainEventText('Ставка RUONIA отражает стоимость однодневных кредитов. Публикуется ежедневно.'))
      .toBe('Ставка по однодневным кредитам между банками отражает стоимость однодневных кредитов.');
    expect(plainEventText('ИПЦ показывает изменение цен. Второй абзац.')).toBe('Инфляция показывает изменение цен.');
    expect(plainEventText('')).toBe('');
  });

  it('короткое название для клетки', () => {
    expect(shortEventTitle('Индекс потребительских цен (ИПЦ)')).toBe('Инфляция');
    expect(shortEventTitle('Заседание ЦБ по ключевой ставке (опорное)')).toBe('Ключевая ставка');
    expect(shortEventTitle('Консолидированный бюджет за квартал по данным Минфина')).toMatch(/…$/);
    expect(shortEventTitle('CBR Key Rate Decision (core)', 'en')).toBe('Key rate');
  });
});

describe('карта регионов: пузыри и шкала', () => {
  it('центр региона лежит внутри рамки карты, у каждого региона свой кружок и кружки не налезают друг на друга', () => {
    const moscow = mapData.regions.find((r) => r.slug === 'moskva');
    const c = pathCentroid(moscow.path);
    expect(c.x).toBeGreaterThan(100);
    expect(c.x).toBeLessThan(200);
    const layout = bubbleLayout(mapData);
    expect(layout.size).toBe(mapData.regions.length);
    const pts = [...layout.values()];
    let overlaps = 0;
    for (let i = 0; i < pts.length; i += 1) {
      for (let j = i + 1; j < pts.length; j += 1) {
        if (Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y) < pts[i].r * 2 - 1.5) overlaps += 1;
      }
    }
    expect(overlaps).toBeLessThanOrEqual(2);
    // Кэш: повторный вызов возвращает ту же раскладку.
    expect(bubbleLayout(mapData)).toBe(layout);
  });

  it('шкала мельче прежних пяти ступеней, крайние цвета прежние', () => {
    expect(MAP_SCALE.length).toBeGreaterThanOrEqual(8);
    expect(MAP_SCALE[0]).toBe('#EFEAE0');
    expect(MAP_SCALE[MAP_SCALE.length - 1]).toBe('#9C7B22');
    expect(new Set(MAP_SCALE).size).toBe(MAP_SCALE.length);
    const q = buildQuantiles([1, 2, 3, 4, 5, 6, 7, 8, 9]);
    expect(new Set([1, 2, 3, 4, 5, 6, 7, 8, 9].map(q)).size).toBeGreaterThanOrEqual(8);
  });
});

describe('подача чисел без жаргона', () => {
  it('«п. п.» заменено словами, а для индекса остаются проценты', () => {
    expect(formatDeltaWithUnit(0.34, '%', { locale: 'ru', plain: true }).text).toContain('процентного пункта');
    expect(formatDeltaWithUnit(0.34, '%', { locale: 'ru' }).text).toContain('п. п.');
    expect(formatDeltaWithUnit(0.34, '%', { locale: 'en', plain: true }).text).toContain('percentage points');
    expect(formatDeltaWithUnit(-0.6, 'руб./л', { locale: 'ru', plain: true }).text).toContain('₽ за литр');
    expect(formatDeltaWithUnit(0.05, 'пунктов', { pct: true, locale: 'ru' }).text).toMatch(/\+0,05\s%/);
  });

  it('подсказка «что это значит» только там, где она нужна', () => {
    expect(explainIndicator('Коэффициент демографической нагрузки', '')).toMatch(/тысячу человек трудоспособного возраста/);
    expect(explainIndicator('Уровень безработицы', '%')).toMatch(/процентных пунктах/);
    expect(explainIndicator('Численность населения', 'чел.')).toBe('');
  });
});

describe('штаты США: названия без кодов', () => {
  it('код отрасли уходит в подсказку, название остаётся читаемым', () => {
    const ru = plainUsIndicatorName('Производство товаров недлительного пользования (код отрасли 311-316,322-326)');
    expect(ru.label).toBe('Производство товаров недлительного пользования');
    expect(ru.hint).toBe('Код отрасли: 311-316,322-326');
    const en = plainUsIndicatorName('Farms (NAICS 111-112)', 'en');
    expect(en).toEqual({ label: 'Farms', hint: 'NAICS industry code: 111-112' });
    expect(plainUsIndicatorName('Безработица').hint).toBe('');
  });

  it('канцелярские названия разделов переименованы', () => {
    expect(plainUsSectionTitle('Вклад заработков отраслей в изменение доходов')).toBe('Какую долю доходов дают отрасли');
    expect(plainUsSectionTitle('Неизвестный раздел')).toBe('Неизвестный раздел');
  });
});
