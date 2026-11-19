import { describe, expect, it } from 'vitest';
import { isSamePageUrlSync } from './routeHit';

const MAP = '/russia/region/map/chislennost-pensionerov-vsego';

describe('isSamePageUrlSync', () => {
  it('year on the map written into the URL by replace is not a new page', () => {
    expect(isSamePageUrlSync({ navigationType: 'REPLACE', prevPathname: MAP, nextPathname: MAP })).toBe(true);
  });

  it('replace with another path (canonical redirect, another map indicator) is a new page', () => {
    expect(isSamePageUrlSync({
      navigationType: 'REPLACE', prevPathname: MAP, nextPathname: '/russia/region/map/uroven-bezrabotitsy',
    })).toBe(false);
  });

  it('link click and back/forward on the same path stay page views', () => {
    expect(isSamePageUrlSync({ navigationType: 'PUSH', prevPathname: MAP, nextPathname: MAP })).toBe(false);
    expect(isSamePageUrlSync({ navigationType: 'POP', prevPathname: MAP, nextPathname: MAP })).toBe(false);
  });
});
