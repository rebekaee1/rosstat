import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Globe2, Landmark, Search, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { RUSSIA_SLUG } from '../lib/inflationCalc';
import { useT } from '../i18n';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchCountries } from '../lib/worldCompareSearch';

/**
 * Выбор страны в калькуляторе инфляции.
 * Паттерн — ComparePage / WorldConceptPicker: подпись обычным регистром, поле с поиском,
 * Россия первой, остальные из API.
 */
export default function CalcCountryPicker({
  countries = [],
  value,
  onChange,
  russiaLabel,
  loading = false,
  fallbackName = '',
}) {
  const t = useT();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  const russia = useMemo(
    () => ({ slug: RUSSIA_SLUG, name: russiaLabel || t('calc.country.russia') }),
    [russiaLabel, t],
  );

  const options = useMemo(() => [russia, ...countries], [russia, countries]);

  // Пока каталог стран грузится, выбранной страны в списке ещё нет: не подменяем её Россией и не показываем слаг.
  const known = options.find((c) => c.slug === value);
  const pending = !known && value && value !== RUSSIA_SLUG;
  const selected = known || (pending ? { slug: value, name: fallbackName || '' } : russia);

  const filtered = useMemo(() => {
    return filterSearchCountries(options, query);
  }, [options, query]);

  useSearchTracking('calc-country', open ? query : '', filtered.length);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
        setQuery('');
      }
    };
    const onKey = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
        setQuery('');
      }
    };
    // pointerdown закрывает список и по касанию, и по мыши (mousedown на сенсоре приходит с задержкой).
    document.addEventListener('pointerdown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const pick = (slug) => {
    onChange?.(slug);
    setOpen(false);
    setQuery('');
  };

  return (
    <div ref={rootRef} className="relative mb-6">
      <p className="mb-2 text-[13px] font-medium text-text-secondary">
        {t('calc.country')}
      </p>
      <button
        type="button"
        className={cn(
          FOCUS_RING_SURFACE,
          'flex h-11 w-full items-center gap-2 rounded-xl border border-border-subtle bg-obsidian px-3 text-left text-sm font-medium text-text-primary transition-colors hover:border-champagne/20',
        )}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={t('calc.country')}
        onClick={() => setOpen((prev) => !prev)}
      >
        {selected.slug === RUSSIA_SLUG
          ? <Landmark className="h-4 w-4 shrink-0 text-champagne" />
          : <Globe2 className="h-4 w-4 shrink-0 text-champagne" />}
        {pending && !selected.name
          ? <span className="skeleton h-4 w-32 rounded-md" role="status" aria-busy={loading || undefined} aria-label={t('common.loading')} />
          : <span className="min-w-0 flex-1 truncate">{selected.name}</span>}
        {pending && !selected.name ? <span className="flex-1" /> : null}
        <ChevronDown className={cn('h-4 w-4 shrink-0 text-text-tertiary transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div
          className="absolute left-0 right-0 z-30 mt-1.5 overflow-hidden rounded-xl border border-border-subtle bg-surface shadow-lg"
          role="listbox"
        >
          <label className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-text-tertiary" />
            <span className="sr-only">{t('calc.country.search')}</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('calc.country.search')}
              aria-label={t('calc.country.searchAria')}
              className="min-h-9 min-w-0 flex-1 bg-transparent text-base text-text-primary outline-none placeholder:text-text-tertiary md:text-sm"
            />
            {query && (
              <button
                type="button"
                aria-label={t('common.clear')}
                onClick={() => setQuery('')}
                className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center text-text-tertiary hover:text-text-primary"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </label>
          <div className="max-h-64 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-3 text-sm text-text-secondary" role="status">
                {t('calc.country.notFound')}
              </div>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.slug}
                  type="button"
                  role="option"
                  aria-selected={c.slug === selected.slug}
                  onClick={() => pick(c.slug)}
                  className={cn(
                    'flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors border-b border-border-subtle/60 last:border-b-0',
                    c.slug === selected.slug
                      ? 'bg-champagne/10 text-champagne-ink font-medium'
                      : 'text-text-primary hover:bg-obsidian-lighter',
                  )}
                >
                  {c.slug === RUSSIA_SLUG
                    ? <Landmark className="h-4 w-4 shrink-0 text-champagne" />
                    : <Globe2 className="h-4 w-4 shrink-0 text-champagne" />}
                  <span className="min-w-0 break-words leading-snug">{c.name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
