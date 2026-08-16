import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import {
  Terminal, Download, Lock, Image as ImageIcon, GitCompare, X, Search, Check, HelpCircle,
} from 'lucide-react';
import { resolveDateFormat, cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import { ChartSkeleton } from './Skeleton';
import { worldChartTitle, worldRangePreset } from '../lib/worldViewModes';
import {
  fetchWorldAverageSeries,
  fetchWorldIndicatorMode,
  useWorldCompareCatalog,
} from '../lib/worldApi';
import { rebaseWorldComparison } from '../lib/worldComparison';

const AVERAGE_CONCEPTS = new Set(['hicp-index', 'unemployment-rate', 'budget-balance-gdp']);
const COMPARISON_COLORS = ['#397C8C', '#7856A8', '#C86B5B', '#4D8A64'];
const MAX_COMPARISONS = COMPARISON_COLORS.length;

function isAbsoluteLevel(unit, modeMeta) {
  const normalized = (unit || '').toLowerCase();
  return modeMeta?.type === 'level'
    && !normalized.includes('%')
    && !normalized.includes('индекс')
    && !normalized.includes('п.п.');
}

function ComparisonPicker({
  options,
  selectedIds,
  onToggle,
  onOpen,
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const selected = new Set(selectedIds);
  const filtered = options.filter((option) => (
    !query.trim()
    || option.country_name.toLowerCase().includes(query.trim().toLowerCase())
  ));
  return (
    <div className="relative min-w-0 flex-1">
      <Search size={14} className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-text-tertiary" />
      <input
        type="search"
        value={query}
        onFocus={() => {
          setOpen(true);
          onOpen();
        }}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          onOpen();
        }}
        placeholder={selectedIds.length ? 'Добавить ещё страну…' : 'Найти страну…'}
        aria-label="Поиск страны для сравнения"
        className="w-full rounded-xl border border-border-subtle bg-obsidian-light py-2.5 pl-9 pr-3 text-xs text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-border-champagne"
      />
      {open && (
        <div className="absolute left-0 right-0 top-full z-40 mt-2 max-h-64 overflow-y-auto rounded-xl border border-border-subtle bg-white p-1.5 shadow-2xl">
          {filtered.length ? filtered.map((option) => {
            const checked = selected.has(option.code);
            const disabled = !checked && selectedIds.length >= MAX_COMPARISONS;
            return (
              <button
                key={option.code}
                type="button"
                disabled={disabled}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onToggle(option.code);
                  setQuery('');
                }}
                className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-xs text-text-secondary transition-colors hover:bg-obsidian-light hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-35"
              >
                <span className="truncate">{option.country_name}</span>
                <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${checked ? 'border-champagne bg-champagne text-white' : 'border-border-subtle'}`}>
                  {checked && <Check size={12} />}
                </span>
              </button>
            );
          }) : (
            <div className="px-3 py-5 text-center text-xs text-text-tertiary">Страна не найдена</div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Секция графика мировой карточки.
 * Переиспользует IndicatorChart; прогноз — только после проверки на
 * исторических данных и по явному переключателю пользователя.
 */
function DownloadButton({ label, onDownload, blocked, hint }) {
  const handleClick = () => {
    if (blocked) {
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    onDownload?.();
  };
  const tooltip = blocked ? 'Скачивание данных — после бесплатной регистрации' : hint;
  return (
    <div className="relative group/dl">
      <button
        type="button"
        onClick={handleClick}
        aria-disabled={blocked}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          blocked
            ? 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer'
            : 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30',
        )}
        title={blocked ? 'Скачивание данных — после бесплатной регистрации' : `Скачать ${label}`}
      >
        {blocked ? <Lock className="w-3.5 h-3.5" /> : <Download className="w-3.5 h-3.5" />}
        {label}
      </button>
      {tooltip && (
        <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-[11px] normal-case tracking-normal text-text-secondary whitespace-nowrap opacity-0 group-hover/dl:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
          {tooltip}
        </div>
      )}
    </div>
  );
}

function ImageButton({ onDownload, authed }) {
  const tooltip = authed
    ? 'Скачать график картинкой (PNG)'
    : 'Скачивание графика — после бесплатной регистрации';
  return (
    <div className="relative group/img" data-no-export="true">
      <button
        type="button"
        onClick={onDownload}
        aria-disabled={!authed}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          authed
            ? 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30'
            : 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer',
        )}
        title={tooltip}
      >
        {authed ? <ImageIcon className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
        PNG
      </button>
      <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-[11px] normal-case tracking-normal text-text-secondary whitespace-nowrap opacity-0 group-hover/img:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
        {tooltip}
      </div>
    </div>
  );
}

export default function WorldChartSection({
  code,
  indicator,
  modeMeta,
  dataPoints,
  forecastData = [],
  forecastEnabled = false,
  showForecast = false,
  onToggleForecast,
  chartLoading,
  emptyHint,
  onFullData,
  onDownloadCsv,
  onDownloadExcel,
  frequency,
  aggregated = false,
  unit: unitOverride,
  country,
  conceptSlug,
  comparisonPeers = [],
}) {
  const { blocked: downloadBlocked, isAuthed: downloadAuthed } = useDownloadAccess();
  const chartRef = useRef(null);
  const unit = unitOverride || modeMeta?.unit || indicator?.unit || '';
  const activeFreq = frequency || modeMeta?.freq || indicator?.frequency;
  const title = worldChartTitle(indicator, modeMeta, activeFreq);
  const [comparisonPickerActive, setComparisonPickerActive] = useState(false);
  // Meta карточки уже несёт строго совместимых peers. Общий каталог нужен
  // только старым карточкам без peers и загружается по первому намерению сравнить.
  const compareCatalog = useWorldCompareCatalog({
    enabled: comparisonPeers.length === 0 && comparisonPickerActive,
  });
  const [comparisonIds, setComparisonIds] = useState([]);
  const [comparisonScale, setComparisonScale] = useState('values');
  const comparisonOptions = useMemo(() => {
    const strictPeers = (comparisonPeers || []).map((item) => ({
      ...item,
      code: `peer:${item.country_slug}:${item.indicator_code}`,
    }));
    if (strictPeers.length) {
      return strictPeers.sort((a, b) => a.country_name.localeCompare(b.country_name, 'ru'));
    }
    return (compareCatalog.data?.items || [])
      .filter((item) => item.concept_slug === conceptSlug && item.country_slug !== country?.slug)
      .sort((a, b) => a.country_name.localeCompare(b.country_name, 'ru'));
  }, [comparisonPeers, compareCatalog.data, conceptSlug, country?.slug]);
  const pickerOptions = useMemo(() => {
    const result = [...comparisonOptions];
    if (AVERAGE_CONCEPTS.has(conceptSlug)) {
      result.unshift({
        code: 'average',
        country_name: conceptSlug === 'hicp-index'
          ? 'Медиана по странам с данными'
          : 'Среднее по странам с данными',
      });
    }
    return result;
  }, [comparisonOptions, conceptSlug]);
  const activeComparisonIds = comparisonIds.filter((id) => (
    pickerOptions.some((option) => option.code === id)
  ));
  const comparisonQueries = useQueries({
    queries: activeComparisonIds.map((id) => ({
      queryKey: ['world-card-comparison', id, conceptSlug, modeMeta?.id],
      queryFn: async ({ signal }) => {
        if (id === 'average') {
          return fetchWorldAverageSeries(conceptSlug, modeMeta?.id, { signal });
        }
        const option = comparisonOptions.find((item) => item.code === id);
        if (!option) return null;
        return fetchWorldIndicatorMode(
          option.country_slug,
          option.indicator_code,
          modeMeta?.id,
          { signal },
        );
      },
      enabled: !!id && !!modeMeta?.id,
      staleTime: 10 * 60 * 1000,
    })),
  });
  const comparisonIdsKey = activeComparisonIds.join('|');
  const queryData = [
    comparisonQueries[0]?.data,
    comparisonQueries[1]?.data,
    comparisonQueries[2]?.data,
    comparisonQueries[3]?.data,
  ];
  const selectedComparisons = useMemo(
    () => activeComparisonIds.map((id, index) => {
      const option = pickerOptions.find((item) => item.code === id);
      const payload = queryData[index];
      return {
        id,
        option,
        label: payload?.meta?.country_name || option?.country_name || 'Сравнение',
        color: COMPARISON_COLORS[index],
        data: payload?.points || payload?.data || [],
      };
    }),
    // Query payload objects are stable in TanStack Query; fixed slots keep the
    // resulting series stable and prevent chart → onFullData render loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [comparisonIdsKey, pickerOptions, queryData[0], queryData[1], queryData[2], queryData[3]],
  );
  const loadedComparisonSeries = useMemo(
    () => selectedComparisons.filter((item) => item.data.length > 0),
    [selectedComparisons],
  );
  const rebased = useMemo(
    () => (comparisonScale === 'index'
      ? rebaseWorldComparison(dataPoints || [], loadedComparisonSeries)
      : null),
    [comparisonScale, dataPoints, loadedComparisonSeries],
  );
  const displayedDataPoints = rebased?.base || dataPoints;
  const displayedComparisonSeries = rebased?.series || loadedComparisonSeries;
  const displayedUnit = rebased ? 'индекс, общая база = 100' : unit;
  const displayedTitle = rebased ? `${title} — динамика, общая база = 100` : title;
  const effectiveShowForecast = forecastEnabled && showForecast && !rebased;
  const toggleComparison = (id) => {
    if (
      !activeComparisonIds.includes(id)
      && activeComparisonIds.length === 0
      && isAbsoluteLevel(unit, modeMeta)
    ) {
      setComparisonScale('index');
    }
    setComparisonIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= MAX_COMPARISONS) return current;
      return [...current, id];
    });
  };
  const compareCodes = activeComparisonIds
    .filter((id) => id !== 'average')
    .map((id) => pickerOptions.find((item) => item.code === id))
    .filter((item) => item?.country_slug && conceptSlug)
    .map((item) => `w:${item.country_slug}:${conceptSlug}`);

  const handleDownloadImage = async () => {
    if (!downloadAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: code, world: true });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${code}_${modeMeta?.id || 'level'}.png`,
      watermark: false,
    }).catch(() => false);
    if (ok) {
      track(events.CHART_IMAGE_DOWNLOAD, {
        indicator: code,
        mode: modeMeta?.id,
        world: true,
      });
    }
  };

  return (
    <section data-block="chart" className="mb-10 sm:mb-16">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3 sm:mb-6 sm:pb-4">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <Terminal className="h-4 w-4 shrink-0 text-champagne" />
          <span className="min-w-0 break-words text-xs leading-snug text-text-secondary line-clamp-3 sm:font-mono sm:text-[11px] sm:uppercase sm:tracking-widest sm:text-text-tertiary sm:line-clamp-2">
            {title}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3" data-no-export="true">
          <div className="relative group/help">
            <Link
              to="/methodology"
              aria-label="Как рассчитывается прогноз"
              onClick={() => track(events.METHODOLOGY_CLICK, {
                indicator: code,
                indicatorCategory: indicator?.category,
                world: true,
              })}
              className="text-text-tertiary transition-colors hover:text-champagne"
            >
              <HelpCircle className="h-4 w-4" />
            </Link>
            <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 whitespace-nowrap rounded-xl border border-border-subtle bg-obsidian px-3 py-2 text-xs text-text-secondary opacity-0 shadow-xl transition-opacity group-hover/help:opacity-100">
              Хотите узнать, как рассчитывается прогноз?
            </div>
          </div>
          <div className="relative group/forecast">
            <label className={cn(
              'flex select-none items-center gap-2.5',
              forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-45',
            )}>
              <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
                Прогноз
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={effectiveShowForecast}
                aria-label="Показать прогноз"
                disabled={!forecastEnabled}
                onClick={onToggleForecast}
                className={cn(
                  'relative h-5 w-10 rounded-full border transition-colors',
                  effectiveShowForecast
                    ? 'border-champagne/30 bg-champagne/30'
                    : 'border-border-subtle bg-obsidian-lighter',
                )}
              >
                <span className={cn(
                  'absolute left-[2px] top-[2px] h-3.5 w-3.5 rounded-full transition-transform',
                  effectiveShowForecast
                    ? 'translate-x-5 bg-champagne'
                    : 'translate-x-0 bg-text-tertiary',
                )}
                />
              </button>
            </label>
            {!forecastEnabled && (
              <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-border-subtle bg-obsidian px-3 py-2 text-[11px] leading-4 text-text-secondary opacity-0 shadow-xl transition-opacity group-hover/forecast:opacity-100">
                Прогноз публикуется только если модель проходит проверку на исторических данных. Для этого ряда — нет.
              </div>
            )}
          </div>
          <DownloadButton label="CSV" onDownload={onDownloadCsv} blocked={downloadBlocked} />
          <DownloadButton label="Excel" onDownload={onDownloadExcel} blocked={downloadBlocked} />
          <ImageButton onDownload={handleDownloadImage} authed={downloadAuthed} />
        </div>
      </div>

      {pickerOptions.length > 0 && (
        <div className="mb-4 rounded-2xl border border-border-subtle bg-surface p-4 shadow-[0_10px_30px_rgba(35,30,16,0.04)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="min-w-0 sm:min-w-[11rem]">
              <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
                <GitCompare size={14} className="text-champagne" />
                Сравнение стран
              </div>
              <div className="mt-1 text-[10px] text-text-tertiary">
                До {MAX_COMPARISONS} сопоставимых рядов
              </div>
            </div>
            <ComparisonPicker
              options={pickerOptions}
              selectedIds={activeComparisonIds}
              onToggle={toggleComparison}
                  onOpen={() => setComparisonPickerActive(true)}
            />
            {activeComparisonIds.length > 0 && (
              <div className="inline-flex shrink-0 rounded-lg bg-obsidian-light p-0.5">
                {[
                  ['values', 'Значения'],
                  ['index', 'Динамика (=100)'],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setComparisonScale(id)}
                    className={`rounded-md px-2.5 py-1.5 text-[10px] transition-colors ${comparisonScale === id ? 'bg-white text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-primary'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {activeComparisonIds.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3">
              {selectedComparisons.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => toggleComparison(item.id)}
                  className="inline-flex max-w-full items-center gap-2 rounded-full border border-border-subtle bg-obsidian-light px-2.5 py-1.5 text-[11px] text-text-secondary transition-colors hover:border-border-champagne hover:text-text-primary"
                  title="Убрать ряд"
                >
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: COMPARISON_COLORS[index] }} />
                  <span className="truncate">{item.label}</span>
                  {comparisonQueries[index]?.isLoading && <span className="text-text-tertiary">…</span>}
                  {comparisonQueries[index]?.isError && <span className="text-danger">нет данных</span>}
                  <X size={11} className="shrink-0 text-text-tertiary" />
                </button>
              ))}
              {conceptSlug && compareCodes.length > 0 && (
                <Link
                  to={`/compare?codes=${encodeURIComponent(
                    [`w:${country.slug}:${conceptSlug}`, ...compareCodes].join(','),
                  )}`}
                  className="ml-auto text-xs text-champagne hover:underline"
                >
                  Открыть полное сравнение
                </Link>
              )}
            </div>
          )}

          {rebased && (
            <p className="mt-3 text-[10px] leading-4 text-text-tertiary">
              Общая база 100 на {rebased.startDate}: сравнивается динамика, а не абсолютный размер показателя.
            </p>
          )}
          {comparisonScale === 'index' && loadedComparisonSeries.length > 0 && !rebased && (
            <p className="mt-3 text-[10px] text-text-secondary">
              Общую базу нельзя построить: у рядов нет общей положительной даты.
            </p>
          )}
        </div>
      )}

      {comparisonQueries.some((query) => query.isError) && (
        <p className="mb-3 text-[12px] text-text-secondary">
          Для части выбранных стран этот режим недоступен. Остальные ряды продолжают отображаться.
        </p>
      )}

      {aggregated && (
        <p className="mb-3 text-[12px] text-text-secondary">
          Ряд получен пересчётом на сайте, а не отдельной публикацией
          {' '}{indicator?.source || 'официального источника'}
          с этой частотой.
        </p>
      )}

      {!forecastEnabled && (
        <p className="mb-3 text-[12px] leading-5 text-text-secondary">
          Прогноз публикуется только если модель проходит проверку на исторических данных.
          {' '}Для этого ряда — нет.
          {' '}
          <Link to="/methodology" className="text-champagne hover:underline">
            Методология
          </Link>
        </p>
      )}

      {showForecast && forecastEnabled && !rebased && (
        <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-tertiary">
          <span>
            Прогноз начинается после последнего официального наблюдения.
          </span>
          <Link to="/methodology" className="text-champagne hover:underline">
            Методология
          </Link>
        </div>
      )}
      {showForecast && forecastEnabled && forecastData.length === 0 && (
        <p className="mb-3 text-[11px] text-text-tertiary">
          Для выбранного преобразования нет полного прогнозного периода.
        </p>
      )}
      {showForecast && rebased && (
        <p className="mb-3 text-[11px] text-text-tertiary">
          Прогноз скрыт при сравнении в общей базе 100.
        </p>
      )}

      {chartLoading ? (
        <ChartSkeleton />
      ) : (
        <div ref={chartRef} className="relative overflow-hidden rounded-[2rem]">
          <IndicatorChart
            key={`${code}-${modeMeta?.id}-${activeFreq}`}
            mode="cpi"
            cpiData={displayedDataPoints || []}
            forecastData={forecastData}
            showForecast={effectiveShowForecast}
            onFullData={onFullData}
            cpiChartTitle={displayedTitle}
            levelTooltipLabel={modeMeta?.label || modeMeta?.group || 'Значение'}
            forecastTooltipLabel="Прогноз"
            emptyHint={emptyHint}
            dateFormat={resolveDateFormat({ frequency: activeFreq, chartMode: 'cpi' })}
            unit={displayedUnit}
            rangePreset={worldRangePreset(activeFreq)}
            chartMode={modeMeta?.id || 'level'}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
            referenceLineY={unit === '%' || unit === 'п.п.' ? 0 : null}
            numericTooltipOnly
            actualSeriesLabel={country?.name}
            comparisonSeries={displayedComparisonSeries}
          />
        </div>
      )}
    </section>
  );
}
