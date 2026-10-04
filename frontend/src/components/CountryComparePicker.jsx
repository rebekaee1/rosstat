import { useState } from 'react';
import { Link } from 'react-router-dom';
import { GitCompare, X, Search, Check } from 'lucide-react';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchCountries } from '../lib/worldCompareSearch';
import { useT } from '../i18n';
import { MAX_COMPARISONS, COMPARISON_COLORS } from '../lib/useCountryComparison';
import Button from './Button';
import Chip from './Chip';
import Spinner from './Spinner';

export function CountryComparePicker({
  options,
  selectedIds,
  onToggle,
  onOpen,
}) {
  const t = useT();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const selected = new Set(selectedIds);
  const filtered = filterSearchCountries(options, query);
  useSearchTracking('world-chart-countries', open ? query : '', filtered.length);
  return (
    <div className="relative min-w-0 flex-1">
      <Search size={14} className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-text-tertiary" />
      <input
        type="search"
        value={query}
        onFocus={() => {
          setOpen(true);
          onOpen?.();
        }}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          onOpen?.();
        }}
        placeholder={selectedIds.length ? t('world.chart.addCountry') : t('world.findCountry')}
        aria-label={t('world.chart.searchCompareAria')}
        className="w-full rounded-xl border border-border-subtle bg-obsidian-light py-2.5 pl-9 pr-3 text-xs text-text-primary pointer-coarse:min-h-11 outline-none transition-colors placeholder:text-text-tertiary focus:border-border-champagne"
      />
      {open && (
        <div className="fe-dialog-panel absolute left-0 right-0 top-full z-40 mt-2 max-h-64 overflow-y-auto rounded-xl border border-border-subtle bg-surface p-1.5 shadow-2xl">
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
                className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-xs text-text-secondary transition-colors hover:bg-obsidian-light hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-35"
              >
                <span className="truncate">{option.country_name}</span>
                <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${checked ? 'border-champagne-ink bg-champagne-ink text-white' : 'border-border-subtle'}`}>
                  {checked && <Check size={12} />}
                </span>
              </button>
            );
          }) : (
            <div className="px-3 py-5 text-center text-xs text-text-tertiary">{t('world.chart.countryNotFound')}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CountryComparePanel({
  pickerOptions,
  activeComparisonIds,
  selectedComparisons,
  comparisonQueries,
  comparisonScale,
  onToggle,
  onOpen,
  onScale,
  conceptSlug,
  countrySlug,
  compareCodes,
  rebased,
  loadedComparisonSeries,
  hint,
}) {
  const t = useT();
  if (!pickerOptions.length) return null;
  return (
    <div className="mb-4 rounded-2xl border border-border-subtle bg-surface p-4 shadow-[0_10px_30px_rgba(35,30,16,0.04)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="min-w-0 sm:min-w-[11rem]">
          <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
            <GitCompare size={14} className="text-champagne" />
            {t('world.chart.compare')}
          </div>
          <div className="mt-1 text-xs text-text-tertiary">
            {t('world.chart.compareLimit', { n: MAX_COMPARISONS })}
          </div>
        </div>
        <CountryComparePicker
          options={pickerOptions}
          selectedIds={activeComparisonIds}
          onToggle={onToggle}
          onOpen={onOpen}
        />
        {activeComparisonIds.length > 0 && (
          <div className="inline-flex shrink-0 gap-1" role="group" aria-label={t('world.chart.compare')}>
            {[
              ['values', t('world.chart.scaleValues')],
              ['index', t('world.chart.scaleIndex')],
            ].map(([id, label]) => (
              <Chip
                key={id}
                active={comparisonScale === id}
                onClick={() => onScale(id)}
              >
                {label}
              </Chip>
            ))}
          </div>
        )}
      </div>

      {hint && (
        <p className="mt-3 text-xs leading-4 text-text-tertiary">
          {hint}
        </p>
      )}

      {activeComparisonIds.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3">
          {selectedComparisons.map((item, index) => (
            <Button
              key={item.id}
              variant="secondary"
              size="sm"
              onClick={() => onToggle(item.id)}
              className="max-w-full gap-2 rounded-full! px-2.5 text-text-secondary"
              title={t('world.chart.removeSeries')}
            >
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: COMPARISON_COLORS[index] }} aria-hidden="true" />
              <span className="min-w-0 truncate">{item.label}</span>
              {comparisonQueries[index]?.isLoading && <Spinner size={11} label={t('common.loading')} />}
              {comparisonQueries[index]?.isError && <span className="text-negative">{t('common.noData')}</span>}
              <X size={12} className="shrink-0 text-text-tertiary" aria-hidden="true" />
            </Button>
          ))}
          {conceptSlug === 'hicp-index' && compareCodes.length > 0 ? (
            <Link to="/world/rating/hicp-index" className="ml-auto inline-flex min-h-8 items-center text-xs text-champagne-ink hover:underline pointer-coarse:min-h-11">
              {t('world.chart.compareInflationRates')}
            </Link>
          ) : conceptSlug && compareCodes.length > 0 && (
            <Link
              to={`/compare?codes=${encodeURIComponent(
                [`w:${countrySlug}:${conceptSlug}`, ...compareCodes].join(','),
              )}`}
              className="ml-auto inline-flex min-h-8 items-center text-xs text-champagne-ink hover:underline pointer-coarse:min-h-11"
            >
              {t('world.chart.openFullCompare')}
            </Link>
          )}
        </div>
      )}

      {rebased && (
        <p className="mt-3 text-xs leading-4 text-text-tertiary">
          {t('world.chart.rebaseNote', { date: rebased.startDate })}
        </p>
      )}
      {comparisonScale === 'index' && loadedComparisonSeries.length > 0 && !rebased && (
        <p className="mt-3 text-xs text-text-secondary">
          {t('world.chart.rebaseFail')}
        </p>
      )}
    </div>
  );
}
