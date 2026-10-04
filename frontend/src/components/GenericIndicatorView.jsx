import { useCallback, useMemo, useState } from 'react';
import { useIndicator } from '../lib/hooks';
import useGenericViewModeData from '../lib/useGenericViewModeData';
import { resolveViewMode } from '../lib/viewModeEngine';
import IndicatorDetailHeader from './IndicatorDetailHeader';
import VariantGroupPicker from './VariantGroupPicker';
import GenericViewModePicker from './GenericViewModePicker';
import IndicatorTelemetryGrid from './IndicatorTelemetryGrid';
import IndicatorChartSection from './IndicatorChartSection';
import IndicatorMethodologyPanel from './IndicatorMethodologyPanel';
import IndicatorForecastSection from './IndicatorForecastSection';
import IndicatorDataTableSection from './IndicatorDataTableSection';
import IndicatorSeoBlocks from './IndicatorSeoBlocks';
import RelatedIndicators from './RelatedIndicators';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import ApiRetryBanner from './ApiRetryBanner';

/**
 * Generic (config-driven) карточка индикатора для семей из
 * `viewModelFamilies.generated.json`.
 *
 * Все режимы — backend-derived ряды (нативный source для уровня, sibling-код
 * для агрегаций/приростов), поэтому unit/частота/имя/методология берутся из
 * метаданных самого ряда (single source of truth), а не из per-family JS.
 *
 * Секции (телеметрия/график/таблица/прогноз/методология) переиспользуются
 * в «плоском» режиме: все `is*Family=false`, `chartMode='cpi'` — дефолтный
 * путь рендерит любой одиночный ряд с корректными подписями по его частоте.
 */
const FLAGS = {
  isPriceCategory: false,
  isHousingFamily: false,
  isPpiFamily: false,
  isAutoLoanFamily: false,
  isMortgageFamily: false,
  isCbrTermSliceFamily: false,
  isKeyRateFamily: false,
  isRuoniaFamily: false,
  isBtcUsdFamily: false,
  isBrentFamily: false,
  isGoldPriceFamily: false,
  isUsdRubFamily: false,
  isEurRubFamily: false,
  isCnyRubFamily: false,
  isBudgetFamily: false,
  isBankCreditFamily: false,
  isHouseholdFinanceFamily: false,
  isMonetaryMassFamily: false,
  isLaborMarketFamily: false,
  isUnemploymentFamily: false,
  isWagesNominalFamily: false,
  isGdpNominalFamily: false,
  isGdpRealFamily: false,
  isInternationalReservesFamily: false,
  isExternalDebtFamily: false,
  isGdpUseFamily: false,
};

const IDENTITY = (v) => v;

