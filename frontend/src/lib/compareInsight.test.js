import { describe, expect, it } from 'vitest';
import {
  formatEndValue, gapInsight, isAbsoluteUnit, lastFiniteValue, spreadLabels, yForValue,
} from './compareInsight';

describe('isAbsoluteUnit', () => {
  it('«млрд $» и «человек» — величины, «%» и индексы — нет', () => {
    expect(isAbsoluteUnit('млрд $')).toBe(true);
    expect(isAbsoluteUnit('человек')).toBe(true);
    expect(isAbsoluteUnit('%')).toBe(false);
    expect(isAbsoluteUnit('п.п.')).toBe(false);
    expect(isAbsoluteUnit('индекс 2015 = 100')).toBe(false);
    expect(isAbsoluteUnit('')).toBe(false);
  });
});

describe('lastFiniteValue', () => {
  it('берёт последнюю точку с числом', () => {
    expect(lastFiniteValue([{ value: 1 }, { value: 5 }, { value: null }])).toBe(5);
    expect(lastFiniteValue([])).toBeNull();
  });
});

describe('formatEndValue', () => {
  it('без копеек: миллионы словами, тысячи группами', () => {
    expect(formatEndValue(28_076_986, { locale: 'ru' })).toMatch(/^28,1\s?млн$/);
    expect(formatEndValue(30_767.4, { locale: 'ru' }).replace(/\s/g, ' ')).toBe('30 767');
    expect(formatEndValue(28_076_986, { locale: 'en' })).toBe('28.1M');
  });
  it('маленькие числа с двумя знаками, проценты с единицей, индекс целым', () => {
    expect(formatEndValue(4.256, { locale: 'ru' })).toBe('4,26');
    expect(formatEndValue(4.2, { unit: '%', locale: 'ru' })).toBe('4,2 %');
    expect(formatEndValue(115.4, { indexed: true, locale: 'ru' })).toBe('115');
    expect(formatEndValue(null)).toBe('');
  });
});

describe('gapInsight', () => {
  it('США и Китай: разрыв в 1,6 раза', () => {
    const r = gapInsight([{ label: 'США', value: 30767 }, { label: 'Китай', value: 19535 }], 'ru');
    expect(r.leader).toBe('США');
    expect(r.other).toBe('Китай');
    expect(r.ratio).toBe('1,6');
    expect(r.plural).toBe('other');
  });
  it('целые разы выбирают форму слова: 2 раза, 5 раз', () => {
    expect(gapInsight([{ label: 'A', value: 2 }, { label: 'B', value: 1 }]).plural).toBe('few');
    expect(gapInsight([{ label: 'A', value: 5 }, { label: 'B', value: 1 }]).plural).toBe('many');
  });
  it('почти равны, один ряд или ноль: без разрыва', () => {
    expect(gapInsight([{ label: 'A', value: 100 }, { label: 'B', value: 102 }]).equal).toBe(true);
    expect(gapInsight([{ label: 'A', value: 1 }])).toBeNull();
    expect(gapInsight([{ label: 'A', value: 0 }, { label: 'B', value: 1 }])).toBeNull();
  });
});

describe('spreadLabels', () => {
  it('разводит близкие подписи, сохраняя порядок', () => {
    const out = spreadLabels([{ key: 'a', y: 100 }, { key: 'b', y: 104 }, { key: 'c', y: 300 }], { min: 10, max: 400, gap: 34 });
    expect(out.b - out.a).toBeGreaterThanOrEqual(34);
    expect(out.c).toBe(300);
  });
  it('не выходит за нижнюю границу', () => {
    const out = spreadLabels([{ key: 'a', y: 390 }, { key: 'b', y: 392 }], { min: 0, max: 400, gap: 34 });
    expect(out.b).toBeLessThanOrEqual(400);
    expect(out.b - out.a).toBeGreaterThanOrEqual(34);
  });
});

describe('yForValue', () => {
  it('верх домена у верхнего края, низ у нижнего', () => {
    expect(yForValue(100, [0, 100], { top: 10, plotHeight: 200 })).toBe(10);
    expect(yForValue(0, [0, 100], { top: 10, plotHeight: 200 })).toBe(210);
    expect(yForValue(1, [5, 5], { top: 0, plotHeight: 10 })).toBeNull();
  });
});
