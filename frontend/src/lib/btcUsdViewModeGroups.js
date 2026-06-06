/**
 * Переключатель BTC/USD — ежедневная цена и сглаживание по периодам.
 */

export const BTC_USD_TOP_GROUPS = [
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
  BTC_USD_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeBtcUsdViewMode,
  topGroupForMode,
} from './btcUsdViewModeResolve.js';

export function getTopGroup(id) {
  return BTC_USD_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
