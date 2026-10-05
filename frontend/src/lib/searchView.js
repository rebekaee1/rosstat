/**
 * Выдача поиска для человека. Сервер отдаёт плоский список по убыванию совпадения; здесь он раскладывается так,
 * как человек выбирает: «Страны», «Рейтинги», «Показатели». Порядок сервера внутри каждого раздела сохраняется,
 * ничего не пропадает: лишнее уходит под «Ещё варианты».
 *
 * Что делает раскладка:
 * - вариации одного показателя с разной частотой сворачиваются в одну строку с переключателем «день, неделя, месяц…»;
 * - один показатель по многим странам («Численность населения», 92 строки) становится строкой с кнопками стран;
 * - для запроса без страны добавляются строки рейтингов («ВВП: рейтинг стран») из каталога рейтингов;
 * - строки, не подтверждённые запросом (нерелевантное «Население, %» после «Безработица Германии»), уходят под «Ещё»;
 * - для запроса про инфляцию первой встаёт понятная «Инфляция, %», а не индекс с базовым годом.
 */
import {
  codeMatchesTargets, filterSearchOptions, normalizeSearchQuery, resolveSynonymTargets,
} from './searchSynonyms';
import { searchFamilyKey, SEARCH_PRIMARY_LIMIT } from './searchGroups';
import { groupByTopic, searchTopic } from './searchText';
import { POPULAR_COUNTRY_SLUGS } from './countryFlag';
import { worldRatingPath } from './sitePaths';

const ENTITY_KINDS = new Set(['country', 'region', 'subnational_region']);
const FREQUENCY_ORDER = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'];
const FREQUENCY_ALIASES = { A: 'annual', yearly: 'annual', M: 'monthly', Q: 'quarterly', W: 'weekly', D: 'daily' };

/** Сколько кнопок стран видно в строке «показатель по странам»; остальные раскрываются кнопкой. */
export const COUNTRY_CHIPS_VISIBLE = 6;
/** Показатель по странам: минимум стран, чтобы свернуть строки в одну. */
const BY_COUNTRY_MIN = 3;
/** Строки сверху, которые не уходят под «Ещё» даже без подтверждения запросом: сервер поставил их первыми не зря. */
const KEEP_TOP = 2;

export function normalizeFrequency(value) {
  const raw = String(value || '');
  return FREQUENCY_ALIASES[raw] || raw;
}

