import { describe, expect, it } from 'vitest';
import { pickPeers, rankRelatedIndicators, tourismParentCode } from './indicatorPeers';

const peers = [
  ['PL', 'poland', 'Польша', 'Poland'], ['DE', 'germany', 'Германия', 'Germany'], ['AT', 'austria', 'Австрия', 'Austria'],
  ['TR', 'turkey', 'Турция', 'Turkey'], ['FR', 'france', 'Франция', 'France'], ['BR', 'brazil', 'Бразилия', 'Brazil'],
].map(([code, slug, name, nameEn]) => ({
  country_code: code, country_slug: slug, country_name: name, country_name_en: nameEn, indicator_code: `${code.toLowerCase()}-x`,
}));

describe('pickPeers', () => {
  it('текущая страна не предлагается, крупные экономики первыми (по алфавиту названий), остальные тоже по алфавиту', () => {
    expect(pickPeers(peers, 'turkey', 'ru').map((p) => p.country_slug)).toEqual(['brazil', 'germany', 'france', 'austria', 'poland']);
  });

  it('названия на языке страницы, предел и мусор на входе', () => {
    expect(pickPeers(peers, '', 'en', 2).map((p) => p.name)).toEqual(['Brazil', 'France']);
    expect(pickPeers(null, 'x', 'ru')).toEqual([]);
    expect(pickPeers([{ country_slug: 'a' }], 'x', 'ru')).toEqual([]);
  });
});

describe('rankRelatedIndicators', () => {
  it('сначала ряды с общим началом кода, затем та же частота и единица; порядок раздела при равенстве', () => {
    const cur = { code: 'tour-outbound-trips', frequency: 'quarterly', unit: 'тыс. поездок' };
    const list = [
      { code: 'tour-agencies', frequency: 'annual', unit: 'ед.' },
      { code: 'tour-inbound-trips', frequency: 'quarterly', unit: 'тыс. поездок' },
      { code: 'tour-outbound-spend', frequency: 'annual', unit: 'млн $' },
      { code: 'tour-outbound-turkey', frequency: 'quarterly', unit: 'тыс. поездок' },
    ];
    expect(rankRelatedIndicators(cur, list).map((i) => i.code))
      .toEqual(['tour-outbound-turkey', 'tour-outbound-spend', 'tour-inbound-trips', 'tour-agencies']);
    expect(rankRelatedIndicators(cur, null)).toEqual([]);
  });
});

describe('tourismParentCode', () => {
  it('ряд по стране → родительский показатель; остальные ряды без родителя', () => {
    expect(tourismParentCode('tour-outbound-egypt')).toBe('tour-outbound-trips');
    expect(tourismParentCode('tour-inbound-china')).toBe('tour-inbound-trips');
    expect(tourismParentCode('tour-outbound-trips')).toBeNull();
    expect(tourismParentCode('cpi')).toBeNull();
    expect(tourismParentCode(undefined)).toBeNull();
  });
});
