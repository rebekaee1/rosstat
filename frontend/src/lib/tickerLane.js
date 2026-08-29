/**
 * Lane живой ленты — строго по locale, не по path.
 * ru (и любой не-en): российский набор на любой странице.
 * en: мировые кроссы вершины.
 */
export function tickerLaneForLocale(locale) {
  return locale === 'en' ? 'world' : 'russia';
}
