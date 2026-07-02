import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom';
import { ArrowRight, GitCompare } from 'lucide-react';
import gsap from 'gsap';
import {
  useIndicator, useIndicatorData, useIndicatorStats, useIndicators, useForecast,
} from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorDetailHeader from '../components/IndicatorDetailHeader';
import VariantGroupPicker from '../components/VariantGroupPicker';
import CpiIndicatorControls from '../components/CpiIndicatorControls';
import HousingIndicatorControls from '../components/HousingIndicatorControls';
import PpiIndicatorControls from '../components/PpiIndicatorControls';
import CbrTermSliceRateIndicatorControls from '../components/CbrTermSliceRateIndicatorControls';
import UnemploymentIndicatorControls from '../components/UnemploymentIndicatorControls';
import ViewModePicker from '../components/ViewModePicker';
import IndicatorTelemetryGrid from '../components/IndicatorTelemetryGrid';
import IndicatorChartSection from '../components/IndicatorChartSection';
import IndicatorMethodologyPanel from '../components/IndicatorMethodologyPanel';
import IndicatorForecastSection from '../components/IndicatorForecastSection';
import IndicatorDataTableSection from '../components/IndicatorDataTableSection';
import IndicatorSeoBlocks from '../components/IndicatorSeoBlocks';
import RegionCrossLink from '../components/RegionCrossLink';
import { findVariantGroup, relatedIndicatorCardCopy } from '../lib/indicatorVariants';
import useIndicatorViewModeData from '../lib/useIndicatorViewModeData';
import {
  findViewModeFamily,
  viewModeCanonicalTarget,
  applyMoMTransform,
  applyAggregateTransform,
  DAILY_AGG_FREQUENCY,
} from '../lib/viewModeFamilies';
import {
  getViewModeFamily,
  isViewModeFamily,
  viewModeCanonicalTarget as engineViewModeCanonicalTarget,
} from '../lib/viewModeEngine';
import GenericIndicatorView from '../components/GenericIndicatorView';
import { getViewModeContent } from '../lib/cpiViewModeContent';
import { HOUSING_CODES, housingCanonicalTarget } from '../lib/housingViewModeResolve';
import { PPI_CODES, ppiCanonicalTarget } from '../lib/ppiViewModeResolve';
import { CBR_TERM_SLICE_CODES } from '../lib/cbrTermSliceRateResolve';
import {
  UNEMPLOYMENT_ROOT,
  unemploymentCanonicalTarget,
  unemploymentDataCodeForMode,
  unemploymentModeMeta,
  normalizeUnemploymentViewMode,
} from '../lib/unemploymentViewModeResolve';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import { isIndicatorListed } from '../lib/categories';

// Правка №16 (звонок 2026-05-21): на карточке ИПП по умолчанию показываем
// г/г %, не уровень индекса 2018=100 (raw 105.2 без контекста бессмыслен).
// Редирект был стёрт при Phase 1 refactor 22-05, восстановлен после ревизии.
const DEFAULT_REDIRECTS = {
  ipi: 'ipi-yoy',
};

// Запоминаем последний выбранный режим карточки (per-indicator), чтобы при
// повторном заходе показать то, что человек смотрел в прошлый раз, а не сбрасывать
// на дефолт. Хранится в localStorage; ключ — код индикатора. SSR-safe (try/catch).
const VIEWMODE_STORE_PREFIX = 'fe:viewmode:';
function readSavedViewMode(code) {
  if (!code) return null;
  try {
    return window.localStorage.getItem(VIEWMODE_STORE_PREFIX + code) || null;
  } catch {
    return null;
  }
}
function writeSavedViewMode(code, mode) {
  if (!code || !mode) return;
  try {
    window.localStorage.setItem(VIEWMODE_STORE_PREFIX + code, mode);
  } catch {
    /* приватный режим / отключённый storage — просто не сохраняем */
  }
}

