import { isReservedFirstSegment, RUSSIA } from './sitePaths';

/**
 * Lane живой ленты по языку: ru, и любой не-en, получает российский набор; en получает мировые кроссы.
 */
export function tickerLaneForLocale(locale) {
  return locale === 'en' ? 'world' : 'russia';
}

/** Страница зарубежной страны (`/germany`, `/india/indicator/...`) или мировой рейтинг: рубли тут не главное. */
export function isForeignWorldPath(pathname) {
  const first = String(pathname || '').split('/').filter(Boolean)[0];
  if (!first) return false;
  if (first === 'world') return true;
  return !isReservedFirstSegment(first) && first !== RUSSIA;
}

/**
 * Lane по языку и региону страницы: русская лента (рубль) остаётся на главной, в России и в «Валютах»,
 * а на страницах других стран русскоязычный посетитель видит те же мировые курсы, что и англоязычный.
 */
export function tickerLaneFor(locale, pathname) {
  if (locale === 'en') return 'world';
  return isForeignWorldPath(pathname) ? 'world' : 'russia';
}
