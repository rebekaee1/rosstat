import { Terminal, Download } from 'lucide-react';
import { unitSuffix, cn } from '../lib/format';
import { track, events } from '../lib/track';
import IndicatorChart from './IndicatorChart';
import { ChartSkeleton } from './Skeleton';
import { getCpiChartTitle } from '../lib/cpiViewModeContent';
import { getHousingChartTitle } from '../lib/housingViewModeContent';
import { getPpiChartTitle } from '../lib/ppiViewModeContent';
import { getAutoLoanChartTitle } from '../lib/autoLoanViewModeContent';
import { getMortgageChartTitle } from '../lib/mortgageRateViewModeContent';
import { getCbrTermSliceChartTitle } from '../lib/cbrTermSliceRateContent';
import { getKeyRateChartTitle } from '../lib/keyRateViewModeContent';
import { getRuoniaChartTitle } from '../lib/ruoniaViewModeContent';
import { getBtcUsdChartTitle } from '../lib/btcUsdViewModeContent';
import { getBrentChartTitle } from '../lib/brentViewModeContent';
import { getCnyRubChartTitle } from '../lib/cnyRubViewModeContent';
import { getEurRubChartTitle } from '../lib/eurRubViewModeContent';
import { getUsdRubChartTitle } from '../lib/usdRubViewModeContent';
import { getBudgetChartTitle } from '../lib/budgetViewModeContent';
import { getBankCreditChartTitle } from '../lib/bankCreditViewModeContent';
import { getHouseholdFinanceChartTitle } from '../lib/householdFinanceViewModeContent';
import { getMonetaryMassChartTitle } from '../lib/monetaryMassViewModeContent';
import { getLaborMarketChartTitle } from '../lib/laborMarketViewModeContent';
import { getUnemploymentChartTitle } from '../lib/unemploymentViewModeContent';
import { getWagesNominalChartTitle } from '../lib/wagesNominalViewModeContent';
import { getGdpNominalChartTitle } from '../lib/gdpNominalViewModeContent';
import { getGdpRealChartTitle } from '../lib/gdpRealViewModeContent';
import { getExternalDebtChartTitle } from '../lib/externalDebtViewModeContent';
import { getGdpUseChartTitle } from '../lib/gdpUseViewModeContent';
import { getInternationalReservesChartTitle } from '../lib/internationalReservesViewModeContent';
import { getGoldPriceChartTitle } from '../lib/goldPriceViewModeContent';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';

/* ── Mode-зависимые подписи ──
   chartMode принимает значения: 'cpi' (default для всех некоммодити-индикаторов),
   'quarterly', 'annual', 'weekly', 'inflation' (только для CPI семьи).
   Для не-CPI индикаторов важен `indicator.frequency` — он задаёт ритм ряда
   (daily/weekly/monthly/quarterly/annual). Прогноз идёт в том же ритме —
   подписи tooltip/легенды/заголовка отражают это. */

const FREQUENCY_LABEL = {
  daily: 'днев.',
  weekly: 'нед.',
  monthly: 'мес.',
  quarterly: 'кв.',
  annual: 'год.',
};

const FREQUENCY_LONG = {
  daily: 'днев.',
  weekly: 'недельная',
  monthly: 'помесячно',
  quarterly: 'квартально',
  annual: 'годовая',
};

function freqLabel(indicator) {
  return FREQUENCY_LABEL[indicator?.frequency] || '';
}

function freqLong(indicator) {
  return FREQUENCY_LONG[indicator?.frequency] || '';
}

