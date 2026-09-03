/**
 * Locale resolver (mirror of backend/app/services/locale.py).
 *
 * Language = host, not ?lang=. After cutover (VITE_APEX_LOCALE_EN=true):
 * apex = en, ru.forecasteconomy.com = ru. Localhost and non-apex hosts
 * stay ru. Explicit EN: X-FE-Locale / en.* / preview_locale.
 * On production hosts the Russian flag goes to ru.forecasteconomy.com
 * (path-identical). Localhost never navigates onto production apex.
 */

export const LOCALE_HEADER = 'X-FE-Locale';
export const PREVIEW_QUERY = 'preview_locale';
export const PRODUCTION_APEX_HOSTS = new Set(['forecasteconomy.com', 'www.forecasteconomy.com']);
export const LOCALE_PREFERENCE_COOKIE = 'fe_locale_pref';
export const LOCALE_PREF_QUERY = 'locale_pref';

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

/**
 * Until cutover, an explicit language choice (cookie) sticks on apex / localhost
 * even after in-app Links drop `?preview_locale=`. Host prefixes `en.` / `ru.`
 * stay authoritative. Cookie is never a bot/SEO signal — SSR still uses host
 * + preview + X-FE-Locale.
 */
export function stickyPreviewFromPreference(pref, { host, apexLocaleEn } = {}) {
  if (apexLocaleEnEnabled(apexLocaleEn)) return null;
  const h = normalizeHost(host);
  if (h.startsWith('en.') || h.startsWith('ru.')) return null;
  if (pref === 'en' || pref === 'ru') return pref;
  return null;
}

export function readLocalePreference() {
  if (typeof document === 'undefined') return null;
  const prefix = `${LOCALE_PREFERENCE_COOKIE}=`;
  for (const part of String(document.cookie || '').split(';')) {
    const item = part.trim();
    if (!item.startsWith(prefix)) continue;
    const value = decodeURIComponent(item.slice(prefix.length)).trim().toLowerCase();
    if (value === 'en' || value === 'ru') return value;
  }
  return null;
}

/** Bound by LocaleProvider so chrome, crumbs, API and numbers share one locale. */
let boundUiLocale;

export function bindUiLocale(locale) {
  boundUiLocale = locale === 'en' || locale === 'ru' ? locale : undefined;
}

export function currentUiLocale() {
  if (boundUiLocale === 'en' || boundUiLocale === 'ru') return boundUiLocale;
  if (typeof window === 'undefined') return 'ru';
  return resolveBrowserLocale();
}

/** Browser entry: host + preview query + sticky preference until cutover. */
export function resolveBrowserLocale() {
  if (typeof window === 'undefined') return 'ru';
  const params = new URLSearchParams(window.location.search);
  const preview = params.get(PREVIEW_QUERY) || stickyPreviewFromPreference(
    readLocalePreference(),
    { host: window.location.hostname },
  );
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

/** Apex / ru. / en. production hosts — never localhost or docker names. */
export function isProductionLocaleHost(hostname) {
  const h = normalizeHost(hostname);
  if (!h) return false;
  if (PRODUCTION_APEX_HOSTS.has(h)) return true;
  return (
    h.endsWith('.forecasteconomy.com')
    && (h.startsWith('ru.') || h.startsWith('en.'))
  );
}

/**
 * After cutover, production hosts swap EN=apex / RU=ru.
 * Until then (and on localhost) the switcher stays on the current origin.
 */
export function usesHostSwapLanguageSwitch({ hostname, apexLocaleEn } = {}) {
  return apexLocaleEnEnabled(apexLocaleEn) && isProductionLocaleHost(hostname);
}

function _windowOrigin() {
  if (typeof window === 'undefined') return '';
  return String(window.location.origin || '').replace(/\/$/, '');
}

function _windowHostname() {
  if (typeof window === 'undefined') return '';
  return window.location.hostname;
}

/**
 * Origin for the language switcher.
 * Until cutover / non-prod hosts: current origin (preview_locale does the rest).
 * After cutover on prod hosts: path-identical host-swap.
 */
export function languageAlternateOrigin(locale, {
  ruOrigin,
  enOrigin,
  hostname,
  currentOrigin,
  apexLocaleEn,
} = {}) {
  const host = hostname || _windowHostname();
  const current = (currentOrigin || _windowOrigin()).replace(/\/$/, '');
  if (!usesHostSwapLanguageSwitch({ hostname: host, apexLocaleEn })) {
    return current;
  }
  const ru = (ruOrigin || 'https://ru.forecasteconomy.com').replace(/\/$/, '');
  const en = (enOrigin || 'https://forecasteconomy.com').replace(/\/$/, '');
  return locale === 'en' ? en : ru;
}

/** Shared cookie Domain for apex + ru. (host-only cookie on ru. is invisible on apex). */
export function localeCookieDomain(hostname) {
  const h = normalizeHost(hostname);
  if (h === 'forecasteconomy.com' || h.endsWith('.forecasteconomy.com')) {
    return '.forecasteconomy.com';
  }
  return '';
}

export function setLocalePreference(locale, { hostname, protocol } = {}) {
  if (typeof document === 'undefined' || !['ru', 'en'].includes(locale)) return;
  const host = hostname || (typeof window !== 'undefined' ? window.location.hostname : '');
  const proto = protocol || (typeof window !== 'undefined' ? window.location.protocol : '');
  const domain = localeCookieDomain(host);
  const domainPart = domain ? `; Domain=${domain}` : '';
  const secure = proto === 'https:' ? '; Secure' : '';
  document.cookie = `${LOCALE_PREFERENCE_COOKIE}=${locale}; Path=/; Max-Age=31536000; SameSite=Lax${domainPart}${secure}`;
}

/**
 * Target URL for the language switcher (testable without navigation).
 * Until cutover: same origin, EN sets preview_locale, RU clears it.
 * After cutover on prod: host-swap, preview stripped.
 * locale_pref stays so SSR persist can write the Domain cookie.
 */
export function buildLanguageSwitchUrl(locale, {
  href,
  hostname,
  apexLocaleEn,
  ruOrigin,
  enOrigin,
} = {}) {
  if (!['ru', 'en'].includes(locale)) return href || '';
  const currentHref = href || (typeof window !== 'undefined' ? window.location.href : '');
  if (!currentHref) return '';
  const current = new URL(currentHref);
  const host = hostname || current.hostname;
  const origin = languageAlternateOrigin(locale, {
    hostname: host,
    currentOrigin: current.origin,
    apexLocaleEn,
    ruOrigin,
    enOrigin,
  });
  const url = new URL(`${current.pathname}${current.search}${current.hash}`, origin);
  url.searchParams.set(LOCALE_PREF_QUERY, locale);
  if (usesHostSwapLanguageSwitch({ hostname: host, apexLocaleEn })) {
    url.searchParams.delete(PREVIEW_QUERY);
  } else if (locale === 'en') {
    url.searchParams.set(PREVIEW_QUERY, 'en');
  } else {
    url.searchParams.delete(PREVIEW_QUERY);
  }
  return url.toString();
}

/** Persist explicit choice, then navigate (preview until cutover, host-swap after). */
export function switchLanguage(locale, opts) {
  if (typeof window === 'undefined') return;
  setLocalePreference(locale);
  const next = buildLanguageSwitchUrl(locale, opts);
  if (next) window.location.assign(next);
}
