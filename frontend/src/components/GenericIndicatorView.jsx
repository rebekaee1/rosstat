import { useCallback, useMemo, useState } from 'react';
import { useIndicator } from '../lib/hooks';
import useGenericViewModeData from '../lib/useGenericViewModeData';
import { resolveViewMode } from '../lib/viewModeEngine';
import IndicatorDetailHeader from './IndicatorDetailHeader';
import VariantGroupPicker from './VariantGroupPicker';
import GenericViewModePicker from './GenericViewModePicker';
import { ViewModesPanel } from './ViewModesPanel';
import IndicatorTelemetryGrid from './IndicatorTelemetryGrid';
import CurrencyTelemetry from './CurrencyTelemetry';
import CurrencyNext from './CurrencyNext';
import { CurrencyCardConverter } from './CurrencyConverter';
import { isCurrencyIndicator } from '../lib/sitePaths';
import { TRIP_UNITS, formatConverted, normalizeRateNameEn, parsePair, quoteUnitsOf, unitWord } from '../lib/currencyRates';
import '../styles/r8e-fixes.css';
import IndicatorChartSection from './IndicatorChartSection';
import IndicatorMethodologyPanel from './IndicatorMethodologyPanel';
import IndicatorForecastSection from './IndicatorForecastSection';
import IndicatorDataTableSection from './IndicatorDataTableSection';
import IndicatorSeoBlocks from './IndicatorSeoBlocks';
import RelatedIndicators from './RelatedIndicators';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { buildIndicatorSummary, dataDigitsOf } from '../lib/indicatorSummary';
import { resolveDateFormat } from '../lib/format';
import { WorldHeroLine } from './WorldStatTiles';
import { isFreshIntraday, useLiveQuote } from '../lib/tickerLive';
import IndicatorHeroValue from './IndicatorHeroValue';
import R6bPulseStrip from './R6bPulseStrip';
import FreshnessNote from './FreshnessNote';
import BrentLiveNote from './BrentLiveNote';
import { russiaIndicatorSubject } from '../lib/cabinetSubjects';
import { indicatorPolarity } from '../lib/deltaTone';
import '../styles/z4-indicator.css';
import '../styles/k5-pages.css';
import '../styles/r3d-card.css';
import '../styles/r6b-card.css';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import ApiRetryBanner from './ApiRetryBanner';
import LoadingNote from './LoadingNote';

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
  const { locale } = useLocale();
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

  // Биткоин (круг 13): число и изменение в шапке берутся от той же котировки и той же базы, что и лента курсов («к цене 24 часа назад»).
  // Раньше шапка сравнивала сегодняшнюю точку ряда с закрытием вчера, а лента — цену с ценой сутки назад: «без изменений» против «+0,6 %».
  const liveSnapshot = useLiveQuote(code === 'btc-usd' ? 'btc-usd' : null);
  const liveBtc = code === 'btc-usd' && isFreshIntraday(liveSnapshot)
    && (dataPoints?.length ?? 0) > 1
    && String(dataPoints[dataPoints.length - 1]?.date || '').slice(0, 10) === liveSnapshot.as_of_day
    ? liveSnapshot : null;
  const heroPoints = useMemo(() => {
    if (!liveBtc) return dataPoints;
    return [...dataPoints.slice(0, -1), { ...dataPoints[dataPoints.length - 1], value: Number(liveBtc.price) }];
  }, [dataPoints, liveBtc]);
  // Одна строка с главным числом под названием: как на странице показателя страны.
  const heroSummary = useMemo(() => buildIndicatorSummary({
    points: heroPoints,
    frequency: effectiveIndicator?.frequency,
    unit: effectiveIndicator?.unit,
    dataDigits: dataDigitsOf(dataPoints),
    locale,
  }), [heroPoints, dataPoints, effectiveIndicator?.frequency, effectiveIndicator?.unit, locale]);
  const heroDateFormat = resolveDateFormat({ chartMode: 'cpi', frequency: effectiveIndicator?.frequency, safeViewMode: safeMode });
  const heroFreq = effectiveIndicator?.frequency;
  // Ряд «по дням»: изменение считается от значения предыдущего дня (круг 12, Г3); при недельной или месячной детализации подпись прежняя.
  const heroDayGap = heroSummary?.prev && heroSummary?.last
    ? (Date.parse(heroSummary.last.date) - Date.parse(heroSummary.prev.date)) / 86_400_000
    : null;
  const heroDeltaSuffix = liveBtc ? t('c13u.delta.last24h') : heroFreq === 'quarterly' ? t('w3.tele.delta.prevQuarter')
    : heroFreq === 'daily' && heroDayGap != null && heroDayGap > 0 && heroDayGap <= 4 ? t('c12u.delta.prevDay')
    : heroFreq === 'weekly' ? t('w3.tele.delta.prevWeek')
      : heroFreq === 'annual' ? t('w3.tele.delta.prevYear')
        : heroFreq === 'monthly' ? t('w3.tele.delta.prevMonth')
          : t('w3.tele.delta.prevValue');
  const heroPolarity = indicatorPolarity(indicator?.name, indicator?.name_en, indicator?.code);

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

  const isCurrency = isCurrencyIndicator(code);
  // R3-D: у курса валюты режимы «к тому же периоду прошлого года» и «по кварталам» только сбивают (человек ждёт цену, а не темп).
  // Прячем их на уровне показа; сам режим, если он уже открыт по ссылке, остаётся доступным.
  const pickerFamily = useMemo(() => {
    if (!isCurrency || !family?.groups) return family;
    const current = family.modes?.find((m) => m.mode === safeMode);
    const hide = new Set(['yoy']);
    if (current && hide.has(current.group)) return family;
    return {
      ...family,
      groups: family.groups.filter((g) => !hide.has(g.id)),
      modes: (family.modes || []).filter((m) => !hide.has(m.group) && m.mode !== 'eop-quarter' && m.mode !== 'avg-quarter'),
    };
  }, [isCurrency, family, safeMode]);
  // На английском название курса пишется одинаково везде: «USD/RUB exchange rate».
  const headerIndicator = isCurrency && locale === 'en' && indicator?.name
    ? { ...indicator, name: normalizeRateNameEn(indicator.name) }
    : indicator;

  // R8-E: у мелких валют «в дорогу» под заголовком стоит «1 000 ₽ = 112 сомони», как в разделе курсов.
  const sendLine = useMemo(() => {
    const pair = isCurrency ? parsePair(code) : null;
    const value = Number(heroSummary?.last?.value);
    if (!pair || pair.quote !== 'RUB' || !TRIP_UNITS.includes(pair.base) || !(value > 0)) return '';
    const perOneRub = value / quoteUnitsOf(effectiveIndicator?.unit);
    if (!(perOneRub > 0)) return '';
    const got = 1000 / perOneRub;
    return `1\u00a0000\u00a0₽ = ${formatConverted(got, locale, { money: true })}\u00a0${unitWord(got, pair.base, locale)}`;
  }, [isCurrency, code, heroSummary, effectiveIndicator?.unit, locale]);

  // При сбое подсказка под пустым графиком ссылается на кнопку «Повторить» выше, а не рассказывает про «загрузку с сервера».
  const chartEmptyHint = !isLoading && (dataPoints?.length ?? 0) === 0
    ? t(isError ? 'indicator.empty.seriesFetch' : 'indicator.empty.recalc')
    : undefined;

  return (
    <>
      {loadingInd && <LoadingNote onRefresh={() => refetch()} className="mb-4" />}
      <IndicatorDetailHeader
        indicator={headerIndicator}
        code={code}
        loading={loadingInd}
        headerRef={headerRef}
        displayFrequency={effectiveIndicator?.frequency}
        subject={russiaIndicatorSubject(code, indicator?.name)}
        aside={(heroSummary || loadingInd || isLoading) ? (
          <IndicatorHeroValue
            summary={loadingInd ? null : heroSummary}
            points={dataPoints}
            dateFormat={heroDateFormat}
            polarity={heroPolarity}
            frequency={heroFreq}
            deltaSuffix={heroDeltaSuffix}
            liveChangePct={liveBtc ? Number(liveBtc.change_pct) : null}
            loading={loadingInd || isLoading}
          />
        ) : null}
      >
        {!loadingInd && sendLine ? <p className="r8e-send-line" data-testid="currency-send-line">{sendLine}</p> : null}
        {!loadingInd && heroSummary ? (
          <WorldHeroLine summary={heroSummary} place="" dateFormat={heroDateFormat} frequency={heroFreq} />
        ) : null}
        {!loadingInd && heroSummary ? (
          <R6bPulseStrip
            summary={heroSummary}
            polarity={heroPolarity}
            deltaSuffix={heroDeltaSuffix}
            dateFormat={heroDateFormat}
            related={relatedIndicators}
            code={code}
            category={indicator?.category}
          />
        ) : null}
      </IndicatorDetailHeader>

      <FreshnessNote freshness={indicator?.freshness} />
      <BrentLiveNote code={code} />

      {/* R3-D: конвертер — главное действие на карточке курса, он стоит сразу под заголовком, а не после графика. */}
      {isCurrency && <CurrencyCardConverter code={code} />}

      <ViewModesPanel label={isCurrency ? t('w6g.cur.show') : undefined}>
        {variantGroup ? (
          <VariantGroupPicker group={variantGroup} currentCode={code} />
        ) : null}

        <GenericViewModePicker
          family={pickerFamily}
          currentMode={safeMode}
          onChange={setViewMode}
          pending={Boolean(isLoading)}
          trackContext={{ code, category: indicator?.category }}
        />
      </ViewModesPanel>

      {isError && (dataPoints?.length ?? 0) === 0 && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          {t('indicator.dataError')}
        </ApiRetryBanner>
      )}

      <div className="z4-stage">
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

        <div className="z4-tiles">
      {isCurrency ? (
        <CurrencyTelemetry
          code={code}
          loading={loadingInd}
          fallback={(
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
              points={dataPoints}
              loading={loadingInd || isLoading}
            />
          )}
        />
      ) : (
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
          points={dataPoints}
          loading={loadingInd || isLoading}
        />
      )}
        </div>
      </div>

      <div className="z4-lower" data-lower={forecastEnabled && showForecast && hasForecast ? 'wide' : 'stack'}>
        <div className="z4-lower__table">
      <IndicatorDataTableSection
        indicator={effectiveIndicator}
        chartMode="cpi"
        safeViewMode={safeMode}
        {...FLAGS}
        dataPoints={dataPoints}
        pairedWithForecast={Boolean(forecastEnabled && showForecast && hasForecast)}
      />
        </div>
        <div className="z4-lower__aside">
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
        <div className="z4-lower__method">
        <IndicatorMethodologyPanel
          indicator={effectiveIndicator}
          content={methodologyContent}
        />
        </div>
      </div>

      {isCurrency && <CurrencyNext code={code} />}

      <IndicatorSeoBlocks blocks={indicator?.seo_blocks} indicatorCode={code} />

      <RelatedIndicators code={code} category={indicator?.category} items={relatedIndicators} />
    </>
  );
}
