import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, GitCompare } from 'lucide-react';
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
import { relatedIndicatorCardCopy } from '../lib/indicatorVariants';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, events } from '../lib/track';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';

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
    dataPoints, viewStats, forecastResp, forecastEnabled, hasForecast, isLoading,
  } = useGenericViewModeData({ family, urlMode: viewMode, indicator });

  const methodologyContent = useMemo(() => ({
    description: effectiveIndicator?.description,
    methodology: effectiveIndicator?.methodology,
  }), [effectiveIndicator?.description, effectiveIndicator?.methodology]);

  const downloadMeta = useMemo(() => ({
    name: effectiveIndicator?.name, unit: effectiveIndicator?.unit,
  }), [effectiveIndicator?.name, effectiveIndicator?.unit]);

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

  const chartEmptyHint = !isLoading && (dataPoints?.length ?? 0) === 0
    ? 'В API пока нет точек для этого режима — ряд появится после ближайшего пересчёта.'
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
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-16">
        <IndicatorMethodologyPanel
          indicator={effectiveIndicator}
          content={methodologyContent}
        />
        <IndicatorForecastSection
          indicator={effectiveIndicator}
          chartMode="cpi"
          safeViewMode={safeMode}
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

      {relatedIndicators.length > 0 && (
        <section data-block="related" className="mt-16">
          <div className="flex items-center gap-4 mb-6 flex-wrap">
            <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
              Похожие индикаторы
            </h2>
            <div className="h-[1px] flex-1 bg-border-subtle" />
            <Link
              to={`/compare?a=${code}`}
              onClick={() => track(events.RELATED_LINK_CLICK, {
                from: code, to: 'compare', surface: 'indicator-cta',
              })}
              className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-champagne hover:text-champagne-muted transition-colors"
            >
              <GitCompare className="w-3.5 h-3.5" />
              Сравнить
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {relatedIndicators.map((rel) => {
              const card = relatedIndicatorCardCopy(rel.code, rel.name, rel.unit);
              return (
                <Link
                  key={rel.code}
                  to={russiaIndicatorPath(rel.code)}
                  onClick={() => track(events.RELATED_INDICATOR_CLICK, {
                    from: code, to: rel.code, indicatorCategory: indicator?.category, surface: 'indicator-related',
                  })}
                  className="group flex items-start gap-3 p-4 rounded-2xl border border-border-subtle bg-surface hover:border-champagne/30 transition-colors min-h-[4.75rem]"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-text-primary leading-snug line-clamp-2 group-hover:text-champagne transition-colors">
                      {card.title}
                    </p>
                    {card.subtitle && (
                      <p className="mt-1.5 text-[10px] font-mono uppercase tracking-widest text-text-tertiary leading-relaxed line-clamp-2">
                        {card.subtitle}
                      </p>
                    )}
                  </div>
                  <ArrowRight className="w-4 h-4 text-text-tertiary shrink-0 mt-0.5 group-hover:text-champagne group-hover:translate-x-0.5 transition-all" />
                </Link>
              );
            })}
          </div>
        </section>
      )}
    </>
  );
}
