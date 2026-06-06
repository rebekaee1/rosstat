/**
 * Кредиты и вклады физических лиц (срез × частота ряда).
 * Правила: .cursor/rules/methodology-language.mdc
 */

import { isHouseholdFinanceFamily } from './householdFinanceViewModeResolve';

function sliceMeta(indicatorCode) {
  if (indicatorCode === 'deposits-individual') {
    return {
      sliceLabel: 'вклады физических лиц',
      sliceLabelShort: 'вклады населения',
      sliceLabelCap: 'Вклады физлицам',
      unitHint: 'млрд руб.',
      balanceSide: 'привлечённые средства домохозяйств в банках',
      productHint: 'переводные, срочные и валютные депозиты',
      siblingLabel: 'кредитам физическим лицам',
      siblingUnit: 'трлн руб.',
    };
  }
  return {
    sliceLabel: 'кредиты физическим лицам',
    sliceLabelShort: 'кредиты населения',
    sliceLabelCap: 'Кредиты физлицам',
    unitHint: 'трлн руб.',
    balanceSide: 'задолженность домохозяйств перед банками',
    productHint: 'ипотека, потребительские займы, автокредиты',
    siblingLabel: 'вкладам физических лиц',
    siblingUnit: 'млрд руб.',
  };
}

function contentLevel(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isDeposits = indicatorCode === 'deposits-individual';
  return {
    description:
      `На графике — ${isDeposits ? 'совокупные' : 'остаток'} ${s.sliceLabel} `
      + `в ${s.unitHint} на конец каждого месяца: ${s.balanceSide}. `
      + (isDeposits
        ? 'В агрегат входят основные виды депозитов населения — без разбивки '
          + 'по сроку, валюте и банку на этом экране. Рост линии обычно означает '
          + 'больше сбережений в системе; снижение — отток или слабые притоки.'
        : 'В один ряд сведены розничные ссуды — без отдельных линий по ипотеке, '
          + 'картам и автокредитам. Рост — расширение портфеля, снижение — '
          + 'погашения и меньшие выдачи, а не «исчезновение» кредитования.')
      + ' Соседняя вкладка семьи показывает '
      + `${s.siblingLabel} в ${s.siblingUnit} за те же даты.`,
    methodology:
      `Режим «помесячно» — официальный ежемесячный ряд Банка России. `
      + `Каждая точка — ${isDeposits ? 'остаток вкладов' : 'остаток задолженности'} `
      + `на последний день месяца, а не поток за 30 дней и не ставка по новым `
      + `договорам. Прогноз на карточке не строится. Для парного анализа откройте `
      + `«${isDeposits ? 'Кредиты физлицам' : 'Вклады физлицам'}» в семье `
      + '«Кредиты и вклады населения» — режим графика сохранится. '
      + 'Чтобы сгладить всплески одного месяца, выберите «Среднее за период».',
  };
}

function contentAggQuarterly(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isDeposits = indicatorCode === 'deposits-individual';
  return {
    description:
      `На графике — средний помесячный ${isDeposits ? 'остаток вкладов' : 'остаток портфеля'} `
      + `${s.sliceLabel} внутри каждого календарного квартала (${s.unitHint}). `
      + (isDeposits
        ? 'Квартальная точка отвечает на вопрос, каким был «типичный» месяц '
          + 'по депозитной базе, если внутри квартала были отпускной отток '
          + 'и декабрьский приток.'
        : 'Квартальная точка помогает увидеть устойчивый тренд закредитованности, '
          + 'когда один месяц с аномальными выдачами искажает картину.')
      + ` Для сравнения с ${s.siblingLabel} переключите вкладку семьи.`,
    methodology:
      `Режим «среднее за период — по кварталам»: простое среднее `
      + `помесячных остатков Банка России внутри квартала (${s.unitHint}). `
      + 'Отдельной квартальной публикации регулятора для такого среза нет — '
      + 'расчёт выполняется при отображении, из того же официального ряда. '
      + (isDeposits
        ? 'Удобно сопоставлять с сезонностью отпусков, выплат дивидендов '
          + 'и концом года, когда семьи часто возвращают деньги в депозиты.'
        : 'Удобно сопоставлять с сезонностью розничных выдач, льготной ипотеки '
          + 'и календарём налоговых платежей, влияющих на спрос на заём.')
      + ' Не суммируйте с вкладами в одной шкале — единицы разные.',
  };
}

function contentAggAnnual(indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const isDeposits = indicatorCode === 'deposits-individual';
  return {
    description:
      `На графике — средний помесячный ${isDeposits ? 'остаток вкладов' : 'остаток'} `
      + `${s.sliceLabel} внутри каждого календарного года (${s.unitHint}). `
      + 'Годовая точка — не декабрь «как есть», а усреднённый уровень по всем '
      + `месяцам года: так честнее сравнить ${isDeposits ? 'эпохи высоких ставок по вкладам' : 'фазы роста потребительского кредита'}.`,
    methodology:
      `Режим «среднее за период — по годам»: среднее всех помесячных `
      + `остатков внутри года (${s.unitHint}) из того же ряда Банка России. `
      + (isDeposits
        ? 'Помогает отделить долгосрочный рост сбережений в банках от '
          + 'краткого всплеска одного месяца. Не путать со «вкладали за год» — '
          + 'здесь только средний остаток на конец месяцев.'
        : 'Помогает сравнить годы с разной динамикой ипотеки и потребкредита '
          + 'без доминирования декабря. Не путать с объёмом выдач за год — '
          + 'на графике остатки портфеля.')
      + ' Переключение на '
      + `${s.siblingLabel} сохраняет выбранный режим отображения.`,
  };
}

export function getHouseholdFinanceChartTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  const unit = s.unitHint.replace(/\.$/, '');
  switch (chartMode) {
    case 'quarterly':
      return `${s.sliceLabelCap} — среднее по кварталам (${unit})`;
    case 'annual':
      return `${s.sliceLabelCap} — среднее по годам (${unit})`;
    default:
      return `${s.sliceLabelCap} — ${indicatorCode === 'deposits-individual' ? 'остаток' : 'портфель'} (${unit})`;
  }
}

export function getHouseholdFinanceTableTitle(chartMode, indicatorCode) {
  const s = sliceMeta(indicatorCode);
  switch (chartMode) {
    case 'quarterly':
      return `Исторические данные — ${s.sliceLabelShort}, среднее по кварталам`;
    case 'annual':
      return `Исторические данные — ${s.sliceLabelShort}, среднее по годам`;
    default:
      return `Исторические данные — ${s.sliceLabelShort} (помесячно)`;
  }
}

export function getHouseholdFinanceViewModeContent({ chartMode = 'level', indicatorCode }) {
  if (chartMode === 'quarterly') return contentAggQuarterly(indicatorCode);
  if (chartMode === 'annual') return contentAggAnnual(indicatorCode);
  return contentLevel(indicatorCode);
}

export { isHouseholdFinanceFamily };
