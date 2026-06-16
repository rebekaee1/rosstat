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
    id: 'inflation',
    label: 'К соотв. периоду пред. года',
    leafMode: 'yoy',
  },
  {
    id: 'step',
    label: 'К прошлому периоду',
    modes: [
      { mode: 'qoq', label: 'Кв/Кв' },
      { mode: 'yoy-annual', label: 'Г/г' },
    ],
  },
  {
    id: 'index',
    label: 'Индекс',
    modes: [
      { mode: 'index', label: 'По кварталам' },
      { mode: 'index-annual', label: 'По годам' },
    ],
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
  { mode: 'yoy', label: 'К соотв. периоду пред. года' },
  { mode: 'qoq', label: 'Кв/Кв' },
  { mode: 'yoy-annual', label: 'Г/г' },
  { mode: 'index', label: 'Индекс — по кварталам' },
  { mode: 'index-annual', label: 'Индекс — по годам' },
];

export function getTopGroup(id) {
  return HOUSING_TOP_GROUPS.find((g) => g.id === id);
}

/** При раскрытии «К прошлому периоду» — кв/кв (как в бюллетене Росстата). */
export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  if (groupId === 'step') return 'qoq';
  const first = group.modes.find((m) => !m.disabled);
  return first?.mode ?? null;
}
