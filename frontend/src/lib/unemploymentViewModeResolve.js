/**
 * Уровень безработицы: помесячный % + derived quarterly / 12М среднее.
 */

export const UNEMPLOYMENT_ROOT = 'unemployment';

export const UNEMPLOYMENT_DERIVED_CODES = [
  'unemployment-quarterly',
  'unemployment-annual',
];

export const UNEMPLOYMENT_URL_MODES = [
  'level',
  'quarterly',
  'annual',
];

/** Режим UI → код ряда в БД и метаданные отображения. */
export const UNEMPLOYMENT_MODE_ROWS = [
  {
    mode: 'level',
    label: 'Помесячно',
    code: UNEMPLOYMENT_ROOT,
    frequency: 'monthly',
    chartSuffix: 'помесячно',
  },
  {
    mode: 'quarterly',
    label: 'По кварталам',
    code: 'unemployment-quarterly',
    frequency: 'quarterly',
    chartSuffix: 'среднее по кварталам',
  },
  {
    mode: 'annual',
    label: '12М среднее',
    code: 'unemployment-annual',
    frequency: 'monthly',
    chartSuffix: 'скользящее 12 месяцев',
  },
];

const AGG_MODES = new Set(['quarterly', 'annual']);

export function isUnemploymentFamily(code) {
  return code === UNEMPLOYMENT_ROOT || UNEMPLOYMENT_DERIVED_CODES.includes(code);
}

export function normalizeUnemploymentViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return UNEMPLOYMENT_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveUnemploymentUrlMode(viewMode) {
  if (!viewMode) return false;
  return UNEMPLOYMENT_URL_MODES.includes(viewMode);
}

export function unemploymentModeMeta(viewMode) {
  const mode = normalizeUnemploymentViewMode(viewMode);
  return UNEMPLOYMENT_MODE_ROWS.find((m) => m.mode === mode)
    ?? UNEMPLOYMENT_MODE_ROWS[0];
}

export function unemploymentDataCodeForMode(viewMode) {
  return unemploymentModeMeta(viewMode).code;
}

export function topGroupForMode(viewMode) {
  const mode = normalizeUnemploymentViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeUnemploymentViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForUnemploymentUrlMode(viewMode) {
  return normalizeUnemploymentViewMode(viewMode);
}

/** Derived-URL → каноническая карточка с ?mode=. */
export function unemploymentCanonicalTarget(code) {
  const row = UNEMPLOYMENT_MODE_ROWS.find((m) => m.code === code);
  if (row && row.mode !== 'level') {
    return { parentCode: UNEMPLOYMENT_ROOT, mode: row.mode };
  }
  return null;
}
