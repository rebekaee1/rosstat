// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatValue } from './format';
import {
  NUMBER_FORMAT_EVENT, __resetPrefs, applyPrefs, converterCurrency, getPrefs, homeCountrySlug,
} from './cabinetPrefs';
import { formatPercentChangeFine } from './indicatorSummary';

afterEach(() => __resetPrefs());

describe('настройки кабинета, которые действуют на сайте (круг 12)', () => {
  it('формат чисел переопределяет разделители независимо от языка страницы и сбрасывается при выходе', () => {
    expect(formatValue(1234.5, 1, 'ru')).toBe('1 234,5');
    const onChange = vi.fn();
    window.addEventListener(NUMBER_FORMAT_EVENT, onChange);
    expect(applyPrefs({ number_format: 'en' })).toBe(true);
    expect(formatValue(1234.5, 1, 'ru')).toBe('1,234.5');
    expect(onChange).toHaveBeenCalledTimes(1);
    // тот же формат второй раз: страницу пересобирать не нужно
    expect(applyPrefs({ number_format: 'en' })).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(applyPrefs(null)).toBe(true);
    expect(formatValue(1234.5, 1, 'ru')).toBe('1 234,5');
    window.removeEventListener(NUMBER_FORMAT_EVENT, onChange);
  });

  it('валюта конвертера: USD, EUR, CNY; рубль и чужое оставляют вход по умолчанию', () => {
    expect(converterCurrency({ currency: 'EUR' })).toBe('EUR');
    expect(converterCurrency({ currency: 'RUB' })).toBeNull();
    expect(converterCurrency(null)).toBeNull();
  });

  it('главная страна: только безопасный slug', () => {
    applyPrefs({ home_country: 'turkey' });
    expect(homeCountrySlug(getPrefs())).toBe('turkey');
    expect(homeCountrySlug({ home_country: '../x' })).toBeNull();
    expect(homeCountrySlug(null)).toBeNull();
  });
});

describe('изменение рядов «по дням» (Г3)', () => {
  it('малое изменение показывается со знаком и тремя знаками, «без изменений» только у нуля', () => {
    expect(formatPercentChangeFine(0.0306, 'ru')).toBe('+0,03 %');
    expect(formatPercentChangeFine(-0.0306, 'ru')).toBe('−0,03 %');
    expect(formatPercentChangeFine(0.6, 'ru')).toBe('+0,6 %');
    expect(formatPercentChangeFine(0, 'ru')).toBeNull();
    expect(formatPercentChangeFine(0.00001, 'ru')).toBeNull();
  });
});
