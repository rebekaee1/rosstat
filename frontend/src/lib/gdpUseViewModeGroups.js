/**
 * Переключатель компонентов ВВП по использованию — поквартально и среднее по годам.
 */

export const GDP_USE_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Поквартально',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  GDP_USE_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeGdpUseViewMode,
  topGroupForMode,
} from './gdpUseViewModeResolve.js';

export function getTopGroup(id) {
  return GDP_USE_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
