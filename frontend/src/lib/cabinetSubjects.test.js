import { describe, expect, it } from 'vitest';
import {
  countrySubject, ratingViewSubject, regionIndicatorSubject, regionSubject, russiaIndicatorSubject, worldIndicatorSubject,
} from './cabinetSubjects';

describe('предметы для кнопок кабинета', () => {
  it('российский показатель: вид indicator, слежение по коду, адрес для «Открыть»', () => {
    expect(russiaIndicatorSubject('cpi', ' Инфляция ')).toEqual({
      kind: 'indicator',
      itemKey: 'cpi',
      title: 'Инфляция',
      payload: { path: '/russia/indicator/cpi' },
      watch: { subjectKind: 'indicator', subjectKey: 'cpi' },
    });
    expect(russiaIndicatorSubject('cpi', 'Инфляция', { only: 'watch' }).only).toBe('watch');
    expect(russiaIndicatorSubject('', 'x')).toBeNull();
  });

  it('показатель страны, страна и регион', () => {
    const world = worldIndicatorSubject('turkey', 'tr-weo-ggxcnl', 'Баланс бюджета');
    expect(world.kind).toBe('world');
    expect(world.payload.path).toBe('/turkey/indicator/tr-weo-ggxcnl');
    expect(world.watch).toEqual({ subjectKind: 'world', subjectKey: 'tr-weo-ggxcnl', countrySlug: 'turkey' });
    expect(countrySubject('turkey', 'Турция').watch).toBeNull();
    expect(regionSubject('moskva', 'Москва').kind).toBe('region');
    expect(regionIndicatorSubject('moskva', 'uroven-bezrabotitsy', 'Безработица').watch.subjectKey).toBe('uroven-bezrabotitsy');
    expect(countrySubject('', 'x')).toBeNull();
  });

  it('вид рейтинга: один и тот же набор даёт один и тот же ключ, группа и колонки в адресе', () => {
    const a = ratingViewSubject({ concept: 'gdp-usd', year: 2025, group: 'g7', cols: ['hicp-index'], title: 'ВВП' });
    const b = ratingViewSubject({ concept: 'gdp-usd', year: 2024, group: 'g7', cols: ['hicp-index'], title: 'ВВП' });
    expect(a.itemKey).toBe(b.itemKey);
    expect(a.kind).toBe('rating_view');
    expect(a.payload.path).toContain('group=g7');
    expect(a.payload.path).toContain('cols=hicp-index');
    expect(ratingViewSubject({ concept: 'gdp-usd' }).itemKey).toBe('gdp-usd');
    expect(ratingViewSubject({})).toBeNull();
  });
});
