// URL-схема карты регионов на /regions:
//   ?view=map
//   &indicator=<code>|overview   — выбранный показатель (или режим «Обзор»)
//   &year=YYYY                   — год на ползунке (только при indicator≠overview)
//
// Без indicator при view=map — дефолтный пресет (первый чип). SSR отдельного
// семейства не заводим: индексные лендинги по показателю уже есть как
// /region-rating/{code}; здесь задача — shareable deep-link на состояние карты.

export const MAP_OVERVIEW = 'overview';

/**
 * @param {URLSearchParams} searchParams
 * @returns {{ view: 'map'|'list', indicator: string|null, year: number|null }}
 */
export function parseRegionsMapParams(searchParams) {
  const view = searchParams.get('view') === 'map' ? 'map' : 'list';
  const raw = searchParams.get('indicator');
  const indicator = raw && /^[a-z0-9-]+$/i.test(raw) ? raw : null;
  const yearRaw = searchParams.get('year');
  const year = yearRaw && /^\d{4}$/.test(yearRaw) ? Number(yearRaw) : null;
  return { view, indicator, year };
}

/**
 * Собирает query для /regions из состояния карты.
 * @returns {URLSearchParams}
 */
export function buildRegionsMapSearchParams({
  view = 'list',
  indicator = null,
  year = null,
} = {}) {
  const p = new URLSearchParams();
  if (view !== 'map') return p;
  p.set('view', 'map');
  if (indicator) p.set('indicator', indicator);
  // year пишем и без indicator (дефолтный первый чип) — иначе шаринг теряет год.
  if (indicator !== MAP_OVERVIEW && year != null) {
    p.set('year', String(year));
  }
  return p;
}

/** Сравнивает два URLSearchParams по сериализованному виду (порядок ключей стабилен). */
export function searchParamsEqual(a, b) {
  return a.toString() === b.toString();
}
