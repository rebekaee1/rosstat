import { describe, expect, it } from 'vitest';
import { pickPeers } from './indicatorPeers';

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
