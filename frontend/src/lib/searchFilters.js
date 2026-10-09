/**
 * Круг 11 (D): фильтры выдачи поиска — страна, периодичность, источник и «как считать» («в среднем за год» / «год к году»).
 * Сервер этих полей пока не принимает, поэтому фильтр работает над тем, что уже пришло (до 50 строк): сужает выдачу, не посылая запрос заново.
 * Источник и способ счёта в строке выдачи прямо не названы, их определяем по коду и названию ряда; когда сервер начнёт отдавать
 * `source` и `basis`, они будут использованы первыми.
 */
import { normalizeFrequency } from './searchView';

export const FILTER_GROUPS = Object.freeze(['country', 'frequency', 'source', 'basis']);
export const EMPTY_FILTERS = Object.freeze({ country: '', frequency: '', source: '', basis: '' });
const FREQUENCIES = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'];
const COUNTRY_OPTIONS_LIMIT = 8;
const SOURCE_ORDER = ['ru', 'national', 'imf', 'eurostat'];

const RUSSIA_KINDS = new Set(['russia', 'russia_indicator', 'region', 'subnational_region', 'subnational_indicator', 'rating']);

function bodyOfCode(item) {
  const code = String(item?.code || '');
  return item?.kind === 'world' ? code.replace(/^[a-z]{2,3}-/, '') : code;
}

/** Откуда ряд: Россия (Росстат, Банк России, Минфин), МВФ, Евростат или национальный источник другой страны. */
export function searchSourceOf(item) {
  const explicit = String(item?.source_id || item?.source || '').trim().toLowerCase();
  if (/imf|мвф/.test(explicit)) return 'imf';
  if (/eurostat|евростат/.test(explicit)) return 'eurostat';
  if (explicit && explicit !== 'undefined') return /rosstat|росстат|cbr|банк россии|минфин/.test(explicit) ? 'ru' : 'national';
  if (RUSSIA_KINDS.has(item?.kind) && item?.kind !== 'rating') return 'ru';
  if (item?.kind !== 'world') return '';
  const body = bodyOfCode(item);
  if (/(^|-)weo(-|$)/.test(body)) return 'imf';
  // Наборы Евростата называются как «prc_hicp_midx», «nama_10_gdp», «tec00118»: подчёркивание или цифровой номер в первом сегменте.
  const dataset = body.split('-')[0];
  if (/_/.test(dataset) || /^[a-z]{2,5}\d{3,}/.test(dataset)) return 'eurostat';
  return 'national';
}

/** Способ счёта у рядов про изменение цен и роста: «в среднем за год» или «год к году». Пусто, если ряд об этом не говорит. */
export function searchBasisOf(item) {
  if (item?.basis === 'avg' || item?.basis === 'yoy') return item.basis;
  const code = String(item?.code || '');
  const path = String(item?.path || '');
  const text = [item?.name, item?.name_ru, item?.name_en, item?.unit].map((part) => String(part || '')).join(' ');
  if (/-a-avg$|-a-avg-|_a_avg|pcpipch/i.test(code)) return 'avg';
  if (/mode=yoy|-rch-m12|rch_m12/i.test(`${path} ${code}`)) return 'yoy';
  if (/в\s+среднем\s+за\s+год|среднегодов|annual\s+average|average\s+(consumer|annual)|year\s+average/i.test(text)) return 'avg';
  if (/за\s+год|год\s+к\s+году|к\s+(тому\s+же\s+месяцу|соответствующему)|year[- ]on[- ]year|year[- ]over[- ]year|y\/y|annual\s+(rate|change)|12[- ]month/i.test(text)) return 'yoy';
  return '';
}

/** Страна строки: слаг и название; Россия и её регионы собираются в «russia». */
export function searchCountryOf(item, russiaName = 'Россия', locale = 'ru') {
  const slug = String(item?.country_slug || '').trim();
  if (slug) {
    const name = String((locale === 'en' && item.country_name_en) || item.country_name || slug);
    return { slug, name };
  }
  if (item?.kind === 'russia' || item?.kind === 'russia_indicator' || item?.kind === 'region' || item?.kind === 'subnational_region' || item?.kind === 'subnational_indicator') {
    return { slug: 'russia', name: russiaName };
  }
  return { slug: '', name: '' };
}

