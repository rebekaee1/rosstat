/**
 * Описание и методология: ставка RUONIA (режим × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isRuoniaFamily } from './ruoniaViewModeResolve';

function contentLevel() {
  return {
    description:
      'На графике — официальная ставка RUONIA в процентах годовых на каждый '
      + 'рабочий день: индикативная взвешенная ставка однодневных рублёвых '
      + 'межбанковских кредитов и депозитов на условиях «овернайт». Линия '
      + 'меняется изо дня в день — это рыночный ориентир ликвидности, '
      + 'а не решение совета директоров по ключевой ставке.',
    methodology:
      'Режим «уровень ставки» — ежедневный официальный ряд Банка России. '
      + 'Каждая точка — ставка за соответствующую дату; в выходные и '
      + 'праздники точек может не быть. Прогноз на карточке не строится. '
      + 'Для сглаженного вида без дневной волатильности выберите группу '
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
      `На графике — среднее значение RUONIA внутри календарных ${period}: `
      + 'из ежедневного ряда считается простое среднее по всем дням '
      + 'внутри интервала. Так удобнее сравнивать «типичный» уровень '
      + 'межбанковской ставки за месяц или квартал без дневных колебаний.',
    methodology:
      `Режим «среднее за период — ${periodLabel}»: агрегация выполняется `
      + 'на стороне отображения из того же официального ряда, что и в '
      + 'режиме уровня. Это не отдельная публикация ЦБ. В расчёт входят '
      + 'только дни, по которым Банк России опубликовал значение.',
  };
}

export function getRuoniaChartTitle(chartMode) {
  switch (chartMode) {
    case 'weekly':
      return 'RUONIA — среднее по неделям (%)';
    case 'monthly':
      return 'RUONIA — среднее по месяцам (%)';
    case 'quarterly':
      return 'RUONIA — среднее по кварталам (%)';
    case 'annual':
      return 'RUONIA — среднее по годам (%)';
    default:
      return 'Ставка RUONIA (%)';
  }
}

export function getRuoniaTableTitle(chartMode) {
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
      return 'Исторические данные — RUONIA';
  }
}

export function getRuoniaViewModeContent({ chartMode = 'level' }) {
  if (chartMode === 'level') return contentLevel();
  if (['weekly', 'monthly', 'quarterly', 'annual'].includes(chartMode)) {
    return contentAgg(chartMode);
  }
  return contentLevel();
}

export { isRuoniaFamily };
