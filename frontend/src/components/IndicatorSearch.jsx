import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { CATEGORIES, isIndicatorListed } from '../lib/categories';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';

const MAX_RESULTS = 8;

/**
 * Минимальный поиск по индикаторам (D1).
 *
 * Источник данных — React-Query `useIndicators()`. Фильтр — substring без
 * учёта регистра по name + name_en + category. Скрытые карточки
 * (`is_listed=false`) в выдаче не показываются — это counterpart'ы,
 * доступные только через FrequencySwitcher из primary.
 *
 * Кнопка Enter переходит к первому результату; Escape очищает.
 */
export default function IndicatorSearch({ className }) {
  const navigate = useNavigate();
  const { data: indicators = [] } = useIndicators();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || q.length < 2) return [];
    return indicators
      .filter(isIndicatorListed)
      .filter((ind) => {
        const haystack = `${ind.name || ''} ${ind.name_en || ''} ${ind.category || ''} ${ind.code || ''}`.toLowerCase();
        return haystack.includes(q);
      })
      .slice(0, MAX_RESULTS);
  }, [query, indicators]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const go = (code) => {
    setOpen(false);
    setQuery('');
    navigate(`/indicator/${code}`);
  };

  const handleKey = (e) => {
    if (e.key === 'Escape') { setQuery(''); setOpen(false); return; }
    if (e.key === 'Enter' && results.length > 0) {
      e.preventDefault();
      go(results[0].code);
    }
  };

  return (
    <div ref={wrapRef} className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary pointer-events-none" />
        <input
          type="search"
          placeholder="Поиск индикатора…"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKey}
          aria-label="Поиск индикатора"
          className={cn(
            FOCUS_RING,
            'rounded-xl bg-obsidian-lighter/60 border border-border-subtle px-8 py-1.5 text-sm w-44 lg:w-56',
            'placeholder:text-text-tertiary focus:bg-surface focus:w-56 lg:focus:w-72 transition-all',
          )}
        />
      </div>
      {open && results.length > 0 && (
        <div
          className="absolute right-0 top-full z-[120] mt-2 w-72 max-h-[min(60vh,360px)] overflow-y-auto rounded-2xl border border-border-subtle bg-surface py-2 shadow-2xl ring-1 ring-black/[0.08]"
          role="listbox"
        >
          {results.map((ind) => {
            const cat = CATEGORIES.find((c) => c.apiCategory === ind.category);
            return (
              <button
                key={ind.code}
                type="button"
                onClick={() => go(ind.code)}
                className={cn(
                  FOCUS_RING,
                  'w-full text-left px-3 py-2 text-sm hover:bg-obsidian-lighter/80 flex flex-col gap-0.5 rounded-lg',
                )}
                role="option"
              >
                <span className="text-text-primary">{ind.name}</span>
                {cat && (
                  <span className="text-[10px] uppercase tracking-wider font-mono text-text-tertiary">
                    {cat.name}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
      {open && query.trim().length >= 2 && results.length === 0 && (
        <div className="absolute right-0 top-full z-[120] mt-2 w-72 rounded-2xl border border-border-subtle bg-surface px-4 py-3 text-sm text-text-tertiary shadow-2xl ring-1 ring-black/[0.08]">
          Ничего не нашли по запросу «{query.trim()}».
        </div>
      )}
    </div>
  );
}
