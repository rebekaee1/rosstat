/**
 * Эмодзи-флаг по двухбуквенному коду страны (ISO 3166-1 alpha-2).
 * Пустая строка, если код не похож на ISO: тогда вызывающий рисует запасной значок, а не «DE» вместо флага.
 */
export function countryFlag(code) {
  const upper = String(code || '').trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(upper)) return '';
  return String.fromCodePoint(...[...upper].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}

/** Страны, которые чаще всего ищут: порядок показа в «Популярных странах» на главной. */
export const POPULAR_COUNTRY_SLUGS = Object.freeze({
  ru: ['russia', 'united-states', 'china', 'germany', 'japan', 'united-kingdom', 'india', 'france', 'brazil', 'turkey'],
  en: ['united-states', 'china', 'germany', 'japan', 'united-kingdom', 'india', 'france', 'russia', 'brazil', 'canada'],
});
