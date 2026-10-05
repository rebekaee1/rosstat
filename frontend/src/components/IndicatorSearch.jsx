import { useState, useEffect, useMemo, useRef, useCallback, useId } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Landmark, MapPin, Search, SearchX, TrendingUp, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import useGlobalSearch from '../lib/useGlobalSearch';
import { useWorldCountries } from '../lib/worldApi';
import { dedupeSearchRows, describeSearchResult, searchExamples } from '../lib/searchExamples';
import { friendlySearchName, splitSearchRows } from '../lib/searchGroups';
import Chip from './Chip';
import CountryFlag from './CountryFlag';
import '../styles/shell.css';

// The palette discovers every public data plane through /search. Empty-query
// suggestions remain small, and typed results preserve geography and slices.
const SEARCH_TRACK_DEBOUNCE_MS = 900;
const SEARCH_MIN_LEN = 2;

const KIND_ICON = { country: Landmark, region: MapPin, subnational_region: MapPin };

/** Подсказка в поле на главной: «Например: Инфляция в США», примеры плавно сменяют друг друга. */
function RotatingHint({ lead, items }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (items.length < 2) return undefined;
    if (typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;
    const timer = setInterval(() => setIndex((i) => (i + 1) % items.length), 3200);
    return () => clearInterval(timer);
  }, [items.length]);
  return (
    <span className="flex-1 min-w-0 truncate text-sm text-text-tertiary">
      {lead}{' '}
      <span key={index} className="fe-rotate-in text-text-secondary">{items[index % items.length]}</span>
    </span>
  );
}

