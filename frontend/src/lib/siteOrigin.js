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

export function getSiteOrigin() {
  if (typeof window === 'undefined' || !window.location?.hostname) {
    return BUILD_ORIGIN;
  }
  const host = window.location.hostname.toLowerCase();
  if (PRODUCTION_HOST_RE.test(host) || host.startsWith('ru.') || host.startsWith('en.')) {
    return String(window.location.origin || BUILD_ORIGIN).replace(/\/$/, '');
  }
  return BUILD_ORIGIN;
}

/** Build-time / SSR-fallback origin (не host-aware). Для runtime — getSiteOrigin(). */
export const SITE_ORIGIN = BUILD_ORIGIN;

export const SITE_HOST = SITE_ORIGIN.replace(/^https?:\/\//, '');
