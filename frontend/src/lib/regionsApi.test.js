import { describe, expect, it } from 'vitest';
import { formatRegionValue, shortUnit, yearDelta } from './regionsApi';

const nbspToSpace = (s) => s.replace(/[\u00a0\u202f]/g, ' ');

describe('formatRegionValue', () => {
  it('пустые значения — тире', () => {
    expect(formatRegionValue(null)).toBe('—');
    expect(formatRegionValue(undefined)).toBe('—');
    expect(formatRegionValue(NaN)).toBe('—');
  });

  it('большие значения без дроби, с разрядами', () => {
    expect(nbspToSpace(formatRegionValue(146980.061))).toBe('146 980');
  });

  it('средние значения с одним знаком', () => {
    expect(formatRegionValue(146.98)).toBe('147');
    expect(formatRegionValue(45.34)).toBe('45,3');
  });

  it('малые значения с двумя знаками', () => {
    expect(formatRegionValue(0.567)).toBe('0,57');
    expect(formatRegionValue(-0.32)).toBe('-0,32');
  });
});

describe('shortUnit', () => {
  it('денежные и физические единицы сокращаются', () => {
    expect(shortUnit('миллионов рублей')).toBe('млн ₽');
    expect(shortUnit('тысяч человек')).toBe('тыс чел.');
    expect(shortUnit('в процентах')).toBe('%');
    expect(shortUnit('%')).toBe('%');
    expect(shortUnit('% к предыдущему году')).toBe('% г/г');
    expect(shortUnit('тысяч гектаров')).toBe('тыс га');
    expect(shortUnit('центнеров с одного гектара')).toBe('ц/га');
  });

  it('не даёт «тысяч тысяч» на оси: сокращает число, не дублирует тысячную единицу', () => {
    // shortUnit не трогает «тысяч семей» — компактный тик оси (formatCompactTick)
    // сокращает ЧИСЛО («23,1 тыс»), а единица ряда остаётся отдельной подписью.
    expect(shortUnit('тысяч семей')).toBe('тысяч семей');
    expect(shortUnit('тысяч турпакетов')).toBe('тысяч турпакетов');
  });

  it('длинная нераспознанная единица опускается', () => {
    expect(shortUnit('на 100 000 человек населения соответствующего возраста')).toBe('');
  });

  it('короткая нераспознанная единица остаётся как есть', () => {
    expect(shortUnit('промилле')).toBe('промилле');
  });
});

describe('yearDelta', () => {
  it('рост и падение с направлением', () => {
    expect(yearDelta(110, 100)).toMatchObject({ pct: 10, up: true, down: false });
    expect(yearDelta(90, 100)).toMatchObject({ pct: -10, up: false, down: true });
  });

  it('нет базы — нет дельты', () => {
    expect(yearDelta(5, null)).toBeNull();
    expect(yearDelta(5, 0)).toBeNull();
    expect(yearDelta(null, 5)).toBeNull();
  });

  it('знакопеременные значения не дают процентного бейджа (В-20)', () => {
    expect(yearDelta(5, -10)).toBeNull();
    expect(yearDelta(-5, 10)).toBeNull();
  });
});
