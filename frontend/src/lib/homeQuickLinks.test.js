import { describe, expect, it } from 'vitest';
import { buildQuickLinks } from './homeQuickLinks';

describe('homeQuickLinks', () => {
  it('русский набор: курс доллара, инфляция и ставка России ведут сразу на страницу показателя', () => {
    const links = buildQuickLinks({ locale: 'ru' });
    expect(links.map((link) => link.id)).toEqual(['usd-rub', 'ru-inflation', 'key-rate', 'india-gdp', 'turkey-inflation']);
    expect(links[0].to).toBe('/currencies/indicator/usd-rub');
    expect(links[1].to).toBe('/russia/indicator/cpi-yoy');
    expect(links[2].to).toBe('/russia/indicator/key-rate');
  });

  it('ВВП Индии до загрузки среза ведёт на страницу страны, после загрузки сразу на показатель', () => {
    expect(buildQuickLinks({ locale: 'ru' })[3].to).toBe('/india');
    const gdp = { items: [{ country_code: 'IN', country_slug: 'india', indicator_code: 'weo-gdp-usd', value: 1, unit: '' }] };
    expect(buildQuickLinks({ locale: 'ru', gdp })[3].to).toBe('/india/indicator/weo-gdp-usd');
  });

  it('английский набор без российских ссылок', () => {
    const links = buildQuickLinks({ locale: 'en' });
    expect(links.map((link) => link.id)).toEqual(['us-inflation', 'fed-rate', 'eur-usd', 'india-gdp', 'turkey-inflation']);
    expect(links.some((link) => link.to.startsWith('/russia'))).toBe(false);
    expect(links[1].to).toBe('/united-states/indicator/us-policy-rate');
  });
});
