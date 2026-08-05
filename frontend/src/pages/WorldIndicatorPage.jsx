// Карточка мирового индикатора: /world/{slug}/{code}?mode=
// Двухуровневый режим (тип × частота), variants, без прогнозов.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ChevronRight, ArrowUpRight } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
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
import { SkeletonBox } from '../components/Skeleton';

const FREQ_RU = {
  daily: 'Ежедневно',
  weekly: 'Еженедельно',
  monthly: 'Ежемесячно',
  quarterly: 'Ежеквартально',
  annual: 'Ежегодно',
};

export default function WorldIndicatorPage() {
  const { slug, code } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlMode = searchParams.get('mode');

  const metaQ = useWorldIndicator(slug, code);
  const countryQ = useWorldCountry(slug);

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
  const apiIsComposite = useMemo(
    () => Array.isArray(metaQ.data?.modes)
      && metaQ.data.modes.some((m) => m.type && m.freq),
    [metaQ.data],
  );

  const dataCode = useMemo(() => {
    if (apiIsComposite) return metaQ.data?.primary_code || code;
    if (!modeParsed) return code;
    const sib = frequencies.find((f) => f.freq === modeParsed.freq && f.code);
    return sib?.code || code;
  }, [apiIsComposite, metaQ.data?.primary_code, code, modeParsed, frequencies]);

  const dataModeParam = apiIsComposite
    ? activeMode
    : worldModeToLegacyDataToken(activeMode);

  const dataQ = useWorldIndicatorData(slug, code, dataModeParam, {
    requestCode: dataCode,
  });

  const [fullChartData, setFullChartData] = useState([]);

  // Канон URL: primary_code + составной ?mode=
  useEffect(() => {
    const primary = metaQ.data?.primary_code;
    if (primary && primary !== code) {
      const mode = activeMode || normalizeWorldModeToken(
        urlMode,
        metaQ.data.indicator?.frequency || 'monthly',
      );
      navigate(`/world/${slug}/${primary}?mode=${encodeURIComponent(mode)}`, {
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

  const setMode = useCallback((mode) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('mode', mode);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const country = metaQ.data?.country;
  const indicator = metaQ.data?.indicator;
  const displayName = stripFrequencySuffix(indicator?.name || '');
  const notFound = metaQ.isError && metaQ.error?.response?.status === 404;

  const variantGroup = useMemo(
    () => worldVariantsToPickerGroup(metaQ.data?.variants),
    [metaQ.data?.variants],
  );

  const points = dataQ.data?.points || [];
  const empty = !dataQ.isLoading && isEmptySeries(points);
  const last = points.length ? points[points.length - 1] : null;
  const displayUnit = dataQ.data?.unit_ru || dataQ.data?.unit
    || modeMeta?.unit || indicator?.unit || '';
  // Единица рядом с числом — только та её часть, что читается справа от значения:
  // «-14,4 индекс» и «7,3 балл индекса» — безграмотно. Полная единица остаётся
  // в подписи оси, в поле «Единица» и в шапке таблицы.
  const unitBesideValue = dataQ.data?.unit_suffix ?? indicator?.unit_suffix ?? '';
  const activeFreq = dataQ.data?.frequency || modeParsed?.freq || indicator?.frequency;
  const aggregated = Boolean(dataQ.data?.aggregated)
    || (modeMeta && modeMeta.official === false);

  useDocumentMeta(indicator && country ? {
    title: `${displayName} — ${country.name}: график и данные`,
    description:
      `${displayName} (${country.name}): последнее значение ${formatWorldValue(last?.value)}${unitBesideValue ? ` ${unitBesideValue}` : ''}`
      + (last?.date ? ` на ${formatDate(last.date, 'full')}` : '')
      + `. Источник: Евростат.`,
    path: `/world/${slug}/${code}`,
  } : {
    title: notFound ? 'Показатель не найден' : 'Мировая экономика',
    description: 'Макроэкономические показатели стран мира.',
    path: `/world/${slug}/${code}`,
  });

  useEffect(() => {
    if (!indicator || !country) return undefined;
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `${displayName} — ${country.name}`,
      description: indicator.description || `${displayName}, ${country.name}. Источник: Евростат.`,
      creator: { '@type': 'Organization', name: 'Евростат' },
      publisher: { '@type': 'Organization', name: 'Forecast Economy', url: 'https://forecasteconomy.com' },
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'world-dataset-jsonld';
    script.textContent = JSON.stringify(jsonLd);
    document.getElementById('world-dataset-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [indicator, country, displayName]);

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
      source: indicator.source || 'Евростат',
    };
  }, [indicator, displayName]);

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
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4 overflow-hidden" aria-label="Хлебные крошки">
        <Link to="/world" className="hover:text-champagne transition-colors shrink-0">Мировая экономика</Link>
        <ChevronRight size={12} className="shrink-0" />
        {country && (
          <Link to={`/world/${slug}`} className="hover:text-champagne transition-colors shrink-0 truncate max-w-[40%]">
            {country.name}
          </Link>
        )}
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-text-secondary truncate">{displayName || '…'}</span>
      </nav>

      {notFound && (
        <div className="rounded-2xl border border-border-subtle bg-surface p-8 text-center mt-8">
          <h1 className="font-display text-2xl font-bold text-text-primary mb-3">Показатель не найден</h1>
          <p className="text-text-secondary mb-6">
            Такого показателя для этой страны нет. Вернитесь к списку или откройте другой раздел платформы.
          </p>
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            <Link to={`/world/${slug}`} className="px-4 py-2 rounded-xl bg-champagne/10 text-champagne hover:bg-champagne/20 transition-colors">
              К стране
            </Link>
            <Link to="/world" className="px-4 py-2 rounded-xl border border-border-subtle text-text-secondary hover:text-champagne transition-colors">
              Все страны
            </Link>
            <Link to="/" className="px-4 py-2 rounded-xl border border-border-subtle text-text-secondary hover:text-champagne transition-colors">
              Главная
            </Link>
          </div>
        </div>
      )}

      {(metaQ.isError && !notFound) && (
        <ApiRetryBanner onRetry={metaQ.refetch} isFetching={metaQ.isFetching} className="mb-6">
          Не удалось загрузить карточку показателя.
        </ApiRetryBanner>
      )}

      {metaQ.isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-96 max-w-full" />
          <SkeletonBox className="h-14 rounded-xl" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}

      {metaQ.data && indicator && (
        <>
          <header className="mb-6">
            <div className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
              {indicator.category}
            </div>
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 mb-1">
              <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary leading-tight flex-1 min-w-[12rem]">
                {displayName}
              </h1>
              <span className="text-sm text-text-secondary shrink-0 pt-1 sm:pt-1.5">
                {country?.name}
              </span>
            </div>

            <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {last ? (
                <>
                  <span className="font-mono text-3xl font-bold text-text-primary">
                    {formatWorldValue(last.value, chartValueDigits(displayUnit))}
                  </span>
                  {unitBesideValue ? (
                    <span className="text-sm text-text-secondary">{unitBesideValue}</span>
                  ) : null}
                  <span className="font-mono text-sm text-text-tertiary">
                    {formatDate(last.date, dateFormat)}
                  </span>
                </>
              ) : dataQ.isLoading ? (
                <SkeletonBox className="h-9 w-40" />
              ) : (
                <span className="text-sm text-text-tertiary">Нет данных для выбранного режима</span>
              )}
            </div>
            {metaQ.data._fromMock && (
              <p className="mt-2 text-[12px] text-text-tertiary font-mono">
                Демо-данные (API ещё не подключён)
              </p>
            )}
          </header>

          {variantGroup && (
            <VariantGroupPicker
              group={variantGroup}
              currentCode={code}
              basePath={`/world/${slug}`}
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
              Не удалось загрузить ряд данных. Попробуйте другой режим или повторите запрос.
            </ApiRetryBanner>
          )}

          <WorldChartSection
            code={code}
            indicator={chartIndicator}
            modeMeta={modeMeta}
            dataPoints={points}
            chartLoading={dataQ.isLoading}
            emptyHint={empty ? 'Для этого режима пока нет точек. Выберите другой режим или вернитесь позже.' : undefined}
            onFullData={setFullChartData}
            onDownloadCsv={handleDownloadCSV}
            onDownloadExcel={handleDownloadExcel}
            frequency={activeFreq}
            aggregated={aggregated}
            unit={displayUnit}
          />

          <div className="grid lg:grid-cols-3 gap-6 mb-12">
            <IndicatorMethodologyPanel
              indicator={methodologyIndicator}
              content={methodologyContent}
            />
            <div className="lg:col-span-2 rounded-[2rem] bg-obsidian-light border border-border-subtle p-8">
              <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-text-secondary mb-4">
                О ряде
              </h3>
              <dl className="grid sm:grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-text-tertiary text-[11px] uppercase tracking-wide mb-1">Частота</dt>
                  <dd className="text-text-primary font-mono">
                    {FREQ_RU[activeFreq] || activeFreq || '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-text-tertiary text-[11px] uppercase tracking-wide mb-1">Единица</dt>
                  <dd className="text-text-primary font-mono">{displayUnit || '—'}</dd>
                </div>
                <div>
                  <dt className="text-text-tertiary text-[11px] uppercase tracking-wide mb-1">История</dt>
                  <dd className="text-text-primary font-mono">
                    {indicator.history_start && indicator.history_end
                      ? `${formatDate(indicator.history_start, 'annual')}–${formatDate(indicator.history_end, 'annual')}`
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-text-tertiary text-[11px] uppercase tracking-wide mb-1">Точек</dt>
                  <dd className="text-text-primary font-mono">
                    {dataQ.data?.count ?? indicator.points_count ?? '—'}
                  </dd>
                </div>
              </dl>
              <div className="mt-6 pt-4 border-t border-border-subtle flex flex-wrap gap-2">
                <Link
                  to={`/world/${slug}`}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-[13px] text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors"
                >
                  Все показатели {country?.name}
                  <ArrowUpRight size={12} />
                </Link>
                <Link
                  to="/world"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-[13px] text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors"
                >
                  Другие страны
                  <ArrowUpRight size={12} />
                </Link>
              </div>
            </div>
          </div>

          <section>
            <DataTable
              key={`${code}-${activeMode}`}
              data={points}
              title={`Исторические данные — ${displayName}`}
              dateFormat={dateFormat}
              unit={displayUnit}
              valueDigits={chartValueDigits(displayUnit)}
            />
          </section>
        </>
      )}
    </div>
  );
}
