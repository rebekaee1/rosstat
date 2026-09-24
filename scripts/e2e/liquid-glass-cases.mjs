/** Representative families, not an exhaustive inventory of public URLs.
 * Codes below were checked against the local database on 2026-09-24.
 * US subnational examples are configured routes; they require populated tables.
 */
export const wage = 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy';
const c = (id, path, family, extra = {}) => ({ id, path, family, status: 200, ...extra });
export const cases = [
  c('home', '/', 'spa-home', { representative: true }),
  c('russia', '/russia', 'spa-country'),
  c('category', '/russia/category/prices', 'spa-category'),
  c('cpi', '/russia/indicator/cpi', 'spa-bespoke-cpi', { representative: true }),
  c('housing', '/russia/indicator/housing-price-primary', 'spa-bespoke-housing'),
  c('ppi', '/russia/indicator/ppi', 'spa-bespoke-ppi'),
  c('key-rate', '/russia/indicator/key-rate', 'spa-generic-step'),
  c('national-year', '/russia/indicator/cpi/2025', 'ssr-national-year', { image: true, representative: true }),
  c('national-historic-year', '/russia/indicator/population/1897', 'ssr-national-historical-year', { image: true }),
  c('national-month', '/russia/indicator/cpi/2025-08', 'ssr-national-month', { image: true }),
  c('regions', '/russia/region', 'spa-region-hub'),
  c('region', '/russia/region/tulskaya-oblast', 'spa-region-profile'),
  c('region-indicator', `/russia/region/tulskaya-oblast/${wage}`, 'spa-region-indicator', {
    // The page probes monthly availability before selecting its existing annual series.
    expected404: [`/api/v1/regions/tulskaya-oblast/i/${wage}/monthly`],
  }),
  c('region-year', `/russia/region/tulskaya-oblast/${wage}/2024`, 'ssr-region-year', { image: true, representative: true }),
  c('region-map', `/russia/region/map/${wage}`, 'spa-region-map'),
  c('region-rating', `/russia/region-rating/${wage}`, 'ssr-region-rating', { image: true }),
  c('region-compare', '/russia/region-vs/moskva-vs-tulskaya-oblast', 'ssr-region-comparison', { image: true }),
  c('germany', '/germany', 'spa-world-country'),
  c('world-indicator', '/germany/indicator/de-weo-ngdpd', 'spa-world-indicator'),
  c('world-year', '/germany/indicator/de-weo-ngdpd/2024', 'ssr-world-year', { image: true, representative: true }),
  c('world-rating', '/world/rating/gdp-usd', 'ssr-world-rating', {
    image: true, continuation: { selector: 'a.seo-chart-link', path: '/world/rating/gdp-usd', spa: true },
  }),
  c('world-rating-year', '/world/rating/gdp-usd/2024', 'ssr-world-rating-year', {
    image: true, continuation: { selector: 'a.seo-chart-link', path: '/world/rating/gdp-usd', year: '2024', spa: true },
  }),
  c('world-compare', '/france-vs-germany/gdp-usd', 'ssr-world-comparison', { image: true }),
  c('us-national', '/united-states/indicator/us-gdp-real', 'spa-us-national'),
  c('us-regions', '/united-states/regions', 'spa-subnational-hub', { subnational: true }),
  c('us-region-map', '/united-states/region/map/unemployment-rate', 'spa-subnational-map', { subnational: true }),
  c('us-region', '/united-states/region/california', 'spa-subnational-profile', { subnational: true }),
  c('us-region-indicator', '/united-states/region/california/unemployment-rate', 'spa-subnational-indicator', { subnational: true, representative: true }),
  c('us-region-annual', '/united-states/region/california/real-gdp', 'spa-subnational-annual', { subnational: true }),
  c('us-region-quarterly', '/united-states/region/california/house-price-index', 'spa-subnational-quarterly', { subnational: true }),
  c('compare', '/compare', 'spa-compare'),
  c('calculator', '/calculator', 'spa-calculator'),
  c('today', '/russia/today', 'ssr-today', { image: true }),
  c('calendar', '/russia/calendar', 'spa-calendar'),
  c('calendar-month', '/russia/calendar/2027/07', 'ssr-calendar-month'),
  c('demographics', '/russia/demographics', 'spa-demographics', { image: true }),
  c('invalid-year', '/russia/indicator/cpi/1899', 'negative-year', { status: 404, browser: false }),
  c('out-of-range-year', '/russia/indicator/cpi/9999', 'negative-year-format', { status: 404, browser: false }),
  c('five-digit-year', '/germany/indicator/de-weo-ngdpd/10000', 'negative-year-format', { status: 404, browser: false }),
  c('invalid-code', '/russia/indicator/qa-nonexistent-series-20260924/2025', 'negative-series', { status: 404, browser: false }),
  c('missing-us-series', '/united-states/region/alabama/minimum-wage', 'negative-subnational-data', { status: 404, browser: false, subnational: true }),
];

export const widths = [320, 390, 768, 1024, 1440, 1920, 2560];

export const apiCases = [
  { id: 'national', path: '/api/v1/indicators/cpi/data', points: 'data', min: 12 },
  { id: 'regional', path: `/api/v1/regions/tulskaya-oblast/i/${wage}`, points: 'series', min: 2 },
  { id: 'world', path: '/api/v1/world/indicators/germany/de-weo-ngdpd/data', points: 'points', min: 2 },
  { id: 'us-national', path: '/api/v1/world/indicators/united-states/us-gdp-real/data', points: 'points', min: 2 },
  { id: 'us-subnational', path: '/api/v1/world/united-states/regions/region/california/unemployment-rate', points: 'series', min: 2, subnational: true },
];
