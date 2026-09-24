import { describe, expect, it } from 'vitest';
import { GENERIC_PAGE_IMAGE, pageImagePath } from './pageImage';

describe('pageImagePath public page families', () => {
  it.each([
    ['/russia/indicator/cpi', '/og/russia/cpi.png'],
    ['/russia/indicator/cpi/2025', '/og/russia/cpi/2025.png'],
    ['/russia/indicator/cpi/2025-07/?utm_source=test#chart', '/og/russia/cpi/2025-07.png'],
    ['/russia/region/moskva/wages', '/og/russia/region/moskva/wages.png'],
    ['/russia/region/moskva/wages/2023', '/og/russia/region/moskva/wages/2023.png'],
    ['/russia/region-rating/wages', '/og/russia/region-rating/wages.png'],
    ['/russia/region-rating/wages?year=2023', '/og/russia/region-rating/wages.png?year=2023'],
    ['/russia/region-vs/moskva-vs-tulskaya-oblast', '/og/russia/region-vs/moskva-vs-tulskaya-oblast.png'],
    ['/russia/region/map/wages?year=2023', '/og/russia/region-rating/wages.png?year=2023'],
    ['/russia/today', '/og/russia/today.png'],
    ['/russia/today/key-rate', '/og/russia/key-rate.png'],
    ['/russia/demographics', '/og/russia/demographics.png'],
    ['/germany', '/og/world/germany.png'],
    ['/germany/indicator/de-prc_hicp_midx-cp00-i15', '/og/world/germany/de-prc_hicp_midx-cp00-i15.png'],
    ['/germany/indicator/de-gdp/2024', '/og/world/germany/de-gdp/2024.png'],
    ['/world/rating/gdp-usd', '/og/world/rating/gdp-usd.png'],
    ['/world/rating/gdp-usd/2024', '/og/world/rating/gdp-usd/2024.png'],
    ['/world/rating/gdp-usd?year=2024', '/og/world/rating/gdp-usd/2024.png'],
    ['/germany-vs-united-states/gdp-usd', '/og/world-vs/germany-vs-united-states/gdp-usd.png'],
    ['/united-states/regions', '/og/world/united-states/regions.png'],
    ['/united-states/region/california', '/og/world/united-states/region/california.png'],
    ['/united-states/region/california/building-permits', '/og/world/united-states/region/california/building-permits.png'],
    ['/united-states/region/map/unemployment-rate?year=2024', '/og/world/united-states/regions.png'],
  ])('%s uses its existing image family', (path, image) => {
    expect(pageImagePath(path)).toBe(image);
  });

  it.each([
    '/', '/russia', '/about', '/methodology', '/privacy', '/terms', '/login',
    '/account', '/register', '/404', '/calculator', '/calculator/mortgage',
    '/compare?codes=cpi,key-rate', '/russia/category/prices', '/russia/region/moskva',
    '/russia/region/map/overview', '/russia/calendar/2024/12',
    '/about/indicator/cpi', '/russia/indicator/cpi/2024-99',
  ])('%s resets to a generic preview instead of a stale or invented graph', (path) => {
    expect(pageImagePath(path)).toBe(GENERIC_PAGE_IMAGE);
  });
});
