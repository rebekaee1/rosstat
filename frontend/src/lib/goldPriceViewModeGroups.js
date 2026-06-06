/**
 * Переключатель цены золота — ежедневно и сглаживание по периодам.
 */

export const GOLD_PRICE_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Цена (ежедневно)',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'weekly', label: 'По неделям' },
      { mode: 'monthly', label: 'По месяцам' },
      { mode: 'quarterly', label: 'По кварталам' },
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  GOLD_PRICE_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeGoldPriceViewMode,
  topGroupForMode,
} from './goldPriceViewModeResolve.js';

export function getTopGroup(id) {
  return GOLD_PRICE_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
