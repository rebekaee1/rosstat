/**
 * Смертемость: число смертей и коэффициент (‰), уровень и темп г/г.
 * Темп г/г на фронте (годовые точки → соседние годы).
 */

export const DEATHS_ROOT = 'deaths';

export const DEATHS_DEMO_CODES = [
  'deaths',
  'death-rate',
];

export const DEATHS_URL_MODES = [
  'level',
  'yoy',
];

export function isDeathsDemoFamily(code) {
  return DEATHS_DEMO_CODES.includes(code);
}

export function normalizeDeathsViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return DEATHS_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveDeathsUrlMode(viewMode) {
  if (!viewMode) return false;
  return DEATHS_URL_MODES.includes(viewMode);
}

export function deathsModeMeta(viewMode, indicatorCode = DEATHS_ROOT) {
  const mode = normalizeDeathsViewMode(viewMode);
  if (mode === 'yoy') {
    return {
      mode: 'yoy',
      label: 'Год к году',
      unit: '%',
      frequency: 'annual',
    };
  }
  if (indicatorCode === 'death-rate') {
    return {
      mode: 'level',
      label: 'За год',
      code: 'death-rate',
      unit: '‰',
      frequency: 'annual',
    };
  }
  return {
    mode: 'level',
    label: 'За год',
    code: DEATHS_ROOT,
    unit: 'тыс. чел.',
    frequency: 'annual',
  };
}

export function topGroupForMode(viewMode) {
  return normalizeDeathsViewMode(viewMode);
}

export function expandedGroupForMode() {
  return null;
}

export function highlightedTopGroup(_expandedGroupId, currentMode) {
  return topGroupForMode(currentMode);
}

export function dataModeForDeathsUrlMode(viewMode) {
  return normalizeDeathsViewMode(viewMode);
}

export function isDeathsVirtualYoyMode(viewMode) {
  return normalizeDeathsViewMode(viewMode) === 'yoy';
}

/** Нет отдельных derived-URL — только канонические карточки. */
export function deathsCanonicalTarget(_code) {
  return null;
}
