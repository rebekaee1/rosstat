/**
 * Средняя заработная плата: номинальный уровень, годовой ряд, реальная, г/г, индекс.
 */

export const WAGES_NOMINAL_ROOT = 'wages-nominal';

export const WAGES_NOMINAL_DERIVED_CODES = [
  'wages-real',
  'wages-yoy',
  'wages-index',
  'wages-nominal-annual',
];

export const WAGES_NOMINAL_URL_MODES = [
  'level',
  'annual',
  'real',
  'yoy',
  'index',
];

/** Режим UI → код ряда в БД. */
export const WAGES_NOMINAL_MODE_ROWS = [
  {
    mode: 'level',
    label: 'Помесячно',
    code: WAGES_NOMINAL_ROOT,
    unit: 'руб.',
    frequency: 'monthly',
  },
  {
    mode: 'annual',
    label: 'С 1991 года',
    code: 'wages-nominal-annual',
    unit: 'руб.',
    frequency: 'annual',
  },
  {
    mode: 'real',
    label: 'Реальная',
    code: 'wages-real',
    unit: '%',
    frequency: 'monthly',
  },
  {
    mode: 'yoy',
    label: 'Год к году',
    code: 'wages-yoy',
    unit: '%',
    frequency: 'monthly',
  },
  {
    mode: 'index',
    label: 'Индекс 2015=100',
    code: 'wages-index',
    unit: 'индекс',
    frequency: 'monthly',
  },
];

const AMOUNT_MODES = new Set(['level', 'annual']);
const DYNAMICS_MODES = new Set(['real', 'yoy', 'index']);

export function isWagesNominalFamily(code) {
  return code === WAGES_NOMINAL_ROOT || WAGES_NOMINAL_DERIVED_CODES.includes(code);
}

export function normalizeWagesNominalViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return WAGES_NOMINAL_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveWagesNominalUrlMode(viewMode) {
  if (!viewMode) return false;
  return WAGES_NOMINAL_URL_MODES.includes(viewMode);
}

export function wagesNominalModeMeta(viewMode) {
  const mode = normalizeWagesNominalViewMode(viewMode);
  return WAGES_NOMINAL_MODE_ROWS.find((m) => m.mode === mode)
    ?? WAGES_NOMINAL_MODE_ROWS[0];
}

export function wagesNominalDataCodeForMode(viewMode) {
  return wagesNominalModeMeta(viewMode).code;
}

export function topGroupForMode(viewMode) {
  const mode = normalizeWagesNominalViewMode(viewMode);
  if (AMOUNT_MODES.has(mode)) return 'amount';
  if (DYNAMICS_MODES.has(mode)) return 'dynamics';
  return 'amount';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeWagesNominalViewMode(viewMode);
  if (AMOUNT_MODES.has(mode)) return 'amount';
  if (DYNAMICS_MODES.has(mode)) return 'dynamics';
  return null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForWagesNominalUrlMode(viewMode) {
  return normalizeWagesNominalViewMode(viewMode);
}

/** Derived-URL → каноническая карточка с ?mode=. */
export function wagesNominalCanonicalTarget(code) {
  const row = WAGES_NOMINAL_MODE_ROWS.find((m) => m.code === code);
  if (row && row.mode !== 'level') {
    return { parentCode: WAGES_NOMINAL_ROOT, mode: row.mode };
  }
  return null;
}
