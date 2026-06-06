/**
 * Номинальный ВВП: уровень, темпы г/г и к/к, годовая сумма.
 */

export const GDP_NOMINAL_ROOT = 'gdp-nominal';

export const GDP_NOMINAL_DERIVED_CODES = [
  'gdp-yoy',
  'gdp-qoq',
  'gdp-nominal-annual',
];

export const GDP_NOMINAL_URL_MODES = [
  'level',
  'yoy',
  'qoq',
  'annual',
];

/** Режим UI → код ряда в БД. */
export const GDP_NOMINAL_MODE_ROWS = [
  {
    mode: 'level',
    label: 'Поквартально',
    code: GDP_NOMINAL_ROOT,
    unit: 'млрд руб.',
    frequency: 'quarterly',
  },
  {
    mode: 'yoy',
    label: 'Год к году',
    code: 'gdp-yoy',
    unit: '%',
    frequency: 'quarterly',
  },
  {
    mode: 'qoq',
    label: 'Квартал к кварталу',
    code: 'gdp-qoq',
    unit: '%',
    frequency: 'quarterly',
  },
  {
    mode: 'annual',
    label: 'За год',
    code: 'gdp-nominal-annual',
    unit: 'млрд руб.',
    frequency: 'annual',
  },
];

const DYNAMICS_MODES = new Set(['yoy', 'qoq']);

export function isGdpNominalFamily(code) {
  return code === GDP_NOMINAL_ROOT || GDP_NOMINAL_DERIVED_CODES.includes(code);
}

export function normalizeGdpNominalViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return GDP_NOMINAL_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveGdpNominalUrlMode(viewMode) {
  if (!viewMode) return false;
  return GDP_NOMINAL_URL_MODES.includes(viewMode);
}

export function gdpNominalModeMeta(viewMode) {
  const mode = normalizeGdpNominalViewMode(viewMode);
  return GDP_NOMINAL_MODE_ROWS.find((m) => m.mode === mode)
    ?? GDP_NOMINAL_MODE_ROWS[0];
}

export function gdpNominalDataCodeForMode(viewMode) {
  return gdpNominalModeMeta(viewMode).code;
}

export function topGroupForMode(viewMode) {
  const mode = normalizeGdpNominalViewMode(viewMode);
  if (mode === 'annual') return 'annual';
  if (DYNAMICS_MODES.has(mode)) return 'dynamics';
  return 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeGdpNominalViewMode(viewMode);
  if (DYNAMICS_MODES.has(mode)) return 'dynamics';
  return null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForGdpNominalUrlMode(viewMode) {
  return normalizeGdpNominalViewMode(viewMode);
}

/** Derived-URL → каноническая карточка с ?mode=. */
export function gdpNominalCanonicalTarget(code) {
  const row = GDP_NOMINAL_MODE_ROWS.find((m) => m.code === code);
  if (row && row.mode !== 'level') {
    return { parentCode: GDP_NOMINAL_ROOT, mode: row.mode };
  }
  return null;
}
