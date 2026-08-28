// Карточка мирового индикатора: /world/{slug}/{code}?mode=
// UI-эталон — российские макрокарточки (TelemetryCard + champagne/15 picker).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, ArrowUpRight, Activity,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getSiteOrigin } from '../lib/siteOrigin';
import {
  useWorldIndicator, useWorldIndicatorData, useWorldCountry, formatWorldValue,
} from '../lib/worldApi';
import {
  adaptWorldModes,
  findWorldMode,
  isEmptySeries,
  normalizeWorldFrequencies,
  normalizeWorldModeToken,
  parseWorldModeToken,
  resolveWorldMode,
  stripFrequencySuffix,
  worldModeToLegacyDataToken,
  worldVariantsToPickerGroup,
} from '../lib/worldViewModes';
import { formatDate, chartValueDigits, resolveDateFormat } from '../lib/format';
import { downloadCSV, downloadExcel } from '../lib/excel';
import { track, events } from '../lib/track';
import WorldViewModePicker from '../components/WorldViewModePicker';
import WorldChartSection from '../components/WorldChartSection';
import VariantGroupPicker from '../components/VariantGroupPicker';
import IndicatorMethodologyPanel from '../components/IndicatorMethodologyPanel';
import DataTable from '../components/DataTable';
import ApiRetryBanner from '../components/ApiRetryBanner';
import TelemetryCard from '../components/TelemetryCard';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { worldIndicatorTrail } from '../lib/breadcrumbs';
import {
  countryPath,
  indicatorPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';

const EMPTY_POINTS = [];

function computeWorldTelemetry(points) {
  if (!points?.length) return null;
  const last = points[points.length - 1];
  const prev = points.length > 1 ? points[points.length - 2] : null;
  let highest = last;
  let sum = 0;
  let n = 0;
  for (const p of points) {
    const v = Number(p.value);
    if (!Number.isFinite(v)) continue;
    sum += v;
    n += 1;
    if (v > Number(highest.value)) highest = p;
  }
  const change = prev != null && Number.isFinite(Number(last.value)) && Number.isFinite(Number(prev.value))
    ? Number(last.value) - Number(prev.value)
    : null;
  return {
    currentValue: last.value,
    currentDate: last.date,
    previousValue: prev?.value,
    previousDate: prev?.date,
    change,
    highest: { value: highest.value, date: highest.date },
    average: n ? sum / n : null,
    dataCount: points.length,
  };
}

export default function WorldIndicatorPage() {
  const { countrySlug, slug: slugParam, code } = useParams();
  const slug = countrySlug || slugParam;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const t = useT();
  const { locale } = useLocale();
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

  const modes = useMemo(
    () => adaptWorldModes({
      modes: metaQ.data?.modes,
      frequencies,
      indicator: metaQ.data?.indicator,
    }),
    [metaQ.data, frequencies],
  );

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

  const forecastAvailable = Boolean(metaQ.data?.forecast_available);
  const [showForecast, setShowForecast] = useState(false);
  const dataQ = useWorldIndicatorData(slug, code, dataModeParam, {
    requestCode: dataCode,
    includeForecast: forecastAvailable && showForecast,
  });

  // #chart из SSR-ссылок (og:image → карточка): скролл к графику, когда
  // данные загружены и секция смонтирована. Эталон — IndicatorChartSection.
  const { hash } = useLocation();
  useEffect(() => {
    if (hash !== '#chart') return;
    const node = document.getElementById('chart');
    if (!node) return;
    node.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [hash, dataQ.isLoading, dataQ.data]);

  const [fullChartData, setFullChartData] = useState([]);

  // Канон URL: primary_code + составной ?mode=
  useEffect(() => {
    const primary = metaQ.data?.primary_code;
    if (primary && primary !== code) {
      const mode = activeMode || normalizeWorldModeToken(
        urlMode,
        metaQ.data.indicator?.frequency || 'monthly',
      );
      navigate(`${indicatorPath(slug, primary)}?mode=${encodeURIComponent(mode)}`, {
        replace: true,
      });
    }
  }, [metaQ.data?.primary_code, code, slug, navigate, activeMode, urlMode, metaQ.data?.indicator?.frequency]);

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
    setShowForecast(false);
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
  // API locale-facing `name` (EN: name_en + slice overlay). Never prefer name_ru.
  const displayName = stripFrequencySuffix(indicator?.name || '');
  const countryName = (locale === 'en' && country?.name_en)
    ? country.name_en
    : (country?.name || '');
  const notFound = metaQ.isError && metaQ.error?.response?.status === 404;

  const variantGroup = useMemo(
    () => worldVariantsToPickerGroup(metaQ.data?.variants, t('world.indicator.slice')),
    [metaQ.data?.variants, t],
  );

  // Стабильная ссылка обязательна: IndicatorChart сообщает объединённый ряд
  // через onFullData; новый [] на каждом рендере замыкал update-loop.
  const points = dataQ.data?.points || EMPTY_POINTS;
  const forecastPoints = dataQ.data?.forecast?.points || EMPTY_POINTS;
  const empty = !dataQ.isLoading && isEmptySeries(points);
  const last = points.length ? points[points.length - 1] : null;
  const telemetry = useMemo(() => computeWorldTelemetry(points), [points]);
  // Prefer locale-facing `unit` (API resolves EN); unit_ru is storage/RU.
  const displayUnit = dataQ.data?.unit || dataQ.data?.unit_ru
    || modeMeta?.unit || indicator?.unit || indicator?.unit_ru || '';
  const unitBesideValue = dataQ.data?.unit_suffix ?? indicator?.unit_suffix ?? '';
  const activeFreq = dataQ.data?.frequency || modeParsed?.freq || indicator?.frequency;
  const aggregated = Boolean(dataQ.data?.aggregated)
    || (modeMeta && modeMeta.official === false);
  const valueDigits = chartValueDigits(displayUnit);
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
  const valuePart = `${formatWorldValue(last?.value)}${unitBesideValue ? ` ${unitBesideValue}` : ''}`;
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
    const source = indicator.source || t('world.indicator.sourceFallback');
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `${displayName} — ${countryName}`,
      description: indicator.description || `${displayName}, ${countryName}. ${source}.`,
      creator: { '@type': 'Organization', name: source },
      publisher: { '@type': 'Organization', name: 'Forecast Economy', url: getSiteOrigin() },
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'world-dataset-jsonld';
    script.textContent = JSON.stringify(jsonLd);
    document.getElementById('world-dataset-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [indicator, country, countryName, displayName, t]);

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

  const methodologyContent = useMemo(() => ({
    description: indicator?.description,
    methodology: indicator?.methodology,
  }), [indicator?.description, indicator?.methodology]);

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
  const originalTitleLabel = t('world.indicator.field.originalTitle', locale === 'en'
    ? 'Original series title'
    : 'Оригинальное название ряда');

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
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6 md:px-8 md:pt-28 md:pb-28">
      <Breadcrumbs
        items={worldIndicatorTrail(
          countryName || country?.name || '…',
          slug,
          displayName || '…',
          code,
        )}
        variant="mono"
      />

      {notFound && (
        <div className="mt-8 rounded-2xl border border-border-subtle bg-surface p-8 text-center">
          <h1 className="mb-3 font-display text-2xl font-bold text-text-primary">{t('world.indicator.notFoundTitle')}</h1>
          <p className="mb-6 text-text-secondary">
            {t('world.indicator.notFoundBody')}
          </p>
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            <Link to={countryPath(slug)} className="rounded-xl bg-champagne/10 px-4 py-2 text-champagne transition-colors hover:bg-champagne/20">
              {t('world.indicator.backToCountry')}
            </Link>
            <Link to="/world" className="rounded-xl border border-border-subtle px-4 py-2 text-text-secondary transition-colors hover:text-champagne">
              {t('world.indicator.allCountries')}
            </Link>
            <Link to="/" className="rounded-xl border border-border-subtle px-4 py-2 text-text-secondary transition-colors hover:text-champagne">
              {t('world.indicator.home')}
            </Link>
          </div>
        </div>
      )}

      {(metaQ.isError && !notFound) && (
        <ApiRetryBanner onRetry={metaQ.refetch} isFetching={metaQ.isFetching} className="mb-6">
          {t('world.indicator.loadError')}
        </ApiRetryBanner>
      )}

      {metaQ.isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-4 w-24" />
          <SkeletonBox className="h-14 w-3/4 max-w-full" />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-6">
            {[0, 1, 2, 3].map((i) => (
              <SkeletonBox key={i} className="h-28 rounded-2xl md:h-48 md:rounded-[2rem]" />
            ))}
          </div>
        </div>
      )}

      {metaQ.data && indicator && (
        <>
          <header className="mb-5 max-w-4xl md:mb-12">
            <div className="mb-2.5 flex flex-wrap items-center gap-2 sm:gap-3 md:mb-4">
              <span className="flex items-center gap-2 rounded-full border border-border-subtle bg-obsidian-light px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest text-text-secondary sm:px-3">
                <Activity className="h-3 w-3 text-champagne" />
                {freqLabel}
              </span>
              {countryName && (
                <Link
                  to={countryPath(slug)}
                  className="hidden font-mono text-xs text-text-tertiary transition-colors hover:text-champagne sm:inline"
                >
                  {countryName}
                </Link>
              )}
              {indicator.category && (
                <span className="hidden font-mono text-xs text-text-tertiary sm:inline">
                  {indicator.category}
                </span>
              )}
            </div>
            <h1 className="mb-1.5 text-pretty font-display text-[1.3rem] font-bold leading-[1.28] tracking-tight text-text-primary sm:text-3xl md:mb-4 md:text-5xl md:leading-tight lg:text-6xl">
              {displayName}
            </h1>
            {metaQ.data._fromMock && (
              <p className="mt-2 font-mono text-[12px] text-text-tertiary">
                {t('world.mockData')}
              </p>
            )}
          </header>

          <section className="mb-6 md:mb-12">
            {dataQ.isLoading && !telemetry ? (
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-6">
                {[0, 1, 2, 3].map((i) => (
                  <SkeletonBox key={i} className="h-28 rounded-2xl md:h-48 md:rounded-[2rem]" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-6">
                <TelemetryCard
                  label={t('indicator.telemetry.current')}
                  value={telemetry?.currentValue}
                  unit={displayUnit}
                  valueDigits={valueDigits}
                  change={telemetry?.change}
                  meta={telemetry?.currentDate
                    ? t('indicator.telemetry.date', { date: formatDate(telemetry.currentDate, dateFormat, locale) })
                    : undefined}
                  delay={0}
                  deltaSuffix={deltaSuffix}
                />
                <TelemetryCard
                  label={previousLabel}
                  value={telemetry?.previousValue}
                  unit={displayUnit}
                  valueDigits={valueDigits}
                  meta={telemetry?.previousDate
                    ? t('indicator.telemetry.date', { date: formatDate(telemetry.previousDate, dateFormat, locale) })
                    : undefined}
                  delay={1}
                />
                {telemetry?.highest && (
                  <TelemetryCard
                    label={t('indicator.telemetry.max')}
                    value={telemetry.highest.value}
                    unit={displayUnit}
                    valueDigits={valueDigits}
                    meta={t('indicator.telemetry.peak', { date: formatDate(telemetry.highest.date, dateFormat, locale) })}
                    delay={2}
                  />
                )}
                {telemetry?.average != null && (
                  <TelemetryCard
                    label={t('indicator.telemetry.avg')}
                    value={telemetry.average}
                    unit={displayUnit}
                    valueDigits={valueDigits}
                    meta={t('indicator.telemetry.obs', { count: telemetry.dataCount })}
                    delay={3}
                  />
                )}
              </div>
            )}
          </section>

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

          {dataQ.isError && (
            <ApiRetryBanner onRetry={dataQ.refetch} isFetching={dataQ.isFetching} className="mb-6">
              {t('world.indicator.dataLoadError')}
            </ApiRetryBanner>
          )}

          <WorldChartSection
            code={code}
            indicator={chartIndicator}
            modeMeta={modeMeta}
            dataPoints={points}
            forecastData={forecastPoints}
            forecastEnabled={forecastAvailable}
            showForecast={showForecast}
            onToggleForecast={() => setShowForecast((current) => !current)}
            chartLoading={dataQ.isLoading}
            emptyHint={empty ? t('world.indicator.emptyMode') : undefined}
            onFullData={setFullChartData}
            onDownloadCsv={handleDownloadCSV}
            onDownloadExcel={handleDownloadExcel}
            frequency={activeFreq}
            aggregated={aggregated}
            unit={displayUnit}
            country={country}
            conceptSlug={indicator.concept_slug}
            comparisonPeers={metaQ.data.peers || []}
          />

          <div className="mb-12 grid grid-cols-1 gap-8 lg:grid-cols-3">
            <IndicatorMethodologyPanel
              indicator={methodologyIndicator}
              content={methodologyContent}
            />
            <div className="rounded-[1.5rem] border border-border-subtle bg-obsidian-light p-5 sm:rounded-[2rem] sm:p-8 lg:col-span-2">
              <h3 className="mb-4 text-xs font-mono uppercase tracking-[0.2em] text-text-secondary">
                {t('world.indicator.aboutSeries')}
              </h3>
              <dl className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">{t('world.indicator.field.freq')}</dt>
                  <dd className="font-mono text-text-primary">
                    {freqLabel}
                  </dd>
                </div>
                <div>
                  <dt className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">{t('world.indicator.field.unit')}</dt>
                  <dd className="font-mono text-text-primary">{displayUnit || '—'}</dd>
                </div>
                <div>
                  <dt className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">{t('world.indicator.field.history')}</dt>
                  <dd className="font-mono text-text-primary">
                    {indicator.history_start && indicator.history_end
                      ? `${formatDate(indicator.history_start, 'annual', locale)}–${formatDate(indicator.history_end, 'annual', locale)}`
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">{t('world.indicator.field.points')}</dt>
                  <dd className="font-mono text-text-primary">
                    {dataQ.data?.count ?? indicator.points_count ?? '—'}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">{t('common.source')}</dt>
                  <dd className="text-[13px] leading-5 text-text-secondary">
                    {sourceLabel}
                  </dd>
                </div>
                {showOriginalTitle && (
                  <div className="sm:col-span-2">
                    <dt className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">
                      {originalTitleLabel}
                    </dt>
                    <dd className="text-[13px] leading-5 text-text-secondary">
                      {originalTitle}
                    </dd>
                  </div>
                )}
              </dl>
              <div className="mt-6 flex flex-wrap gap-2 border-t border-border-subtle pt-4">
                <Link
                  to={countryPath(slug)}
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-champagne hover:text-champagne"
                >
                  {t('world.indicator.allOfCountry', { country: countryName || country?.name || '' })}
                  <ArrowUpRight size={12} />
                </Link>
                <Link
                  to="/world"
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-champagne hover:text-champagne"
                >
                  {t('world.indicator.allCountries')}
                  <ArrowUpRight size={12} />
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
