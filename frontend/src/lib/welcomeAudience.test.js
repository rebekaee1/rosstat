import { describe, expect, it } from 'vitest';
import { countrySlug, detectVisitorCountry, welcomeAudience } from './welcomeAudience';

describe('приветственный экран: чьи источники показать', () => {
  it('часовой пояс сильнее языка: en-US в Лондоне — это Великобритания', () => {
    expect(detectVisitorCountry({ timeZone: 'Europe/London', languages: ['en-US', 'en'] })).toBe('GB');
    expect(welcomeAudience({ timeZone: 'Europe/London', languages: ['en-US'] }).sources).toEqual(['ONS', 'Bank of England', 'IMF']);
  });

  it('США: пояс или en-US без возражений пояса', () => {
    expect(welcomeAudience({ timeZone: 'America/Chicago', languages: ['en-US'] }).key).toBe('US');
    expect(welcomeAudience({ timeZone: null, languages: ['en-US'] }).sources).toEqual(['FRED', 'BLS', 'BEA']);
  });

  it('en-US в незнакомом поясе не выдаётся за США: общий международный набор', () => {
    const a = welcomeAudience({ timeZone: 'Africa/Lagos', languages: ['en-US', 'en'] });
    expect(a.key).toBe('WORLD');
    expect(a.sources).toEqual(['IMF', 'Eurostat', 'FRED']);
  });

  it('страны Евросоюза и ЕАСТ получают Евростат, ЕЦБ и МВФ, а в сравнении стоит их страна', () => {
    const de = welcomeAudience({ timeZone: 'Europe/Berlin', languages: ['de-DE', 'en'] });
    expect(de).toMatchObject({ key: 'EU', sources: ['Eurostat', 'ECB', 'IMF'], home: 'Germany', peer: 'France' });
    const fr = welcomeAudience({ timeZone: null, languages: ['fr'] });
    expect(fr).toMatchObject({ key: 'EU', home: 'France', peer: 'Germany' });
  });

  it.each([
    ['America/Toronto', 'CA', 'Statistics Canada'],
    ['Australia/Sydney', 'AU', 'ABS'],
    ['Asia/Tokyo', 'JP', 'Bank of Japan'],
    ['Asia/Kolkata', 'IN', 'MOSPI'],
    ['America/Sao_Paulo', 'BR', 'Banco Central'],
    ['Asia/Shanghai', 'CN', 'NBS'],
  ])('%s → %s, первым стоит национальное ведомство', (timeZone, key, first) => {
    const a = welcomeAudience({ timeZone, languages: ['en'] });
    expect(a.key).toBe(key);
    expect(a.sources[0]).toBe(first);
  });

  it('ничего не известно или мусор — общий набор, без падений', () => {
    for (const signals of [undefined, {}, { timeZone: 'Mars/Olympus', languages: [null, 42, ''] }, { languages: 'en' }]) {
      const a = welcomeAudience(signals);
      expect(a.key).toBe('WORLD');
      expect(a.home).toBe('United States');
      expect(a.peer).toBe('Germany');
    }
  });

  it('регион берётся и из тега с письменностью (zh-Hans-CN)', () => {
    expect(detectVisitorCountry({ timeZone: null, languages: ['zh-Hans-CN'] })).toBe('CN');
    expect(detectVisitorCountry({ timeZone: null, languages: ['pt-BR'] })).toBe('BR');
  });

  it('у набора есть адреса стран на сайте: по ним берётся настоящий ряд', () => {
    expect(countrySlug('United Kingdom')).toBe('united-kingdom');
    expect(countrySlug('United States')).toBe('united-states');
    const gb = welcomeAudience({ timeZone: 'Europe/London', languages: ['en-GB'] });
    expect(gb).toMatchObject({ homeSlug: 'united-kingdom', peerSlug: 'germany' });
    const world = welcomeAudience({});
    expect(world).toMatchObject({ homeSlug: 'united-states', peerSlug: 'germany' });
  });
});
