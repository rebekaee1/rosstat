import { describe, it, expect } from 'vitest';
import { NBSP, formatPointsDelta, plainIndicatorTitle } from './regionUi';

describe('formatPointsDelta', () => {
  it('показывает разницу процентов в пунктах, а не процент от процента', () => {
    expect(formatPointsDelta(10.1, 7, 'ru').text).toBe(`+3,1${NBSP}п.п.`);
    expect(formatPointsDelta(1, 1.8, 'ru').text).toBe(`−0,8${NBSP}п.п.`);
    expect(formatPointsDelta(10.1, 7, 'en').text).toBe(`+3.1${NBSP}p.p.`);
  });

  it('практически равные значения — ноль, а нет данных — null', () => {
    expect(formatPointsDelta(5, 5.01, 'ru').diff).toBe(0);
    expect(formatPointsDelta(null, 5)).toBeNull();
    expect(formatPointsDelta(5, undefined)).toBeNull();
  });
});

describe('plainIndicatorTitle', () => {
  it('объясняет коэффициенты демографической нагрузки человеческими словами', () => {
    expect(plainIndicatorTitle('Коэффициенты демографической нагрузки — моложе трудоспособного возраста'))
      .toBe('Детей на 1000 человек трудоспособного возраста');
    expect(plainIndicatorTitle('Коэффициенты демографической нагрузки — старше трудоспособного возраста'))
      .toMatch(/на 1000 человек трудоспособного/);
  });

  it('остальные названия не трогает', () => {
    expect(plainIndicatorTitle('Численность населения')).toBe('Численность населения');
  });
});
