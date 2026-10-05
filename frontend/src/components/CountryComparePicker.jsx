import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { GitCompare, Globe2, X, Search, Check } from 'lucide-react';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchCountries, suggestedCompareOptions } from '../lib/worldCompareSearch';
import { useLocale, useT } from '../i18n';
import { MAX_COMPARISONS, COMPARISON_COLORS } from '../lib/useCountryComparison';
import { orderCountryOptions } from '../lib/countryOrder';
import Button from './Button';
import Chip from './Chip';
import Spinner from './Spinner';
import CountryFlag from './CountryFlag';
import '../styles/w6-g.css';

/** После выбора страны график должен быть на виду: подкручиваем к нему, если он ушёл за край экрана. */
function scrollChartIntoView() {
  const chart = document.getElementById('chart');
  if (!chart?.scrollIntoView) return;
  const top = chart.getBoundingClientRect().top;
  if (top >= 0 && top < window.innerHeight * 0.5) return;
  const reduce = typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  chart.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
}

export function CountryComparePicker({
  options,
  selectedIds,
  onToggle,
  onOpen,
}) {
  const t = useT();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);
  const selected = new Set(selectedIds);
  const filtered = query.trim() ? filterSearchCountries(options, query) : orderCountryOptions(options);
  useSearchTracking('world-chart-countries', open ? query : '', filtered.length);
  return (
    <div className="relative min-w-0 flex-1">
      <Search size={14} className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-text-tertiary" />
      <input
        ref={inputRef}
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
        className="w-full rounded-xl border border-border-subtle bg-surface py-2.5 pl-9 pr-3 text-sm text-text-primary pointer-coarse:min-h-11 pointer-coarse:text-base outline-none transition-colors placeholder:text-text-tertiary focus:border-border-champagne"
      />
      {open && (
        <div className="fe-dialog-panel fe-w6g-solid-panel absolute left-0 right-0 top-full z-[60] mt-2 max-h-64 overflow-y-auto rounded-xl border border-border-subtle bg-surface p-1.5 shadow-2xl">
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
                  // Выбор сделан: список закрывается, клавиатура уходит, график остаётся на виду.
                  setOpen(false);
                  inputRef.current?.blur();
                  window.setTimeout(scrollChartIntoView, 60);
                }}
                className="flex min-h-11 w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:bg-obsidian-light hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-35"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  {option.country_code
                    ? <CountryFlag code={option.country_code} />
                    : <Globe2 size={16} className="shrink-0 text-text-tertiary" aria-hidden="true" />}
                  <span className="truncate">{option.country_name}</span>
                </span>
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

/**
 * Страны разного размера на одной оси: меньшая линия кажется ровной, хотя меняется.
 * Плашка стоит НАД графиком и одним нажатием включает проценты.
 */
export function ScaleNudge({ show, onScale }) {
  const t = useT();
  if (!show) return null;
  return (
    <div className="fe-w6g-scale-nudge mb-3" role="status" data-testid="compare-scale-nudge" data-no-export="true">
      <p>{t('w6g.chart.scaleNudge')}</p>
      <Button variant="primary" onClick={() => onScale('index')}>
        {t('w6g.chart.showPercent')}
      </Button>
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
  baseLabel = '',
  baseColor = '#202A3C',
  suggestPercent = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const [searchOpen, setSearchOpen] = useState(false);
  if (!pickerOptions.length) return null;
  const quick = suggestedCompareOptions(pickerOptions, locale)
    .filter((option) => !activeComparisonIds.includes(option.code));
  const atLimit = activeComparisonIds.length >= MAX_COMPARISONS;
  return (
    <div className="fe-compare-panel mb-4 rounded-3xl border border-border-subtle bg-surface p-4 shadow-[0_10px_30px_rgba(35,30,16,0.04)]">
      <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <GitCompare size={15} className="text-champagne" aria-hidden="true" />
        {t('world.chart.compare')}
      </div>

      {/* Одно нажатие: популярные страны чипами, поиск остальных по кнопке. */}
      {!atLimit && (
        <div className="fe-compare-quick mt-3" role="group" aria-label={t('w6e.compare.with')}>
          <span className="fe-compare-quick__label">{t('w6e.compare.with')}</span>
          {quick.map((option) => (
            <Chip
              key={option.code}
              active={false}
              className="fe-chip--country"
              onClick={() => onToggle(option.code)}
            >
              {option.country_code ? <CountryFlag code={option.country_code} /> : null}
              <span className="min-w-0 truncate">{option.country_name}</span>
            </Chip>
          ))}
          <Chip
            active={searchOpen}
            className="fe-chip--more"
            aria-expanded={searchOpen}
            onClick={() => {
              setSearchOpen((value) => !value);
              onOpen?.();
            }}
          >
            {t('w6e.compare.others')}
          </Chip>
        </div>
      )}

      {searchOpen && !atLimit && (
        <div className="mt-3">
          <CountryComparePicker
            options={pickerOptions}
            selectedIds={activeComparisonIds}
            onToggle={onToggle}
            onOpen={onOpen}
          />
        </div>
      )}


      {activeComparisonIds.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3">
          {baseLabel && (
            <span className="fe-compare-base" title={baseLabel}>
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: baseColor }} aria-hidden="true" />
              <span className="min-w-0 truncate">{baseLabel}</span>
            </span>
          )}
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
          <div className="inline-flex shrink-0 gap-1" role="group" aria-label={t('world.chart.compare')}>
            {[
              ['values', t('world.chart.scaleValues'), undefined],
              ['index', t('world.chart.scaleIndex'), t('w6e.compare.scaleHint')],
            ].map(([id, label, title]) => (
              <Chip
                key={id}
                active={comparisonScale === id}
                title={title}
                onClick={() => onScale(id)}
              >
                {label}
              </Chip>
            ))}
          </div>
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

      {suggestPercent && comparisonScale === 'values' && (
        <div className="fe-compare-suggest" role="note">
          <span>{t('w6e.compare.suggest')}</span>
          <Button variant="secondary" size="sm" onClick={() => onScale('index')}>
            {t('w6e.compare.suggestCta')}
          </Button>
        </div>
      )}

      {hint && (
        <p className="mt-3 text-xs leading-4 text-text-tertiary">
          {hint}
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
