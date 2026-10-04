/**
 * Флаг страны как эмодзи по двухбуквенному коду (ISO 3166-1 alpha-2).
 * Коды каталога UK и EL — это GB и GR. Для неизвестного кода возвращается пустая строка:
 * вместо флага в интерфейсе просто ничего не рисуется, а не серый глобус.
 */
const ALIASES = { UK: 'GB', EL: 'GR' };
const REGIONAL_A = 0x1f1e6;

export function countryFlag(code) {
  const raw = String(code ?? '').trim().toUpperCase();
  const iso = ALIASES[raw] || raw;
  if (!/^[A-Z]{2}$/.test(iso)) return '';
  return String.fromCodePoint(...[...iso].map((letter) => REGIONAL_A + letter.charCodeAt(0) - 65));
}

/**
 * Одинаковая точность чисел в одном списке: «30 767», «5 048», а не «5 048,1» рядом с «4 003,0».
 * Знаки после запятой зависят от самого крупного значения набора.
 */
export function uniformDigits(values) {
  let max = 0;
  for (const raw of values || []) {
    if (raw == null || raw === '') continue;
    const value = Math.abs(Number(raw));
    if (Number.isFinite(value) && value > max) max = value;
  }
  if (max >= 1000) return 0;
  if (max >= 5) return 1;
  return 2;
}

/**
 * Единица рядом с числом: короткая («%», «млрд $») стоит у самого числа,
 * длинное пояснение («% экономически активного населения») уходит в подпись под ним.
 * @returns {{ short: string, long: string }}
 */
export function splitUnit(unit) {
  const text = String(unit ?? '').trim();
  if (!text) return { short: '', long: '' };
  if (/^%|,\s*%$/.test(text)) return { short: '%', long: text === '%' ? '' : text };
  if (text.length <= 14) return { short: text, long: '' };
  return { short: '', long: text };
}

/** Страны, которые чаще всего ищут: порядок показа в «Популярных странах» на главной. */
export const POPULAR_COUNTRY_SLUGS = Object.freeze({
  ru: ['russia', 'united-states', 'china', 'germany', 'japan', 'united-kingdom', 'india', 'france', 'brazil', 'turkey'],
  en: ['united-states', 'china', 'germany', 'japan', 'united-kingdom', 'india', 'france', 'russia', 'brazil', 'canada'],
});
