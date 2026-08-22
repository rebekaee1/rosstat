import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
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
  useWorldSearch,
  WORLD_GLOBAL_SEARCH_LIMIT,
} from '../lib/worldApi';
import { useLocale, useT } from '../i18n';
import {
  expandSearchQuery,
  filterSearchIndicators,
} from '../lib/searchSynonyms';

// Поиск — это директория: список скроллится (`max-h-[60vh] overflow-y-auto`) и
// поддерживает клавиатурную навигацию. Жёсткого «топ-12» больше нет (звонок
// 2026-06-25: «главное, чтобы можно было листать»).
//
// Две стадии (чтобы пустой запрос не вываливал ~900 авто-сиблингов режимов вида
// `cpi-food-yoy`, `corp-bond-index-mom` — это выглядело бы как «сделано
// студентом»):
//   • пустой запрос → чистая витрина: только листинговые индикаторы России
//     (is_listed), листается целиком;
//   • введён запрос → Россия (весь каталог, включая скрытые срезы) + мир
//     через /world/search; сначала российские, затем мировые с меткой страны.
// MAX_RESULTS — страховка от патологического рендера на коротком запросе
// (только российская часть; мир ограничен WORLD_GLOBAL_SEARCH_LIMIT).
const MAX_RESULTS = 600;
const SEARCH_TRACK_DEBOUNCE_MS = 900;
const SEARCH_MIN_LEN = 2;

/**
 * Поиск по индикаторам (правка №1 из звонка 2026-05-21).
 *
 * UX — command-palette: маленькая кнопка с лупой в Navbar открывает modal
 * по центру экрана. Внутри modal — большой инпут + полный список совпадений
 * (скроллится) + клавиатурная навигация (стрелки, Enter, Esc). Хоткеи Cmd+K / Ctrl+K
 * открывают modal из любой точки приложения. На мобильных — full-screen
 * sheet (тот же компонент, breakpoint в стилях).
 *
 * Источники: React-Query `useIndicators()` (Россия) + `useWorldSearch`
 * (мир, при непустом запросе). Клик: Россия → `/russia/indicator/{code}`,
 * мир → `/{country}/indicator/{code}`.
 */
