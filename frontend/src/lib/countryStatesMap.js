// Страны, у которых в профиле на странице страны стоит карта субъектов (круг 10, К5). Отдельный лёгкий модуль без геометрии:
// страница проверяет по нему, нужно ли вообще догружать карту (JSON штатов весит ~170 КБ и нужен только странице США).
export const COUNTRY_STATES_MAP_SLUGS = Object.freeze(['united-states']);

export function hasCountryStatesMap(slug) {
  return COUNTRY_STATES_MAP_SLUGS.includes(slug);
}
