/**
 * Публичный origin сайта (canonical / embed / Метrika file).
 *
 * Build-time default = текущий прод. В браузере на production-хостах
 * (apex / www / ru. / en.) берём ``window.location.origin``, чтобы
 * self-canonical и og:url совпадали с хостом запроса (ADR-0013 §F).
 * Localhost / preview → build-time origin (как раньше).
 */
const BUILD_ORIGIN = (
  import.meta.env.VITE_PUBLIC_BASE_URL || 'https://forecasteconomy.com'
).replace(/\/$/, '');

const PRODUCTION_HOST_RE = /^(?:www\.|ru\.|en\.)?forecasteconomy\.com$/i;

/**
 * Absolute page URL with the same serialization as the SSR canonical.
 * The site root has no trailing slash. hreflang hrefs must match this string.
 */
export function publicPageUrl(origin, path) {
  const base = String(origin || '').replace(/\/$/, '');
  const raw = path || '/';
  const q = raw.indexOf('?');
  let page = q === -1 ? raw : raw.slice(0, q);
  const query = q === -1 ? '' : raw.slice(q);
  if (!page.startsWith('/')) page = `/${page}`;
  if (page !== '/' && page.endsWith('/')) page = page.replace(/\/+$/, '') || '/';
  const url = page === '/' ? base : `${base}${page}`;
  return url + query;
}

export function getSiteOrigin() {
  if (typeof window === 'undefined' || !window.location?.hostname) {
    return BUILD_ORIGIN;
  }
  const host = window.location.hostname.toLowerCase();
  // www and en. are not locales. Canonical of those hosts is the apex,
  // matching backend resolve_request_origin (ru. stays the Russian origin).
  if (host === 'www.forecasteconomy.com' || host.startsWith('en.')) {
    return BUILD_ORIGIN;
  }
  if (PRODUCTION_HOST_RE.test(host) || host.startsWith('ru.')) {
    return String(window.location.origin || BUILD_ORIGIN).replace(/\/$/, '');
  }
  return BUILD_ORIGIN;
}

/** Build-time / SSR-fallback origin (не host-aware). Для runtime — getSiteOrigin(). */
export const SITE_ORIGIN = BUILD_ORIGIN;

export const SITE_HOST = SITE_ORIGIN.replace(/^https?:\/\//, '');