/** Описание факетов строки для отбора. */
export function searchFacets(item, { russiaName, locale } = {}) {
  const country = searchCountryOf(item, russiaName, locale);
  return {
    country: country.slug,
    countryName: country.name,
    frequency: normalizeFrequency(item?.frequency),
    source: searchSourceOf(item),
    basis: searchBasisOf(item),
  };
}

/**
 * Варианты для чипов по пришедшей выдаче. Группа показывается, только если в ней больше одного значения (иначе фильтровать нечем).
 * Выбранное значение остаётся в списке всегда, чтобы его можно было снять.
 * @returns {{ country: object[], frequency: object[], source: object[], basis: object[] }} значения `{ value, label, count }`
 */
export function buildFilterOptions(results, filters = EMPTY_FILTERS, { russiaName = 'Россия', locale = 'ru' } = {}) {
  const countries = new Map();
  const frequencies = new Map();
  const sources = new Map();
  const bases = new Map();
  for (const item of results || []) {
    if (item?.kind === 'rating') continue;
    const facets = searchFacets(item, { russiaName, locale });
    if (facets.country) {
      const known = countries.get(facets.country) || { value: facets.country, label: facets.countryName, count: 0 };
      known.count += 1;
      countries.set(facets.country, known);
    }
    if (facets.frequency && FREQUENCIES.includes(facets.frequency)) frequencies.set(facets.frequency, (frequencies.get(facets.frequency) || 0) + 1);
    if (facets.source) sources.set(facets.source, (sources.get(facets.source) || 0) + 1);
    if (facets.basis) bases.set(facets.basis, (bases.get(facets.basis) || 0) + 1);
  }
  const pick = (map, order, selected) => {
    const list = order
      ? order.filter((value) => map.has(value)).map((value) => ({ value, count: map.get(value) }))
      : [...map.entries()].map(([value, count]) => ({ value, count }));
    if (selected && !list.some((entry) => entry.value === selected)) list.push({ value: selected, count: 0 });
    return list.length > 1 || (selected && list.length) ? list : [];
  };
  const countryList = [...countries.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, locale));
  let shownCountries = countryList.slice(0, COUNTRY_OPTIONS_LIMIT);
  if (filters.country && !shownCountries.some((entry) => entry.value === filters.country)) {
    shownCountries = [...shownCountries, countries.get(filters.country) || { value: filters.country, label: filters.country, count: 0 }];
  }
  return {
    country: shownCountries.length > 1 || filters.country ? shownCountries : [],
    frequency: pick(frequencies, FREQUENCIES, filters.frequency),
    source: pick(sources, SOURCE_ORDER, filters.source),
    // «Как считать» нужно, когда есть оба способа: с одним нечего переключать.
    basis: bases.size > 1 || filters.basis ? pick(bases, ['avg', 'yoy'], filters.basis) : [],
  };
}

export function activeFilterCount(filters) {
  return FILTER_GROUPS.filter((group) => Boolean(filters?.[group])).length;
}

/** Выдача после фильтров. Рейтинги и пустые значения не отбираются: строки-рейтинги к стране и частоте не относятся. */
export function applySearchFilters(results, filters, { russiaName, locale } = {}) {
  if (!activeFilterCount(filters)) return results;
  return (results || []).filter((item) => {
    if (item?.kind === 'rating') return true;
    const facets = searchFacets(item, { russiaName, locale });
    if (filters.country && facets.country !== filters.country) return false;
    if (filters.frequency && facets.frequency !== filters.frequency) return false;
    if (filters.source && facets.source !== filters.source) return false;
    if (filters.basis && facets.basis !== filters.basis) return false;
    return true;
  });
}
