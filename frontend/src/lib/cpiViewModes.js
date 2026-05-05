/**
 * Доступные режимы графика для индикаторов из категории «Цены»
 * (cpi / cpi-food / cpi-nonfood / cpi-services).
 *
 * - inflation: накопленная инфляция за 12 месяцев (доступно для всех CPI-кодов)
 * - weekly:    недельный ИПЦ (только для общего cpi — Росстат публикует
 *              недельный бюллетень только по полной корзине)
 * - cpi:       месячный прирост к предыдущему месяцу
 * - quarterly: квартальная инфляция (произведение 3 месячных индексов)
 * - annual:    годовая инфляция (скользящее окно 12 месяцев)
 * - index:     уровень индекса (значения вокруг 100, как у housing). Прогноз
 *              на этом режиме приходит из того же CPI-Monthly (без вычитания 100).
 */
export const CPI_VIEW_MODES = [
  { mode: 'inflation', label: 'Инфляция за год', generalOnly: false },
  { mode: 'weekly', label: 'Недельная', generalOnly: true },
  { mode: 'cpi', label: 'Месячная', generalOnly: false },
  { mode: 'quarterly', label: 'Квартальная', generalOnly: false },
  { mode: 'annual', label: 'Годовая', generalOnly: false },
  { mode: 'index', label: 'Индекс', generalOnly: false },
];

/**
 * Получить список режимов, доступных для конкретного кода:
 * для общего `cpi` — все режимы; для подкатегорий — без `weekly`.
 */
export function visibleCpiViewModes(code) {
  return CPI_VIEW_MODES.filter((item) => !item.generalOnly || code === 'cpi');
}
