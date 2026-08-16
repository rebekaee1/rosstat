/**
 * Locale resolver (mirror of backend/app/services/locale.py).
 *
 * Language = host, not ?lang=. Localhost and non-apex hosts default to ru.
 * Production apex stays ru until VITE_APEX_LOCALE_EN=true (cutover with
 * ru. as Russian canon). Explicit EN: X-FE-Locale / en.* / preview_locale.
 * Vite-only: ?preview_locale=en (noindex, not canonical).
 */

export const LOCALE_HEADER = 'X-FE-Locale';
export const PREVIEW_QUERY = 'preview_locale';
export const PRODUCTION_APEX_HOSTS = new Set(['forecasteconomy.com', 'www.forecasteconomy.com']);

export function normalizeHost(host) {
  if (!host) return '';
  return String(host).split(',')[0].trim().toLowerCase().split(':')[0];
}

/** Build-time cutover flag (must match RUSTATS_APEX_LOCALE_EN on backend). */
export function apexLocaleEnEnabled(explicit) {
  if (explicit === true || explicit === false) return explicit;
  const v = import.meta.env?.VITE_APEX_LOCALE_EN;
  return v === 'true' || v === '1';
}

/**
 * @param {{ host?: string, header?: string, preview?: string|null, apexLocaleEn?: boolean }} opts
 * @returns {'ru'|'en'}
 */
export function resolveLocale({ host, header, preview, apexLocaleEn } = {}) {
  const raw = (header || '').trim().toLowerCase();
  if (raw === 'en' || raw === 'ru') return raw;

  const prev = (preview || '').trim().toLowerCase();
  if (prev === 'en' || prev === 'ru') return prev;

  const h = normalizeHost(host);
  if (h.startsWith('ru.')) return 'ru';
  if (h.startsWith('en.')) return 'en';
  if (PRODUCTION_APEX_HOSTS.has(h)) {
    return apexLocaleEnEnabled(apexLocaleEn) ? 'en' : 'ru';
  }
  return 'ru';
}

/** Browser entry: host + optional preview query (dev / explicit preview only). */
export function resolveBrowserLocale() {
  if (typeof window === 'undefined') return 'ru';
  const params = new URLSearchParams(window.location.search);
  const preview = params.get(PREVIEW_QUERY);
  return resolveLocale({
    host: window.location.hostname,
    preview,
  });
}

export function isPreviewLocaleActive() {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(window.location.search);
  const preview = params.get(PREVIEW_QUERY);
  return preview === 'en' || preview === 'ru';
}

export function htmlLang(locale) {
  return locale === 'en' ? 'en' : 'ru';
}

export function ogLocale(locale) {
  return locale === 'en' ? 'en_US' : 'ru_RU';
}

/** Swap host for language switcher links (path-identical). */
export function languageAlternateOrigin(locale, { ruOrigin, enOrigin } = {}) {
  const ru = (ruOrigin || 'https://ru.forecasteconomy.com').replace(/\/$/, '');
  const en = (enOrigin || 'https://forecasteconomy.com').replace(/\/$/, '');
  return locale === 'en' ? en : ru;
}
