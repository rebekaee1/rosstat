/**
 * Двухуровневый переключатель режимов ИПЦ (вариант A).
 *
 * Верх: Инфляция за год | К прошлому периоду | Индекс
 * Низ: у каждой кнопки свой ?mode= (см. cpiViewModeResolve.js).
 *
 * Правки созвона 2026-06-06: группа «Рост за период» удалена; «Индекс» стал
 * раскрывающейся группой (по месяцам / кварталам / годам); в «К прошлому
 * периоду» квартальный шаг переименован в «Кв/Кв».
 */

/** @typedef {'inflation'|'step'|'index'} CpiViewTopGroupId */

/** @typedef {{ mode: string, label: string, disabled?: boolean, hint?: string }} CpiViewLeafMode */

export const CPI_TOP_GROUPS = [
  {
    id: 'inflation',
    label: 'Инфляция за год',
    leafMode: 'inflation',
  },
  {
    id: 'step',
    label: 'К прошлому периоду',
    modes: [
      { mode: 'step-weekly', label: 'Н/н' },
      { mode: 'step-monthly', label: 'М/м' },
      { mode: 'qoq', label: 'Кв/Кв' },
      { mode: 'yoy', label: 'Г/г' },
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
  CPI_ACTIVE_URL_MODES as CPI_ACTIVE_MODES,
  CPI_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeCpiViewMode,
  topGroupForMode,
} from './cpiViewModeResolve.js';

/** Плоский список (legacy / поиск). */
/** Только активные режимы (дамп методологий, поиск). */
export const CPI_VIEW_MODES_FLAT = [
  { mode: 'inflation', label: 'Инфляция за год' },
  { mode: 'step-weekly', label: 'Н/н' },
  { mode: 'step-monthly', label: 'М/м' },
  { mode: 'qoq', label: 'Кв/Кв' },
  { mode: 'yoy', label: 'Г/г' },
  { mode: 'index', label: 'Индекс — по месяцам' },
  { mode: 'index-quarterly', label: 'Индекс — по кварталам' },
  { mode: 'index-annual', label: 'Индекс — по годам' },
];

export function getTopGroup(id) {
  return CPI_TOP_GROUPS.find((g) => g.id === id);
}

/** Первый доступный подрежим группы. */
export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  const first = group.modes.find((m) => !m.disabled);
  return first?.mode ?? null;
}

export function visibleCpiViewModes(_code) {
  void _code;
  return CPI_VIEW_MODES_FLAT;
}