/** Основа названия без уточнений: «Численность населения (оценка)» и «Численность населения, чел.» → одна основа. */
function nameBase(name) {
  return String(name || '').split(/\s*[(,:]|\s[—–-]\s/)[0].trim().toLocaleLowerCase();
}

function queryWithoutNumbers(query) {
  return normalizeSearchQuery(query).replace(/(?:^|\s)\d{1,4}(?:[-./]\d{1,2})*\s*%?(?=\s|$)/g, ' ').replace(/\s+/g, ' ').trim();
}

/** Ключи строк, подтверждённых запросом (общий для сайта разбор слов и синонимов). */
function confirmedKeys(items, query, nameOf) {
  const text = queryWithoutNumbers(query);
  if (!text) return null;
  const matched = filterSearchOptions(items, text, {
    getSearchItem: (item) => ({ ...item, name: nameOf(item) }),
  });
  return matched.length ? new Set(matched.map((item) => item.key)) : null;
}

/** Строки рейтингов, подходящие запросу. Только для запроса без страны и региона. */
export function ratingRowsFor(query, { intent, concepts, labelOf, t, limit = 2 } = {}) {
  if (!concepts?.length) return [];
  if (intent?.countries?.length || intent?.regions?.length) return [];
  const text = queryWithoutNumbers(query);
  if (text.length < 2) return [];
  const matched = filterSearchOptions(concepts, text, {
    getSearchItem: (item) => ({
      ...item, concept_slug: item.slug, name: labelOf(item), search_label: labelOf(item),
    }),
  }).slice(0, limit);
  return matched.map((concept) => ({
    id: `rating:${concept.slug}`,
    type: 'rating',
    item: { key: `rating:${concept.slug}`, kind: 'rating', code: concept.slug, path: worldRatingPath(concept.slug), navigation: 'spa' },
    open: { key: `rating:${concept.slug}`, kind: 'rating', code: concept.slug, path: worldRatingPath(concept.slug), navigation: 'spa' },
    name: t('w6d.search.ratingTitle', { name: labelOf(concept) }),
    detail: t('w6d.search.ratingHint'),
    conceptSlug: concept.slug,
  }));
}

/** Показатель рейтинга по смыслу названия («численность населения» → Население); по синонимам, а не по словам. */
export function matchRatingConcept(text, concepts) {
  if (!concepts?.length || !text) return null;
  let targets = resolveSynonymTargets(text);
  if (!targets.length) {
    // Падежные формы («населения»): слово без последней буквы, как в общем разборе синонимов.
    for (const word of normalizeSearchQuery(text).split(' ')) {
      if (word.length < 6) continue;
      targets = resolveSynonymTargets(word) || [];
      if (!targets.length) targets = resolveSynonymTargets(word.slice(0, -1)) || [];
      if (targets.length) break;
    }
  }
  if (!targets.length) return null;
  const exact = concepts.find((concept) => targets.includes(concept.slug));
  return exact || concepts.find((concept) => codeMatchesTargets(concept.slug, targets)) || null;
}

const INFLATION_NAME = /inflation|инфляц|annual rate of change|изменение (?:потребительских )?цен за год|за 12 месяцев|12-month/i;
const ANNUAL_NAME = /annual|year|за год|годов|12-month|за 12 месяцев/i;
const INDEX_UNIT = /index|индекс|\d{4}\s*=\s*100/i;

/**
 * Для запроса про инфляцию первой встаёт строка с понятными процентами (лучше годовая), а не индекс
 * с базой 2015 = 100. Строки чужой страны и группы стран не поднимаются, если страна названа в запросе.
 */
function promoteHeadline(rows, query, nameOf, intent) {
  const targets = resolveSynonymTargets(queryWithoutNumbers(query));
  if (!targets.some((target) => target === 'inflation' || target === 'cpi' || target === 'hicp-index')) return rows;
  const wanted = intent?.countries?.length ? new Set(intent.countries) : null;
  const isReady = (item) => {
    const unit = String(item.unit || '');
    if (wanted && !wanted.has(item.country_slug)) return false;
    return /%|процент|percent/i.test(unit) && !INDEX_UNIT.test(unit) && INFLATION_NAME.test(nameOf(item));
  };
  const window = rows.slice(0, 12);
  const at = window.findIndex((item) => isReady(item) && ANNUAL_NAME.test(nameOf(item)))
    >= 0
    ? window.findIndex((item) => isReady(item) && ANNUAL_NAME.test(nameOf(item)))
    : window.findIndex(isReady);
  if (at <= 0) return rows;
  return [rows[at], ...rows.slice(0, at), ...rows.slice(at + 1)];
}

const CONSTANT_PRICES = /постоянн\S*\s+цен|constant\s+prices|chain[- ]linked|цепн/i;
const DOLLAR_UNIT = /\$|usd|долл/i;
/** Окно близких по оценке строк сервера, внутри которого главный показатель поднимается выше «побочных». */
const MAIN_WINDOW = 25;

/** 0 — главный годовой показатель; выше — квартальные и «в постоянных ценах», которые человек ищет реже. */
function mainTier(item, nameOf) {
  let tier = 0;
  if (CONSTANT_PRICES.test(`${nameOf(item)} ${item.unit || ''}`)) tier += 2;
  if (normalizeFrequency(item.frequency) === 'quarterly') tier += 1;
  if (DOLLAR_UNIT.test(String(item.unit || ''))) tier -= 1;
  return tier;
}

/**
 * Среди строк, которые сервер оценил почти одинаково, главный показатель (годовой, в долларах) идёт выше
 * квартального и «в постоянных ценах». Строки с заметно большей оценкой сервера не трогаются.
 */
function preferMain(rows, nameOf) {
  const top = rows.find((row) => Number.isFinite(row.score))?.score;
  if (top == null) return rows;
  const near = rows.filter((row) => Number.isFinite(row.score) && top - row.score <= MAIN_WINDOW);
  if (near.length < 2) return rows;
  const rest = rows.filter((row) => !near.includes(row));
  const sorted = near.map((row, index) => [row, index])
    .sort((a, b) => mainTier(a[0], nameOf) - mainTier(b[0], nameOf) || a[1] - b[1])
    .map(([row]) => row);
  return [...sorted, ...rest];
}

const CURRENCY_CODE = /^(?:usd|eur|cny|gbp)-rub$|^(?:btc|eth)-usd$/;

/** Коды курсов, о которых спросил человек («usd», «курс доллара», «dollar rate»); пусто, если запрос не про курс. */
function currencyTargets(query) {
  const text = queryWithoutNumbers(query);
  if (!text) return [];
  const found = new Set(resolveSynonymTargets(text) || []);
  for (const piece of text.split(' ')) {
    if (piece.length >= 3) for (const code of resolveSynonymTargets(piece) || []) found.add(code);
  }
  return [...found].filter((code) => CURRENCY_CODE.test(code));
}

/** Курс по запросу «usd» встаёт первым: выше рейтингов ВВП и прочих «страновых» строк. */
function promoteCurrency(rows, targets) {
  if (!targets.length) return rows;
  const at = rows.findIndex((item) => targets.includes(item.code));
  if (at <= 0) return rows;
  return [rows[at], ...rows.slice(0, at), ...rows.slice(at + 1)];
}

/** Запрос из одной буквы: сначала страны и главные показатели, региональные ряды в конец. */
function placeRank(item) {
  if (item.region_slug || item.kind === 'region' || item.kind === 'subnational_region') return 2;
  return item.kind === 'russia' || item.kind === 'world' ? 0 : 1;
}

function frequencyChips(members) {
  const byFrequency = new Map();
  for (const item of members) {
    const freq = normalizeFrequency(item.frequency);
    if (FREQUENCY_ORDER.includes(freq) && !byFrequency.has(freq)) byFrequency.set(freq, item);
  }
  return FREQUENCY_ORDER.filter((freq) => byFrequency.has(freq)).map((freq) => ({ frequency: freq, item: byFrequency.get(freq) }));
}

function countryRank(item, popular) {
  const index = popular.indexOf(item.country_slug);
  return index === -1 ? popular.length : index;
}

/**
 * @param rows        строки выдачи без дублей (порядок сервера)
 * @param ctx.query   введённый запрос
 * @param ctx.intent  `intent` ответа сервера ({countries, regions, year, month})
 * @param ctx.nameOf  название строки на языке интерфейса (без «человеческой» правки)
 * @param ctx.titleOf название для показа
 * @param ctx.detailOf подпись для показа
 */
export function buildSearchView(rows, {
  query, intent = null, locale = 'ru', nameOf, titleOf, detailOf, t, ratingConcepts = [], ratingLabelOf = null,
  primaryLimit = SEARCH_PRIMARY_LIMIT,
}) {
  const popular = POPULAR_COUNTRY_SLUGS[locale === 'en' ? 'en' : 'ru'] || [];
  let entities = [];
  let series = [];
  for (const row of rows || []) (ENTITY_KINDS.has(row.kind) ? entities : series).push(row);
  const singleLetter = [...normalizeSearchQuery(query)].filter((ch) => /[\p{L}\p{N}]/u.test(ch)).length === 1;
  if (singleLetter) {
    const byRank = (list, rank) => list.map((row, index) => [row, index])
      .sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(([row]) => row);
    series = byRank(series, placeRank);
    entities = byRank(entities, (row) => (row.kind === 'country' ? 0 : 1));
  }
  const currencyCodes = currencyTargets(query);

  // 1. Подтверждённые запросом строки; остальные, кроме верхних, уходят под «Ещё».
  // Пока запрос подтверждён меньше чем двумя строками, ничего не прячем: уверенного «ядра» ответа ещё нет.
  const confirmedAll = confirmedKeys(series, query, nameOf);
  const confirmed = confirmedAll && confirmedAll.size >= 2 ? confirmedAll : null;
  const relevant = [];
  const demoted = [];
  // Страна названа в запросе: строки другой территории («Большая двадцатка», еврозона) — это «похожее», а не ответ.
  const wantedCountries = intent?.countries?.length && !intent?.regions?.length ? new Set(intent.countries) : null;
  series.forEach((item, index) => {
    const foreign = wantedCountries && item.country_slug && !wantedCountries.has(item.country_slug);
    if (foreign) demoted.push(item);
    else if (!confirmed || index < KEEP_TOP || confirmed.has(item.key)) relevant.push(item);
    else demoted.push(item);
  });
  // Страна из запроса идёт первой: её строки выше строк без привязки к стране (порядок внутри групп сохраняется).
  const preferred = preferMain(relevant, nameOf);
  const countryFirst = wantedCountries
    ? preferred.map((row, index) => [row, index])
      .sort((a, b) => (wantedCountries.has(a[0].country_slug) ? 0 : 1) - (wantedCountries.has(b[0].country_slug) ? 0 : 1) || a[1] - b[1])
      .map(([row]) => row)
    : preferred;
  const ordered = promoteCurrency(promoteHeadline(countryFirst, query, nameOf, intent), currencyCodes);

  // 2. Вариации одной семьи: частоты — в переключатель, повторы — под «Ещё».
  const hiddenDuplicates = [];
  const familyMembers = new Map();
  for (const item of ordered) {
    const key = searchFamilyKey(item, nameOf(item));
    if (!familyMembers.has(key)) familyMembers.set(key, []);
    familyMembers.get(key).push(item);
  }
  let units = [];
  const seenFamily = new Set();
  for (const item of ordered) {
    const key = searchFamilyKey(item, nameOf(item));
    if (seenFamily.has(key)) continue;
    seenFamily.add(key);
    const members = familyMembers.get(key);
    const chips = frequencyChips(members);
    if (chips.length >= 2) {
      const chipItems = new Set(chips.map((chip) => chip.item));
      for (const member of members.slice(1)) if (!chipItems.has(member)) hiddenDuplicates.push(member);
      units.push({ type: 'family', primary: item, chips });
    } else {
      hiddenDuplicates.push(...members.slice(1));
      units.push({ type: 'item', primary: item });
    }
  }

  // 3. Один показатель по многим странам: одна строка и кнопки стран.
  const noExplicitGeo = !(intent?.countries?.length || intent?.regions?.length);
  if (noExplicitGeo) {
    const byBase = new Map();
    for (const unit of units) {
      if (unit.type === 'family') continue;
      const item = unit.primary;
      if (item.kind !== 'world' && item.kind !== 'russia') continue;
      const base = nameBase(nameOf(item));
      if (!base) continue;
      if (!byBase.has(base)) byBase.set(base, []);
      byBase.get(base).push(unit);
    }
    const winners = [...byBase.entries()]
      .map(([base, list]) => ({ base, list, countries: new Set(list.map((unit) => unit.primary.country_slug)) }))
      .filter((group) => group.countries.size >= BY_COUNTRY_MIN)
      .sort((a, b) => b.countries.size - a.countries.size);
    const replaced = new Map();
    const dropped = new Set();
    for (const group of winners.slice(0, 2)) {
      const seenCountry = new Set();
      const members = [];
      for (const unit of group.list) {
        const slug = unit.primary.country_slug;
        if (seenCountry.has(slug)) {
          hiddenDuplicates.push(unit.primary);
          dropped.add(unit);
          continue;
        }
        seenCountry.add(slug);
        members.push(unit.primary);
        if (unit !== group.list[0]) dropped.add(unit);
      }
      const sorted = [...members].sort((a, b) => countryRank(a, popular) - countryRank(b, popular));
      replaced.set(group.list[0], { type: 'byCountry', primary: group.list[0].primary, countries: sorted, base: group.base });
    }
    units = units.flatMap((unit) => {
      if (replaced.has(unit)) return [replaced.get(unit)];
      return dropped.has(unit) ? [] : [unit];
    });
  }

  // 4. Строки рейтингов.
  const ratingRows = ratingRowsFor(query, { intent, concepts: ratingConcepts, labelOf: ratingLabelOf || nameOf, t });

  // 5. Видимые строки.
  const toRow = (unit) => {
    const item = unit.primary;
    const base = { id: item.key, item, open: item, name: titleOf(item), detail: detailOf(item) };
    if (unit.type === 'family') return { ...base, type: 'family', chips: unit.chips };
    if (unit.type === 'byCountry') {
      const concept = matchRatingConcept(unit.base, ratingConcepts);
      const rating = concept
        ? { key: `rating:${concept.slug}`, kind: 'rating', code: concept.slug, path: worldRatingPath(concept.slug), navigation: 'spa' }
        : null;
      return {
        ...base,
        id: `by-country:${unit.base}`,
        type: 'byCountry',
        countries: unit.countries,
        rating,
        open: rating || unit.countries[0] || item,
        detail: t('w6d.search.byCountryHint', { n: unit.countries.length }),
      };
    }
    return { ...base, type: 'item' };
  };
  const countryRows = entities.map((item) => ({ id: item.key, type: 'item', item, open: item, name: titleOf(item), detail: detailOf(item) }));
  const seriesRows = units.map(toRow);
  // Запрос про курс («usd», «курс доллара»): курсы выше рейтингов и стран.
  const currencyQuery = currencyCodes.length > 0 && series.some((item) => currencyCodes.includes(item.code));
  const geoFirst = !currencyQuery && (noExplicitGeo || !seriesRows.length);
  const order = geoFirst
    ? [['countries', countryRows], ['ratings', ratingRows], ['indicators', seriesRows]]
    : [['indicators', seriesRows], ['ratings', ratingRows], ['countries', countryRows]];

  const sections = [];
  const overflow = [];
  let budget = primaryLimit;
  for (const [id, list] of order) {
    const visible = list.slice(0, Math.max(0, budget));
    overflow.push(...list.slice(visible.length));
    budget -= visible.length;
    if (visible.length) sections.push({ id, rows: visible });
  }
  const plain = (item) => ({ id: `more:${item.key}`, type: 'item', item, open: item, name: titleOf(item), detail: detailOf(item) });
  const moreRows = [
    ...overflow.flatMap((row) => (row.type === 'item' || row.type === 'rating' ? [row] : [plain(row.item)])),
    ...hiddenDuplicates.map(plain),
    ...demoted.map(plain),
  ];
  const seenMore = new Set();
  const uniqueMore = moreRows.filter((row) => {
    const key = row.item.key;
    if (seenMore.has(key)) return false;
    seenMore.add(key);
    return true;
  });
  // «Ещё варианты» по темам: инфляция и цены, курсы, ставки… Порядок строк = порядок на экране (по нему ходят стрелки).
  const moreGroups = groupByTopic(uniqueMore, (row) => searchTopic(row.item));
  const more = moreGroups.flatMap((group) => group.rows);
  const flat = sections.flatMap((section) => section.rows);
  return {
    sections, more, moreGroups, moreTopics: moreGroups.map((group) => group.id), flat, hiddenCount: more.length,
  };
}