function chartTitle({
  chartMode, isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily, isMortgageFamily,
  isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily,
  isGoldPriceFamily,
  isUsdRubFamily,
  isEurRubFamily,
  isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isLaborMarketFamily,
  isUnemploymentFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isMonetaryMassFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
  indicator, safeViewMode,
}) {
  if (isWagesNominalFamily) {
    return getWagesNominalChartTitle(chartMode);
  }
  if (isGdpNominalFamily) {
    return getGdpNominalChartTitle(chartMode);
  }
  if (isGdpRealFamily) {
    return getGdpRealChartTitle(chartMode);
  }
  if (isUnemploymentFamily) {
    return getUnemploymentChartTitle(chartMode);
  }
  if (isPpiFamily) {
    return getPpiChartTitle(chartMode, safeViewMode);
  }
  if (isGdpUseFamily) {
    return getGdpUseChartTitle(chartMode, indicator?.code);
  }
  if (isExternalDebtFamily) {
    return getExternalDebtChartTitle(chartMode);
  }
  if (isInternationalReservesFamily) {
    return getInternationalReservesChartTitle(chartMode);
  }
  if (isLaborMarketFamily && indicator?.code) {
    return getLaborMarketChartTitle(chartMode, indicator.code);
  }
  if (isMonetaryMassFamily && indicator?.code) {
    return getMonetaryMassChartTitle(chartMode, indicator.code);
  }
  if (isGoldPriceFamily) {
    return getGoldPriceChartTitle(chartMode);
  }
  if (isBudgetFamily && indicator?.code) {
    return getBudgetChartTitle(chartMode, indicator.code);
  }
  if (isHouseholdFinanceFamily && indicator?.code) {
    return getHouseholdFinanceChartTitle(chartMode, indicator.code);
  }
  if (isBankCreditFamily) {
    return getBankCreditChartTitle(chartMode);
  }
  if (isBrentFamily) {
    return getBrentChartTitle(chartMode);
  }
  if (isUsdRubFamily) {
    return getUsdRubChartTitle(chartMode);
  }
  if (isEurRubFamily) {
    return getEurRubChartTitle(chartMode);
  }
  if (isCnyRubFamily) {
    return getCnyRubChartTitle(chartMode);
  }
  if (isBtcUsdFamily) {
    return getBtcUsdChartTitle(chartMode);
  }
  if (isRuoniaFamily) {
    return getRuoniaChartTitle(chartMode);
  }
  if (isKeyRateFamily) {
    return getKeyRateChartTitle(chartMode);
  }
  if (isMortgageFamily) {
    return getMortgageChartTitle(chartMode);
  }
  if (isAutoLoanFamily) {
    return getAutoLoanChartTitle(chartMode);
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceChartTitle(chartMode, indicator?.code);
  }
  if (isHousingFamily && indicator?.code) {
    return getHousingChartTitle(chartMode, indicator.code);
  }
  if (isPriceCategory && indicator?.code) {
    return getCpiChartTitle(chartMode, indicator.code, safeViewMode);
  }
  const suffix = unitSuffix(indicator?.unit);
  const freq = freqLong(indicator);
  const baseTitle = `${indicator?.name || 'Показатель'}${suffix ? ` (${suffix})` : ''}`;
  return freq ? `${baseTitle} — ${freq}` : baseTitle;
}

function levelTooltipLabel({
  chartMode, isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily, isMortgageFamily,
  isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily,
  isGoldPriceFamily,
  isUsdRubFamily,
  isEurRubFamily,
  isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isLaborMarketFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isMonetaryMassFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
  indicator,
}) {
  const isFxRub = isUsdRubFamily || isEurRubFamily || isCnyRubFamily;
  const isCommodityPrice = isBtcUsdFamily || isBrentFamily || isGoldPriceFamily;
  const isMonthlyAgg = isBudgetFamily || isBankCreditFamily || isHouseholdFinanceFamily
    || isLaborMarketFamily || isMonetaryMassFamily;
  const isQuarterlyAgg = isExternalDebtFamily || isGdpUseFamily;
  const isWeeklyStockAgg = isInternationalReservesFamily;
  const isStockAgg = isMonthlyAgg || isQuarterlyAgg || isWeeklyStockAgg;
  const isDailyAgg = isKeyRateFamily || isRuoniaFamily || isCommodityPrice || isFxRub
    || isStockAgg;
  if (isStockAgg && chartMode === 'level') return 'Значение';
  if (isStockAgg && chartMode !== 'level') return 'Среднее';
  if (isCommodityPrice && chartMode === 'level') return 'Цена';
  if (isCommodityPrice && chartMode !== 'level') return 'Среднее';
  if (isFxRub && chartMode === 'level') return 'Курс';
  if (isFxRub && chartMode !== 'level') return 'Среднее';
  if ((isAutoLoanFamily || isMortgageFamily || isCbrTermSliceFamily
    || isKeyRateFamily || isRuoniaFamily) && chartMode === 'level') {
    return 'Ставка';
  }
  if (isDailyAgg && chartMode !== 'level') return 'Среднее';
  if ((isHousingFamily || isPpiFamily) && chartMode === 'index') return 'Индекс';
  if (isPpiFamily && chartMode === 'mom') return 'М/м';
  if (chartMode === 'quarterly') return 'Кв. инфляция';
  if (chartMode === 'annual') return 'Год. инфляция';
  if (chartMode === 'weekly') return 'Нед. ИПЦ';
  if (chartMode === 'yoy') return 'Г/г';
  if (chartMode === 'qoq') return 'К/к';
  if (chartMode === 'period-weekly') return 'С нач. мес.';
  if (chartMode === 'period-monthly') return 'За месяц';
  if (isWagesNominalFamily && chartMode === 'index') return 'Индекс';
  if (chartMode === 'index') return 'ИПЦ';
  if (isPriceCategory) return 'Прирост';
  const freq = freqLabel(indicator);
  return freq ? `Факт (${freq})` : 'Значение';
}

