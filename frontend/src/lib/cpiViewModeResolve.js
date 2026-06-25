/**
 * Канонические URL-режимы ИПЦ и их разрешение в ряд данных / группу UI.
 *
 * Правки созвона 2026-06-11:
 *   - «Инфляция за год» переименована в «К соответствующему периоду
 *     предыдущего года» (режим `inflation`, остаётся дефолтом);
 *   - Г/г (`yoy`) считается по годам — декабрь к декабрю, одна точка на год
 *     (ряд `*-annual`), а не по месяцам;
 *   - легаси-режимы «Рост за период» `quarterly`/`annual` канонизируются в
 *     `qoq`/`yoy` (математически это те же ряды);
 *   - недельные режимы доступны только на общем ИПЦ: по срезам корзины
 *     официальной недельной статистики нет.
 */

/** @typedef {'inflation'|'index'|'index-quarterly'|'index-annual'|'period-weekly'|'period-monthly'|'step-weekly'|'step-monthly'|'qoq'|'yoy'} CpiUrlMode */

/** @typedef {'inflation'|'index'|'annual'|'weekly'|'cpi'|'qoq'|'period-weekly'|'period-monthly'} CpiDataMode */

export const CPI_URL_MODES = [
  'inflation',
  'inflation-quarter',
  'inflation-year',
  'index',
  'index-quarterly',
  'index-annual',
  'period-weekly',
  'period-monthly',
  'step-weekly',
  'step-monthly',
  'qoq',
  'yoy',
];

/** Режимы, требующие недельного ряда — есть только у общего ИПЦ. */
const WEEKLY_URL_MODES = new Set(['step-weekly', 'period-weekly', 'period-monthly']);

/** Подрежимы группы «Индекс» → гранулярность последней точки периода. */
export function cpiIndexGranularity(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  if (mode === 'index-quarterly') return 'quarter';
  if (mode === 'index-annual') return 'year';
  return null;
}

/** Подрежимы группы «К соотв. периоду пред. года» → гранулярность точки. */
export function cpiInflationGranularity(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  if (mode === 'inflation-quarter') return 'quarter';
  if (mode === 'inflation-year') return 'year';
  return null;
}

export const CPI_DISABLED_MODES = new Set();

/** Режимы с собственным рядом и корректным графиком. */
export const CPI_ACTIVE_URL_MODES = [...CPI_URL_MODES];

const LEGACY_TO_CANONICAL = {
  weekly: 'step-weekly',
  cpi: 'step-monthly',
  // «Рост за период»: квартальная = кв/кв, годовая = г/г (декабрь к декабрю).
  quarterly: 'qoq',
  annual: 'yoy',
};

export function normalizeCpiViewMode(viewMode) {
  if (!viewMode) return 'inflation';
  const canonical = LEGACY_TO_CANONICAL[viewMode]
    ?? (CPI_URL_MODES.includes(viewMode) ? viewMode : null);
  if (!canonical) return 'inflation';
  return canonical;
}

/** Доступен ли режим для данного кода состава корзины (срезы — без недельных). */
export function isCpiModeAvailableForCode(viewMode, code) {
  if (!code || code === 'cpi') return true;
  return !WEEKLY_URL_MODES.has(normalizeCpiViewMode(viewMode));
}

export function isCpiModeDisabled(viewMode) {
  if (!viewMode) return false;
  const raw = LEGACY_TO_CANONICAL[viewMode] ?? viewMode;
  return CPI_DISABLED_MODES.has(raw);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  if (mode.startsWith('inflation')) return 'inflation';
  if (mode.startsWith('index')) return 'index';
  if (mode.startsWith('period-')) return 'period';
  if (mode.startsWith('step-') || mode === 'qoq' || mode === 'yoy') {
    return 'step';
  }
  return 'inflation';
}

export function expandedGroupForMode(viewMode) {
  return topGroupForMode(viewMode);
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

/** Какой ряд/API грузить. */
export function dataModeForUrlMode(viewMode) {
  const mode = normalizeCpiViewMode(viewMode);
  switch (mode) {
    case 'inflation':
    case 'inflation-quarter':
    case 'inflation-year':
      return 'inflation';
    case 'index':
    case 'index-quarterly':
    case 'index-annual':
      return 'index';
    case 'period-weekly':
      return 'period-weekly';
    case 'step-weekly':
      return 'weekly';
    case 'period-monthly':
      return 'period-monthly';
    case 'step-monthly':
      return 'cpi';
    case 'yoy':
      // Г/г по годам: ряд годовой инфляции «декабрь к декабрю» (одна точка/год).
      return 'annual';
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
