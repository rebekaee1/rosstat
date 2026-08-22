import { describe, expect, it } from 'vitest';
import { formatRegionValue, regionValueDigits, shortUnit, yearDelta } from './regionsApi';

const nbspToSpace = (s) => s.replace(/[\u00a0\u202f]/g, ' ');

describe('regionValueDigits', () => {
  it('крупные счётные — без дроби', () => {
    expect(regionValueDigits(146980.061)).toBe(0);
    expect(regionValueDigits(45000)).toBe(0);
  });

  it('десятки и сотни — один знак', () => {
    expect(regionValueDigits(146.98)).toBe(1);
    expect(regionValueDigits(45.34)).toBe(1);
    expect(regionValueDigits(73.4)).toBe(1);
  });

  it('величины порядка единиц и доли — три знака', () => {
    expect(regionValueDigits(1.152)).toBe(3);
    expect(regionValueDigits(1.195)).toBe(3);
    expect(regionValueDigits(0.567)).toBe(3);
    expect(regionValueDigits(-0.32)).toBe(3);
    expect(regionValueDigits(9.99)).toBe(3);
  });
});

describe('formatRegionValue', () => {
  it('пустые значения — тире', () => {
    expect(formatRegionValue(null)).toBe('—');
    expect(formatRegionValue(undefined)).toBe('—');
    expect(formatRegionValue(NaN)).toBe('—');
  });

  it('большие значения без дроби, с разрядами', () => {
    expect(nbspToSpace(formatRegionValue(146980.061, 'ru'))).toBe('146 980');
    expect(nbspToSpace(formatRegionValue(146980.061, 'en'))).toBe('146,980');
  });

  it('средние значения с одним знаком', () => {
    expect(formatRegionValue(146.98, 'ru')).toBe('147');
    expect(formatRegionValue(45.34, 'ru')).toBe('45,3');
    expect(formatRegionValue(45.34, 'en')).toBe('45.3');
  });

  it('коэффициенты порядка единиц сохраняют сотые и тысячные', () => {
    expect(formatRegionValue(1.152, 'ru')).toBe('1,152');
    expect(formatRegionValue(1.195, 'ru')).toBe('1,195');
    expect(formatRegionValue(1.152, 'en')).toBe('1.152');
    expect(formatRegionValue(1.4, 'ru')).toBe('1,4');
    expect(formatRegionValue(1.074, 'ru')).toBe('1,074');
  });

  it('доли меньше единицы — до трёх знаков, без хвостовых нулей', () => {
    expect(formatRegionValue(0.567, 'ru')).toBe('0,567');
    expect(formatRegionValue(-0.32, 'ru')).toBe('-0,32');
    expect(formatRegionValue(0.567, 'en')).toBe('0.567');
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
