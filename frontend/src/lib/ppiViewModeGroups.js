/**
 * Двухуровневый переключатель ИЦП — ось как у ИПЦ на ежемесячных данных.
 *
 * Верх: К соответствующему периоду предыдущего года | К прошлому периоду | Индекс
 * «Индекс» раскрывается в по месяцам / по кварталам / по годам.
 *
 * Источник: в обзоре Росстата — м/м и г/г в %; в БД — накопленный индекс
 * 2010=100. «К соответствующему периоду предыдущего года» — помесячный
 * ряд г/г; Г/г в «К прошлому периоду» — по годам, декабрь к декабрю
 * (правки созвона 2026-06-11, «под копирку» с ИПЦ).
 */

export const PPI_TOP_GROUPS = [
  {
    id: 'inflation',
    label: 'К соотв. периоду пред. года',
    leafMode: 'yoy',
  },
  {
    id: 'step',
    label: 'К прошлому периоду',
    modes: [
      { mode: 'mom', label: 'М/м' },
      { mode: 'qoq', label: 'Кв/Кв' },
      { mode: 'annual', label: 'Г/г' },
    ],
  },
  {
    id: 'index',
    label: 'Индекс',
    modes: [
      { mode: 'index', label: 'По месяцам' },
      { mode: 'index-quarterly', label: 'По кварталам' },
      { mode: 'index-annual', label: 'По годам' },
    ],
  },
];

export {
  PPI_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizePpiViewMode,
  topGroupForMode,
} from './ppiViewModeResolve.js';

export const PPI_VIEW_MODES_FLAT = [
  { mode: 'yoy', label: 'К соотв. периоду пред. года' },
  { mode: 'mom', label: 'К прошлому периоду (м/м)' },
  { mode: 'qoq', label: 'К прошлому периоду (кв/кв)' },
  { mode: 'annual', label: 'К прошлому периоду (г/г)' },
  { mode: 'index', label: 'Индекс — по месяцам' },
  { mode: 'index-quarterly', label: 'Индекс — по кварталам' },
  { mode: 'index-annual', label: 'Индекс — по годам' },
];

export function getTopGroup(id) {
  return PPI_TOP_GROUPS.find((g) => g.id === id);
}

/** Первый доступный подрежим группы (актуально только для «Индекс»). */
export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  const first = group.modes.find((m) => !m.disabled);
  return first?.mode ?? null;
}
