/**
 * Описание и методология: курс юаня CNY/RUB (режим × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isCnyRubFamily } from './cnyRubViewModeResolve';

function contentLevel() {
  return {
    description:
      'На графике — официальный курс китайского юаня к рублю в рублях '
      + 'за один юань: значение, которое Банк России устанавливает '
      + 'ежедневно на основе итогов валютного рынка. Линия меняется '
      + 'изо дня в день и отражает, сколько рублей стоит юань в расчётах '
      + 'и отчётности, а не биржевую котировку в реальном времени.',
    methodology:
      'Режим «курс (ежедневно)» — официальный дневной ряд Банка России. '
      + 'Каждая точка — курс на соответствующую дату; в выходные и '
      + 'праздники значение может не обновляться. Прогноз на карточке '
      + 'не строится. Для сглаженного тренда без дневных скачков '
      + 'выберите «Среднее за период» в переключателе над графиком.',
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
      `На графике — средний официальный курс юаня внутри календарных `
      + `${period}: из ежедневного ряда считается простое среднее по всем `
      + `дням с опубликованным значением. Так удобнее сравнить «типичный» `
      + `уровень курса за месяц или квартал без отдельных всплесков дней.`,
    methodology:
      `Режим «среднее за период — ${periodLabel}»: агрегация выполняется `
      + 'на стороне отображения из того же официального ряда, что и в '
      + 'режиме ежедневного курса. Это не отдельная публикация ЦБ. '
      + 'В расчёт входят только дни, по которым Банк России опубликовал курс.',
  };
}

export function getCnyRubChartTitle(chartMode) {
  switch (chartMode) {
    case 'weekly':
      return 'Курс юаня — среднее по неделям (руб.)';
    case 'monthly':
      return 'Курс юаня — среднее по месяцам (руб.)';
    case 'quarterly':
      return 'Курс юаня — среднее по кварталам (руб.)';
    case 'annual':
      return 'Курс юаня — среднее по годам (руб.)';
    default:
      return 'Курс юаня (CNY/RUB)';
  }
}

export function getCnyRubTableTitle(chartMode) {
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
      return 'Исторические данные — CNY/RUB';
  }
}

export function getCnyRubViewModeContent({ chartMode = 'level' }) {
  if (chartMode === 'level') return contentLevel();
  if (['weekly', 'monthly', 'quarterly', 'annual'].includes(chartMode)) {
    return contentAgg(chartMode);
  }
  return contentLevel();
}

export { isCnyRubFamily };
