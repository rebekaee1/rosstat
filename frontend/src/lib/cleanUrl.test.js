import { describe, it, expect } from 'vitest';
import { cleanSearch, cleanPathWithSearch } from './cleanUrl';

describe('cleanSearch', () => {
  it('strips Yandex etext marker', () => {
    expect(cleanSearch('?etext=2202.5NNLXIJb0-ki4cI0SaFLKeUEwLC2M_raAtIJpn3UfODF')).toBe('');
  });

  it('strips multiple tracking params at once', () => {
    expect(cleanSearch('?etext=abc&yclid=123&utm_source=ya')).toBe('');
  });

  it('preserves meaningful params alongside tracking ones', () => {
    expect(cleanSearch('?etext=abc&a=usd-rub&b=eur-rub')).toBe('?a=usd-rub&b=eur-rub');
  });

  it('returns empty string for empty/missing search', () => {
    expect(cleanSearch('')).toBe('');
    expect(cleanSearch('?')).toBe('');
    expect(cleanSearch(null)).toBe('');
  });

  it('keeps original search if no tracking params present', () => {
    expect(cleanSearch('?a=usd-rub&b=eur-rub')).toBe('?a=usd-rub&b=eur-rub');
  });

  it('strips ysclid (Yandex Search ClickID)', () => {
    expect(cleanSearch('?ysclid=lor7sw5p9o')).toBe('');
  });

  it('strips ybaip / openstat / igshid', () => {
    expect(cleanSearch('?ybaip=1&openstat=ad&igshid=xyz')).toBe('');
  });
});

describe('cleanPathWithSearch', () => {
  it('combines clean path with cleaned search', () => {
    expect(cleanPathWithSearch('/category/prices', '?etext=foo&utm_source=ya')).toBe('/category/prices');
  });

  it('preserves meaningful query params', () => {
    expect(cleanPathWithSearch('/compare', '?a=usd-rub&b=eur-rub&etext=x')).toBe('/compare?a=usd-rub&b=eur-rub');
  });
});
