/**
 * Выдача поиска для человека: первые варианты видны сразу, «вариации» одного показателя сворачиваются.
 * Сервер отдаёт все совпадения подряд (по восемь вариантов «Гармонизированного индекса потребительских цен»
 * для одной страны), и без свёртки их не отличить без вчитывания. Порядок сервера сохраняется:
 * первым остаётся самый релевантный представитель семьи.
 */

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
 * Название строки обычными словами: индекс потребительских цен страны — «Инфляция: Германия».
 * Остальные названия остаются как пришли с сервера.
 */
export function friendlySearchName(item, name, t) {
  if (item?.country_name && HICP_RE.test(String(name || '').trim())) {
    return t('shell3.search.inflation', { country: item.country_name });
  }
  return name;
}
