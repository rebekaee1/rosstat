/**
 * Переключатель «Число смертей» — WIP-модуль под DeathsViewModePicker.
 *
 * Живая карточка `/indicator/deaths` идёт через generic T10
 * (GenericViewModePicker). Режимы здесь зеркалят
 * viewModelFamilies.generated.json::deaths, чтобы import picker'а
 * не ломал Vite, если файл начнут подключать.
 */

export const DEATHS_URL_MODES = ['level', 'yoy', 'index'];

export const DEATHS_TOP_GROUPS = [
  { id: 'level', label: 'Уровень', leafMode: 'level' },
  { id: 'yoy', label: 'К соотв. периоду пред. года', leafMode: 'yoy' },
  { id: 'index', label: 'Индекс', leafMode: 'index' },
];

export function normalizeDeathsViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return DEATHS_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function topGroupForMode(viewMode) {
  const mode = normalizeDeathsViewMode(viewMode);
  return DEATHS_TOP_GROUPS.find((g) => g.leafMode === mode)?.id ?? 'level';
}

/** Все группы leaf — expanded не используется; сигнатура как у unemployment/cpi. */
export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}
