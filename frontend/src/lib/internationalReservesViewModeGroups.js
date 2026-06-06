/**
 * Переключатель международных резервов — еженедельно и среднее за период.
 */

export const INTERNATIONAL_RESERVES_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Еженедельно',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'monthly', label: 'По месяцам' },
      { mode: 'quarterly', label: 'По кварталам' },
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  INTERNATIONAL_RESERVES_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeInternationalReservesViewMode,
  topGroupForMode,
} from './internationalReservesViewModeResolve.js';

export function getTopGroup(id) {
  return INTERNATIONAL_RESERVES_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
