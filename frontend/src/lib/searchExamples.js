/**
 * Примеры запросов обычными словами: чипы под поиском на главной, «Популярное» в диалоге поиска
 * и подсказки на пустой выдаче. Тексты — в messages (`shell.search.example.N`), здесь только порядок.
 * Первые HOME_EXAMPLE_COUNT идут на главную, все — в диалог.
 */
import { indicatorPath, russiaIndicatorPath } from './sitePaths';
import { plainUnit } from './searchText';

export const SEARCH_EXAMPLE_KEYS = Object.freeze([
  'shell.search.example.1',
  'shell.search.example.2',
  'shell.search.example.3',
  'shell.search.example.4',
  'shell.search.example.5',
  'shell.search.example.6',
  'w6d.search.example.7',
  'w6d.search.example.8',
]);

/**
 * Подсказки с готовым адресом открываются сразу, без поиска: это показатели, чей код известен заранее
 * (ставка ФРС США, курс евро, нефть Brent, цена золота ЦБ, ключевая ставка России). Остальные подсказки
 * («Инфляция в Турции») запускают поиск и открывают лучший результат сами.
 */
const SUGGESTION_PATHS = Object.freeze({
  'shell.search.example.4': () => indicatorPath('united-states', 'us-policy-rate'),
  'shell.search.example.5': () => russiaIndicatorPath('eur-usd'),
  'shell.search.example.6': () => russiaIndicatorPath('brent'),
  'w6d.search.example.7': () => russiaIndicatorPath('gold-price'),
  'w6d.search.example.8': () => russiaIndicatorPath('key-rate'),
});

/** @returns {{ key: string, text: string, path: string|null }[]} */
export function searchSuggestions(t, limit = SEARCH_EXAMPLE_KEYS.length) {
  return SEARCH_EXAMPLE_KEYS.slice(0, limit).map((key) => ({
    key,
    text: t(key),
    path: SUGGESTION_PATHS[key] ? SUGGESTION_PATHS[key]() : null,
  }));
}

export const HOME_EXAMPLE_COUNT = 4;

export function searchExamples(t, limit = SEARCH_EXAMPLE_KEYS.length) {
  return SEARCH_EXAMPLE_KEYS.slice(0, limit).map((key) => t(key));
}

const FREQUENCIES = new Set(['daily', 'weekly', 'monthly', 'quarterly', 'annual']);

/**
 * Человеческая подпись результата без внутренних кодов: «Германия — по месяцам, %».
 * Идентификаторы рядов, коды стран и категории базы в подпись не попадают.
 */
export function describeSearchResult(item, t, locale = 'ru') {
  const isRussia = item.kind === 'russia' || item.kind === 'russia_indicator';
  const place = [];
  for (const part of [item.region_name, item.country_name || (isRussia ? t('search.russia') : '')]) {
    const text = String(part || '').trim();
    if (text && place[place.length - 1] !== text) place.push(text);
  }
  const tail = [];
  if (FREQUENCIES.has(item.frequency)) tail.push(t(`shell.freq.${item.frequency}`));
  const unit = plainUnit(String(item.unit || '').trim(), locale);
  if (unit) tail.push(unit);
  const kindLabel = item.kind === 'country'
    ? t('shell.search.kind.country')
    : (item.kind === 'region' || item.kind === 'subnational_region') ? t('shell.search.kind.region') : '';
  const head = place.length ? place.join(', ') : kindLabel;
  if (item.kind === 'country') return kindLabel;
  return [head, tail.join(', ')].filter(Boolean).join(' — ');
}

/** Склейка дублей: одинаковое имя и одинаковая подпись человеку не отличить, оставляем первый (самый релевантный). */
export function dedupeSearchRows(rows, nameOf, detailOf) {
  const seen = new Set();
  const out = [];
  for (const row of rows) {
    const signature = `${nameOf(row)}|${detailOf(row)}`;
    if (seen.has(signature)) continue;
    seen.add(signature);
    out.push(row);
  }
  return out;
}

const VARIANT_HINTS = [
  [/пред\S*\s+месяц|previous\s+month|month[- ]on[- ]month|m\/m/i, 'c9b.search.variant.month'],
  [/за\s+год|year[- ]on[- ]year|annual\s+rate|годов|за\s+12\s+месяцев|12-month|y\/y/i, 'c9b.search.variant.year'],
  [/индекс|index/i, 'c9b.search.variant.index'],
];

/**
 * Круг 9 (Q3): разные ряды получают на экране одно и то же название («Инфляция в Турции»), и человек видит дубли. Здесь строки с
 * одинаковым видимым названием и подписью разводятся по смыслу сырого названия («к пред. месяцу», «за год», «индекс»); те, у кого
 * различителя нет или он повторяется, считаются повтором и убираются (остаётся самый релевантный, порядок сервера).
 * @returns {{ rows: object[], variants: Map<string, string> }} variants: ключ строки → подпись различителя
 */
export function separateVisibleTwins(rows, { titleOf, detailOf, nameOf, t }) {
  const groups = new Map();
  for (const row of rows) {
    const signature = `${titleOf(row)}|${detailOf(row)}`;
    if (!groups.has(signature)) groups.set(signature, []);
    groups.get(signature).push(row);
  }
  const drop = new Set();
  const variants = new Map();
  for (const members of groups.values()) {
    if (members.length < 2) continue;
    const seenHints = new Set();
    for (const row of members) {
      const text = `${nameOf(row)} ${row.unit || ''}`;
      const hint = VARIANT_HINTS.find(([pattern]) => pattern.test(text))?.[1] || '';
      if (seenHints.has(hint)) { drop.add(row); continue; }
      seenHints.add(hint);
      if (hint) variants.set(row.key, t(hint));
    }
    // Различитель нужен, только когда в группе осталось больше одной строки; единственная строка называется как раньше.
    const kept = members.filter((row) => !drop.has(row));
    if (kept.length < 2) for (const row of kept) variants.delete(row.key);
  }
  return { rows: rows.filter((row) => !drop.has(row)), variants };
}
