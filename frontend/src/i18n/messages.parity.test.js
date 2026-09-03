import { describe, expect, it } from 'vitest';
import {
  htmlLang,
  ogLocale,
  resolveLocale,
  PRODUCTION_APEX_HOSTS,
  localeCookieDomain,
  languageAlternateOrigin,
  buildLanguageSwitchUrl,
  isProductionLocaleHost,
  stickyPreviewFromPreference,
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

describe('language switcher until cutover', () => {
  it('does not treat localhost as a production locale host', () => {
    expect(isProductionLocaleHost('localhost')).toBe(false);
    expect(isProductionLocaleHost('127.0.0.1')).toBe(false);
    expect(isProductionLocaleHost('frontend')).toBe(false);
    expect(isProductionLocaleHost('forecasteconomy.com')).toBe(true);
    expect(isProductionLocaleHost('ru.forecasteconomy.com')).toBe(true);
  });

  it('localhost EN stays on the current origin with preview_locale=en', () => {
    expect(languageAlternateOrigin('en', {
      hostname: 'localhost',
      currentOrigin: 'http://localhost:3000',
      apexLocaleEn: false,
    })).toBe('http://localhost:3000');

    const next = buildLanguageSwitchUrl('en', {
      href: 'http://localhost:3000/',
      hostname: 'localhost',
      apexLocaleEn: false,
    });
    const url = new URL(next);
    expect(url.origin).toBe('http://localhost:3000');
    expect(url.hostname).not.toBe('forecasteconomy.com');
    expect(url.searchParams.get('preview_locale')).toBe('en');
    expect(url.searchParams.get('locale_pref')).toBe('en');
  });

  it('apex until cutover stays on the same host with preview_locale=en', () => {
    expect(languageAlternateOrigin('en', {
      hostname: 'forecasteconomy.com',
      currentOrigin: 'https://forecasteconomy.com',
      apexLocaleEn: false,
    })).toBe('https://forecasteconomy.com');

    const next = buildLanguageSwitchUrl('en', {
      href: 'https://forecasteconomy.com/russia/today',
      hostname: 'forecasteconomy.com',
      apexLocaleEn: false,
    });
    const url = new URL(next);
    expect(url.origin).toBe('https://forecasteconomy.com');
    expect(url.pathname).toBe('/russia/today');
    expect(url.searchParams.get('preview_locale')).toBe('en');
  });

  it('RU from an EN preview drops preview_locale and stays on origin', () => {
    const next = buildLanguageSwitchUrl('ru', {
      href: 'http://localhost:5173/?preview_locale=en&x=1',
      hostname: 'localhost',
      apexLocaleEn: false,
    });
    const url = new URL(next);
    expect(url.origin).toBe('http://localhost:5173');
    expect(url.searchParams.get('preview_locale')).toBeNull();
    expect(url.searchParams.get('locale_pref')).toBe('ru');
    expect(url.searchParams.get('x')).toBe('1');
  });

  it('after cutover on prod hosts path-identical host-swap without preview', () => {
    expect(languageAlternateOrigin('en', {
      hostname: 'ru.forecasteconomy.com',
      currentOrigin: 'https://ru.forecasteconomy.com',
      apexLocaleEn: true,
    })).toBe('https://forecasteconomy.com');
    expect(languageAlternateOrigin('ru', {
      hostname: 'forecasteconomy.com',
      currentOrigin: 'https://forecasteconomy.com',
      apexLocaleEn: true,
    })).toBe('https://ru.forecasteconomy.com');

    const toEn = new URL(buildLanguageSwitchUrl('en', {
      href: 'https://ru.forecasteconomy.com/russia/indicator/cpi',
      hostname: 'ru.forecasteconomy.com',
      apexLocaleEn: true,
    }));
    expect(toEn.origin).toBe('https://forecasteconomy.com');
    expect(toEn.pathname).toBe('/russia/indicator/cpi');
    expect(toEn.searchParams.get('preview_locale')).toBeNull();
    expect(toEn.searchParams.get('locale_pref')).toBe('en');

    const toRu = new URL(buildLanguageSwitchUrl('ru', {
      href: 'https://forecasteconomy.com/canada/indicator/ca-weo-ngdpd',
      hostname: 'forecasteconomy.com',
      apexLocaleEn: true,
    }));
    expect(toRu.origin).toBe('https://ru.forecasteconomy.com');
    expect(toRu.pathname).toBe('/canada/indicator/ca-weo-ngdpd');
    expect(toRu.searchParams.get('preview_locale')).toBeNull();
    expect(toRu.searchParams.get('locale_pref')).toBe('ru');

    const localhostCutover = new URL(buildLanguageSwitchUrl('en', {
      href: 'http://localhost:3000/',
      hostname: 'localhost',
      apexLocaleEn: true,
    }));
    expect(localhostCutover.origin).toBe('http://localhost:3000');
    expect(localhostCutover.searchParams.get('preview_locale')).toBe('en');
  });
});

describe('stickyPreviewFromPreference', () => {
  it('keeps EN on gated apex / localhost until cutover', () => {
    expect(stickyPreviewFromPreference('en', {
      host: 'forecasteconomy.com',
      apexLocaleEn: false,
    })).toBe('en');
    expect(stickyPreviewFromPreference('en', { host: 'localhost', apexLocaleEn: false })).toBe('en');
  });

  it('does not override en./ru. hosts or post-cutover apex', () => {
    expect(stickyPreviewFromPreference('ru', {
      host: 'en.forecasteconomy.com',
      apexLocaleEn: false,
    })).toBeNull();
    expect(stickyPreviewFromPreference('en', {
      host: 'forecasteconomy.com',
      apexLocaleEn: true,
    })).toBeNull();
  });
});

describe('localeCookieDomain', () => {
  it('shares cookie across apex and ru. subdomain', () => {
    expect(localeCookieDomain('forecasteconomy.com')).toBe('.forecasteconomy.com');
    expect(localeCookieDomain('ru.forecasteconomy.com')).toBe('.forecasteconomy.com');
    expect(localeCookieDomain('www.forecasteconomy.com')).toBe('.forecasteconomy.com');
    expect(localeCookieDomain('localhost')).toBe('');
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
