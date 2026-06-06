/**
 * Реальный ВВП: уровень, темпы г/г и к/к, годовая сумма.
 */

export const GDP_REAL_ROOT = 'gdp-real';

export const GDP_REAL_DERIVED_CODES = [
  'gdp-real-yoy',
  'gdp-real-qoq',
  'gdp-real-annual',
];

export const GDP_REAL_URL_MODES = [
  'level',
  'yoy',
  'qoq',
  'annual',
];

/** Режим UI → код ряда в БД. */
export const GDP_REAL_MODE_ROWS = [
  {
    mode: 'level',
    label: 'Поквартально',
    code: GDP_REAL_ROOT,
    unit: 'млрд руб.',
    frequency: 'quarterly',
  },
  {
    mode: 'yoy',
    label: 'Год к году',
    code: 'gdp-real-yoy',
    unit: '%',
    frequency: 'quarterly',
  },
  {
    mode: 'qoq',
    label: 'Квартал к кварталу',
    code: 'gdp-real-qoq',
    unit: '%',
    frequency: 'quarterly',
  },
  {
    mode: 'annual',
    label: 'За год',
    code: 'gdp-real-annual',
    unit: 'млрд руб.',
    frequency: 'annual',
  },
];

const DYNAMICS_MODES = new Set(['yoy', 'qoq']);

export function isGdpRealFamily(code) {
  return code === GDP_REAL_ROOT || GDP_REAL_DERIVED_CODES.includes(code);
}

export function normalizeGdpRealViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return GDP_REAL_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveGdpRealUrlMode(viewMode) {
  if (!viewMode) return false;
  return GDP_REAL_URL_MODES.includes(viewMode);
}

export function gdpRealModeMeta(viewMode) {
  const mode = normalizeGdpRealViewMode(viewMode);
  return GDP_REAL_MODE_ROWS.find((m) => m.mode === mode)
    ?? GDP_REAL_MODE_ROWS[0];
}

export function gdpRealDataCodeForMode(viewMode) {
  return gdpRealModeMeta(viewMode).code;
}

export function topGroupForMode(viewMode) {
  const mode = normalizeGdpRealViewMode(viewMode);
  if (mode === 'annual') return 'annual';
  if (DYNAMICS_MODES.has(mode)) return 'dynamics';
  return 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeGdpRealViewMode(viewMode);
  if (DYNAMICS_MODES.has(mode)) return 'dynamics';
  return null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForGdpRealUrlMode(viewMode) {
  return normalizeGdpRealViewMode(viewMode);
}

/** Derived-URL → каноническая карточка с ?mode=. */
export function gdpRealCanonicalTarget(code) {
  const row = GDP_REAL_MODE_ROWS.find((m) => m.code === code);
  if (row && row.mode !== 'level') {
    return { parentCode: GDP_REAL_ROOT, mode: row.mode };
  }
  return null;
}
