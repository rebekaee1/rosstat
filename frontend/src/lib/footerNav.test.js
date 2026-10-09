import { describe, expect, it } from 'vitest';
import { footerHomeCountryColumn, footerSourceLinks, footerWorldLinks } from './footerNav';

describe('footer hub crawl paths', () => {
  it('RU country column links today and regional rankings', () => {
    const hrefs = footerHomeCountryColumn('ru').links.map((link) => link.to);
    expect(hrefs).toContain('/russia/today');
    expect(hrefs).toContain('/russia/region-rating');
    expect(hrefs).toContain('/russia/region');
    expect(hrefs).toContain('/russia/calendar');
  });

  it('EN world column reaches the same hubs with descriptive keys', () => {
    const links = footerWorldLinks('en');
    const hrefs = links.map((link) => link.to);
    expect(hrefs).toContain('/russia/today');
    expect(hrefs).toContain('/russia/region-rating');
    expect(hrefs).toContain('/russia/calendar');
    expect(hrefs).toContain('/russia/demographics');
    expect(links.map((link) => link.key)).toContain('footer.economyToday');
    expect(links.map((link) => link.key)).toContain('footer.regionRatings');
  });

  it('RU world column does not repeat the Russia silo', () => {
    const hrefs = footerWorldLinks('ru').map((link) => link.to);
    expect(hrefs).not.toContain('/russia/today');
    expect(hrefs).not.toContain('/russia/region-rating');
  });
});

describe('footer sources by page (круг 11, G, U19)', () => {
  const keys = (locale, path) => footerSourceLinks(locale, path).map((item) => item.key);

  it('EN: на страницах России источники российские, на странице Турции МВФ, Евростат и Банк России', () => {
    expect(keys('en', '/russia')).toEqual(['footer.rosstat', 'footer.cbr', 'footer.minfin', 'footer.imf', 'footer.eurostat']);
    expect(keys('en', '/russia/indicator/cpi')).toContain('footer.rosstat');
    expect(keys('en', '/currencies/indicator/usd-rub')).toContain('footer.cbr');
    expect(keys('en', '/turkey')).toEqual(['footer.imf', 'footer.eurostat', 'footer.cbr']);
    expect(keys('en', '/turkey/indicator/hicp-index')).toContain('footer.cbr');
  });

  it('EN: остальные страницы и главная сохраняют прежний список (США и ЕС)', () => {
    expect(keys('en', '/')).toEqual(keys('en'));
    expect(keys('en', '/germany')).toContain('footer.bls');
    expect(keys('en', '/united-states')).toContain('footer.fred');
  });

  it('RU: список не зависит от страницы', () => {
    expect(keys('ru', '/turkey')).toEqual(keys('ru', '/'));
    expect(keys('ru', '/')).toContain('footer.rosstat');
  });

  it('у каждого источника контекста есть ссылка', () => {
    for (const path of ['/russia', '/turkey']) {
      for (const item of footerSourceLinks('en', path)) expect(item.href).toMatch(/^https:\/\//);
    }
  });
});
