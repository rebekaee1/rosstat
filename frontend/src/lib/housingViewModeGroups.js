/**
 * Двухуровневый переключатель цен на жильё — ось как у ИПЦ, с учётом квартальной частоты.
 *
 * Источник (PDF): официально публикуется прирост к/к; индекс 2010=100 — цепочка
 * от этих приростов; г/г — производный ряд от индекса.
 *
 * Нет аналогов: «Инфляция за 12 мес.» и «Рост за период» (неделя/месяц) — только
 * квартальные ряды.
 */

export const HOUSING_TOP_GROUPS = [
  {
    id: 'step',
    label: 'К прошлому периоду',
    modes: [
      { mode: 'qoq', label: 'К/к' },
      { mode: 'yoy', label: 'Г/г' },
    ],
  },
  {
    id: 'index',
    label: 'Индекс',
    leafMode: 'index',
  },
];

export {
  HOUSING_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeHousingViewMode,
  topGroupForMode,
} from './housingViewModeResolve.js';

export const HOUSING_VIEW_MODES_FLAT = [
  { mode: 'qoq', label: 'К/к' },
  { mode: 'yoy', label: 'Г/г' },
  { mode: 'index', label: 'Индекс' },
];

export function getTopGroup(id) {
  return HOUSING_TOP_GROUPS.find((g) => g.id === id);
}

/** При раскрытии «К прошлому периоду» — к/к (как в бюллетене Росстата). */
export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  if (groupId === 'step') return 'qoq';
  const first = group.modes.find((m) => !m.disabled);
  return first?.mode ?? null;
}