function forecastTooltipLabel({ chartMode, indicator }) {
  if (chartMode === 'quarterly') return 'Прогноз (кв.)';
  if (chartMode === 'annual') return 'Прогноз (год.)';
  if (chartMode === 'weekly') return 'Прогноз (нед.)';
  if (chartMode === 'inflation') return 'Прогноз (12 мес.)';
  if (chartMode === 'index') return 'Прогноз (мес. ИПЦ)';
  const freq = freqLabel(indicator);
  return freq ? `Прогноз (${freq})` : 'Прогноз';
}

function dateFormatFor({ chartMode, indicator, safeViewMode }) {
  if (safeViewMode === 'index-quarterly') return 'quarterly';
  if (safeViewMode === 'index-annual') return 'annual';
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'yoy' || chartMode === 'period-weekly' || chartMode === 'period-monthly') return 'full';
  if (chartMode !== 'inflation' && indicator?.frequency === 'daily') return 'day';
  if (indicator?.frequency === 'quarterly') return 'quarterly';
  if (indicator?.frequency === 'annual') return 'annual';
  if (indicator?.frequency === 'weekly') return 'short';
  return 'full';
}

function rangePresetFor({
  chartMode, indicator, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily,
  isGoldPriceFamily,
  isUsdRubFamily,
  isEurRubFamily,
  isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isLaborMarketFamily,
  isMonetaryMassFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
}) {
  const isFxRub = isUsdRubFamily || isEurRubFamily || isCnyRubFamily;
  const isCommodityPrice = isBtcUsdFamily || isBrentFamily || isGoldPriceFamily;
  const isMonthlyStockAgg = isBudgetFamily || isBankCreditFamily || isHouseholdFinanceFamily
    || isLaborMarketFamily || isMonetaryMassFamily;
  const isDailyAgg = isKeyRateFamily || isRuoniaFamily || isCommodityPrice || isFxRub
    || isMonthlyStockAgg;
  if (isInternationalReservesFamily && chartMode === 'level') return 'weekly';
  if (isInternationalReservesFamily && chartMode === 'monthly') return 'default';
  if (isInternationalReservesFamily && chartMode === 'quarterly') return 'quarterly';
  if (isInternationalReservesFamily && chartMode === 'annual') return 'annual';
  if (isExternalDebtFamily && chartMode === 'level') return 'quarterly';
  if (isExternalDebtFamily && chartMode === 'annual') return 'annual';
  if (isGdpUseFamily && chartMode === 'level') return 'quarterly';
  if (isGdpUseFamily && chartMode === 'annual') return 'annual';
  if (isDailyAgg && chartMode === 'level') return 'daily';
  if (isDailyAgg && chartMode === 'weekly') return 'weekly';
  if (isDailyAgg && chartMode === 'monthly') return 'default';
  if (isDailyAgg && chartMode === 'quarterly') return 'quarterly';
  if (isDailyAgg && chartMode === 'annual') return 'annual';
  /* Mode-driven для CPI семьи (annual mode → 10y/25y/all). */
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'weekly') return 'weekly';
  if (chartMode === 'yoy' || chartMode === 'period-weekly' || chartMode === 'period-monthly') return 'default';
  // Накопленный индекс CPI — длинная история (2000+), показываем 5y/10y/25y/all.
  if (chartMode === 'index') return 'quarterly';
  /* Frequency-driven для остальных индикаторов. */
  const freq = indicator?.frequency;
  if (freq === 'quarterly') return 'quarterly';
  if (freq === 'annual') return 'annual';
  if (freq === 'weekly') return 'weekly';
  if (freq === 'daily') return 'daily';
  return 'default';
}

