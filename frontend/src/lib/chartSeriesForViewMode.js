/**
 * Выбор ряда для графика/таблицы по chartMode.
 * key-rate / ruonia / btc-usd / usd|eur|cny-rub: агрегаты уже в dataPoints.
 */
export function chartSeriesForViewMode({
  chartMode,
  isKeyRateFamily,
  isRuoniaFamily,
  isBtcUsdFamily,
  isBrentFamily,
  isGoldPriceFamily,
  isUsdRubFamily,
  isEurRubFamily,
  isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isMonetaryMassFamily,
  isLaborMarketFamily,
  isUnemploymentFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodWeeklyDataPoints,
  periodMonthlyDataPoints,
}) {
  if (isKeyRateFamily || isRuoniaFamily || isBtcUsdFamily || isBrentFamily
    || isGoldPriceFamily || isUsdRubFamily || isEurRubFamily || isCnyRubFamily || isBudgetFamily
    || isBankCreditFamily || isHouseholdFinanceFamily || isMonetaryMassFamily
    || isLaborMarketFamily || isUnemploymentFamily || isWagesNominalFamily
    || isGdpNominalFamily
    || isGdpRealFamily
    || isInternationalReservesFamily
    || isExternalDebtFamily || isGdpUseFamily) {
    return dataPoints;
  }
  if (chartMode === 'quarterly') return quarterlyDataPoints;
  if (chartMode === 'annual') return annualDataPoints;
  if (chartMode === 'weekly') return weeklyDataPoints;
  if (chartMode === 'yoy') return yoyDataPoints;
  if (chartMode === 'qoq') return qoqDataPoints;
  if (chartMode === 'period-weekly') return periodWeeklyDataPoints;
  if (chartMode === 'period-monthly') return periodMonthlyDataPoints;
  if (chartMode === 'mom') return momDataPoints;
  return dataPoints;
}