export default function IndicatorSearch({
  className, variant = 'icon', inlinePlaceholder, examples, initialQuery,
}) {
  const t = useT();
  const { locale } = useLocale();
  const navigate = useNavigate();
  const resultId = useId();
  // Поиск грузится лениво: при hover/focus кнопки или первом открытии (кэш React-Query — 5 мин).
  // Переход с серверной 404 или внешней ссылки: `/?q=инфляция` сразу открывает поиск с этим запросом.
  const seed = String(initialQuery || '').trim();
  const [shouldLoad, setShouldLoad] = useState(Boolean(seed));
  const [open, setOpen] = useState(Boolean(seed));
  const arm = useCallback(() => setShouldLoad(true), []);
  const [query, setQuery] = useState(seed);
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
  const globalSearch = useGlobalSearch(qTrim, { enabled: shouldLoad && open && !isComposing });
  const isSearchPending = Boolean(qTrim) && (isComposing || globalSearch.isDebouncing || globalSearch.isPending);
  const isSearchError = Boolean(qTrim) && !globalSearch.isDebouncing && globalSearch.isError;
  const isLoading = isSearchPending;
  const popular = useMemo(() => searchExamples(t), [t]);
  // Флаги в выдаче: код страны берём из общего (кэшированного) каталога стран, он грузится только при открытом поиске.
  const countriesQ = useWorldCountries({ enabled: shouldLoad && open });
  const flagBySlug = useMemo(() => {
    const map = new Map([['russia', 'RU']]);
    for (const country of countriesQ.data?.countries || []) {
      if (country?.slug && country?.code) map.set(country.slug, country.code);
    }
    return map;
  }, [countriesQ.data]);

  // «Долго»: отметка ставится таймером для конкретной фразы и гаснет сама, когда фраза или состояние меняются.
  const [slowFor, setSlowFor] = useState('');
  useEffect(() => {
    if (!(isLoading && qTrim)) return undefined;
    const timer = setTimeout(() => setSlowFor(qTrim), 2500);
    return () => clearTimeout(timer);
  }, [isLoading, qTrim]);
  const slow = isLoading && Boolean(qTrim) && slowFor === qTrim;

  // Выдача сервера целиком (для телеметрии спроса) и то, что видит человек: без дублей и без внутренних кодов.
  const results = useMemo(
    () => (qTrim && !isSearchPending && !isSearchError ? globalSearch.data?.results || [] : []),
    [qTrim, isSearchPending, isSearchError, globalSearch.data],
  );
  const nameOf = useCallback(
    (item) => (locale === 'en' && item.name_en ? item.name_en : item.name),
    [locale],
  );
  const detailOf = useCallback((item) => describeSearchResult(item, t), [t]);
  const allRows = useMemo(() => {
    if (!qTrim) {
      return popular.map((text, i) => ({
        kind: 'suggestion', key: `suggest:${i}`, name: text, query: text,
      }));
    }
    return dedupeSearchRows(results, nameOf, detailOf);
  }, [qTrim, popular, results, nameOf, detailOf]);
  // Вариации одного показателя сворачиваются в «Ещё варианты»: сначала человек видит самое подходящее.
  const grouped = useMemo(() => (qTrim ? splitSearchRows(allRows, nameOf) : null), [qTrim, allRows, nameOf]);
  const [moreFor, setMoreFor] = useState('');
  const showMore = Boolean(qTrim) && moreFor === qTrim;
  const rows = grouped && !showMore ? grouped.primary : allRows;
  const hiddenCount = grouped ? grouped.more.length : 0;
  const highlighted = Math.max(0, Math.min(hi, rows.length - 1));

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
    if (item?.kind === 'suggestion') {
      // Подсказка не уводит со страницы: подставляет запрос, поиск показывает результаты.
      setQuery(item.query);
      setHi(0);
      inputRef.current?.focus();
      return;
    }
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
  }, [highlighted, open, rows]);

  const handleListKey = (e) => {
    if (isComposing || e.isComposing || e.nativeEvent?.isComposing || e.keyCode === 229) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHi(Math.min(highlighted + 1, Math.max(rows.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi(Math.max(highlighted - 1, 0));
    } else if (e.key === 'Enter' && rows[highlighted]) {
      e.preventDefault();
      go(rows[highlighted], highlighted + 1);
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
        <>
          <button
            ref={triggerRef}
            type="button"
            onClick={() => { arm(); setOpen(true); }}
            onMouseEnter={arm}
            onFocus={arm}
            className={cn(
              FOCUS_RING,
              'group w-full flex min-h-14 items-center gap-3 rounded-2xl border border-border-subtle bg-surface px-4 py-3.5 text-left fe-press',
              'shadow-sm hover:border-champagne/40 transition-colors',
              className,
            )}
            aria-label={t('search.openAria')}
          >
            <Search className="w-5 h-5 text-text-tertiary shrink-0 group-hover:text-champagne transition-colors" aria-hidden="true" />
            {examples?.length
              ? <RotatingHint lead={t('shell.search.hintLead')} items={examples} />
              : <span className="flex-1 text-sm text-text-tertiary truncate">{placeholder}</span>}
            <kbd className="hidden sm:inline text-xs font-sans text-text-tertiary border border-border-subtle rounded px-1.5 py-0.5">
              {isAppleModKey ? '⌘K' : 'Ctrl+K'}
            </kbd>
          </button>
          {examples?.length ? (
            <ul className="fe-search-examples" aria-label={t('shell.search.examplesAria')}>
              {examples.map((example) => (
                <li key={example}>
                  <Chip
                    onClick={() => { arm(); setQuery(example); setHi(0); setOpen(true); }}
                    aria-pressed={undefined}
                  >
                    {example}
                  </Chip>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <button
          ref={triggerRef}
          type="button"
          onClick={() => { arm(); setOpen(true); }}
          onMouseEnter={arm}
          onFocus={arm}
          className={cn(
            FOCUS_RING,
            'rounded-xl flex items-center justify-center p-1.5 bg-obsidian-lighter/50 border border-border-subtle text-text-secondary hover:text-text-primary hover:bg-obsidian-lighter/80 transition-colors [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11',
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
          className="fixed inset-0 z-[200] flex items-start justify-center px-3 pt-3 sm:px-4 sm:pt-[10vh]"
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
          <div className="fe-dialog-panel fe-search-panel relative flex max-h-[calc(100dvh-1.5rem)] w-full max-w-2xl flex-col rounded-2xl border border-border-subtle bg-surface shadow-2xl overflow-hidden sm:max-h-[calc(90dvh-1rem)]">
            <div className="fe-search-field relative flex shrink-0 items-center gap-3 px-4 py-2 border-b border-border-subtle">
              {isLoading && qTrim
                ? <span className="fe-search-spinner shrink-0" aria-hidden="true" data-testid="search-spinner" />
                : <Search className="w-5 h-5 text-text-tertiary shrink-0" aria-hidden="true" />}
              <input
                ref={inputRef}
                type="search"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                onCompositionStart={() => setIsComposing(true)}
                onCompositionEnd={(e) => { onQueryChange(e.currentTarget.value); setIsComposing(false); }}
                onKeyDown={handleListKey}
                placeholder={t('search.placeholder')}
                className="min-h-12 min-w-0 flex-1 bg-transparent outline-none text-base text-text-primary placeholder:text-text-tertiary"
                aria-label={t('search.queryAria')}
                maxLength={256}
                role="combobox"
                aria-autocomplete="list"
                aria-expanded="true"
                aria-controls={`${resultId}-list`}
                aria-describedby={`${resultId}-help`}
                aria-activedescendant={rows[highlighted] ? `${resultId}-result-${highlighted}` : undefined}
              />
              <button
                type="button"
                onClick={close}
                className={cn(FOCUS_RING, 'fe-press flex min-h-11 min-w-11 items-center justify-center rounded-xl p-1 text-text-tertiary hover:text-text-primary')}
                aria-label={t('common.close')}
              >
                <X className="w-5 h-5" />
              </button>
              <span className="fe-search-progress" data-active={isLoading && qTrim ? 'true' : 'false'} aria-hidden="true" />
            </div>

            <p id={`${resultId}-help`} className="px-4 pt-3 pb-1 text-xs leading-relaxed text-text-secondary [@media(pointer:coarse)]:sr-only">
              {t('search.help')}
            </p>

            {qTrim && !isLoading && globalSearch.data?.corrected_query && globalSearch.data.corrected_query !== qTrim && (
              <div className="px-4 py-2 text-sm text-text-secondary" role="status">
                {t('search.corrected', { query: globalSearch.data.corrected_query })}
              </div>
            )}

            <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain py-2 sm:max-h-[60vh]" role="listbox" id={`${resultId}-list`} aria-busy={isLoading}>
              {!qTrim ? (
                <div role="group" aria-labelledby={`${resultId}-popular`}>
                  <p id={`${resultId}-popular`} className="px-4 pb-1 pt-1 text-sm font-semibold text-text-secondary">
                    {t('shell.search.popular')}
                  </p>
                  {rows.map((item, i) => (
                    <SearchRow
                      key={item.key}
                      item={item}
                      index={i}
                      id={`${resultId}-result-${i}`}
                      active={i === highlighted}
                      name={item.name}
                      detail=""
                      onHover={setHi}
                      onPick={go}
                    />
                  ))}
                </div>
              ) : rows.length === 0 ? (
                <div className="px-5 py-6 text-sm text-text-secondary" role="status" aria-live="polite">
                  {isLoading && (
                    <div className="mb-4 space-y-3" aria-hidden="true" data-testid="search-skeleton">
                      {[72, 58, 66].map((width) => (
                        <div key={width} className="flex items-center gap-3">
                          <span className="skeleton h-10 w-10 shrink-0 rounded-xl" />
                          <span className="flex-1 space-y-1.5">
                            <span className="skeleton block h-3.5 rounded" style={{ width: `${width}%` }} />
                            <span className="skeleton block h-3 w-2/5 rounded" />
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {isLoading ? <><span className="fe-search-loading-text">{String(t('search.loading')).replace(/[….]+$/, '')}</span>{slow && <span className="mt-1 block text-xs" data-testid="search-slow">{t('search.slow')}</span>}</>
                    : isSearchError ? (
                      <>
                        {t('search.error')}
                        <button type="button" onClick={() => globalSearch.refetch()} className={cn(FOCUS_RING, 'block mt-3 min-h-11 text-champagne-ink font-medium')}>{t('common.retry')}</button>
                      </>
                    ) : globalSearch.data?.reason === 'unsupported_query' ? t('search.unsupportedQuery')
                      : globalSearch.data?.reason === 'unsupported_period' ? t('search.unsupportedPeriod')
                        : globalSearch.data?.reason === 'ambiguous_geography' ? t('search.ambiguousGeography')
                          : (
                            <div className="text-center" data-testid="search-nothing">
                              <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-champagne/10 text-champagne-ink" aria-hidden="true">
                                <SearchX size={22} />
                              </span>
                              <p className="mt-3 text-base font-semibold text-text-primary">{t('search.nothingFound', { query: qTrim })}</p>
                              <ul className="mx-auto mt-3 max-w-sm space-y-1 text-left text-sm text-text-secondary">
                                <li>{t('shell.search.tip.spelling')}</li>
                                <li>{t('shell.search.tip.short')}</li>
                                <li>{t('shell.search.tip.place')}</li>
                              </ul>
                              <p className="mt-4 text-sm font-medium text-text-secondary">{t('shell.search.tryThese')}</p>
                              <ul className="mt-2 flex flex-wrap justify-center gap-2">
                                {popular.slice(0, 4).map((example) => (
                                  <li key={example}>
                                    <Chip aria-pressed={undefined} onClick={() => { onQueryChange(example); inputRef.current?.focus(); }}>{example}</Chip>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                </div>
              ) : (
                <>
                  {rows.map((item, i) => (
                    <SearchRow
                      key={item.key}
                      item={item}
                      index={i}
                      id={`${resultId}-result-${i}`}
                      active={i === highlighted}
                      name={friendlySearchName(item, nameOf(item), t)}
                      detail={detailOf(item)}
                      flagCode={flagBySlug.get(item.country_slug) || ''}
                      onHover={setHi}
                      onPick={go}
                    />
                  ))}
                  {globalSearch.data?.has_more && !isLoading && (
                    <p className="px-4 pb-2 pt-3 text-sm text-text-secondary">{t('search.refine')}</p>
                  )}
                </>
              )}
            </div>

            {qTrim && hiddenCount > 0 && !isLoading ? (
              <button
                type="button"
                className={cn(FOCUS_RING, 'fe-search-more fe-press shrink-0')}
                aria-expanded={showMore}
                onClick={() => setMoreFor(showMore ? '' : qTrim)}
              >
                {showMore ? t('shell3.search.fewerVariants') : t('shell3.search.moreVariants', { n: hiddenCount })}
              </button>
            ) : null}

            <div className="fe-search-kbd px-4 py-2 border-t border-border-subtle flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-tertiary [@media(pointer:coarse)]:hidden">
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

/** Одна строка выдачи: значок вида, название, подпись «где и как часто», крупная цель нажатия. */
function SearchRow({ item, index, id, active, name, detail, flagCode = '', onHover, onPick }) {
  const isSuggestion = item.kind === 'suggestion';
  const Icon = isSuggestion ? Search : KIND_ICON[item.kind] || TrendingUp;
  // Страна — её флаг вместо значка; у региона и показателя значок вида, а флаг страны — маленьким бейджем в углу.
  const flagAsIcon = item.kind === 'country' && Boolean(flagCode);
  const flagBadge = !isSuggestion && !flagAsIcon && Boolean(flagCode);
  return (
    <button
      style={isSuggestion ? { '--fe-delay': `${Math.min(index, 5) * 0.03}s`, '--fe-duration': '0.2s', '--fe-rise': '6px' } : undefined}
      type="button"
      data-row={index}
      id={id}
      onMouseEnter={() => onHover(index)}
      onClick={() => onPick(item, index + 1)}
      className={cn(
        'fe-search-row w-full min-h-14 text-left px-4 py-2.5 flex items-center gap-3 transition-colors',
        isSuggestion && 'fe-reveal',
        active ? 'bg-champagne/10' : 'hover:bg-obsidian-lighter/60',
      )}
      role="option"
      tabIndex={-1}
      aria-selected={active}
    >
      <span className="fe-search-row__tile relative grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-champagne/10 text-champagne-ink" aria-hidden="true">
        {flagAsIcon ? <CountryFlag code={flagCode} className="fe-search-row__flag" /> : <Icon size={18} />}
        {flagBadge ? <CountryFlag code={flagCode} className="fe-search-row__badge" /> : null}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] font-medium leading-snug text-text-primary whitespace-normal break-words">{name}</span>
        {detail ? <span className="mt-0.5 block text-[13px] leading-snug text-text-secondary whitespace-normal break-words">{detail}</span> : null}
      </span>
    </button>
  );
}
