import { describe, it, expect } from 'vitest';
import {
  NBSP, compactParts, formatPointsDelta, glueNumbers, plainIndicatorTitle, unitLabel,
} from './regionUi';

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

describe('glueNumbers', () => {
  it('«10 000» не рвётся переносом, «5 %» не отрывается от числа', () => {
    expect(glueNumbers('на 10 000 человек населения')).toBe(`на 10${NBSP}000 человек населения`);
    expect(glueNumbers('рост 5 % за год')).toBe(`рост 5${NBSP}% за год`);
    expect(glueNumbers('в 1998 2024')).toBe('в 1998 2024');
  });

  it('названия показателей возвращаются со склеенными числами', () => {
    expect(plainIndicatorTitle('Коэффициенты миграционного прироста на 10 000 человек населения'))
      .toBe(`Коэффициенты миграционного прироста на 10${NBSP}000 человек населения`);
  });
});

describe('нагрузка «всего» и единицы на душу населения', () => {
  it('общая демографическая нагрузка получает понятное название', () => {
    expect(plainIndicatorTitle('Коэффициенты демографической нагрузки — всего'))
      .toBe('Детей и пожилых на 1000 человек трудоспособного возраста');
  });

  it('«на 1000 человек населения» сокращается до короткой единицы', () => {
    expect(unitLabel('на 1000 человек населения')).toBe('на 1000 чел.');
    expect(unitLabel('на 10 000 человек населения', 'en')).toBe('per 10,000 people');
  });

  it('число и единица отдаются раздельно (число жирным, единица обычной)', () => {
    expect(compactParts(0.4, 'на 1000 человек населения')).toEqual({ num: '0,4', unit: `на${NBSP}1000${NBSP}чел.` });
    expect(compactParts(null, '₽')).toEqual({ num: '—', unit: '' });
  });
});
