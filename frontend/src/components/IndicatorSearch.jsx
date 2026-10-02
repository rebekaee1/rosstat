import { useState, useEffect, useMemo, useRef, useCallback, useId } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { findCategoryByApiLabel } from '../lib/categories';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import {
  russiaIndicatorPath,
  indicatorPath,
} from '../lib/sitePaths';
import {
  useWorldCompareCatalog,
} from '../lib/worldApi';
import { useLocale, useT } from '../i18n';
import useGlobalSearch from '../lib/useGlobalSearch';

// The palette discovers every public data plane through /search. Empty-query
// suggestions remain small, and typed results preserve geography and slices.
const SEARCH_TRACK_DEBOUNCE_MS = 900;
const SEARCH_MIN_LEN = 2;

export default function IndicatorSearch({ className, variant = 'icon', inlinePlaceholder }) {
  const t = useT();
  const { locale } = useLocale();
  const navigate = useNavigate();
  const resultId = useId();
  // Каталог нужен только при открытии палитры. Раньше полный список
  // (include_unlisted, ~290 мс) тянулся на КАЖДОЙ странице, т.к. компонент
  // всегда смонтирован в Navbar — это утяжеляло первый рендер любой карточки.
  // Грузим лениво: при hover/focus кнопки или первом открытии. React-Query
  // кэширует на 5 мин, поэтому повторные открытия мгновенны.
  const [shouldLoad, setShouldLoad] = useState(false);
  const [open, setOpen] = useState(false);
  const arm = useCallback(() => setShouldLoad(true), []);
  const [query, setQuery] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const [hi, setHi] = useState(0); // highlighted result index
  const triggerRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  // Спрос-аналитика поиска (звонок 2026-06-19): refs, чтобы читать актуальный
  // запрос/число результатов в обработчиках без раздувания deps и записи ref
  // во время рендера.
  const lastSentRef = useRef('');     // дедуп debounce-события search_query
  const queryRef = useRef('');        // последний введённый запрос
  const resultsCountRef = useRef(0);  // число результатов для него
  const selectedRef = useRef(false);  // был ли выбран результат (иначе abandon)
  const interactionRef = useRef('');

  const qTrim = query.trim();
  const { data: indicators = [], isPending: isRussiaPending, isError: isRussiaError, refetch: retryRussia } = useIndicators({ enabled: shouldLoad && !qTrim && locale === 'ru' });
  const globalSearch = useGlobalSearch(qTrim, { enabled: shouldLoad && open && !isComposing });
  const { data: worldPreview, isPending: isPreviewPending, isError: isPreviewError, refetch: retryPreview } = useWorldCompareCatalog({
    enabled: locale === 'en' && shouldLoad && open && !qTrim,
  });
  const isSearchPending = Boolean(qTrim) && (isComposing || globalSearch.isDebouncing || globalSearch.isPending);
  const isSearchError = qTrim ? !globalSearch.isDebouncing && globalSearch.isError
    : locale === 'en' ? isPreviewError : isRussiaError;
  const isLoading = isSearchPending || (!qTrim && (locale === 'en' ? isPreviewPending : isRussiaPending));

  const results = useMemo(() => {
    if (qTrim) return isSearchPending || isSearchError ? [] : globalSearch.data?.results || [];
    if (locale === 'en') {
      return (worldPreview?.items || [])
        .filter(item => item.country_slug === 'united-states' && item.indicator_code)
        .map(item => ({
          kind: 'world', key: `world:united-states:${item.indicator_code}`,
          code: item.indicator_code, name: item.concept_name, name_en: item.concept_name_en,
          country_slug: 'united-states', country_name: item.country_name_en || item.country_name,
          path: indicatorPath('united-states', item.indicator_code),
        }));
    }
    return indicators.filter(ind => ind.is_listed !== false).map(ind => ({
      ...ind, kind: 'russia', key: `ru:${ind.code}`, path: russiaIndicatorPath(ind.code),
    }));
  }, [qTrim, isSearchPending, isSearchError, globalSearch.data, locale, worldPreview, indicators]);
  const highlighted = Math.max(0, Math.min(hi, results.length - 1));
  const repeatedNames = useMemo(() => {
    const counts = new Map();
    for (const item of results) {
      const name = locale === 'en' && item.name_en ? item.name_en : item.name;
      counts.set(name, (counts.get(name) || 0) + 1);
    }
    return new Set([...counts].filter(([, count]) => count > 1).map(([name]) => name));
  }, [results, locale]);

  const close = useCallback(() => {
    // Брошенный запрос (закрыли без выбора) — сигнал спроса не хуже выбранного.
    const q = (queryRef.current || '').trim();
    if (q.length >= SEARCH_MIN_LEN && !selectedRef.current) {
      track(events.SEARCH_ABANDON, { q: q.slice(0, 256), results: resultsCountRef.current, context: 'global', interaction_id: interactionRef.current });
    }
    setOpen(false);
    setQuery('');
    setIsComposing(false);
    setHi(0);
  }, []);

  const go = useCallback((item, position = null) => {
    if (!item?.path?.startsWith('/') || item.path.startsWith('//') || item.path.includes('\\')) return;
    const q = (queryRef.current || '').trim();
    selectedRef.current = true;
    // position — номер строки в выдаче (1-based): клики по хвосту = сигнал,
    // что ранжирование каталога не совпадает со спросом.
    track(events.SEARCH_SELECT, {
      q: q.slice(0, 256),
      code: item.code,
      scope: item.kind, country: item.country_slug || 'russia',
      ...(item.region_slug ? { region: item.region_slug } : {}),
      path: item.path, context: 'global', version: globalSearch.data?.version || 'suggestions',
      interaction_id: interactionRef.current,
      ...(position ? { position } : {}),
    });
    close();
    if (item.navigation === 'document') window.location.assign(item.path);
    else navigate(item.path);
  }, [close, navigate, globalSearch.data?.version]);

  // Cmd+K / Ctrl+K — открыть; Escape — закрыть; '/' — открыть (если не в инпуте)
  useEffect(() => {
    const onKey = (e) => {
      if (e.defaultPrevented || isComposing || e.isComposing || e.keyCode === 229) return;
      // Every Navbar/inline instance is mounted, but only one visible trigger
      // may claim a global shortcut. Portals escape CSS-hidden parents.
      if (!open) {
        if (document.querySelector('[data-fe-search-dialog]')) return;
        const trigger = triggerRef.current;
        if (!trigger || trigger.getClientRects().length === 0 || getComputedStyle(trigger).visibility === 'hidden') return;
      }
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        arm();
        if (open) close();
        else setOpen(true);
        return;
      }
      if (e.key === '/' && !open) {
        const tag = document.activeElement?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA' && !document.activeElement?.isContentEditable) {
          e.preventDefault();
          arm();
          setOpen(true);
        }
        return;
      }
      if (e.key === 'Escape' && open) {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, close, arm, isComposing]);

  // фокус при открытии + сброс состояния спрос-аналитики на новую сессию поиска
  useEffect(() => {
    if (!open) return;
    selectedRef.current = false;
    lastSentRef.current = '';
    interactionRef.current = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const timer = setTimeout(() => inputRef.current?.focus(), 30);
    return () => {
      clearTimeout(timer);
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected && typeof previousFocus.focus === 'function') previousFocus.focus();
    };
  }, [open]);

  // Актуальные запрос/число результатов — в refs (для обработчиков close/go).
  useEffect(() => {
    queryRef.current = query;
    resultsCountRef.current = isLoading || isSearchError ? null : results.length;
  });

  // Debounce-трекинг введённого запроса (введённое, но ещё не отправленное).
  // results.length в момент срабатывания соответствует текущему query.
  useEffect(() => {
    if (!open || isLoading || isSearchError) return undefined;
    const q = query.trim();
    if (q.length < SEARCH_MIN_LEN) return undefined;
    const count = results.length;
    const t = setTimeout(() => {
      if (q === lastSentRef.current) return;
      lastSentRef.current = q;
      track(events.SEARCH_QUERY, {
        q: q.slice(0, 256),
        results: count,
        context: 'global', version: globalSearch.data?.version || 'v2',
        interaction_id: interactionRef.current,
        keys: results.map(item => item.key), returned_count: results.length,
        has_more: Boolean(globalSearch.data?.has_more),
      });
    }, SEARCH_TRACK_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query, open, results, isLoading, isSearchError, globalSearch.data?.version, globalSearch.data?.has_more]);

  const onQueryChange = (v) => {
    setQuery(v);
    setHi(0);
  };

  // прокрутка к выделенному элементу
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-row="${highlighted}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlighted, open, results]);

  const handleListKey = (e) => {
    if (isComposing || e.isComposing || e.nativeEvent?.isComposing || e.keyCode === 229) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHi(Math.min(highlighted + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi(Math.max(highlighted - 1, 0));
    } else if (e.key === 'Enter' && results[highlighted]) {
      e.preventDefault();
      go(results[highlighted], highlighted + 1);
    }
  };

  // navigator.platform устарел и в части сред врёт; сначала Client Hints,
  // затем явный Win/Linux/Android в UA, и только потом platform/UA Macintosh.
  const isAppleModKey = (() => {
    if (typeof navigator === 'undefined') return false;
    const hint = navigator.userAgentData?.platform;
    if (hint) return /mac|iphone|ipad|ipod/i.test(hint);
    const ua = navigator.userAgent || '';
    if (/Windows|Android|CrOS|Linux/i.test(ua) && !/Android.*Macintosh/i.test(ua)) {
      return false;
    }
    const platform = navigator.platform || '';
    if (platform) return /Mac|iPhone|iPad|iPod/i.test(platform);
    return /Mac OS X|Macintosh|iPhone|iPad|iPod/i.test(ua);
  })();

  const mod = isAppleModKey ? '⌘' : 'Ctrl';
  const placeholder = inlinePlaceholder || t('home.searchPlaceholder');

  return (
    <>
      {variant === 'pill' ? (
        // Хедер-десктоп (звонок 2026-06-19): лупа + подпись «Поиск», чуть шире
        // прежней иконки — поиск был малозаметен.
        <button
          ref={triggerRef}
          type="button"
          onClick={() => { arm(); setOpen(true); }}
          onMouseEnter={arm}
          onFocus={arm}
          className={cn(
            FOCUS_RING,
            'flex items-center gap-2 rounded-full pl-3 pr-3.5 py-1.5 bg-obsidian-lighter/50 border border-border-subtle text-text-secondary hover:text-text-primary hover:border-champagne/30 transition-colors',
            className,
          )}
          aria-label={t('search.openAriaMod', { mod })}
          title={t('search.titleMod', { mod })}
        >
          <Search className="w-4 h-4 shrink-0" aria-hidden="true" />
          {/* На 1024–1280px подпись скрыта — экономим ширину навбара. */}
          <span className="text-sm font-medium hidden xl:inline">{t('common.search')}</span>
        </button>
      ) : variant === 'inline' ? (
        <button
          ref={triggerRef}
          type="button"
          onClick={() => { arm(); setOpen(true); }}
          onMouseEnter={arm}
          onFocus={arm}
          className={cn(
            FOCUS_RING,
            'group w-full flex items-center gap-3 rounded-2xl border border-border-subtle bg-surface px-4 py-3.5 text-left',
            'shadow-sm hover:border-champagne/40 transition-colors',
            className,
          )}
          aria-label={t('search.openAria')}
        >
          <Search className="w-4 h-4 text-text-tertiary shrink-0 group-hover:text-champagne transition-colors" aria-hidden="true" />
          <span className="flex-1 text-sm text-text-tertiary truncate">{placeholder}</span>
          <kbd className="hidden sm:inline text-[10px] font-mono text-text-tertiary border border-border-subtle rounded px-1.5 py-0.5">
            {isAppleModKey ? '⌘K' : 'Ctrl+K'}
          </kbd>
        </button>
      ) : (
        <button
          ref={triggerRef}
          type="button"
          onClick={() => { arm(); setOpen(true); }}
          onMouseEnter={arm}
          onFocus={arm}
          className={cn(
            FOCUS_RING,
            'rounded-xl flex items-center justify-center p-1.5 bg-obsidian-lighter/50 border border-border-subtle text-text-secondary hover:text-text-primary hover:bg-obsidian-lighter/80 transition-colors',
            className,
          )}
          aria-label={t('search.openAriaMod', { mod })}
          title={t('search.titleMod', { mod })}
        >
          <Search className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      )}

      {open && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[200] flex items-start justify-center pt-[10vh] px-4"
          role="dialog"
          data-fe-search-dialog
          aria-modal="true"
          aria-label={t('search.dialogAria')}
          aria-describedby={`${resultId}-help`}
          onKeyDown={(event) => {
            if (event.key !== 'Tab') return;
            const controls = [...event.currentTarget.querySelectorAll('input, button:not([tabindex="-1"])')].filter(el => !el.disabled);
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
          }}
        >
          <button
            type="button"
            aria-label={t('common.close')}
            tabIndex={-1}
            className="absolute inset-0 bg-text-primary/30 backdrop-blur-[2px]"
            onClick={close}
          />
          <div className="fe-dialog-panel relative flex max-h-[calc(90dvh-1rem)] w-full max-w-2xl flex-col rounded-2xl border border-border-subtle bg-surface shadow-2xl overflow-hidden">
            <div className="flex shrink-0 items-center gap-3 px-4 py-3 border-b border-border-subtle">
              <Search className="w-4 h-4 text-text-tertiary shrink-0" aria-hidden="true" />
              <input
                ref={inputRef}
                type="search"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                onCompositionStart={() => setIsComposing(true)}
                onCompositionEnd={(e) => { onQueryChange(e.currentTarget.value); setIsComposing(false); }}
                onKeyDown={handleListKey}
                placeholder={t('search.placeholder')}
                className="min-w-0 flex-1 bg-transparent outline-none text-base text-text-primary placeholder:text-text-tertiary"
                aria-label={t('search.queryAria')}
                maxLength={256}
                role="combobox"
                aria-autocomplete="list"
                aria-expanded="true"
                aria-controls={`${resultId}-list`}
                aria-describedby={`${resultId}-help`}
                aria-activedescendant={results[highlighted] ? `${resultId}-result-${highlighted}` : undefined}
              />
              <button
                type="button"
                onClick={close}
                className={cn(FOCUS_RING, 'flex min-h-11 min-w-11 items-center justify-center rounded-lg p-1 text-text-tertiary hover:text-text-primary')}
                aria-label={t('common.close')}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p id={`${resultId}-help`} className="px-4 pt-3 pb-1 text-xs leading-relaxed text-text-tertiary">
              {t('search.help')}
            </p>

            {qTrim && !isLoading && globalSearch.data?.corrected_query && globalSearch.data.corrected_query !== qTrim && (
              <div className="px-4 py-2 text-xs text-text-tertiary" role="status">
                {t('search.corrected', { query: globalSearch.data.corrected_query })}
              </div>
            )}

            <div ref={listRef} className="min-h-0 max-h-[60vh] overflow-y-auto py-2" role="listbox" id={`${resultId}-list`} aria-busy={isLoading}>
              {results.length === 0 ? (
                <div className="px-4 py-6 text-sm text-text-tertiary" role="status" aria-live="polite">
                  {isLoading ? t('search.loading') : isSearchError ? t('search.error')
                    : qTrim && globalSearch.data?.reason === 'unsupported_query' ? t('search.unsupportedQuery')
                      : qTrim && globalSearch.data?.reason === 'unsupported_period' ? t('search.unsupportedPeriod')
                      : qTrim && globalSearch.data?.reason === 'ambiguous_geography' ? t('search.ambiguousGeography')
                        : qTrim ? t('search.nothingFound', { query: qTrim }) : t('search.empty')}
                  {isSearchError && <button type="button" onClick={() => qTrim ? globalSearch.refetch() : locale === 'en' ? retryPreview() : retryRussia()} className={cn(FOCUS_RING, 'block mt-3 text-champagne')}>{t('common.retry')}</button>}
                </div>
              ) : (
                results.map((item, i) => {
                  const isRussia = item.kind === 'russia' || item.kind === 'russia_indicator';
                  const cat = isRussia ? findCategoryByApiLabel(item.category_ru || item.category) : null;
                  const active = i === highlighted;
                  const displayName = locale === 'en' && item.name_en ? item.name_en : item.name;
                  const frequency = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'].includes(item.frequency)
                    ? t(`world.freq.long.${item.frequency}`) : item.frequency;
                  const detail = [
                    item.region_name,
                    item.country_name || (isRussia ? t('search.russia') : null),
                    locale === 'en' ? cat?.nameEn || cat?.name || item.category : cat?.name || item.category,
                    frequency, item.unit, repeatedNames.has(displayName) ? item.code : null,
                  ].filter(Boolean).join(' / ');
                  return (
                    <button
                      key={item.key}
                      type="button"
                      data-row={i}
                      id={`${resultId}-result-${i}`}
                      onMouseEnter={() => setHi(i)}
                      onClick={() => go(item, i + 1)}
                      className={cn(
                        'w-full text-left px-4 py-2.5 flex items-center gap-3 transition-colors',
                        active ? 'bg-champagne/10' : 'hover:bg-obsidian-lighter/60',
                      )}
                      role="option"
                      tabIndex={-1}
                      aria-selected={active}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-text-primary whitespace-normal break-words">{displayName}</div>
                        {detail && <div className="mt-1 text-xs text-text-tertiary whitespace-normal break-words">{detail}</div>}
                      </div>
                    </button>
                  );
                })
              )}
            </div>

            <div className="px-4 py-2 border-t border-border-subtle flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-mono text-text-tertiary">
              {globalSearch.data?.has_more && qTrim && !isLoading && <span className="w-full">{t('search.refine')}</span>}
              <span><kbd className="px-1 py-0.5 rounded border border-border-subtle">↑</kbd> <kbd className="px-1 py-0.5 rounded border border-border-subtle">↓</kbd> {t('search.hint.nav')}</span>
              <span><kbd className="px-1 py-0.5 rounded border border-border-subtle">Enter</kbd> {t('search.hint.open')}</span>
              <span><kbd className="px-1 py-0.5 rounded border border-border-subtle">Esc</kbd> {t('search.hint.close')}</span>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
