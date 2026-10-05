// Карточка мирового индикатора: /world/{slug}/{code}?mode=
// UI-эталон — российские макрокарточки (TelemetryCard + champagne/15 picker).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowUpRight, Activity,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getSiteOrigin } from '../lib/siteOrigin';
import { completeDataset } from '../lib/datasetJsonLd';
import { mountJsonLd } from '../lib/jsonLd';
import {
  useWorldIndicator, useWorldIndicatorData, useWorldCountry, useWorldCompareSnapshot, formatWorldValue,
  localizeWorldUnit,
} from '../lib/worldApi';
import {
  adaptWorldModes,
  buildWorldModeToken,
  findWorldMode,
  indicatorPublicName,
  isEmptySeries,
  normalizeWorldFrequencies,
  normalizeWorldModeToken,
  parseWorldModeToken,
  pickEnDisplay,
  resolveWorldMode,
  stripFrequencySuffix,
  worldModeToLegacyDataToken,
  worldVariantsToPickerGroup,
} from '../lib/worldViewModes';
import { formatDate, chartValueDigits, resolveDateFormat } from '../lib/format';
import { indicatorPolarity } from '../lib/deltaTone';
import { buildIndicatorSummary, rankAmongCountries } from '../lib/indicatorSummary';
import { deriveWorldMode } from '../lib/worldDerive';
import { downloadCSV, downloadExcel } from '../lib/excel';
import { track, events } from '../lib/track';
import WorldViewModePicker from '../components/WorldViewModePicker';
import { ViewModesPanel } from '../components/ViewModesPanel';
import WorldChartSection from '../components/WorldChartSection';
import VariantGroupPicker from '../components/VariantGroupPicker';
import IndicatorMethodologyPanel from '../components/IndicatorMethodologyPanel';
import SourceLink from '../components/SourceLink';
import DataTable from '../components/DataTable';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import DeltaBadge from '../components/DeltaBadge';
import WorldCountUp from '../components/WorldCountUp';
import WorldStatTiles, { WorldHeroLine } from '../components/WorldStatTiles';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import Button from '../components/Button';
import '../styles/platform-pages.css';
import '../styles/world.css';
import '../styles/x2-indicator.css';
import { worldIndicatorTrail } from '../lib/breadcrumbs';
import {
  countryPath,
  indicatorPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import '../styles/w6e-indicator.css';

const EMPTY_POINTS = [];

export default function WorldIndicatorPage() {
  const { countrySlug, slug: slugParam, code } = useParams();
  const slug = countrySlug || slugParam;
  const navigate = useNavigate();
  const t = useT();
  const { locale } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlMode = searchParams.get('mode');

  const metaQ = useWorldIndicator(slug, code);
  const apiIsComposite = Array.isArray(metaQ.data?.modes)
    && metaQ.data.modes.some((m) => m.type && m.freq);
  // Современная meta уже содержит страну и sibling-частоты. Тяжёлый каталог
  // страны нужен только для legacy-контракта; не конкурируем с первым графиком.
  const countryQ = useWorldCountry(slug, {
    enabled: Boolean(metaQ.data) && !apiIsComposite,
  });

  // Frequencies: из meta или из схлопнутого каталога страны (легаси API).
  const frequencies = useMemo(() => {
    if (!metaQ.data) return [];
    const fromMeta = normalizeWorldFrequencies(
      metaQ.data.frequencies,
      metaQ.data.indicator?.frequency,
    );
    if (fromMeta.length > 1 || fromMeta.some((f) => f.code)) return fromMeta;

    // Легаси: ищем частотных близнецов в каталоге страны по имени без суффикса.
    const cats = countryQ.data?.categories || [];
    const myName = stripFrequencySuffix(metaQ.data.indicator?.name);
    const myUnit = metaQ.data.indicator?.unit || '';
    const siblings = [];
    for (const cat of cats) {
      for (const ind of cat.indicators || []) {
        if (stripFrequencySuffix(ind.name) === myName && (ind.unit || '') === myUnit) {
          siblings.push({
            freq: ind.frequency,
            code: ind.code,
            points_count: ind.points_count,
            official: true,
          });
        }
      }
    }
    if (siblings.length > 1) return siblings;
    return fromMeta;
  }, [metaQ.data, countryQ.data]);

  const allModes = useMemo(
    () => adaptWorldModes({
      modes: metaQ.data?.modes,
      frequencies,
      indicator: metaQ.data?.indicator,
    }),
    [metaQ.data, frequencies],
  );
  // Режимы, которые не удалось ни загрузить, ни посчитать, прячем: кнопка не должна вести в сломанное состояние.
  const [failedModes, setFailedModes] = useState(() => new Set());
  const modes = useMemo(() => {
    const level = allModes.find((m) => m.type === 'level');
    // У ряда, который уже сам индекс («2015 = 100»), второй «Индекс» от старта ничем не отличается от «Значений».
    const levelIsIndex = /индекс|index|=\s*100/i.test(level?.unit || metaQ.data?.indicator?.unit || '');
    return allModes.filter((m) => !(m.type === 'index' && levelIsIndex)
      && !failedModes.has(`${code}|${m.id}`));
  }, [allModes, failedModes, code, metaQ.data?.indicator?.unit]);

  const fallbackFreq = frequencies[0]?.freq || metaQ.data?.indicator?.frequency || 'monthly';
  const activeMode = resolveWorldMode(modes, urlMode, fallbackFreq);
  const modeMeta = findWorldMode(modes, activeMode);
  const modeParsed = parseWorldModeToken(activeMode);

  // Новый API: data всегда с primary + составной mode.
  // Легаси: грузим sibling-код + старый токен режима.
  const dataCode = useMemo(() => {
    if (apiIsComposite) return metaQ.data?.primary_code || code;
    if (!modeParsed) return code;
    const sib = frequencies.find((f) => f.freq === modeParsed.freq && f.code);
    return sib?.code || code;
  }, [apiIsComposite, metaQ.data?.primary_code, code, modeParsed, frequencies]);

  const dataModeParam = apiIsComposite
    ? activeMode
    : (metaQ.data ? worldModeToLegacyDataToken(activeMode) : null);

  const forecastAvailable = modeMeta?.forecastable != null
    ? Boolean(modeMeta.forecastable)
    : (
      Boolean(metaQ.data?.forecast_available)
      && modeParsed?.freq !== 'weekly'
      && modeParsed?.freq !== 'daily'
    );
  const [showForecast, setShowForecast] = useState(true);
  const redirecting = Boolean(metaQ.data?.redirect_to);
  const dataQ = useWorldIndicatorData(slug, code, redirecting ? null : dataModeParam, {
    requestCode: dataCode,
    includeForecast: forecastAvailable && showForecast,
  });
  // Сервер отказал в режиме «год к году», «к прошлому периоду» или «индекс»: считаем его на странице из значений.
  const modeType = modeParsed?.type;
  const needsFallback = Boolean(
    dataQ.isError && !redirecting && modeType && modeType !== 'level' && modeParsed?.freq,
  );
  const levelToken = needsFallback ? buildWorldModeToken('level', modeParsed.freq) : null;
  const levelQ = useWorldIndicatorData(
    slug,
    code,
    levelToken ? (apiIsComposite ? levelToken : worldModeToLegacyDataToken(levelToken)) : null,
    { requestCode: dataCode },
  );
  const derived = useMemo(
    () => (needsFallback && levelQ.data?.points ? deriveWorldMode(levelQ.data.points, modeType) : null),
    [needsFallback, levelQ.data, modeType],
  );
  const modeUnusable = needsFallback && Boolean(levelQ.data) && !derived;
  useEffect(() => {
    if (!modeUnusable || !activeMode) return;
    setFailedModes((prev) => {
      const key = `${code}|${activeMode}`;
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
  }, [modeUnusable, activeMode, code]);


  const [fullChartData, setFullChartData] = useState([]);

  // Канон URL: unlisted член merge-группы (замороженный ГИПЦ) → listed primary.
  useEffect(() => {
    const to = metaQ.data?.redirect_to;
    if (!to || typeof to !== 'string') return;
    const q = to.indexOf('?');
    const pathname = q >= 0 ? to.slice(0, q) : to;
    const rawSearch = q >= 0 ? to.slice(q + 1) : '';
    const next = new URLSearchParams(rawSearch);
    const preview = searchParams.get('preview_locale');
    if (preview) next.set('preview_locale', preview);
    const qs = next.toString();
    navigate(
      { pathname, search: qs ? `?${qs}` : '' },
      { replace: true },
    );
  }, [metaQ.data?.redirect_to, navigate, searchParams]);

  // Канон URL: primary_code + составной ?mode= (preview_locale не теряем).
  useEffect(() => {
    if (metaQ.data?.redirect_to) return;
    const primary = metaQ.data?.primary_code;
    if (primary && primary !== code) {
      const mode = activeMode || normalizeWorldModeToken(
        urlMode,
        metaQ.data.indicator?.frequency || 'monthly',
      );
      const next = new URLSearchParams(searchParams);
      next.set('mode', mode);
      const search = next.toString();
      navigate(
        { pathname: indicatorPath(slug, primary), search: search ? `?${search}` : '' },
        { replace: true },
      );
    }
  }, [metaQ.data?.primary_code, code, slug, navigate, activeMode, urlMode, metaQ.data?.indicator?.frequency, searchParams]);

  useEffect(() => {
    if (!activeMode) return;
    if (urlMode === activeMode) return;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('mode', activeMode);
      return next;
    }, { replace: true });
  }, [activeMode, urlMode, setSearchParams]);

  useEffect(() => {
    setShowForecast(true);
  }, [code, activeMode]);

  const setMode = useCallback((mode) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('mode', mode);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const country = metaQ.data?.country;
  const indicator = metaQ.data?.indicator;
  const displayName = indicatorPublicName(indicator, locale);
  const countryName = (locale === 'en' && country?.name_en)
    ? country.name_en
    : (country?.name || '');
  const notFound = metaQ.isError && metaQ.error?.response?.status === 404;
  const categoryLabel = locale === 'en'
    ? pickEnDisplay(indicator?.category, indicator?.category_en)
    : (indicator?.category || '');

  const variantGroup = useMemo(
    () => worldVariantsToPickerGroup(
      metaQ.data?.variants,
      t('world.indicator.slice'),
      { locale },
    ),
    [metaQ.data?.variants, t, locale],
  );

  // Стабильная ссылка обязательна: IndicatorChart сообщает объединённый ряд
  // через onFullData; новый [] на каждом рендере замыкал update-loop.
  const points = derived ? derived.points : (dataQ.data?.points || EMPTY_POINTS);
  const forecastPoints = derived ? EMPTY_POINTS : (dataQ.data?.forecast?.points || EMPTY_POINTS);
  const dataLoading = dataQ.isLoading || (needsFallback && levelQ.isLoading);
  const dataError = needsFallback ? levelQ.isError : dataQ.isError;
  const dataRefetch = needsFallback ? levelQ.refetch : dataQ.refetch;
  const dataFetching = needsFallback ? levelQ.isFetching : dataQ.isFetching;
  const empty = !dataLoading && !dataError && isEmptySeries(points);
  const last = points.length ? points[points.length - 1] : null;
  let rawUnit = dataQ.data?.unit || dataQ.data?.unit_ru
    || modeMeta?.unit || indicator?.unit || indicator?.unit_ru || '';
  if (derived) {
    rawUnit = derived.unit === 'percent' ? '%'
      : derived.unit === 'index' ? t('w6e.unit.indexStart')
        : (levelQ.data?.unit || modeMeta?.unit || indicator?.unit || '');
  } else if ((modeType === 'yoy' || modeType === 'step') && /индекс|index|=\s*100/i.test(rawUnit)) {
    // «Изменение за год» не может быть в «индексе 2015 = 100»: это проценты.
    rawUnit = '%';
  }
  const displayUnit = localizeWorldUnit(rawUnit, locale);
  const unitBesideValue = localizeWorldUnit(
    dataQ.data?.unit_suffix || indicator?.unit_suffix || '',
    locale,
  );
  const activeFreq = dataQ.data?.frequency || modeParsed?.freq || indicator?.frequency;
  const aggregated = Boolean(dataQ.data?.aggregated)
    || (modeMeta && modeMeta.official === false);
  // Знаков после запятой ровно столько, сколько есть в самих данных: «1 815 983», «3,1», а не «1 815 983,00» и «3,10».
  const valueDigits = points.length > 0
    ? Math.min(2, Math.max(...points.map((point) => {
      const value = Number(point.value);
      return Number.isFinite(value) ? (String(Math.abs(value)).split('.')[1] || '').length : 0;
    })))
    : chartValueDigits(rawUnit || displayUnit);
  const polarity = indicatorPolarity(displayName);
  const summary = useMemo(
    () => buildIndicatorSummary({
      points,
      frequency: dataQ.data?.frequency || modeParsed?.freq || indicator?.frequency,
      unit: displayUnit,
      modeType,
      dataDigits: valueDigits,
      locale,
    }),
    [points, dataQ.data?.frequency, modeParsed?.freq, indicator?.frequency, displayUnit, modeType, valueDigits, locale],
  );
  // Место среди стран: по снимку последних значений того же понятия, только для обычных величин (ВВП, население).
  const rankConcept = summary?.kind === 'level' && modeType === 'level' ? indicator?.concept_slug : null;
  const snapshotQ = useWorldCompareSnapshot(rankConcept);
  const rank = useMemo(() => {
    const snap = snapshotQ.data;
    if (!snap?.items || snap?.concept?.value_mode !== 'level') return null;
    return rankAmongCountries(snap.items, country?.code, summary?.last?.value);
  }, [snapshotQ.data, country?.code, summary?.last?.value]);
  const deltaSuffix = activeFreq === 'quarterly' ? t('indicator.telemetry.delta.prevQuarter')
    : activeFreq === 'annual' ? t('indicator.telemetry.delta.prevYear')
      : activeFreq === 'weekly' ? t('indicator.telemetry.delta.prevWeek')
        : activeFreq === 'daily' ? t('indicator.telemetry.delta.prevValue')
          : t('indicator.telemetry.delta.prevValue');
  const previousLabel = activeFreq === 'quarterly' ? t('indicator.telemetry.prevQuarter')
    : activeFreq === 'annual' ? t('indicator.telemetry.prevYear')
      : activeFreq === 'weekly' ? t('indicator.telemetry.prevWeek')
        : activeFreq === 'daily' ? t('indicator.telemetry.prev')
          : activeFreq === 'monthly' ? t('indicator.telemetry.prevMonth')
            : t('indicator.telemetry.prev');
  const FREQ_KEYS = {
    daily: 'world.indicator.freq.daily',
    weekly: 'world.indicator.freq.weekly',
    monthly: 'world.indicator.freq.monthly',
    quarterly: 'world.indicator.freq.quarterly',
    annual: 'world.indicator.freq.annual',
  };
  const freqLabel = FREQ_KEYS[activeFreq] ? t(FREQ_KEYS[activeFreq]) : (activeFreq || '—');

  const sourceLabel = localizeSource(
    indicator?.source || t('world.indicator.sourceFallback'),
    locale,
  );
  // Один расчёт издателя и на панели методологии, и в блоке «О ряде»
  // (methodologyIndicator ниже переиспользует то же sourceLabel).
  const valuePart = `${formatWorldValue(last?.value, valueDigits, locale)}${unitBesideValue ? ` ${unitBesideValue}` : ''}`;
  useDocumentMeta(indicator && country ? {
    title: t('world.indicator.metaTitle', { name: displayName, country: countryName }),
    description: last?.date
      ? t('world.indicator.metaDesc', {
        name: displayName,
        country: countryName,
        value: valuePart,
        unit: '',
        date: formatDate(last.date, 'full', locale),
        source: sourceLabel,
      })
      : t('world.indicator.metaDescNoDate', {
        name: displayName,
        country: countryName,
        value: valuePart,
        unit: '',
        source: sourceLabel,
      }),
    path: indicatorPath(slug, code),
  } : {
    title: notFound ? t('world.indicator.notFoundTitle') : t('world.eyebrow'),
    description: t('world.coverageNote'),
    path: indicatorPath(slug, code),
  });

  useEffect(() => {
    if (!indicator || !country) return undefined;
    const source = indicator.source?.trim();
    const jsonLd = completeDataset({
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `${displayName} — ${countryName}`,
      description: indicator.description || `${displayName}, ${countryName}.${source ? ` ${source}.` : ''}`,
      ...(source ? { creator: { '@type': 'Organization', name: source } } : {}),
      publisher: { '@type': 'Organization', name: 'Forecast Economy', url: getSiteOrigin() },
    }, locale);
    return mountJsonLd(jsonLd);
  }, [indicator, country, countryName, displayName, locale, t]);

  useEffect(() => {
    if (!indicator) return;
    track(events.INDICATOR_VIEW, {
      indicator: `world:${slug}:${code}`,
      country: slug,
      code,
      mode: activeMode,
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indicator?.code, slug, code]);

  const methodologyContent = useMemo(() => {
    const description = indicator?.description;
    const methodology = indicator?.methodology;
    const source = sourceLabel || indicator?.source || (locale === 'en' ? 'the listed source' : 'указанный источник');
    const subject = displayName || indicator?.name_en || (locale === 'en' ? 'This indicator' : 'Показатель');
    const place = countryName || (locale === 'en' ? 'this country' : 'эта страна');
    // Пустая методология не должна выглядеть пустой: говорим, откуда данные и что показано на графике.
    const fallbackDescription = t('z1.world.descFallback', { subject, place, source });
    const fallbackMethodology = t('z1.world.methodFallback', { source });
    if (locale !== 'en') {
      const cleaned = typeof methodology === 'string'
        ? methodology.replace(/\s*На графике показан наиболее общий доступный срез показателя\.?/g, '').trim()
        : methodology;
      return {
        description: description || fallbackDescription,
        methodology: cleaned || fallbackMethodology,
      };
    }
    const hideRu = (text) => (
      text && /[А-Яа-яЁё]/.test(text) ? undefined : text
    );
    return {
      description: hideRu(description) || fallbackDescription,
      methodology: hideRu(methodology) || fallbackMethodology,
    };
  }, [indicator?.description, indicator?.methodology, indicator?.source, sourceLabel, displayName, countryName, indicator?.name_en, locale, t]);

  const methodologyIndicator = useMemo(() => {
    if (!indicator) return null;
    return {
      ...indicator,
      name: displayName,
      source: sourceLabel,
    };
  }, [indicator, displayName, sourceLabel]);

  // Блок «О ряде»: поле «источник» показывает издателя (тот же localizeSource,
  // что идёт в панель методологии), а английский титул набора из источника —
  // отдельной строкой, но только если он отличается от отображаемого имени.
  const originalTitle = (indicator?.name_en || '').trim();
  const showOriginalTitle = Boolean(originalTitle) && originalTitle !== displayName;


  const downloadMeta = useMemo(() => ({
    name: displayName,
    unit: displayUnit,
  }), [displayName, displayUnit]);

  const handleDownloadExcel = useCallback(async () => {
    try {
      const ok = await downloadExcel(fullChartData, activeMode, code, 'all', downloadMeta);
      if (ok) track(events.DOWNLOAD_EXCEL, { indicator: code, world: true, mode: activeMode });
    } catch { /* сеть */ }
  }, [fullChartData, activeMode, code, downloadMeta]);

  const handleDownloadCSV = useCallback(async () => {
    try {
      const ok = await downloadCSV(fullChartData, activeMode, code, 'all', downloadMeta);
      if (ok) track(events.DOWNLOAD_CSV, { indicator: code, world: true, mode: activeMode });
    } catch { /* сеть */ }
  }, [fullChartData, activeMode, code, downloadMeta]);

  const dateFormat = resolveDateFormat({
    frequency: activeFreq,
    chartMode: 'cpi',
  });

  const chartIndicator = useMemo(() => {
    if (!indicator) return null;
    return { ...indicator, name: displayName, frequency: activeFreq };
  }, [indicator, displayName, activeFreq]);

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6 md:px-8 md:pt-28 md:pb-28">
      <Breadcrumbs
        items={worldIndicatorTrail(
          countryName || country?.name || '',
          slug,
          displayName || '',
          code,
        )}
        className="flex-nowrap! overflow-hidden [&>span:last-child]:min-w-0 [&>span:last-child>span]:block [&>span:last-child>span]:truncate"
      />

      {notFound && (
        <div className="mt-8 rounded-2xl border border-border-subtle bg-surface p-8 text-center">
          <h1 className="mb-3 font-display text-2xl font-bold text-text-primary">{t('world.indicator.notFoundTitle')}</h1>
          <p className="mb-6 text-text-secondary">
            {t('world.indicator.notFoundBody')}
          </p>
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            <Button as={Link} to={countryPath(slug)} variant="primary">
              {t('world.indicator.backToCountry')}
            </Button>
            <Button as={Link} to="/#countries" variant="secondary">
              {t('world.indicator.allCountries')}
            </Button>
            <Button as={Link} to="/" variant="secondary">
              {t('world.indicator.home')}
            </Button>
          </div>
        </div>
      )}

      {(metaQ.isError && !notFound) && (
        <ApiRetryBanner onRetry={metaQ.refetch} isFetching={metaQ.isFetching} className="mb-6">
          {t('world.indicator.loadError')}
        </ApiRetryBanner>
      )}

      {(metaQ.isLoading || redirecting) && (
        <div className="space-y-4" role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => metaQ.refetch()} className="mb-4" />
          <SkeletonBox className="h-6 w-28 rounded-full" />
          <SkeletonBox className="h-8 w-3/4 max-w-full sm:h-10 md:h-14 lg:h-[4.5rem]" />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-6">
            {[0, 1, 2, 3].map((i) => (
              <SkeletonBox key={i} className="h-28 rounded-2xl md:h-48 md:rounded-[2rem]" />
            ))}
          </div>
        </div>
      )}

      {metaQ.data && indicator && (
        <>
          <header className="fe-data-header">
            <div className="mb-2.5 flex flex-wrap items-center gap-2 sm:gap-3 md:mb-4">
              <span className="flex items-center gap-2 rounded-full border border-border-subtle bg-obsidian-light px-3 py-1 text-[13px] font-medium text-text-secondary">
                <Activity className="h-3.5 w-3.5 text-champagne-ink" aria-hidden="true" />
                {freqLabel}
              </span>
              {countryName && (
                <Link
                  to={countryPath(slug)}
                  className="hidden text-sm text-text-secondary transition-colors hover:text-champagne-ink sm:inline"
                >
                  {countryName}
                </Link>
              )}
              {categoryLabel && (
                <span className="hidden text-sm text-text-secondary sm:inline">
                  {categoryLabel}
                </span>
              )}
            </div>
            <h1 className="mb-1.5 text-pretty font-display text-[1.3rem] font-bold leading-[1.28] tracking-tight text-text-primary sm:text-3xl md:mb-4 md:text-5xl md:leading-tight lg:text-6xl">
              {displayName}
            </h1>
            {summary ? (
              <WorldHeroLine summary={summary} place={countryName} dateFormat={dateFormat} />
            ) : (dataLoading && !dataError ? <SkeletonBox className="fe-hero-line-skeleton" /> : null)}
            {metaQ.data._fromMock && (
              <p className="mt-2 text-xs text-text-secondary">
                {t('world.mockData')}
              </p>
            )}
          </header>

          <ViewModesPanel>
            {variantGroup && (
              <VariantGroupPicker
                group={variantGroup}
                currentCode={code}
                basePath={`${countryPath(slug)}/indicator`}
              />
            )}

            {modes.length > 0 && (
              <WorldViewModePicker
                modes={modes}
                currentMode={activeMode}
                onChange={setMode}
                trackContext={{ code, category: indicator.category }}
              />
            )}
          </ViewModesPanel>

          {dataError && (
            <ApiRetryBanner onRetry={dataRefetch} isFetching={dataFetching} className="mb-6">
              {t('world.indicator.dataLoadError')}
            </ApiRetryBanner>
          )}

          {!dataError && (
            <WorldChartSection
              code={code}
              indicator={chartIndicator}
              modeMeta={modeMeta}
              dataPoints={points}
              forecastData={forecastPoints}
              forecastEnabled={forecastAvailable && !derived}
              forecastDerivedFrom={dataQ.data?.forecast?.derived_from || null}
              forecastGateStatus={
                dataQ.data?.forecast?.quality?.gate_status
                || metaQ.data?.forecast_gate_status
                || (forecastAvailable ? 'passed' : null)
              }
              showForecast={showForecast}
              onToggleForecast={() => setShowForecast((current) => !current)}
              chartLoading={dataLoading}
              emptyHint={empty ? t('world.indicator.emptyMode') : undefined}
              onFullData={setFullChartData}
              onDownloadCsv={handleDownloadCSV}
              onDownloadExcel={handleDownloadExcel}
              frequency={activeFreq}
              aggregated={aggregated}
              aggregation={dataQ.data?.aggregation || modeMeta?.aggregation || null}
              unit={displayUnit}
              country={country}
              conceptSlug={indicator.concept_slug}
              comparisonPeers={metaQ.data.peers || []}
            />
          )}

          <section className="mb-6 md:mb-10">
            {dataLoading && !summary ? (
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-4">
                {[0, 1, 2, 3].map((i) => (
                  <SkeletonBox key={i} className="h-32 rounded-3xl" />
                ))}
              </div>
            ) : (
              <WorldStatTiles
                summary={summary}
                dateFormat={dateFormat}
                frequency={activeFreq}
                previousLabel={previousLabel}
                deltaSuffix={deltaSuffix}
                polarity={polarity}
                rank={rank}
              />
            )}
          </section>

          {dataQ.data?.forecast?.quality?.gate_status === 'passed' && (
            <details className="w2-details w2-details--card" aria-label={locale === 'en' ? 'Forecast methodology' : 'Методология прогноза'}>
              <summary>{locale === 'en' ? 'How our forecast is checked' : 'Как мы проверяем наш прогноз'}</summary>
              <p>
                {locale === 'en'
                  ? 'We test the full forecast horizon on rolling historical windows against a seasonal-naive benchmark. Our forecast is published only when MASE is below 1 and the error is at least 2% lower.'
                  : 'Мы проверяем весь горизонт прогноза на последовательных исторических отрезках и сравниваем с сезонной наивной моделью. Наш прогноз публикуется только при MASE ниже 1 и ошибке минимум на 2% меньше ориентира.'}
              </p>
              <p className="mt-2 text-sm">
                {dataQ.data.forecast.model_name}
                {' — '}MASE {Number(dataQ.data.forecast.quality.mase).toFixed(2)}
              </p>
            </details>
          )}

          <div className="mb-12 grid grid-cols-1 gap-8 lg:grid-cols-3">
            <IndicatorMethodologyPanel
              indicator={methodologyIndicator}
              content={methodologyContent}
              sourcePath={indicator.source_url || indicatorPath(slug, code)}
            />
            <div className="rounded-3xl border border-border-subtle bg-obsidian-light p-5 sm:p-8 lg:col-span-2">
              <h3 className="mb-4 text-base font-semibold text-text-primary">
                {t('world.indicator.aboutSeries')}
              </h3>
              <dl className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="mb-1 text-xs text-text-secondary">{t('world.indicator.field.freq')}</dt>
                  <dd className="text-text-primary">
                    {freqLabel}
                  </dd>
                </div>
                <div>
                  <dt className="mb-1 text-xs text-text-secondary">{t('world.indicator.field.unit')}</dt>
                  <dd className="text-text-primary">{displayUnit || '—'}</dd>
                </div>
                <div>
                  <dt className="mb-1 text-xs text-text-secondary">{t('world.indicator.field.history')}</dt>
                  <dd className="text-text-primary">
                    {indicator.history_start && indicator.history_end
                      ? `${formatDate(indicator.history_start, 'annual', locale)}–${formatDate(indicator.history_end, 'annual', locale)}`
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="mb-1 text-xs text-text-secondary">{t('common.source')}</dt>
                  <dd className="text-[15px] leading-5 text-text-secondary">
                    <SourceLink
                      href={indicator.source_url}
                      className="text-champagne-ink underline-offset-2 hover:underline"
                      textClassName=""
                    >
                      {sourceLabel}
                    </SourceLink>
                  </dd>
                </div>
              </dl>
              <details className="w2-details">
                <summary>{t('w2.ind.more')}</summary>
                <dl className="mt-2 grid gap-4 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="mb-1 text-xs text-text-secondary">{t('world.indicator.field.points')}</dt>
                    <dd className="text-text-primary">
                      {dataQ.data?.count ?? indicator.points_count ?? '—'}
                    </dd>
                  </div>
                  {showOriginalTitle && (
                    <div className="sm:col-span-2">
                      <dt className="mb-1 text-xs text-text-secondary">
                        {t('world.indicator.field.sourceName')}
                      </dt>
                      <dd className="leading-5 text-text-secondary">
                        {originalTitle}
                      </dd>
                    </div>
                  )}
                </dl>
              </details>
              <div className="mt-6 flex flex-wrap gap-2 border-t border-border-subtle pt-4">
                <Link
                  to={countryPath(slug)}
                  className="fe-tap-inline gap-1 rounded-full border border-border-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-champagne hover:text-champagne-ink"
                >
                  {t('world.indicator.allOfCountry', { country: countryName || country?.name || '' })}
                  <ArrowUpRight size={12} aria-hidden="true" />
                </Link>
                <Link
                  to="/#countries"
                  className="fe-tap-inline gap-1 rounded-full border border-border-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-champagne hover:text-champagne-ink"
                >
                  {t('world.indicator.allCountries')}
                  <ArrowUpRight size={12} aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>

          <section>
            <DataTable
              key={`${code}-${activeMode}`}
              data={points}
              title={t('table.historical', { name: displayName })}
              dateFormat={dateFormat}
              unit={displayUnit}
              valueDigits={chartValueDigits(displayUnit)}
              showUnitInValues={false}
            />
          </section>
        </>
      )}
    </div>
  );
}
