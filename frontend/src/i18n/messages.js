import { currentUiLocale, resolveBrowserLocale } from './locale';

/**
 * Словари грузятся динамически и только нужного языка: язык задаёт хост, смена языка перезагружает страницу.
 * Оба словаря в одном бандле стоили ~130 КБ gzip на каждом заходе (замер circle-12), нужный — 57–71 КБ.
 * Top-level await держит остальной код на прежней синхронной модели (`t()` и `MESSAGES` готовы к первому вызову).
 * Предзагрузку чанка языка в <head> ставит public/consent.js (токен __FE_LOCALE_CHUNKS__ подставляет vite.config.js),
 * иначе чанк пошёл бы только после выполнения main-*.js. В тестах и в Node (нет window) читаются оба словаря.
 */
export const MESSAGES = {};

if (import.meta.env.MODE === 'test' || typeof window === 'undefined') {
  const [ru, en] = await Promise.all([import('./messages.ru.js'), import('./messages.en.js')]);
  MESSAGES.ru = ru.default;
  MESSAGES.en = en.default;
} else {
  const pageLocale = resolveBrowserLocale();
  const module = await (pageLocale === 'en' ? import('./messages.en.js') : import('./messages.ru.js'));
  MESSAGES[pageLocale === 'en' ? 'en' : 'ru'] = module.default;
}

/** Словарь, который есть в бандле: нужный язык, иначе любой загруженный (ключи у ru и en совпадают, см. parity-тест). */
function dictionaryFor(locale) {
  return MESSAGES[locale] || MESSAGES.ru || MESSAGES.en || {};
}

/** Есть ли у ключа свой текст (для понятий рейтинга без собственных подписей). */
export function hasMessage(key) {
  return Object.prototype.hasOwnProperty.call(dictionaryFor(currentUiLocale()), key);
}

/**
 * Resolve a UI string. Used by LocaleProvider and non-React modules (breadcrumbs).
 * @param {string} key
 * @param {Record<string, string|number>|string} [varsOrFallback] object = {n} interp; string = fallback
 * @param {'ru'|'en'} [locale]
 */
export function translate(key, varsOrFallback, locale) {
  const loc = locale || currentUiLocale();
  const dict = dictionaryFor(loc);
  const has = Object.prototype.hasOwnProperty.call(dict, key);
  let text = has ? dict[key] : undefined;
  if (text == null) {
    if (typeof varsOrFallback === 'string') return varsOrFallback;
    text = (MESSAGES.ru && MESSAGES.ru[key]) || key;
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
  return Object.keys(dictionaryFor(locale)).length;
}
