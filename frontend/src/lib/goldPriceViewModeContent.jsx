/**
 * Учётная цена золота Банка России (режим × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isGoldPriceFamily } from './goldPriceViewModeResolve';

function contentLevel() {
  return {
    description:
      'На графике — учётная цена золота Банка России в рублях за грамм '
      + 'на каждый рабочий день публикации. Это официальный ориентир для '
      + 'оценки стоимости монетарного золота и ряда операций регулятора, '
      + 'а не биржевая котировка в долларах за унцию. Рост линии означает '
      + 'дорожающее золото в рублях — из‑за мировой цены, курса или обоих факторов.',
    methodology:
      'Режим «цена (ежедневно)» — дневной ряд учётных цен Банка России '
      + 'в рублях за грамм. Каждая точка — значение на дату публикации; '
      + 'внутридневные колебания бирж в отдельную точку не попадают. '
      + 'Прогноз не строится. Для сглаженного тренда без дневного шума '
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
      `На графике — средняя учётная цена золота в рублях за грамм внутри `
      + `календарных ${period}: из ежедневного ряда считается простое `
      + `среднее по всем дням с опубликованным значением. Так проще увидеть `
      + `тренд за месяц или квартал без резких скачков отдельных сессий `
      + `и курсовых гэпов.`,
    methodology:
      `Режим «среднее за период — ${periodLabel}»: агрегация выполняется `
      + 'на стороне отображения из того же дневного ряда Банка России, '
      + 'что и в режиме цены. Это не отдельная официальная публикация '
      + 'со средней ценой — расчёт для удобства графика. В расчёт входят '
      + 'только дни, по которым есть дневная точка.',
  };
}

export function getGoldPriceChartTitle(chartMode) {
  switch (chartMode) {
    case 'weekly':
      return 'Цена золота — средняя по неделям (руб./г)';
    case 'monthly':
      return 'Цена золота — средняя по месяцам (руб./г)';
    case 'quarterly':
      return 'Цена золота — средняя по кварталам (руб./г)';
    case 'annual':
      return 'Цена золота — средняя по годам (руб./г)';
    default:
      return 'Цена золота Банка России (руб./г)';
  }
}

export function getGoldPriceTableTitle(chartMode) {
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
      return 'Исторические данные — цена золота';
  }
}

export function getGoldPriceViewModeContent({ chartMode = 'level' }) {
  if (chartMode === 'level') return contentLevel();
  if (['weekly', 'monthly', 'quarterly', 'annual'].includes(chartMode)) {
    return contentAgg(chartMode);
  }
  return contentLevel();
}

export { isGoldPriceFamily };
