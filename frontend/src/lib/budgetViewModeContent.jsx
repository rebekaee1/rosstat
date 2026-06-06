/**
 * Описание и методология: федеральный бюджет (срез × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isBudgetFamily } from './budgetViewModeResolve';

function sliceMeta(indicatorCode) {
  switch (indicatorCode) {
    case 'budget-revenue':
      return {
        sliceLabel: 'доходы',
        sliceLabelCap: 'Доходы',
        signHint: 'положительные значения — поступления в бюджет',
        levelFocus:
          'отражает силу налоговой и неналоговой базы в конкретном месяце',
        aggFocus:
          'показывает, сколько в среднем поступало в казну за месяц внутри периода',
      };
    case 'budget-expenditure':
      return {
        sliceLabel: 'расходы',
        sliceLabelCap: 'Расходы',
        signHint: 'значения отражают объём исполненных расходов бюджета',
        levelFocus:
          'показывает, сколько бюджет фактически исполнил по выплатам за месяц',
        aggFocus:
          'характеризует средний месячный объём исполнения расходов внутри периода',
      };
    default:
      return {
        sliceLabel: 'дефицит или профицит',
        sliceLabelCap: 'Дефицит/профицит',
        signHint: 'отрицательное значение — дефицит, положительное — профицит',
        levelFocus:
          'показывает, закрылся ли месяц с профицитом или с дефицитом',
        aggFocus:
          'даёт средний уровень сальдо по месяцам внутри квартала или года',
      };
  }
}

function contentLevel(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const subject = s.sliceLabel === 'дефицит или профицит' ? 'сальдо' : s.sliceLabel;
  return {
    description:
      `На графике — помесячные ${s.sliceLabel} федерального бюджета России `
      + 'в млрд рублей: каждая точка относится к одному календарному месяцу. '
      + `Линия ${s.levelFocus}; ${s.signHint}.`,
    methodology:
      `Режим «помесячно» для ${subject}: официальный ряд исполнения бюджета `
      + 'Минфина России в млрд руб. за месяц, история с 2011 года. Прогноз '
      + 'не строится. Для сравнения кварталов или лет без отдельных всплесков '
      + 'выберите «Среднее за период». Соседние вкладки семьи «Федеральный бюджет» '
      + (indicatorCode === 'budget-revenue'
        ? 'ведут к расходам и сальдо за те же даты.'
        : indicatorCode === 'budget-expenditure'
          ? 'ведут к доходам и сальдо за те же даты.'
          : 'ведут к доходам и расходам за те же даты.'),
  };
}

function contentAgg(indicatorCode, mode) {
  const s = sliceMeta(indicatorCode);
  const periodLabel = mode === 'quarterly' ? 'по кварталам' : 'по годам';
  const period = mode === 'quarterly' ? 'кварталам' : 'годам';
  const subject = s.sliceLabel === 'дефицит или профицит' ? 'сальдо' : s.sliceLabel;
  let aggMethodologyExtra = '';
  if (indicatorCode === 'budget-deficit') {
    aggMethodologyExtra =
      ' Удобно сравнить, в каких кварталах сальдо в среднем было дефицитным, '
      + 'а в каких — ближе к нулю или профицитным.';
  } else if (indicatorCode === 'budget-revenue') {
    aggMethodologyExtra =
      ' Помогает отделить устойчиво высокие поступления от одного сильного месяца '
      + 'внутри квартала.';
  } else {
    aggMethodologyExtra =
      ' Позволяет увидеть, был ли период в целом «тяжёлым» по выплатам, '
      + 'даже если один месяц выбивался из ряда.';
  }
  return {
    description:
      `На графике — среднее помесячное значение ${s.sliceLabel} внутри `
      + `календарных ${period}: ${s.aggFocus}. Расчёт из того же ряда, `
      + 'что в режиме «помесячно».',
    methodology:
      `Режим «среднее за период — ${periodLabel}» для ${subject}: простое среднее `
      + 'помесячных значений Минфина внутри каждого календарного интервала; '
      + 'отдельной публикации ведомства для таких средних нет.'
      + aggMethodologyExtra,
  };
}

export function getBudgetChartTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  switch (chartMode) {
    case 'quarterly':
      return `${s.sliceLabelCap} бюджета — среднее по кварталам (млрд руб.)`;
    case 'annual':
      return `${s.sliceLabelCap} бюджета — среднее по годам (млрд руб.)`;
    default:
      if (indicatorCode === 'budget-deficit') {
        return 'Дефицит/профицит федерального бюджета (млрд руб.)';
      }
      return `${s.sliceLabelCap} федерального бюджета (млрд руб.)`;
  }
}

export function getBudgetTableTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  switch (chartMode) {
    case 'quarterly':
      return `Исторические данные — ${s.sliceLabel}, среднее по кварталам`;
    case 'annual':
      return `Исторические данные — ${s.sliceLabel}, среднее по годам`;
    default:
      return `Исторические данные — ${s.sliceLabel} (помесячно)`;
  }
}

export function getBudgetViewModeContent({ chartMode = 'level', indicatorCode }) {
  if (chartMode === 'level') return contentLevel(indicatorCode);
  if (chartMode === 'quarterly' || chartMode === 'annual') {
    return contentAgg(indicatorCode, chartMode);
  }
  return contentLevel(indicatorCode);
}

export { isBudgetFamily };
