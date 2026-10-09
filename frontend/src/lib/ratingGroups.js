/**
 * Группы стран для фильтра рейтинга: «Все / G7 / БРИКС / СНГ» (круг 11, F).
 * Состав G7 и БРИКС берётся из общих подборок сравнения (`COUNTRY_GROUPS`), СНГ задан здесь двухбуквенными кодами:
 * в каталоге сайта сейчас только Россия, Армения, Азербайджан и Молдавия, остальные страны группы появятся в фильтре сами,
 * как только у них будут данные (отдельного списка поддерживать не нужно).
 */
import { COUNTRY_GROUPS, isoForSlug } from './slugFlags';

function codesOf(id) {
  const group = COUNTRY_GROUPS.find((item) => item.id === id);
  return new Set((group?.slugs || []).map((slug) => isoForSlug(slug)).filter(Boolean));
}

const CIS_CODES = new Set(['RU', 'AM', 'AZ', 'BY', 'KZ', 'KG', 'MD', 'TJ', 'UZ']);

/** Порядок кнопок: «Все» всегда первая. */
export const RATING_GROUP_IDS = Object.freeze(['all', 'g7', 'brics', 'cis']);

const CODES_BY_ID = {
  g7: codesOf('g7'),
  brics: codesOf('brics'),
  cis: CIS_CODES,
};

/** Допустимый идентификатор группы из адреса; неизвестное значение — «все страны». */
export function normalizeRatingGroup(raw) {
  const id = String(raw || '').toLowerCase();
  return RATING_GROUP_IDS.includes(id) ? id : 'all';
}

/** Входит ли страна (двухбуквенный код) в группу. */
export function inRatingGroup(groupId, countryCode) {
  if (!groupId || groupId === 'all') return true;
  return Boolean(CODES_BY_ID[groupId]?.has(String(countryCode || '').toUpperCase()));
}

/** Строки рейтинга, оставшиеся после фильтра группы (порядок сохраняется). */
export function filterRowsByGroup(rows, groupId) {
  if (!groupId || groupId === 'all') return rows;
  return rows.filter((row) => inRatingGroup(groupId, row.country_code));
}

/** Сколько строк даст каждая группа: пустые группы кнопкой не показываются. */
export function groupCounts(rows) {
  const counts = { all: rows.length };
  for (const id of RATING_GROUP_IDS) {
    if (id !== 'all') counts[id] = filterRowsByGroup(rows, id).length;
  }
  return counts;
}
