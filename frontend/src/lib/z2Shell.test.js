// Раунд 2, зона Z2: чистые функции оболочки (меню, мега-панель, подвал, подсказки 404).
import { describe, expect, it } from 'vitest';
import { primaryNav, mobileNavGroups, resolveActiveNavId, RATES_TO } from './navItems';
import { megaCountries, megaIndicators } from './megaMenu';
import { footerToolLinks, footerWorldLinks } from './footerNav';
import { suggestForPath } from './notFoundSuggest';

describe('меню: «Курсы валют»', () => {
  it('пункт стоит после «Прогнозов» и до «России», с короткой подписью для 1280–1535 px', () => {
    const ids = primaryNav('ru').map((item) => item.id);
    expect(ids).toEqual(['countries', 'world-rating', 'compare', 'forecasts', 'currencies', 'russia']);
    const rates = primaryNav('ru').find((item) => item.id === 'currencies');
    expect(rates).toMatchObject({ to: '/currencies', labelKey: 'z2.nav.rates', shortLabelKey: 'z2.nav.ratesShort' });
    expect(RATES_TO).toBe('/currencies');
  });

  it('в английской версии он тоже есть, «Россия» заменена на США', () => {
    const ids = primaryNav('en').map((item) => item.id);
    expect(ids).toContain('currencies');
    expect(ids).toContain('united-states');
    expect(ids).not.toContain('russia');
  });

  it('подсвечивается на странице валют и на карточках курсов', () => {
    expect(resolveActiveNavId('/currencies')).toBe('currencies');
    expect(resolveActiveNavId('/currencies/indicator/usd-rub')).toBe('currencies');
  });

  it('меню телефона: «Курсы валют» на прежнем месте между категориями и методологией', () => {
    const main = mobileNavGroups('ru')[0].items.map((item) => item.id);
    expect(main.indexOf('currencies')).toBe(main.indexOf('categories') + 1);
    expect(mobileNavGroups('ru')[0].items.find((item) => item.id === 'currencies').labelKey).toBe('z2.nav.rates');
  });
});

describe('мега-панель стран', () => {
  it('двенадцать стран с флагом и названием на языке посетителя', () => {
    const ru = megaCountries('ru');
    expect(ru).toHaveLength(12);
    expect(ru[0]).toMatchObject({ slug: 'united-states', label: 'США', to: '/united-states' });
    expect(ru[0].flag).toBe('\u{1F1FA}\u{1F1F8}');
    expect(megaCountries('en')[0].label).toBe('United States');
    expect(ru.every((c) => c.flag && c.label && c.to)).toBe(true);
  });

  it('популярные рейтинги ведут на страницы рейтингов стран', () => {
    const list = megaIndicators();
    expect(list.map((i) => i.to)).toEqual(expect.arrayContaining(['/world/rating/gdp-usd', '/world/rating/unemployment-rate']));
    expect(list.every((i) => i.labelKey.startsWith('z2.mega.'))).toBe(true);
  });
});

describe('подвал: ссылки на новые разделы', () => {
  it('«Мир» получает «Прогнозы» и «Курсы валют», «Инструменты» начинаются с конвертера', () => {
    const keys = footerWorldLinks('ru').map((l) => l.key);
    expect(keys).toEqual(expect.arrayContaining(['w6b.nav.forecasts', 'z2.nav.rates']));
    const tools = footerToolLinks();
    expect(tools[0]).toMatchObject({ to: '/currencies', key: 'z2.tools.converter' });
    expect(tools.map((l) => l.to)).toEqual(['/currencies', '/calculator', '/calculator/mortgage', '/calculator/compound']);
  });
});

describe('404: подсказки', () => {
  it('/forecasts предлагает «Прогнозы» первыми, затем методологию', () => {
    const found = suggestForPath('/forecasts');
    expect(found[0]).toMatchObject({ labelKey: 'z2.nf.guess.forecasts' });
    expect(found.map((g) => g.labelKey)).toContain('w6f.nf.guess.methodology');
  });

  it('/compare и /prognozy тоже угадываются', () => {
    expect(suggestForPath('/compare')[0].to).toBe('/compare');
    expect(suggestForPath('/prognozy')[0].labelKey).toBe('z2.nf.guess.forecasts');
  });
});
