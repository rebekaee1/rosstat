// @vitest-environment jsdom
// Круг 13 (R-CAB, C2): «Формат чисел» из настроек кабинета действует и там, где число рисуется не через formatValue
// (бегущая строка, подсказка графика сравнения, конвертер, подписи регионов).
import { afterEach, describe, expect, it } from 'vitest';
import { formatValue, numberTag, setNumberFormat } from './format';
import { formatRate } from './currencyRates';

afterEach(() => setNumberFormat(null));

describe('numberTag', () => {
  it('без настройки идёт по языку страницы', () => {
    expect(numberTag('en')).toBe('en-US');
    expect(numberTag('ru')).toBe('ru-RU');
  });

  it('настройка формата чисел сильнее языка страницы', () => {
    setNumberFormat('ru');
    expect(numberTag('en')).toBe('ru-RU');
    setNumberFormat('en');
    expect(numberTag('ru')).toBe('en-US');
  });

  it('formatValue и конвертер говорят одним форматом', () => {
    setNumberFormat('ru');
    expect(formatValue(1234.5, 1, 'en')).toBe('1 234,5');
    expect(formatRate(12.5, 'en')).toBe('12,50');
    setNumberFormat('en');
    expect(formatValue(1234.5, 1, 'ru')).toBe('1,234.5');
    expect(formatRate(12.5, 'ru')).toBe('12.50');
  });
});
