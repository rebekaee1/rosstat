/**
 * Описание и методология: нефть Brent (режим × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isBrentFamily } from './brentViewModeResolve';

function contentLevel() {
  return {
    description:
      'На графике — цена нефти марки Brent в долларах США за баррель '
      + 'на конец каждого календарного дня по рыночным котировкам. '
      + 'Brent — главный мировой ориентир для сортов нефти из Северного '
      + 'моря; для России динамика цены связана с экспортными доходами, '
      + 'курсом рубля и бюджетом.',
    methodology:
      'Режим «цена (ежедневно)» — дневной ряд в долларах за баррель. '
      + 'Каждая точка — итог дня; внутридневные колебания на графике '
      + 'не разворачиваются. Прогноз не строится. Для сглаженного тренда '
      + 'без дневного шума выберите «Среднее за период» в переключателе '
      + 'над графиком.',
  };
}

function contentAgg(mode) {
  const labels = {
    weekly: 'неделям',
    monthly: 'месяцам',
    quarterly: 'кварталам',
    annual: 'годам',
  };
  const period = labels[mode] ?? 'периодам';
  const periodLabel = period === 'неделям' ? 'по неделям'
    : period === 'месяцам' ? 'по месяцам'
      : period === 'кварталам' ? 'по кварталам' : 'по годам';
  return {
    description:
      `На графике — средняя цена Brent в долларах за баррель внутри `
      + `календарных ${period}: из ежедневного ряда считается простое `
      + `среднее по всем дням с опубликованным значением. Так проще увидеть `
      + `тренд за месяц или квартал без резких скачков отдельных сессий.`,
    methodology:
      `Режим «среднее за период — ${periodLabel}»: агрегация выполняется `
      + 'на стороне отображения из того же дневного ряда, что и в режиме '
      + 'цены. Это не отдельная официальная публикация. В расчёт входят '
      + 'только дни, по которым есть дневная точка.',
  };
}

export function getBrentChartTitle(chartMode) {
  switch (chartMode) {
    case 'weekly':
      return 'Нефть Brent — средняя цена по неделям (USD/барр.)';
    case 'monthly':
      return 'Нефть Brent — средняя цена по месяцам (USD/барр.)';
    case 'quarterly':
      return 'Нефть Brent — средняя цена по кварталам (USD/барр.)';
    case 'annual':
      return 'Нефть Brent — средняя цена по годам (USD/барр.)';
    default:
      return 'Нефть Brent (USD/баррель)';
  }
}

export function getBrentTableTitle(chartMode) {
  switch (chartMode) {
    case 'weekly':
      return 'Исторические данные — среднее по неделям';
    case 'monthly':
      return 'Исторические данные — среднее по месяцам';
    case 'quarterly':
      return 'Исторические данные — среднее по кварталам';
    case 'annual':
      return 'Исторические данные — среднее по годам';
    default:
      return 'Исторические данные — Brent';
  }
}

export function getBrentViewModeContent({ chartMode = 'level' }) {
  if (chartMode === 'level') return contentLevel();
  if (['weekly', 'monthly', 'quarterly', 'annual'].includes(chartMode)) {
    return contentAgg(chartMode);
  }
  return contentLevel();
}

export { isBrentFamily };