export default function IndicatorSearch({ className, variant = 'icon', inlinePlaceholder }) {
  const t = useT();
  const { locale } = useLocale();
  const navigate = useNavigate();
  // Каталог нужен только при открытии палитры. Раньше полный список
  // (include_unlisted, ~290 мс) тянулся на КАЖДОЙ странице, т.к. компонент
  // всегда смонтирован в Navbar — это утяжеляло первый рендер любой карточки.
  // Грузим лениво: при hover/focus кнопки или первом открытии. React-Query
  // кэширует на 5 мин, поэтому повторные открытия мгновенны.
  const [shouldLoad, setShouldLoad] = useState(false);
  const { data: indicators = [] } = useIndicators({ includeUnlisted: true, enabled: shouldLoad });
  const [open, setOpen] = useState(false);
  const arm = useCallback(() => setShouldLoad(true), []);
  const [query, setQuery] = useState('');
  const [hi, setHi] = useState(0); // highlighted result index
  const inputRef = useRef(null);
  const listRef = useRef(null);
  // Спрос-аналитика поиска (звонок 2026-06-19): refs, чтобы читать актуальный
  // запрос/число результатов в обработчиках без раздувания deps и записи ref
  // во время рендера.
  const lastSentRef = useRef('');     // дедуп debounce-события search_query
  const queryRef = useRef('');        // последний введённый запрос
  const resultsCountRef = useRef(0);  // число результатов для него
  const selectedRef = useRef(false);  // был ли выбран результат (иначе abandon)

  const qTrim = query.trim();
  const worldNeedle = expandSearchQuery(qTrim);
  const { data: worldSearch } = useWorldSearch(worldNeedle, {
    limit: WORLD_GLOBAL_SEARCH_LIMIT,
    enabled: shouldLoad && open && worldNeedle.length >= 1,
  });

  const results = useMemo(() => {
    if (!qTrim) {
      // Витрина: только листинговые индикаторы России, листается целиком.
      return indicators
        .filter((ind) => ind.is_listed !== false)
        .map((ind) => ({
          kind: 'russia',
          key: `ru:${ind.code}`,
          code: ind.code,
          name: ind.name,
          name_en: ind.name_en,
          category: ind.category,
          category_ru: ind.category_ru,
          seo_keywords: ind.seo_keywords,
        }));
    }

    // Подстрока + синонимы + fuzzy (опечатки). seo_keywords по-прежнему
    // в haystack: «зарплата» находит «Средняя заработная плата».
    const russiaHits = filterSearchIndicators(indicators, qTrim, { limit: MAX_RESULTS })
      .map((ind) => ({
        kind: 'russia',
        key: `ru:${ind.code}`,
        code: ind.code,
        name: ind.name,
        name_en: ind.name_en,
        category: ind.category,
        category_ru: ind.category_ru,
      }));

    const worldHits = (worldSearch?.results || []).map((row) => ({
      kind: 'world',
      key: `world:${row.country_slug}:${row.code}`,
      code: row.code,
      name: row.name || row.name_ru,
      name_en: row.name_en,
      category: row.category,
      country_slug: row.country_slug,
      country_name: row.country_name,
    }));

    return [...russiaHits, ...worldHits];
  }, [qTrim, indicators, worldSearch]);

  const close = useCallback(() => {
    // Брошенный запрос (закрыли без выбора) — сигнал спроса не хуже выбранного.
    const q = (queryRef.current || '').trim();
    if (q.length >= SEARCH_MIN_LEN && !selectedRef.current) {
      track(events.SEARCH_ABANDON, { q: q.slice(0, 120), results: resultsCountRef.current });
    }
    setOpen(false);
    setQuery('');
    setHi(0);
  }, []);

  const go = useCallback((item, position = null) => {
    if (!item?.code) return;
    const q = (queryRef.current || '').trim();
    selectedRef.current = true;
    // position — номер строки в выдаче (1-based): клики по хвосту = сигнал,
    // что ранжирование каталога не совпадает со спросом.
    track(events.SEARCH_SELECT, {
      q: q.slice(0, 120),
      code: item.code,
      ...(item.kind === 'world' ? { country: item.country_slug, scope: 'world' } : { scope: 'russia' }),
      ...(position ? { position } : {}),
    });
    close();
    if (item.kind === 'world' && item.country_slug) {
      navigate(indicatorPath(item.country_slug, item.code));
    } else {
      navigate(russiaIndicatorPath(item.code));
    }
  }, [close, navigate]);

  // Cmd+K / Ctrl+K — открыть; Escape — закрыть; '/' — открыть (если не в инпуте)
  useEffect(() => {
    const onKey = (e) => {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        arm();
        setOpen((o) => !o);
        return;
      }
      if (e.key === '/' && !open) {
        const tag = document.activeElement?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
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
  }, [open, close, arm]);

  // фокус при открытии + сброс состояния спрос-аналитики на новую сессию поиска
  useEffect(() => {
    if (!open) return;
    selectedRef.current = false;
    lastSentRef.current = '';
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open]);

  // Актуальные запрос/число результатов — в refs (для обработчиков close/go).
  useEffect(() => {
    queryRef.current = query;
    resultsCountRef.current = results.length;
  });

  // Debounce-трекинг введённого запроса (введённое, но ещё не отправленное).
  // results.length в момент срабатывания соответствует текущему query.
  useEffect(() => {
    if (!open) return undefined;
    const q = query.trim();
    if (q.length < SEARCH_MIN_LEN) return undefined;
    const count = results.length;
    const t = setTimeout(() => {
      if (q === lastSentRef.current) return;
      lastSentRef.current = q;
      track(events.SEARCH_QUERY, {
        q: q.slice(0, 120),
        results: count,
        context: 'global',
      });
    }, SEARCH_TRACK_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query, open, results.length]);

  const onQueryChange = (v) => {
    setQuery(v);
    setHi(0);
  };

  // прокрутка к выделенному элементу
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-row="${hi}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [hi, open]);

  const handleListKey = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHi((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[hi]) {
      e.preventDefault();
      go(results[hi], hi + 1);
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
          aria-modal="true"
          aria-label={t('search.dialogAria')}
        >
          <button
            type="button"
            aria-label={t('common.close')}
            className="absolute inset-0 bg-text-primary/30 backdrop-blur-[2px]"
            onClick={close}
          />
          <div className="relative w-full max-w-2xl rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/[0.08] overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3 border-b border-border-subtle">
              <Search className="w-4 h-4 text-text-tertiary shrink-0" aria-hidden="true" />
              <input
                ref={inputRef}
                type="search"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                onKeyDown={handleListKey}
                placeholder={t('search.placeholder')}
                className="flex-1 bg-transparent outline-none text-base text-text-primary placeholder:text-text-tertiary"
                aria-label={t('search.queryAria')}
              />
              <button
                type="button"
                onClick={close}
                className={cn(FOCUS_RING, 'rounded-lg p-1 text-text-tertiary hover:text-text-primary')}
                aria-label={t('common.close')}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div ref={listRef} className="max-h-[60vh] overflow-y-auto py-2" role="listbox">
              {results.length === 0 ? (
                <div className="px-4 py-6 text-sm text-text-tertiary">
                  {query.trim()
                    ? t('search.nothingFound', { query: query.trim() })
                    : t('search.empty')}
                </div>
              ) : (
                results.map((item, i) => {
                  const isWorld = item.kind === 'world';
                  const cat = !isWorld
                    ? findCategoryByApiLabel(item.category_ru || item.category)
                    : null;
                  const active = i === hi;
                  const displayName = locale === 'en' && item.name_en ? item.name_en : item.name;
                  const secondaryName = isWorld
                    ? null
                    : (locale === 'en'
                      ? (item.name_en ? item.name : null)
                      : item.name_en);
                  const rightLabel = isWorld
                    ? (item.country_name || item.country_slug)
                    : (locale === 'en'
                      ? (cat?.nameEn || cat?.name)
                      : cat?.name);
                  return (
                    <button
                      key={item.key}
                      type="button"
                      data-row={i}
                      onMouseEnter={() => setHi(i)}
                      onClick={() => go(item, i + 1)}
                      className={cn(
                        'w-full text-left px-4 py-2.5 flex items-center gap-3 transition-colors',
                        active ? 'bg-champagne/10' : 'hover:bg-obsidian-lighter/60',
                      )}
                      role="option"
                      aria-selected={active}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-text-primary truncate">{displayName}</div>
                        {secondaryName && (
                          <div className="text-[11px] font-mono text-text-tertiary truncate">
                            {secondaryName}
                          </div>
                        )}
                        {isWorld && item.category && (
                          <div className="text-[11px] text-text-tertiary truncate">
                            {item.category}
                          </div>
                        )}
                      </div>
                      {rightLabel && (
                        <span className="text-[10px] uppercase tracking-wider font-mono text-text-tertiary shrink-0">
                          {rightLabel}
                        </span>
                      )}
                    </button>
                  );
                })
              )}
            </div>

            <div className="px-4 py-2 border-t border-border-subtle flex items-center gap-4 text-[11px] font-mono text-text-tertiary">
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
