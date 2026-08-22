import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Globe2, Landmark, Search, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { RUSSIA_SLUG } from '../lib/inflationCalc';
import { useT } from '../i18n';
import useSearchTracking from '../lib/useSearchTracking';

/**
 * Выбор страны в калькуляторе инфляции.
 * Паттерн — ComparePage / WorldConceptPicker: подпись mono 10px, поле с поиском,
 * Россия первой, остальные из API.
 */
export default function CalcCountryPicker({
  countries = [],
  value,
  onChange,
  russiaLabel,
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

  const selected = options.find((c) => c.slug === value) || russia;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((c) => (c.name || '').toLowerCase().includes(q));
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
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const pick = (slug) => {
    onChange?.(slug);
    setOpen(false);
    setQuery('');
  };

  return (
    <div ref={rootRef} className="relative mb-6">
      <p className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
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
        <span className="min-w-0 flex-1 truncate">{selected.name}</span>
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
              className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary"
            />
            {query && (
              <button
                type="button"
                aria-label={t('common.clear')}
                onClick={() => setQuery('')}
                className="shrink-0 text-text-tertiary hover:text-text-primary"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </label>
          <div className="max-h-64 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-3 text-sm text-text-tertiary">
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
                    'flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors border-b border-border-subtle/60 last:border-b-0',
                    c.slug === selected.slug
                      ? 'bg-champagne/10 text-champagne'
                      : 'text-text-primary hover:bg-obsidian-lighter',
                  )}
                >
                  {c.slug === RUSSIA_SLUG
                    ? <Landmark className="h-4 w-4 shrink-0 text-champagne" />
                    : <Globe2 className="h-4 w-4 shrink-0 text-champagne" />}
                  <span className="truncate">{c.name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
