/**
 * URL-режимы семейства цен на жильё (квартальные ряды Росстата).
 * Семантика режимов — как «К прошлому периоду» / «Индекс» у ИПЦ (cpiViewModeResolve).
 */

export const HOUSING_CODES = ['housing-price-primary', 'housing-price-secondary'];

// Ось как у ИПЦ (созвон 2026-06-16):
//   - `yoy` — квартальная YoY (каждый квартал к тому же кварталу год назад),
//     группа «К соответствующему периоду предыдущего года» (дефолт);
//   - `yoy-annual` — Г/г «по годам» (декабрь к декабрю, одна точка/год),
//     подрежим группы «К прошлому периоду»;
//   - `qoq` — Кв/Кв; `index`/`index-annual` — накопленный уровень.
export const HOUSING_URL_MODES = ['yoy', 'yoy-annual', 'qoq', 'index', 'index-annual'];

const LEGACY_TO_CANONICAL = {
  level: 'index',
};

export function normalizeHousingViewMode(viewMode) {
  if (!viewMode) return 'yoy';
  const canonical = LEGACY_TO_CANONICAL[viewMode]
    ?? (HOUSING_URL_MODES.includes(viewMode) ? viewMode : null);
  if (!canonical) return 'yoy';
  return canonical;
}

export function isActiveHousingUrlMode(viewMode) {
  if (!viewMode) return false;
  const raw = LEGACY_TO_CANONICAL[viewMode] ?? viewMode;
  return HOUSING_URL_MODES.includes(raw);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeHousingViewMode(viewMode);
  if (mode === 'yoy') return 'inflation';
  if (mode.startsWith('index')) return 'index';
  return 'step';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeHousingViewMode(viewMode);
  // `yoy` — лист дефолтной группы «К соотв. периоду пред. года»: не раскрываем.
  if (mode === 'yoy') return null;
  if (mode.startsWith('index')) return 'index';
  return 'step';
}

/** Подрежимы группы «Индекс» → гранулярность последней точки периода. */
export function housingIndexGranularity(viewMode) {
  const mode = normalizeHousingViewMode(viewMode);
  if (mode === 'index-annual') return 'year';
  return null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

/** Какой ряд грузить (совместим с chartMode в useIndicatorViewModeData). */
export function dataModeForHousingUrlMode(viewMode) {
  const mode = normalizeHousingViewMode(viewMode);
  if (mode.startsWith('index')) return 'index';
  if (mode === 'qoq') return 'qoq';
  // Г/г «по годам» — годовой ряд декабрь-к-декабрю (одна точка/год).
  if (mode === 'yoy-annual') return 'annual';
  return 'yoy';
}

/** Старые derived-URL → каноническая карточка parent + ?mode= */
export function housingCanonicalTarget(code) {
  const map = {
    'housing-yoy-primary': { parentCode: 'housing-price-primary', mode: 'yoy' },
    'housing-yoy-secondary': { parentCode: 'housing-price-secondary', mode: 'yoy' },
    'housing-qoq-primary': { parentCode: 'housing-price-primary', mode: 'qoq' },
    'housing-qoq-secondary': { parentCode: 'housing-price-secondary', mode: 'qoq' },
  };
  return map[code] ?? null;
}
