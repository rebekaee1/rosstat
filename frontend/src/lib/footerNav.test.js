import { describe, expect, it } from 'vitest';
import { footerHomeCountryColumn, footerWorldLinks } from './footerNav';

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
