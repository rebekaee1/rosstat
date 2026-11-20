/**
 * Выдача поиска для человека: первые варианты видны сразу, «вариации» одного показателя сворачиваются.
 * Сервер отдаёт все совпадения подряд (по восемь вариантов «Гармонизированного индекса потребительских цен»
 * для одной страны), и без свёртки их не отличить без вчитывания. Порядок сервера сохраняется:
 * первым остаётся самый релевантный представитель семьи.
 */

import { inCountry, inflationTitle, isIndexUnit, plainTitle } from './searchText';

/** Сколько строк видно, пока человек не нажал «Ещё варианты». */
export const SEARCH_PRIMARY_LIMIT = 8;

// Гармонизированный индекс потребительских цен — официальная мера инфляции Евростата; человеку это «инфляция».
const HICP_RE = /^(гармонизированн\S* индекс потребительских цен|harmoni[sz]ed index of consumer prices)/i;

/** Основа названия до первого уточнения: «ВВП (в текущих ценах)» и «ВВП, на душу» → «ввп». */
function nameBase(name) {
  return String(name || '').split(/\s*[(,:]|\s[—–-]\s/)[0].trim().toLocaleLowerCase();
}

/** Семья вариаций: одна страна (или регион) и одна основа названия. Страны и разделы сами по себе — каждый своя семья. */
export function searchFamilyKey(row, name) {
  const place = row.region_slug || row.country_slug || row.country_name || '';
  if (row.kind === 'country' || row.kind === 'region' || row.kind === 'subnational_region') {
    return `${row.kind}|${row.key || place}`;
  }
  return `${row.kind}|${place}|${nameBase(name)}`;
}

/**
 * Делит выдачу на видимую часть и «ещё варианты».
 * В «ещё» уходят повторные члены семьи и всё, что дальше лимита.
 */
export function splitSearchRows(rows, nameOf, { primaryLimit = SEARCH_PRIMARY_LIMIT } = {}) {
  const seen = new Set();
  const primary = [];
  const more = [];
  for (const row of rows || []) {
    const key = searchFamilyKey(row, nameOf(row));
    if (seen.has(key) || primary.length >= primaryLimit) {
      more.push(row);
    } else {
      seen.add(key);
      primary.push(row);
    }
  }
  return { primary, more };
}

/**
 * Название строки обычными словами: индекс потребительских цен страны — «Инфляция в Германии»,
 * служебные слова («ИПЦ», «цепные объёмы», база индекса) убраны. Остальные названия остаются как пришли.
 */
export function friendlySearchName(item, name, t, locale = 'ru') {
  return withTaxEra(baseSearchName(item, name, t, locale), t);
}

// Курортный сбор и туристический налог (правка 24): в выдаче по «налог» и «сбор» это два разных ряда разных лет.
const RESORT_FEE_RE = /курортн\S*\s+сбор|resort\s+fee/i;
const TOURIST_TAX_RE = /туристическ\S*\s+налог|tourist\s+tax/i;
const HAS_YEAR_RE = /\b(?:19|20)\d{2}\b/;

/** К названию добавляются годы действия («до 2024 года», «с 2025 года»); название с годом остаётся как есть. */
export function withTaxEra(title, t) {
  const text = String(title || '');
  if (!text || HAS_YEAR_RE.test(text) || typeof t !== 'function') return text;
  if (RESORT_FEE_RE.test(text)) return `${text} ${t('kt6_search_era_resortFee')}`;
  if (TOURIST_TAX_RE.test(text)) return `${text} ${t('kt6_search_era_touristTax')}`;
  return text;
}

function baseSearchName(item, name, t, locale) {
  const text = String(name || '').trim();
  if (item?.country_name && HICP_RE.test(text)) {
    return inflationTitle(item.country_name, t, locale);
  }
  // Годовая инфляция страны в процентах: «Инфляция в Турции, за год» (а не «Индекс потребительских цен …»).
  if (item?.country_name && isAnnualInflationPercent(item, text)) {
    const where = inCountry(item.country_name, locale);
    return where
      ? t('z8.search.inflationYear', { where })
      : t('z8.search.inflationYearPlain', { country: item.country_name });
  }
  return plainTitle(name, locale);
}

const INFLATION_NAME = /inflation|инфляц|annual rate of change|изменение (?:потребительских )?цен|consumer price/i;
const ANNUAL_NAME = /annual|year[- ]on[- ]year|за год|годов|12-month|за 12 месяцев|к соответствующему/i;

/** Строка «процент изменения цен за год»: единица — проценты (не индекс), в названии инфляция и «за год». */
function isAnnualInflationPercent(item, name) {
  const unit = String(item?.unit || '');
  if (!/%|процент|percent/i.test(unit) || isIndexUnit(unit)) return false;
  return INFLATION_NAME.test(name) && ANNUAL_NAME.test(name);
}