/**
 * Секция «График» страницы индикатора:
 *   тулбар (заголовок + кнопки CSV/Excel + переключатель прогноза) +
 *   сам IndicatorChart с правильными режим-зависимыми пропсами.
 *
 * Таблица данных и таблица прогноза идут отдельными секциями ниже —
 * этот компонент отвечает только за визуализацию ряда.
 */
export default function IndicatorChartSection({
  code,
  indicator,
  chartMode,
  safeViewMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isAutoLoanFamily,
  isMortgageFamily,
  isCbrTermSliceFamily,
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
  isLaborMarketFamily,
  isUnemploymentFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isMonetaryMassFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
  chartLoading,

  inflationResp,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodMonthlyDataPoints,
  periodWeeklyDataPoints,

  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,
  weeklyForecastData,
  yoyForecastData,
  qoqForecastData,
  periodMonthlyForecastData,
  periodWeeklyForecastData,

  forecastEnabled,
  showForecast,
  onToggleForecast,

  onChartData,
  onRangeChange,
  emptyHint,

  onDownloadCsv,
  onDownloadExcel,
}) {
  const chartCpiData = chartSeriesForViewMode({
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
    isLaborMarketFamily,
    isUnemploymentFamily,
    isWagesNominalFamily,
    isGdpNominalFamily,
    isGdpRealFamily,
    isMonetaryMassFamily,
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
  });

  const forecastData = chartMode === 'quarterly' ? quarterlyForecastData
    : chartMode === 'annual' ? annualForecastResp
      : chartMode === 'weekly' ? weeklyForecastData
        : chartMode === 'yoy' ? yoyForecastData
          : chartMode === 'qoq' ? qoqForecastData
            : chartMode === 'period-weekly' ? periodWeeklyForecastData
              : chartMode === 'period-monthly' ? periodMonthlyForecastData
                : displayForecastData;

  const handleForecastToggle = () => {
    if (!forecastEnabled) return;
    onToggleForecast();
    track(events.FORECAST_TOGGLE, {
      show: !showForecast,
      indicator: code,
      indicatorCategory: indicator?.category,
    });
  };

  const handleForecastKeyDown = (e) => {
    if (forecastEnabled && (e.key === ' ' || e.key === 'Enter')) {
      e.preventDefault();
      handleForecastToggle();
    }
  };

  return (
    <section className="mb-16">
      <div className="flex items-center justify-between mb-6 border-b border-border-subtle pb-4 flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <Terminal className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
            {(isPriceCategory || isHousingFamily || isPpiFamily || isAutoLoanFamily
              || isMortgageFamily || isCbrTermSliceFamily || isKeyRateFamily || isRuoniaFamily
              || isBtcUsdFamily || isBrentFamily || isGoldPriceFamily || isUsdRubFamily
              || isEurRubFamily
              || isCnyRubFamily || isBudgetFamily || isBankCreditFamily
              || isHouseholdFinanceFamily || isLaborMarketFamily || isUnemploymentFamily
              || isWagesNominalFamily || isGdpNominalFamily || isGdpRealFamily
              || isMonetaryMassFamily
              || isInternationalReservesFamily
              || isExternalDebtFamily || isGdpUseFamily)
              ? 'График выбранного режима'
              : 'Динамика показателя'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onDownloadCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
            title="Скачать CSV"
          >
            <Download className="w-3.5 h-3.5" />
            CSV
          </button>
          <button
            onClick={onDownloadExcel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
            title="Скачать Excel"
          >
            <Download className="w-3.5 h-3.5" />
            Excel
          </button>

          <div className="relative group">
            <label className={cn(
              'flex items-center gap-3 select-none',
              forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50',
            )}>
              <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                Прогноз
              </span>
              <div
                role="switch"
                aria-checked={forecastEnabled && showForecast}
                aria-label="Показать прогноз"
                tabIndex={forecastEnabled ? 0 : -1}
                onClick={handleForecastToggle}
                onKeyDown={handleForecastKeyDown}
                className={cn(
                  'relative w-10 h-5 rounded-full transition-colors duration-300',
                  forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed',
                  forecastEnabled && showForecast
                    ? 'bg-champagne/30'
                    : 'bg-obsidian-lighter border border-border-subtle',
                )}
              >
                <div className={cn(
                  'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                  forecastEnabled && showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary',
                )} />
              </div>
            </label>
            {!forecastEnabled && (
              <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
                Прогноз для этого режима недоступен
              </div>
            )}
          </div>
        </div>
      </div>

      {chartLoading ? (
        <ChartSkeleton />
      ) : (
        <div className="relative overflow-hidden rounded-[2rem]">
          <IndicatorChart
            key={`${indicator?.code}-${chartMode}`}
            mode={
              isKeyRateFamily || isRuoniaFamily || isBtcUsdFamily || isBrentFamily
              || isGoldPriceFamily || isUsdRubFamily || isEurRubFamily || isCnyRubFamily
              || isBudgetFamily || isBankCreditFamily || isHouseholdFinanceFamily
              || isLaborMarketFamily || isUnemploymentFamily || isWagesNominalFamily
              || isGdpNominalFamily || isGdpRealFamily
              || isMonetaryMassFamily || isInternationalReservesFamily || isExternalDebtFamily
              || isGdpUseFamily
              || ['quarterly', 'annual', 'weekly', 'index', 'yoy', 'qoq', 'mom', 'real',
                'period-weekly', 'period-monthly'].includes(chartMode)
              || ((isAutoLoanFamily || isMortgageFamily || isCbrTermSliceFamily) && chartMode === 'level')
                ? 'cpi'
                : chartMode
            }
            inflation={inflationResp}
            cpiData={chartCpiData}
            forecastData={forecastData}
            showForecast={forecastEnabled && showForecast}
            onChartData={onChartData}
            onRangeChange={onRangeChange}
            referenceLineY={(isPriceCategory || isHousingFamily || isPpiFamily) && chartMode !== 'index' ? 0 : null}
            cpiChartTitle={chartTitle({
              chartMode, isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily,
              isMortgageFamily, isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily,
              isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily,
              isCnyRubFamily,
              isBudgetFamily,
              isBankCreditFamily,
              isHouseholdFinanceFamily,
              isLaborMarketFamily,
              isUnemploymentFamily,
              isWagesNominalFamily,
              isGdpNominalFamily,
              isGdpRealFamily,
              isMonetaryMassFamily,
              isInternationalReservesFamily,
              isExternalDebtFamily,
              isGdpUseFamily,
              indicator, safeViewMode,
            })}
            levelTooltipLabel={levelTooltipLabel({
              chartMode, isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily,
              isMortgageFamily, isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily,
              isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily,
              isCnyRubFamily,
              isBudgetFamily,
              isBankCreditFamily,
              isHouseholdFinanceFamily,
              isLaborMarketFamily,
              isUnemploymentFamily,
              isWagesNominalFamily,
              isGdpNominalFamily,
              isGdpRealFamily,
              isMonetaryMassFamily,
              isInternationalReservesFamily,
              isExternalDebtFamily,
              isGdpUseFamily,
              indicator,
            })}
            forecastTooltipLabel={forecastTooltipLabel({ chartMode, indicator })}
            emptyHint={emptyHint}
            dateFormat={dateFormatFor({ chartMode, indicator, safeViewMode })}
            unit={chartMode === 'index' ? 'индекс' : ((isPpiFamily || isHousingFamily) && chartMode !== 'index' ? '%' : (indicator?.unit || '%'))}
            rangePreset={rangePresetFor({
              chartMode, indicator, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily,
              isBrentFamily,
              isGoldPriceFamily,
              isUsdRubFamily,
              isEurRubFamily,
              isCnyRubFamily,
              isBudgetFamily,
              isBankCreditFamily,
              isHouseholdFinanceFamily,
              isLaborMarketFamily,
              isUnemploymentFamily,
              isMonetaryMassFamily,
              isInternationalReservesFamily,
              isExternalDebtFamily,
              isGdpUseFamily,
            })}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
          />
        </div>
      )}
    </section>
  );
}
