import { describe, expect, it } from 'vitest';
import {
  htmlLang,
  ogLocale,
  resolveLocale,
  PRODUCTION_APEX_HOSTS,
} from './locale.js';
import { MESSAGES } from './messages.js';

describe('resolveLocale', () => {
  it('defaults localhost and unknown hosts to ru', () => {
    expect(resolveLocale({ host: 'localhost' })).toBe('ru');
    expect(resolveLocale({ host: '127.0.0.1' })).toBe('ru');
    expect(resolveLocale({ host: 'frontend' })).toBe('ru');
  });

  it('honours X-FE-Locale / preview override', () => {
    expect(resolveLocale({ host: 'localhost', header: 'en' })).toBe('en');
    expect(resolveLocale({ host: 'localhost', preview: 'en' })).toBe('en');
    expect(resolveLocale({ host: 'forecasteconomy.com', header: 'ru' })).toBe('ru');
  });

  it('keeps production apex on ru until cutover flag', () => {
    for (const host of PRODUCTION_APEX_HOSTS) {
      expect(resolveLocale({ host, apexLocaleEn: false })).toBe('ru');
      expect(resolveLocale({ host })).toBe('ru');
    }
    expect(resolveLocale({ host: 'ru.forecasteconomy.com' })).toBe('ru');
  });

  it('maps production apex to en when cutover enabled; en. always en', () => {
    for (const host of PRODUCTION_APEX_HOSTS) {
      expect(resolveLocale({ host, apexLocaleEn: true })).toBe('en');
    }
    expect(resolveLocale({ host: 'en.forecasteconomy.com' })).toBe('en');
    expect(resolveLocale({ host: 'ru.forecasteconomy.com', apexLocaleEn: true })).toBe('ru');
  });
});

describe('htmlLang / ogLocale', () => {
  it('maps locale codes', () => {
    expect(htmlLang('en')).toBe('en');
    expect(htmlLang('ru')).toBe('ru');
    expect(ogLocale('en')).toBe('en_US');
    expect(ogLocale('ru')).toBe('ru_RU');
  });
});

describe('messages parity', () => {
  it('ru keys ⊆ en keys', () => {
    const ru = Object.keys(MESSAGES.ru || {});
    const en = new Set(Object.keys(MESSAGES.en || {}));
    const missing = ru.filter((k) => !en.has(k));
    expect(missing).toEqual([]);
  });

  it('en keys ⊆ ru keys', () => {
    const en = Object.keys(MESSAGES.en || {});
    const ru = new Set(Object.keys(MESSAGES.ru || {}));
    const missing = en.filter((k) => !ru.has(k));
    expect(missing).toEqual([]);
  });

  it('exposes both locale buckets', () => {
    expect(MESSAGES).toHaveProperty('ru');
    expect(MESSAGES).toHaveProperty('en');
  });
});
