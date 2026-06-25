/**
 * Двухуровневый переключатель режимов ИПЦ (вариант A).
 *
 * Верх: К соответствующему периоду предыдущего года | К прошлому периоду | Индекс
 * Низ: у каждой кнопки свой ?mode= (см. cpiViewModeResolve.js).
 *
 * Правки созвона 2026-06-06: группа «Рост за период» удалена; «Индекс» стал
 * раскрывающейся группой (по месяцам / кварталам / годам); в «К прошлому
 * периоду» квартальный шаг переименован в «Кв/Кв».
 * Правки созвона 2026-06-11: «Инфляция за год» переименована в
 * «К соответствующему периоду предыдущего года» (тот же ряд, остаётся
 * дефолтом); Г/г считается по годам; недельный шаг (Н/н) — только на общем
 * ИПЦ, по срезам корзины официальной недельной статистики нет.
 */

/** @typedef {'inflation'|'step'|'index'} CpiViewTopGroupId */

/** @typedef {{ mode: string, label: string, cpiOnly?: boolean, disabled?: boolean, hint?: string }} CpiViewLeafMode */

export const CPI_TOP_GROUPS = [
  {
    id: 'inflation',
    label: 'К соотв. периоду пред. года',
    modes: [
      { mode: 'inflation', label: 'По месяцам' },
      { mode: 'inflation-quarter', label: 'По кварталам' },
      { mode: 'inflation-year', label: 'По годам' },
    ],
  },
  {
    id: 'step',
    label: 'К прошлому периоду',
    modes: [
      { mode: 'step-weekly', label: 'Н/н', cpiOnly: true },
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
  isCpiModeAvailableForCode,
  normalizeCpiViewMode,
  topGroupForMode,
} from './cpiViewModeResolve.js';

/** Группы переключателя для конкретного состава корзины (срезы — без Н/н). */
export function cpiTopGroupsForCode(code) {
  if (!code || code === 'cpi') return CPI_TOP_GROUPS;
  return CPI_TOP_GROUPS.map((group) => (group.modes
    ? { ...group, modes: group.modes.filter((m) => !m.cpiOnly) }
    : group));
}

/** Плоский список (legacy / поиск). */
/** Только активные режимы (дамп методологий, поиск). */
export const CPI_VIEW_MODES_FLAT = [
  { mode: 'inflation', label: 'К соотв. периоду пред. года — по месяцам' },
  { mode: 'inflation-quarter', label: 'К соотв. периоду пред. года — по кварталам' },
  { mode: 'inflation-year', label: 'К соотв. периоду пред. года — по годам' },
  { mode: 'step-weekly', label: 'Н/н', cpiOnly: true },
  { mode: 'step-monthly', label: 'М/м' },
  { mode: 'qoq', label: 'Кв/Кв' },
  { mode: 'yoy', label: 'Г/г' },
  { mode: 'index', label: 'Индекс — по месяцам' },
  { mode: 'index-quarterly', label: 'Индекс — по кварталам' },
  { mode: 'index-annual', label: 'Индекс — по годам' },
];

export function getTopGroup(id, code = null) {
  return cpiTopGroupsForCode(code).find((g) => g.id === id);
}

/** Первый доступный подрежим группы. */
export function defaultSubModeForGroup(groupId, code = null) {
  const group = getTopGroup(groupId, code);
  if (!group?.modes) return null;
  const first = group.modes.find((m) => !m.disabled);
  return first?.mode ?? null;
}

export function visibleCpiViewModes(code) {
  if (!code || code === 'cpi') return CPI_VIEW_MODES_FLAT;
  return CPI_VIEW_MODES_FLAT.filter((m) => !m.cpiOnly);
}
