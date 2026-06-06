/**
 * Канонические URL-режимы ИПЦ и их разрешение в ряд данных / группу UI.
 *
 * «Рост за период» и «К прошлому периоду» не делят один ?mode= — у каждой
 * кнопки свой идентификатор.
 */

/** @typedef {'inflation'|'index'|'quarterly'|'annual'|'period-weekly'|'period-monthly'|'step-weekly'|'step-monthly'|'qoq'|'yoy'} CpiUrlMode */

/** @typedef {'inflation'|'index'|'quarterly'|'annual'|'weekly'|'cpi'|'yoy'|'qoq'|'period-weekly'|'period-monthly'} CpiDataMode */

export const CPI_URL_MODES = [
  'inflation',
  'index',
  'index-quarterly',
  'index-annual',
  'period-weekly',
  'period-monthly',
  'quarterly',
  'annual',
  'step-weekly',
  'step-monthly',
  'qoq',
  'yoy',
];

/** Подрежимы группы «Индекс» → гранулярность последней точки периода. */
export function cpiIndexGranularity(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  if (mode === 'index-quarterly') return 'quarter';
  if (mode === 'index-annual') return 'year';
  return null;
}

export const CPI_DISABLED_MODES = new Set();

/** Режимы с собственным рядом и корректным графиком. */
export const CPI_ACTIVE_URL_MODES = [...CPI_URL_MODES];

const LEGACY_TO_CANONICAL = {
  weekly: 'step-weekly',
  cpi: 'step-monthly',
};

export function normalizeCpiViewMode(viewMode) {
  if (!viewMode) return 'inflation';
  const canonical = LEGACY_TO_CANONICAL[viewMode]
    ?? (CPI_URL_MODES.includes(viewMode) ? viewMode : null);
  if (!canonical) return 'inflation';
  return canonical;
}

export function isCpiModeDisabled(viewMode) {
  if (!viewMode) return false;
  const raw = LEGACY_TO_CANONICAL[viewMode] ?? viewMode;
  return CPI_DISABLED_MODES.has(raw);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  if (mode === 'inflation') return 'inflation';
  if (mode.startsWith('index')) return 'index';
  if (mode.startsWith('period-') || mode === 'quarterly' || mode === 'annual') {
    return 'period';
  }
  if (mode.startsWith('step-') || mode === 'qoq' || mode === 'yoy') {
    return 'step';
  }
  return 'inflation';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  if (mode === 'inflation') return null;
  return topGroupForMode(mode);
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

/** Какой ряд/API грузить. */
export function dataModeForUrlMode(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  switch (mode) {
    case 'inflation':
      return 'inflation';
    case 'index':
    case 'index-quarterly':
    case 'index-annual':
      return 'index';
    case 'quarterly':
      return 'quarterly';
    case 'annual':
      return 'annual';
    case 'period-weekly':
      return 'period-weekly';
    case 'step-weekly':
      return 'weekly';
    case 'period-monthly':
      return 'period-monthly';
    case 'step-monthly':
      return 'cpi';
    case 'yoy':
      return 'yoy';
    case 'qoq':
      return 'qoq';
    default:
      return 'inflation';
  }
}

export function isActiveCpiUrlMode(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  return CPI_ACTIVE_URL_MODES.includes(mode);
}
