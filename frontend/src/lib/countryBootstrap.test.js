/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import {
  COUNTRY_BOOTSTRAP_ID,
  preloadedFigurePoints,
  readCountryBootstrap,
  resetCountryBootstrapCache,
} from './countryBootstrap';

function mountBootstrap(payload) {
  const el = document.createElement('script');
  el.type = 'application/json';
  el.id = COUNTRY_BOOTSTRAP_ID;
  el.textContent = typeof payload === 'string' ? payload : JSON.stringify(payload);
  document.head.appendChild(el);
}

const ENTRY = {
  concept_slug: 'unemployment-rate',
  indicator_code: 'de-une',
  frequency: 'monthly',
  date: '2026-06-01',
  value: 3.4,
  points: [['2026-04-01', 3.2], ['2026-05-01', 3.3], ['2026-06-01', 3.4]],
};

function payload(overrides = {}) {
  return {
    v: 1, slug: 'germany', locale: 'ru', country: { code: 'DE', name: 'Германия' }, overview: [ENTRY], ...overrides,
  };
}

afterEach(() => {
  resetCountryBootstrapCache();
  document.getElementById(COUNTRY_BOOTSTRAP_ID)?.remove();
});

describe('countryBootstrap', () => {
  it('читает предзагрузку своей страны и языка', () => {
    mountBootstrap(payload());
    const data = readCountryBootstrap('germany', 'ru');
    expect(data.overview).toHaveLength(1);
    expect(data.country.name).toBe('Германия');
  });

  it('без элемента, с битым JSON или чужой версией возвращает null', () => {
    expect(readCountryBootstrap('germany', 'ru')).toBeNull();
    resetCountryBootstrapCache();
    mountBootstrap('{broken');
    expect(readCountryBootstrap('germany', 'ru')).toBeNull();
    resetCountryBootstrapCache();
    document.getElementById(COUNTRY_BOOTSTRAP_ID).remove();
    mountBootstrap(payload({ v: 2 }));
    expect(readCountryBootstrap('germany', 'ru')).toBeNull();
  });

  it('другая страна или другой язык не используют чужие цифры', () => {
    mountBootstrap(payload());
    expect(readCountryBootstrap('france', 'ru')).toBeNull();
    expect(readCountryBootstrap('germany', 'en')).toBeNull();
  });

  it('пустой overview не считается предзагрузкой', () => {
    mountBootstrap(payload({ overview: [] }));
    expect(readCountryBootstrap('germany', 'ru')).toBeNull();
  });
});

describe('preloadedFigurePoints', () => {
  const data = payload();
  const item = { ...ENTRY, points: undefined };

  it('отдаёт точки для той же карточки', () => {
    expect(preloadedFigurePoints(data, item)).toEqual([
      { date: '2026-04-01', value: 3.2 },
      { date: '2026-05-01', value: 3.3 },
      { date: '2026-06-01', value: 3.4 },
    ]);
  });

  it('если живой каталог новее серверного снимка, предзагрузка не подходит', () => {
    expect(preloadedFigurePoints(data, { ...item, date: '2026-07-01' })).toBeNull();
    expect(preloadedFigurePoints(data, { ...item, value: 3.5 })).toBeNull();
    expect(preloadedFigurePoints(data, { ...item, indicator_code: 'other' })).toBeNull();
  });

  it('ряд из одной точки график не рисует: нужна сеть', () => {
    const one = payload({ overview: [{ ...ENTRY, points: [['2026-06-01', 3.4]] }] });
    expect(preloadedFigurePoints(one, item)).toBeNull();
    expect(preloadedFigurePoints(null, item)).toBeNull();
  });
});
