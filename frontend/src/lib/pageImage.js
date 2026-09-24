import { isReservedFirstSegment, WORLD_RATING_DEFAULT_CONCEPT } from './sitePaths';

export const GENERIC_PAGE_IMAGE = '/og-image-v3.png';

/** Public image routes mirror nginx and the shared server renderer.
 * A page without its own data image always resets to the brand preview.
 */
export function pageImagePath(pathname = '/') {
  const path = pathname.split(/[?#]/)[0].replace(/\/+$/, '') || '/';
  const year = new URLSearchParams(pathname.split('?')[1]?.split('#')[0]).get('year');
  const country = path.split('/')[1];
  const isWorldCountry = country !== 'russia' && country !== '404' && !isReservedFirstSegment(country);
  let match;
  if (path === '/russia/demographics') return '/og/russia/demographics.png';
  if ((match = path.match(/^\/russia\/indicator\/([a-z0-9-]+)(?:\/(\d{4}(?:-(?:0[1-9]|1[0-2]))?))?$/))) {
    return `/og/russia/${match[1]}${match[2] ? `/${match[2]}` : ''}.png`;
  }
  // Maps are not a region called "map". Russia reuses the matching ranking
  // image, as its SSR does; subnational maps share their country-region hub.
  if ((match = path.match(/^\/russia\/region\/map\/([a-z0-9-]+)$/))) {
    if (match[1] === 'overview') return GENERIC_PAGE_IMAGE;
    return `/og/russia/region-rating/${match[1]}.png${/^\d{4}$/.test(year || '') ? `?year=${year}` : ''}`;
  }
  if ((match = path.match(/^\/russia\/region\/([a-z0-9-]+)\/([a-z0-9-]+)(?:\/(\d{4}))?$/))) {
    return `/og/russia/region/${match[1]}/${match[2]}${match[3] ? `/${match[3]}` : ''}.png`;
  }
  if ((match = path.match(/^\/russia\/(region-rating|region-vs)\/([a-z0-9-]+)$/))) {
    const period = match[1] === 'region-rating' && /^\d{4}$/.test(year || '') ? `?year=${year}` : '';
    return `/og/russia/${match[1]}/${match[2]}.png${period}`;
  }
  if ((match = path.match(/^\/russia\/today(?:\/([a-z0-9-]+))?$/))) {
    return match[1] ? `/og/russia/${match[1]}.png` : '/og/russia/today.png';
  }
  if ((match = path.match(/^\/world\/rating\/([a-z0-9-]+)(?:\/(\d{4}))?$/))) {
    const period = match[2] || (/^\d{4}$/.test(year || '') ? year : null);
    return `/og/world/rating/${match[1]}${period ? `/${period}` : ''}.png`;
  }
  if (path === '/world/rating') return `/og/world/rating/${WORLD_RATING_DEFAULT_CONCEPT}.png`;
  if ((match = path.match(/^\/([a-z0-9-]+)-vs-([a-z0-9-]+)\/([a-z0-9-]+)$/))) {
    return `/og/world-vs/${match[1]}-vs-${match[2]}/${match[3]}.png`;
  }
  if (isWorldCountry && (match = path.match(/^\/([a-z0-9-]+)\/indicator\/([a-z0-9_.-]+)(?:\/(\d{4}))?$/))) {
    return `/og/world/${match[1]}/${match[2]}${match[3] ? `/${match[3]}` : ''}.png`;
  }
  if (isWorldCountry && (match = path.match(/^\/([a-z0-9-]+)\/(?:regions|region\/map\/[a-z0-9-]+)$/))) {
    return `/og/world/${match[1]}/regions.png`;
  }
  if (isWorldCountry && (match = path.match(/^\/([a-z0-9-]+)\/region\/([a-z0-9-]+)(?:\/([a-z0-9-]+))?$/))) {
    return `/og/world/${match[1]}/region/${match[2]}${match[3] ? `/${match[3]}` : ''}.png`;
  }
  if (isWorldCountry && /^\/[a-z0-9-]+$/.test(path)) return `/og/world/${country}.png`;
  return GENERIC_PAGE_IMAGE;
}
