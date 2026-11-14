import { splitUnit } from './countryFlag';
import { plainUnit } from './searchText';
import { shortUnit } from './shortUnit';

const MAX = 14;
// Цена «за что»: сохраняем, за что цена («₽ за поездку»), а не голый «₽» общего словаря.
const PRICE_PER = [[/^рублей за\s+/i, '₽ за '], [/^roubles per\s+/i, '₽ per ']];
const THOUSAND = [[/^тысяч\s+/i, 'тыс. '], [/^thousand\s+/i, 'thous. ']];

function compact(text, rules) {
  let out = text;
  for (const [pattern, replacement] of rules) out = out.replace(pattern, replacement);
  return out !== text && out.length <= MAX + 2 ? out : '';
}

/**
 * Единица у числа в строке выдачи поиска. Короткая («%», «тысяч гектаров») ставится как есть; длинная —
 * «₽ за поездку» / «₽ per item» для цен, иначе короткой формой общего словаря («thousand hectares» → «thous. ha»,
 * «миллионов рублей» → «млн ₽»), если помещается. Только строка выдачи поиска: страницы регионов не меняются.
 * 14.11.2026: длинные единицы у числа не ставились вовсе — «26.94, 2024» в английской выдаче без единицы.
 */
export function rowUnit(unit, locale = 'ru') {
  const plain = plainUnit(String(unit || '').trim(), locale);
  const short = splitUnit(plain).short;
  if (short) return short;
  const price = compact(plain, PRICE_PER);
  if (price) return price;
  const known = shortUnit(plain);
  if (known && known !== plain && known.length <= MAX) return known;
  return compact(plain, THOUSAND);
}
