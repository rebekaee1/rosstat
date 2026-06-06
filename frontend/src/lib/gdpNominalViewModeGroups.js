/**
 * Переключатель номинального ВВП — уровень, темпы, годовой итог.
 */

export const GDP_NOMINAL_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Поквартально',
    leafMode: 'level',
  },
  {
    id: 'dynamics',
    label: 'Темпы',
    modes: [
      { mode: 'yoy', label: 'Год к году' },
      { mode: 'qoq', label: 'Квартал к кварталу' },
    ],
  },
  {
    id: 'annual',
    label: 'За год',
    leafMode: 'annual',
  },
];

export {
  GDP_NOMINAL_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeGdpNominalViewMode,
  topGroupForMode,
} from './gdpNominalViewModeResolve.js';

export function getTopGroup(id) {
  return GDP_NOMINAL_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