// Единый config-driven движок (lib/viewModeEngine): все 31 семьи из
// canonical-конфига (ставки/валюты/сырьё/деньги/кредиты/бюджет/ВВП/рынок
// труда/население) рендерятся через GenericIndicatorView с backend-derived
// рядами. Price/index-семьи (ИПЦ/ИЦП/жильё) в конфиг НЕ входят и остаются на
// специализированных ветках ниже (отдельная миграция index-бакетов).

export default function IndicatorDetail() {
  const { code } = useParams();
  const navigate = useNavigate();
  const headerRef = useRef(null);
  const [showForecast, setShowForecast] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const target = DEFAULT_REDIRECTS[code];
    if (target) {
      // Если дефолтный таргет — sibling generic-семьи (ipi-yoy), НЕ прыгаем на
      // его код: движок тут же канонизирует его обратно в `base?mode=yoy`, а
      // эта ветка снова сработает на `base` (mode игнорируется) → бесконечный
      // редирект-цикл и шторм перезапросов (лаг/подвисание карточки ИПП).
      // Выражаем дефолт через `?mode=` прямо на base и ставим guard: если mode
      // уже выставлен — ничего не делаем.
      const targetCanon = engineViewModeCanonicalTarget(target);
      if (targetCanon && isViewModeFamily(targetCanon.base)) {
        if (!searchParams.get('mode')) {
          // Восстанавливаем сохранённый режим (последний выбор пользователя),
          // иначе — дефолтный режим карточки (для ИПП это «год к году»).
          const savedMode = readSavedViewMode(targetCanon.base);
          const mode = savedMode || targetCanon.mode;
          navigate(
            `/indicator/${targetCanon.base}?mode=${encodeURIComponent(mode)}`,
            { replace: true },
          );
        }
        return;
      }
      navigate(`/indicator/${target}`, { replace: true });
      return;
    }
    // Config-driven канонизация: derived sibling (m2-yoy) → base?mode=yoy.
    const engineCanon = engineViewModeCanonicalTarget(code);
    if (engineCanon) {
      const fam = getViewModeFamily(engineCanon.base);
      const isDefault = engineCanon.mode === fam?.defaultMode;
      const suffix = isDefault ? '' : `?mode=${encodeURIComponent(engineCanon.mode)}`;
      navigate(`/indicator/${engineCanon.base}${suffix}`, { replace: true });
      return;
    }
    const canon = viewModeCanonicalTarget(code)
      ?? unemploymentCanonicalTarget(code)
      ?? housingCanonicalTarget(code)
      ?? ppiCanonicalTarget(code);
    if (canon) {
      const isHousingParent = HOUSING_CODES.includes(canon.parentCode);
      const isPpiParent = PPI_CODES.includes(canon.parentCode);
      const omitMode = canon.mode === 'level'
        || (isHousingParent && canon.mode === 'yoy')
        || (isPpiParent && canon.mode === 'yoy');
      const suffix = omitMode ? '' : `?mode=${encodeURIComponent(canon.mode)}`;
      navigate(`/indicator/${canon.parentCode}${suffix}`, { replace: true });
    }
  }, [code, navigate, searchParams]);
  // viewMode хранится в URL (?mode=…) — сохраняется при смене состава/среза.
  const urlMode = searchParams.get('mode');
  // Generic config-driven семьи всегда дефолтят в level (defaultMode='level'),
  // поэтому baseline для setViewMode/defaultViewMode = 'level'.
  const isGenericFamilyCode = isViewModeFamily(code);
  // Config-движок (31 семья) уже даёт defaultMode='level'; здесь остаются
  // только легаси-семьи вне движка, дефолтящие в level: срезы ставок CBR и
  // корень безработицы.
  const levelRateDefault = isGenericFamilyCode
    || CBR_TERM_SLICE_CODES.includes(code)
    || code === UNEMPLOYMENT_ROOT;
  const defaultViewMode = levelRateDefault
    ? 'level'
    : PPI_CODES.includes(code) || HOUSING_CODES.includes(code)
      ? 'yoy'
      : 'inflation';
  const viewMode = urlMode || defaultViewMode;
  const setViewMode = useCallback((mode) => {
    const baseline = levelRateDefault
      ? 'level'
      : PPI_CODES.includes(code) || HOUSING_CODES.includes(code)
        ? 'yoy'
        : 'inflation';
    writeSavedViewMode(code, mode || baseline);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (mode && mode !== baseline) next.set('mode', mode);
      else next.delete('mode');
      return next;
    }, { replace: true });
  }, [setSearchParams, code, levelRateDefault]);

  // Восстановление последнего выбранного режима при заходе без явного ?mode
  // (например, переход из каталога). Для семей с DEFAULT_REDIRECTS (ИПП)
  // восстановление уже сделано в редирект-эффекте выше. Здесь — все остальные
  // (жильё, ИЦП, generic-семьи), у которых дефолт выражается чистым URL.
  useEffect(() => {
    if (urlMode) return;
    if (DEFAULT_REDIRECTS[code]) return;
    const saved = readSavedViewMode(code);
    if (saved && saved !== defaultViewMode) {
      setViewMode(saved);
    }
    // namerenно зависим только от code: эффект — разовое восстановление на
    // карточку, не должен реагировать на последующую ручную смену режима.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);
  const [fullChartData, setFullChartData] = useState([]);

  const {
    data: indicator,
    isLoading: loadingInd,
    isError: indError,
    error: indErr,
    refetch: refetchInd,
    isFetching: fetchingInd,
  } = useIndicator(code);

  // Пока данные индикатора не пришли — не трогаем <head>: SSR-renderer
  // (seo_renderer.py::render_indicator_html) уже положил правильный title из
  // БД, плюс canonical/og:*. Любая клиентская перезапись на промежуточное
  // значение (например, "Индикатор cpi") вызывала бы flap у поисковиков.
  useDocumentMeta(indicator ? {
    title: indicator.seo_title || indicator.name,
    description: indicator.seo_description,
    path: `/indicator/${code}`,
  } : null);

  const { data: stats } = useIndicatorStats(code);
  const variantGroup = findVariantGroup(code);
  // Соседи по той же категории — нижний CTA-блок «Похожие индикаторы».
  // Загружается лениво (после того как мы знаем category), потому что
  // useIndicators({ category }) приходит из общего react-query-кэша и обычно
  // уже прогрет на /category/:slug страницей-родителем.
  const { data: siblings } = useIndicators({
    category: indicator?.category,
    includeInactive: false,
    enabled: Boolean(indicator?.category),
  });

  const relatedIndicators = useMemo(() => {
    if (!siblings?.length || !indicator) return [];
    return siblings
      .filter((s) => s.code !== indicator.code && isIndicatorListed(s) && s.is_active)
      .slice(0, 6);
  }, [siblings, indicator]);

  const view = useIndicatorViewModeData({ code, viewMode });
  const {
    isPriceCategory, isHousingFamily, isPpiFamily,
    isCbrTermSliceFamily,
    isUnemploymentFamily,
    isUnemploymentCanonical,
    safeViewMode, chartMode, shouldSubtract100,
    dataPoints: baseDataPoints, momDataPoints, inflationResp,
    quarterlyDataPoints, annualDataPoints, weeklyDataPoints,
    yoyDataPoints, qoqDataPoints, periodMonthlyDataPoints, periodWeeklyDataPoints,
    displayForecastData, quarterlyForecastData, annualForecastResp,
    yoyForecastData, qoqForecastData, periodMonthlyForecastData, periodWeeklyForecastData,
    stats: baseViewStats, cpiPrevDate,
    chartLoading: baseChartLoading, loadingData, loadingInflation,
    loadingAnnual, loadingWeekly, loadingQuarterly, loadingYoy, loadingQoq,
    loadingPeriodMonthly, loadingPeriodWeekly,
    dataError, fetchingData, hasForecastData, forecastEnabled: baseForecastEnabled,
    refetchData, refetchInflation, refetchForecast,
  } = view;

  // ============================================================
  // View-mode families (Phase 1+2+3): in-page переключение
  // «режим отображения» вместо отдельных карточек в каталоге.
  //
  // Если текущий код — корень family (exports / wages-nominal / unemployment
  // / housing-price-* и т.д.) и URL содержит ?mode=… — подгружаем derived
  // и подменяем dataPoints. Виртуальные transforms (MoM, agg) считаются
  // на фронте без backend-дёргания. См. lib/viewModeFamilies.js.
  //
  // Daily aggregation (Phase 5, daily-индикаторы вроде key-rate, ruonia,
  // cbr-fx-*, gold-price) обрабатывается отдельно ниже (dailyAggregation).
  // ============================================================
  const viewFamily = findViewModeFamily(code);
  const isFamily = !!viewFamily;
  const familyAllowedModes = useMemo(
    () => (viewFamily ? viewFamily.modes.map((m) => m.mode) : []),
    [viewFamily],
  );
  const familyMode = isFamily
    ? (familyAllowedModes.includes(viewMode) ? viewMode : 'level')
    : null;
  const familyModeMeta = useMemo(
    () => (viewFamily && familyMode ? viewFamily.modes.find((m) => m.mode === familyMode) : null),
    [viewFamily, familyMode],
  );
  const isVirtualTransform = isFamily && familyMode !== 'level' && !!familyModeMeta?.transform;
  const unemploymentSafeMode = isUnemploymentCanonical
    ? normalizeUnemploymentViewMode(viewMode)
    : null;
  const unemploymentDerivedCode = isUnemploymentCanonical && unemploymentSafeMode !== 'level'
    ? unemploymentDataCodeForMode(unemploymentSafeMode)
    : null;

  const familyDerivedCode = isFamily && familyMode !== 'level' && !isVirtualTransform
    ? familyModeMeta?.code ?? null
    : null;
  const modeSubstituteCode = familyDerivedCode || unemploymentDerivedCode;

  const { data: familyDerivedResp, isLoading: loadingFamilyDerived } = useIndicatorData(
    modeSubstituteCode,
    undefined,
    { enabled: !!modeSubstituteCode },
  );
  const { data: familyForecastResp, refetch: refetchFamilyForecast } = useForecast(
    modeSubstituteCode,
    { enabled: !!modeSubstituteCode },
  );
  // ============================================================
  // Phase 5 — daily aggregation transforms (weekly/monthly/quarterly/annual).
  // Применяется к ЛЮБОМУ daily-индикатору, который ещё не принадлежит
  // family (чтобы не конфликтовало). Режимы:
  //   ?mode=weekly | monthly | quarterly | annual  → avg по bucket'ам.
  // ============================================================
  const dailyAggGranularity = useMemo(() => {
    if (isFamily) return null;
    if (indicator?.frequency !== 'daily') return null;
    const mapping = { weekly: 'week', monthly: 'month', quarterly: 'quarter', annual: 'year' };
    return mapping[viewMode] || null;
  }, [isFamily, indicator?.frequency, viewMode]);

  const familyDataPoints = useMemo(() => {
    if (isVirtualTransform && familyModeMeta?.transform === 'mom') {
      return applyMoMTransform(baseDataPoints || []);
    }
    if (modeSubstituteCode && familyDerivedResp?.data?.length) {
      return familyDerivedResp.data;
    }
    if (dailyAggGranularity) {
      return applyAggregateTransform(baseDataPoints || [], dailyAggGranularity);
    }
    return null;
  }, [
    isVirtualTransform, familyModeMeta, modeSubstituteCode, familyDerivedResp,
    baseDataPoints, dailyAggGranularity,
  ]);

  const dataPoints = familyDataPoints || baseDataPoints;

  // Telemetry-cards — пересчёт по подменённому ряду (если он есть).
  const familyViewStats = useMemo(() => {
    if (!familyDataPoints?.length) return null;
    const pts = familyDataPoints;
    const current = pts[pts.length - 1];
    const previous = pts.length > 1 ? pts[pts.length - 2] : null;
    const highest = pts.reduce((max, p) => (p.value > max.value ? p : max), pts[0]);
    const avg = pts.reduce((sum, p) => sum + p.value, 0) / pts.length;
    return {
      currentValue: current.value,
      currentDate: current.date,
      previousValue: previous?.value,
      previousDate: previous?.date,
      change: previous ? current.value - previous.value : null,
      highest: { value: highest.value, date: highest.date },
      average: avg,
      dataCount: pts.length,
    };
  }, [familyDataPoints]);

  const viewStats = familyViewStats || baseViewStats;
  const chartLoading = baseChartLoading || (modeSubstituteCode && loadingFamilyDerived);
  const familyForecastValues = familyForecastResp?.forecast?.values;
  const familyHasForecast = Array.isArray(familyForecastValues) && familyForecastValues.length > 0;
  const isSubstituteDerivedMode = !!modeSubstituteCode;
  const chartForecastData = (isFamily && familyMode !== 'level' && !isVirtualTransform)
    ? familyForecastResp
    : displayForecastData;
  const forecastEnabled = !!dailyAggGranularity || isSubstituteDerivedMode
    ? false
    : (isFamily && familyMode !== 'level' && !isVirtualTransform)
      ? familyHasForecast
      : baseForecastEnabled;
  const hasForecastDataForSection = isSubstituteDerivedMode
    ? false
    : (isFamily && familyMode !== 'level' && !isVirtualTransform)
      ? familyHasForecast
      : hasForecastData;

  // Подменяем `indicator` для downstream-компонентов (телеметрия, график,
  // download, таблица) — даёт правильный unit, frequency и расширенное имя
  // («Экспорт товаров (YoY %)» или «Безработица (Квартально)»).
  // Unit берётся из режима: если `modeMeta.unit` задан — используем его;
  // если не задан — сохраняем родительскую единицу.
  // Frequency берётся из `modeMeta.frequency` для real siblings (например,
  // wages-nominal-annual → annual) и из `DAILY_AGG_FREQUENCY[granularity]`
  // для daily-aggregation (Phase 5). Для virtual `mom`-transform или
  // `level`-режима frequency остаётся родительская. См. trap «View-mode
  // family metadata leak» в CONTEXT.md.
  // Хедер страницы остаётся оригинальным (`indicator.name`), чтобы
  // breadcrumbs и H1 не дёргались при смене mode — frequency-pill в Header
  // подменяется через отдельный prop `displayFrequency`.
  const effectiveIndicator = useMemo(() => {
    if (!indicator) return indicator;
    if (isFamily && familyMode !== 'level') {
      const suffix = familyModeMeta ? familyModeMeta.label : familyMode;
      return {
        ...indicator,
        unit: familyModeMeta?.unit ?? indicator.unit,
        frequency: familyModeMeta?.frequency ?? indicator.frequency,
        name: `${indicator.name} (${suffix})`,
      };
    }
    if (isUnemploymentCanonical && unemploymentSafeMode !== 'level') {
      const uMeta = unemploymentModeMeta(unemploymentSafeMode);
      return {
        ...indicator,
        frequency: uMeta.frequency,
        name: `${indicator.name} (${uMeta.label})`,
      };
    }
    if (dailyAggGranularity) {
      const aggLabel = viewMode === 'weekly' ? 'среднее по неделям'
        : viewMode === 'monthly' ? 'среднее по месяцам'
          : viewMode === 'quarterly' ? 'среднее по кварталам'
            : viewMode === 'annual' ? 'среднее по годам' : 'среднее за период';
      return {
        ...indicator,
        frequency: DAILY_AGG_FREQUENCY[dailyAggGranularity] ?? indicator.frequency,
        name: `${indicator.name} (${aggLabel})`,
      };
    }
    return indicator;
  }, [indicator, isFamily, familyMode, familyModeMeta, isUnemploymentCanonical, unemploymentSafeMode, dailyAggGranularity, viewMode]);

  const adj = useCallback((v) => {
    if (v == null || !shouldSubtract100) return v;
    return Number(v) - 100;
  }, [shouldSubtract100]);

  useEffect(() => {
    const els = headerRef.current?.querySelectorAll('[data-animate]');
    if (!els?.length) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(els,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 1, ease: 'power3.out', stagger: 0.1 }
    );
    return () => tween.kill();
  }, []);

  useEffect(() => {
    if (!indicator?.code) return;
    track(events.INDICATOR_VIEW, {
      indicator: indicator.code,
      indicatorCategory: indicator.category,
    });
  }, [indicator?.code, indicator?.category]);

  useScrollDepth({
    key: code,
    page: 'indicator',
    indicator: code,
    indicatorCategory: indicator?.category,
  });

  const handleFullData = useCallback((data) => {
    setFullChartData(data);
  }, [setFullChartData]);

  const downloadMeta = useMemo(() => ({
    name: effectiveIndicator?.name, unit: effectiveIndicator?.unit,
  }), [effectiveIndicator?.name, effectiveIndicator?.unit]);

  const downloadMode = isPriceCategory ? chartMode : null;

  // Выгрузка — всегда полный ряд (вся история), а не видимое окно графика.
  const handleDownloadExcel = useCallback(async () => {
    try {
      const ok = await downloadExcel(fullChartData, downloadMode, code, 'all', downloadMeta);
      if (ok) track(events.DOWNLOAD_EXCEL, { indicator: code, range: 'all', indicatorCategory: indicator?.category });
    } catch { /* сеть/сервер — молча, UI не ломаем */ }
  }, [fullChartData, downloadMode, code, downloadMeta, indicator]);

  const handleDownloadCSV = useCallback(async () => {
    try {
      const ok = await downloadCSV(fullChartData, downloadMode, code, 'all', downloadMeta);
      if (ok) track(events.DOWNLOAD_CSV, { indicator: code, range: 'all', indicatorCategory: indicator?.category });
    } catch { /* сеть/сервер — молча, UI не ломаем */ }
  }, [fullChartData, downloadMode, code, downloadMeta, indicator]);

  const chartEmptyHint = useMemo(() => {
    if (dataError) {
      return 'Не удалось получить исторический ряд. Нажмите «Повторить» выше или проверьте backend / прокси Vite.';
    }
    if (!loadingData && (dataPoints?.length ?? 0) === 0) {
      return (
        'В API пока нет точек для этого кода — например, прод ещё без backfill ключевой ставки, или локальный backend не запущен. '
        + 'После появления данных график заполнится автоматически.'
      );
    }
    return undefined;
  }, [dataError, loadingData, dataPoints]);

  const refetchIndicatorPage = useCallback(() => {
    refetchInd();
    refetchData();
    if (isPriceCategory) refetchInflation();
    refetchForecast();
    if (modeSubstituteCode) refetchFamilyForecast();
  }, [
    refetchInd, refetchData, refetchInflation, refetchForecast,
    refetchFamilyForecast, modeSubstituteCode, isPriceCategory,
  ]);

  const apiBannerFetching = fetchingInd || fetchingData;
  const viewModeContent = getViewModeContent({
    chartMode, safeViewMode, isPriceCategory, isHousingFamily, isPpiFamily,
    isCbrTermSliceFamily,
    isUnemploymentFamily,
    indicator,
  });
  const s = viewStats;

  const genericFamily = getViewModeFamily(code);
  const useGeneric = !!genericFamily;
  if (useGeneric) {
    return (
      <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
        <GenericIndicatorView
          code={code}
          indicator={indicator}
          family={genericFamily}
          viewMode={viewMode}
          setViewMode={setViewMode}
          stats={stats}
          variantGroup={variantGroup}
          relatedIndicators={relatedIndicators}
          loadingInd={loadingInd}
          headerRef={headerRef}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      {(indError || dataError) && (
        <div className="mb-8">
          <ApiRetryBanner
            onRetry={refetchIndicatorPage}
            isFetching={apiBannerFetching}
          >
            {indError && (
              <span className="block">
                Карточка индикатора не загрузилась
                {indErr?.message ? ` (${indErr.message})` : ''}.
              </span>
            )}
            {dataError && (
              <span className="block">
                Исторические данные недоступны — график и таблица без ряда.
              </span>
            )}
          </ApiRetryBanner>
        </div>
      )}

      <IndicatorDetailHeader
        indicator={indicator}
        code={code}
        loading={loadingInd}
        headerRef={headerRef}
        displayFrequency={effectiveIndicator?.frequency}
      />

      <IndicatorTelemetryGrid
        indicator={effectiveIndicator}
        viewStats={s}
        stats={stats}
        isPriceCategory={isPriceCategory}
        isHousingFamily={isHousingFamily}
        isPpiFamily={isPpiFamily}
        chartMode={chartMode}
        safeViewMode={safeViewMode}
        cpiPrevDate={cpiPrevDate}
        adj={adj}
        loading={
          loadingInd
          || (chartMode === 'inflation' && loadingInflation)
          || (chartMode === 'annual' && loadingAnnual)
          || (chartMode === 'weekly' && loadingWeekly)
          || (chartMode === 'quarterly' && loadingQuarterly)
          || (chartMode === 'yoy' && loadingYoy)
          || (chartMode === 'qoq' && loadingQoq)
          || (chartMode === 'period-monthly' && loadingPeriodMonthly)
          || (chartMode === 'period-weekly' && loadingPeriodWeekly)
          || (chartMode === 'mom' && loadingData)
          || (chartMode === 'index' && loadingData)
        }
      />

      {/* Оба переключателя — НАД графиком, сверху вниз:
          1) «Состав» (категории-родственники: cpi → cpi-food / housing-primary →
             housing-secondary и т.д.) — меняет сам индикатор и весь набор данных.
          2) «Режим инфляции» (мес / кв / год / нед / индекс) — меняет представление
             того же индикатора, должен стоять сразу над графиком.
          3) График.
          Под графиком — никаких переключателей (только range-пресеты внутри самого
          IndicatorChart и форекаст-toggle в тулбаре). */}
      {/* Generic config-driven семьи (31 шт.) рендерятся через
          GenericIndicatorView (early-return выше) — здесь остаются только
          специализированные ценовые/индексные карточки и срезы ставок CBR,
          не входящие в canonical-конфиг движка. */}
      {isPriceCategory ? (
        <CpiIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isHousingFamily ? (
        <HousingIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isPpiFamily ? (
        <PpiIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isCbrTermSliceFamily ? (
        <CbrTermSliceRateIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isUnemploymentFamily && isUnemploymentCanonical ? (
        <UnemploymentIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : (
        <VariantGroupPicker group={variantGroup} currentCode={code} />
      )}

      {isFamily && !isHousingFamily && !isPpiFamily
        && !isCbrTermSliceFamily && !isUnemploymentFamily && (
        <ViewModePicker
          title="Режим отображения"
          modes={viewFamily.modes.map((m) => ({ mode: m.mode, label: m.label }))}
          currentMode={familyMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      )}

      {/* Phase 5: daily-агрегации для прочих daily-индикаторов вне family/движка */}
      {!isFamily && !isUnemploymentFamily
        && indicator?.frequency === 'daily' && (
        <ViewModePicker
          title="Частота отображения"
          modes={[
            { mode: 'level', label: 'Ежедневно' },
            { mode: 'weekly', label: 'Понедельно' },
            { mode: 'monthly', label: 'Помесячно' },
            { mode: 'quarterly', label: 'Поквартально' },
            { mode: 'annual', label: 'Годово' },
          ]}
          currentMode={dailyAggGranularity ? viewMode : 'level'}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      )}

      <IndicatorChartSection
        code={code}
        indicator={effectiveIndicator}
        chartMode={chartMode}
        safeViewMode={safeViewMode}
        isPriceCategory={isPriceCategory}
        isHousingFamily={isHousingFamily}
        isPpiFamily={isPpiFamily}
        isCbrTermSliceFamily={isCbrTermSliceFamily}
        isUnemploymentFamily={isUnemploymentFamily}
        chartLoading={chartLoading}
        inflationResp={inflationResp}
        dataPoints={dataPoints}
        momDataPoints={momDataPoints}
        quarterlyDataPoints={quarterlyDataPoints}
        annualDataPoints={annualDataPoints}
        weeklyDataPoints={weeklyDataPoints}
        yoyDataPoints={yoyDataPoints}
        qoqDataPoints={qoqDataPoints}
        periodMonthlyDataPoints={periodMonthlyDataPoints}
        periodWeeklyDataPoints={periodWeeklyDataPoints}
        displayForecastData={chartForecastData}
        quarterlyForecastData={quarterlyForecastData}
        annualForecastResp={annualForecastResp}
        yoyForecastData={yoyForecastData}
        qoqForecastData={qoqForecastData}
        periodMonthlyForecastData={periodMonthlyForecastData}
        periodWeeklyForecastData={periodWeeklyForecastData}
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
          indicator={indicator}
          content={viewModeContent}
        />
        <IndicatorForecastSection
          indicator={indicator}
          chartMode={chartMode}
          safeViewMode={safeViewMode}
          inflationResp={inflationResp}
          displayForecastData={chartForecastData}
          quarterlyForecastData={quarterlyForecastData}
          annualForecastResp={annualForecastResp}
          yoyForecastData={yoyForecastData}
          qoqForecastData={qoqForecastData}
          periodMonthlyForecastData={periodMonthlyForecastData}
          periodWeeklyForecastData={periodWeeklyForecastData}
          forecastEnabled={forecastEnabled}
          showForecast={showForecast}
          hasForecastData={hasForecastDataForSection}
        />
      </div>

      <IndicatorDataTableSection
        indicator={effectiveIndicator}
        chartMode={chartMode}
        safeViewMode={safeViewMode}
        isPriceCategory={isPriceCategory}
        isHousingFamily={isHousingFamily}
        isPpiFamily={isPpiFamily}
        isCbrTermSliceFamily={isCbrTermSliceFamily}
        isUnemploymentFamily={isUnemploymentFamily}
        inflationResp={inflationResp}
        dataPoints={dataPoints}
        momDataPoints={momDataPoints}
        quarterlyDataPoints={quarterlyDataPoints}
        annualDataPoints={annualDataPoints}
        weeklyDataPoints={weeklyDataPoints}
        yoyDataPoints={yoyDataPoints}
        qoqDataPoints={qoqDataPoints}
        periodMonthlyDataPoints={periodMonthlyDataPoints}
        periodWeeklyDataPoints={periodWeeklyDataPoints}
      />

      <IndicatorSeoBlocks blocks={indicator?.seo_blocks} indicatorCode={code} />

      <RegionCrossLink macroCode={code} />

      {relatedIndicators.length > 0 && (
        <section className="mt-16">
          <div className="flex items-center gap-4 mb-6 flex-wrap">
            <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
              Похожие индикаторы
            </h2>
            <div className="h-[1px] flex-1 bg-border-subtle" />
            <Link
              to={`/compare?a=${code}`}
              onClick={() => track(events.RELATED_LINK_CLICK, {
                from: code,
                to: 'compare',
                surface: 'indicator-cta',
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
                to={`/indicator/${rel.code}`}
                onClick={() => track(events.RELATED_INDICATOR_CLICK, {
                  from: code,
                  to: rel.code,
                  indicatorCategory: indicator?.category,
                  surface: 'indicator-related',
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
    </div>
  );
}
