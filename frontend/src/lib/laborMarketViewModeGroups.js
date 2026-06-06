/**
 * Переключатель рынка труда — помесячно и сглаживание по периодам.
 */

export const LABOR_MARKET_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Помесячно',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'quarterly', label: 'По кварталам' },
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  LABOR_MARKET_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeLaborMarketViewMode,
  topGroupForMode,
} from './laborMarketViewModeResolve.js';

export function getTopGroup(id) {
  return LABOR_MARKET_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
