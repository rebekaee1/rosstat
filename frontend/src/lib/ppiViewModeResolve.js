/**
 * URL-режимы семейства ИЦП (ежемесячные ряды Росстата).
 * Семантика групп — как у ИПЦ (cpiViewModeResolve): «Инфляция за год»
 * (помесячный ряд rolling 12m), «К прошлому периоду» (м/м) и «Индекс»
 * с подрежимами по месяцам / кварталам / годам.
 *
 * Правки созвона 2026-06-06: «Инфляция за год» = помесячный г/г (не «декабрь
 * к декабрю»); «Индекс» стал раскрывающейся группой; «декабрь-к-декабрю»
 * (annual) с карточки убран.
 */

export const PPI_CODES = ['ppi'];

export const PPI_URL_MODES = ['yoy', 'mom', 'index', 'index-quarterly', 'index-annual'];

const LEGACY_TO_CANONICAL = {
  level: 'index',
  // старая «годовая» (декабрь к декабрю) больше не показывается отдельно —
  // редиректим на помесячную инфляцию за год.
  annual: 'yoy',
};

export function normalizePpiViewMode(viewMode) {
  if (!viewMode) return 'yoy';
  const canonical = LEGACY_TO_CANONICAL[viewMode]
    ?? (PPI_URL_MODES.includes(viewMode) ? viewMode : null);
  if (!canonical) return 'yoy';
  return canonical;
}

export function isActivePpiUrlMode(viewMode) {
  if (!viewMode) return false;
  const raw = LEGACY_TO_CANONICAL[viewMode] ?? viewMode;
  return PPI_URL_MODES.includes(raw);
}

/** Подрежимы группы «Индекс» → гранулярность последней точки периода. */
export function ppiIndexGranularity(viewMode) {
  const mode = normalizePpiViewMode(viewMode);
  if (mode === 'index-quarterly') return 'quarter';
  if (mode === 'index-annual') return 'year';
  return null;
}

export function topGroupForMode(viewMode) {
  const mode = normalizePpiViewMode(viewMode);
  if (mode === 'yoy') return 'inflation';
  if (mode.startsWith('index')) return 'index';
  return 'step';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizePpiViewMode(viewMode);
  if (mode === 'yoy') return null;
  if (mode === 'mom') return null;
  return 'index';
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForPpiUrlMode(viewMode) {
  const mode = normalizePpiViewMode(viewMode);
  if (mode === 'index-quarterly' || mode === 'index-annual') return 'index';
  return mode;
}

/** Старые derived-URL → каноническая карточка + ?mode= */
export function ppiCanonicalTarget(code) {
  const map = {
    'ppi-yoy': { parentCode: 'ppi', mode: 'yoy' },
    'ppi-annual': { parentCode: 'ppi', mode: 'yoy' },
  };
  return map[code] ?? null;
}
