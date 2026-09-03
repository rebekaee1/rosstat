import ru from './messages.ru.js';
import en from './messages.en.js';
import { currentUiLocale } from './locale';

export const MESSAGES = { ru, en };

/**
 * Resolve a UI string. Used by LocaleProvider and non-React modules (breadcrumbs).
 * @param {string} key
 * @param {Record<string, string|number>|string} [varsOrFallback] object = {n} interp; string = fallback
 * @param {'ru'|'en'} [locale]
 */
export function translate(key, varsOrFallback, locale) {
  const loc = locale || currentUiLocale();
  const dict = MESSAGES[loc] || MESSAGES.ru;
  const has = Object.prototype.hasOwnProperty.call(dict, key);
  let text = has ? dict[key] : undefined;
  if (text == null) {
    if (typeof varsOrFallback === 'string') return varsOrFallback;
    text = MESSAGES.ru[key] || key;
  }
  if (varsOrFallback && typeof varsOrFallback === 'object') {
    text = String(text).replace(/\{(\w+)\}/g, (_, name) => (
      varsOrFallback[name] != null ? String(varsOrFallback[name]) : `{${name}}`
    ));
  }
  return text;
}

/** Standalone t() for modules outside React (bound UI locale, else host / preview). */
export function t(key, varsOrFallback, locale) {
  return translate(key, varsOrFallback, locale);
}

export function messageKeyCount(locale = 'ru') {
  return Object.keys(MESSAGES[locale] || {}).length;
}
