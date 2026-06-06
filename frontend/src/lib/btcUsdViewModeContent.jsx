/**
 * Описание и методология: биткоин BTC/USD (режим × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isBtcUsdFamily } from './btcUsdViewModeResolve';

function contentLevel() {
  return {
    description:
      'На графике — цена одного биткоина в долларах США на конец каждого '
      + 'календарного дня по спотовому рынку: линия отражает закрытие '
      + 'торговой сессии на выбранной бирже. Рынок криптовалют работает '
      + 'круглосуточно, поэтому точки идут без выходных, в отличие от '
      + 'большинства российских макропоказателей.',
    methodology:
      'Режим «цена (ежедневно)» — официальный для карточки ряд в долларах '
      + 'за сутки. Каждая точка — цена закрытия дня; внутри дня возможны '
      + 'сильные колебания, на графике виден только итог дня. Прогноз не '
      + 'строится. Для сглаженного тренда без дневного шума выберите '
      + '«Среднее за период» в переключателе над графиком.',
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
      `На графике — средняя цена биткоина в долларах внутри календарных `
      + `${period}: из ежедневного ряда считается простое среднее по всем `
      + `дням интервала. Так проще увидеть тренд за месяц или квартал без `
      + `резких внутридневных скачков отдельных дней.`,
    methodology:
      `Режим «среднее за период — ${periodLabel}»: агрегация выполняется `
      + 'на стороне отображения из того же дневного ряда, что и в режиме '
      + 'цены. Это не отдельная публикация биржи. В расчёт входят все '
      + 'календарные дни периода, по которым есть дневная точка.',
  };
}

export function getBtcUsdChartTitle(chartMode) {
  switch (chartMode) {
    case 'weekly':
      return 'Биткоин — средняя цена по неделям (USD)';
    case 'monthly':
      return 'Биткоин — средняя цена по месяцам (USD)';
    case 'quarterly':
      return 'Биткоин — средняя цена по кварталам (USD)';
    case 'annual':
      return 'Биткоин — средняя цена по годам (USD)';
    default:
      return 'Биткоин (BTC/USD)';
  }
}

export function getBtcUsdTableTitle(chartMode) {
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
      return 'Исторические данные — BTC/USD';
  }
}

export function getBtcUsdViewModeContent({ chartMode = 'level' }) {
  if (chartMode === 'level') return contentLevel();
  if (['weekly', 'monthly', 'quarterly', 'annual'].includes(chartMode)) {
    return contentAgg(chartMode);
  }
  return contentLevel();
}

export { isBtcUsdFamily };