export default function GenericIndicatorView({
  code,
  indicator,
  family,
  viewMode,
  setViewMode,
  stats,
  variantGroup,
  relatedIndicators = [],
  loadingInd,
  headerRef,
}) {
  const t = useT();
  const [showForecast, setShowForecast] = useState(true);
  const [fullChartData, setFullChartData] = useState([]);

  const resolved = useMemo(() => resolveViewMode(family, viewMode), [family, viewMode]);
  const safeMode = resolved?.mode ?? family?.defaultMode;

  // Метаданные именно отображаемого ряда (native source или derived sibling) —
  // источник истины для unit/частоты/имени/методологии режима.
  const { data: resolvedIndicator } = useIndicator(resolved?.code);
  // В-19: пока метаданные sibling'а грузятся, unit/frequency берём из конфига
  // режима (resolved) — иначе первый paint выходит с единицей/частотой родителя
  // («млрд руб.» на графике «% г/г»).
  const effectiveIndicator = useMemo(() => {
    if (resolvedIndicator) return resolvedIndicator;
    if (!indicator || !resolved || resolved.isNative) return indicator;
    return {
      ...indicator,
      unit: resolved.unit ?? indicator.unit,
      frequency: resolved.frequency ?? indicator.frequency,
    };
  }, [resolvedIndicator, indicator, resolved]);

  const {
    dataPoints, viewStats, forecastResp, forecastEnabled, hasForecast, isLoading, isError, refetch, isFetching,
  } = useGenericViewModeData({ family, urlMode: viewMode, indicator });

  const methodologyContent = useMemo(() => ({
    description: effectiveIndicator?.description,
    methodology: effectiveIndicator?.methodology,
  }), [effectiveIndicator?.description, effectiveIndicator?.methodology]);

  const downloadMeta = useMemo(() => ({
    name: effectiveIndicator?.name, unit: effectiveIndicator?.unit,
    source: effectiveIndicator?.source, source_url: effectiveIndicator?.source_url,
    frequency: effectiveIndicator?.frequency,
  }), [effectiveIndicator]);

  const handleFullData = useCallback((d) => setFullChartData(d), []);

  // Выгрузка — всегда полный ряд (вся история), а не видимое окно графика.
  const handleDownloadExcel = useCallback(async () => {
    try {
      const ok = await downloadExcel(fullChartData, null, resolved?.code ?? code, 'all', downloadMeta);
      if (ok) track(events.DOWNLOAD_EXCEL, { indicator: code, range: 'all', indicatorCategory: indicator?.category });
    } catch { /* сеть/сервер — молча */ }
  }, [fullChartData, resolved, code, downloadMeta, indicator]);

  const handleDownloadCSV = useCallback(async () => {
    try {
      const ok = await downloadCSV(fullChartData, null, resolved?.code ?? code, 'all', downloadMeta);
      if (ok) track(events.DOWNLOAD_CSV, { indicator: code, range: 'all', indicatorCategory: indicator?.category });
    } catch { /* сеть/сервер — молча */ }
  }, [fullChartData, resolved, code, downloadMeta, indicator]);

  const chartEmptyHint = !isLoading && !isError && (dataPoints?.length ?? 0) === 0
    ? t('indicator.empty.recalc')
    : undefined;

  return (
    <>
      <IndicatorDetailHeader
        indicator={indicator}
        code={code}
        loading={loadingInd}
        headerRef={headerRef}
        displayFrequency={effectiveIndicator?.frequency}
      />

      <IndicatorTelemetryGrid
        indicator={effectiveIndicator}
        viewStats={viewStats}
        stats={stats}
        {...FLAGS}
        chartMode="cpi"
        safeViewMode={safeMode}
        cpiPrevDate={null}
        adj={IDENTITY}
        firstDate={dataPoints?.[0]?.date}
        loading={loadingInd || isLoading}
      />

      {variantGroup ? (
        <VariantGroupPicker group={variantGroup} currentCode={code} />
      ) : null}

      <GenericViewModePicker
        family={family}
        currentMode={safeMode}
        onChange={setViewMode}
        trackContext={{ code, category: indicator?.category }}
      />

      {isError && (dataPoints?.length ?? 0) === 0 && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          {t('indicator.dataError')}
        </ApiRetryBanner>
      )}

      <IndicatorChartSection
        code={code}
        indicator={effectiveIndicator}
        chartMode="cpi"
        safeViewMode={safeMode}
        {...FLAGS}
        chartLoading={isLoading}
        dataPoints={dataPoints}
        displayForecastData={forecastResp}
        forecastEnabled={forecastEnabled}
        showForecast={showForecast}
        onToggleForecast={() => setShowForecast((v) => !v)}
        onFullData={handleFullData}
        emptyHint={chartEmptyHint}
        onDownloadCsv={handleDownloadCSV}
        onDownloadExcel={handleDownloadExcel}
        worldCompare={indicator?.world_compare}
        onNeedCompatibleMode={setViewMode}
      />

      <div className="fe-info-grid" data-forecast={forecastEnabled && showForecast && hasForecast ? 'on' : 'off'}>
        <IndicatorMethodologyPanel
          indicator={effectiveIndicator}
          content={methodologyContent}
        />
        <IndicatorForecastSection
          indicator={effectiveIndicator}
          chartMode="cpi"
          safeViewMode={safeMode}
          dataPoints={dataPoints}
          displayForecastData={forecastResp}
          forecastEnabled={forecastEnabled}
          showForecast={showForecast}
          hasForecastData={hasForecast}
        />
      </div>

      <IndicatorDataTableSection
        indicator={effectiveIndicator}
        chartMode="cpi"
        safeViewMode={safeMode}
        {...FLAGS}
        dataPoints={dataPoints}
      />

      <IndicatorSeoBlocks blocks={indicator?.seo_blocks} indicatorCode={code} />

      <RelatedIndicators code={code} category={indicator?.category} items={relatedIndicators} />
    </>
  );
}
