import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { CATEGORIES } from '../lib/categories';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';

const MAX_RESULTS = 12;
const SEARCH_TRACK_DEBOUNCE_MS = 900;
const SEARCH_MIN_LEN = 2;

/**
 * Поиск по индикаторам (правка №1 из звонка 2026-05-21).
 *
 * UX — command-palette: маленькая кнопка с лупой в Navbar открывает modal
 * по центру экрана. Внутри modal — большой инпут + до 12 результатов +
 * клавиатурная навигация (стрелки, Enter, Esc). Хоткеи Cmd+K / Ctrl+K
 * открывают modal из любой точки приложения. На мобильных — full-screen
 * sheet (тот же компонент, breakpoint в стилях).
 *
 * Источник данных — React-Query `useIndicators()`. Фильтр — substring без
 * учёта регистра по name + name_en + category + code.
 *
 * Звонок 2026-05-22: показываем ВСЕ active-индикаторы, включая скрытые
 * из листинга каталога (exports-monthly, exports-yoy, services-*-monthly,
 * deposit-rate-medium, и т.д.). Логика: каталог — это **витрина**, поиск —
 * **директория**. Пользователь набирает «экспорт» и ожидает увидеть все
 * варианты: помесячно, квартально, к г/г, к кварталу.
 */
export default function IndicatorSearch({ className, variant = 'icon', inlinePlaceholder }) {
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

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return indicators.slice(0, MAX_RESULTS);
    }
    return indicators
      .filter((ind) => {
        // seo_keywords содержит синонимы/корни («зарплата», «оплата труда»,
        // «инфляция», «ИПЦ» и т.д.) — критично для substring-поиска,
        // потому что name «Средняя заработная плата» не содержит подстроку
        // «зарпл» (нужны keywords с разными формами слова).
        const haystack = `${ind.name || ''} ${ind.name_en || ''} ${ind.category || ''} ${ind.code || ''} ${ind.seo_keywords || ''}`.toLowerCase();
        return haystack.includes(q);
      })
      .slice(0, MAX_RESULTS);
  }, [query, indicators]);

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

  const go = useCallback((code) => {
    const q = (queryRef.current || '').trim();
    selectedRef.current = true;
    track(events.SEARCH_SELECT, { q: q.slice(0, 120), code });
    close();
    navigate(`/indicator/${code}`);
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
      track(events.SEARCH_QUERY, { q: q.slice(0, 120), results: count });
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
      setHi((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[hi]) {
      e.preventDefault();
      go(results[hi].code);
    }
  };

  const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform || '');

  const placeholder = inlinePlaceholder || 'Найдите индикатор — например, инфляция, ВВП или ключевая ставка';

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
          aria-label={`Открыть поиск индикаторов (${isMac ? '⌘' : 'Ctrl'}+K)`}
          title={`Поиск индикаторов (${isMac ? '⌘' : 'Ctrl'}+K)`}
        >
          <Search className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span className="text-sm font-medium">Поиск</span>
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
          aria-label="Открыть поиск индикаторов"
        >
          <Search className="w-4 h-4 text-text-tertiary shrink-0 group-hover:text-champagne transition-colors" aria-hidden="true" />
          <span className="flex-1 text-sm text-text-tertiary truncate">{placeholder}</span>
          <kbd className="hidden sm:inline text-[10px] font-mono text-text-tertiary border border-border-subtle rounded px-1.5 py-0.5">
            {isMac ? '⌘K' : 'Ctrl+K'}
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
          aria-label={`Открыть поиск индикаторов (${isMac ? '⌘' : 'Ctrl'}+K)`}
          title={`Поиск индикаторов (${isMac ? '⌘' : 'Ctrl'}+K)`}
        >
          <Search className="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      )}

      {open && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[200] flex items-start justify-center pt-[10vh] px-4"
          role="dialog"
          aria-modal="true"
          aria-label="Поиск индикаторов"
        >
          <button
            type="button"
            aria-label="Закрыть"
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
                placeholder="Поиск индикатора по названию или категории…"
                className="flex-1 bg-transparent outline-none text-base text-text-primary placeholder:text-text-tertiary"
                aria-label="Поисковый запрос"
              />
              <button
                type="button"
                onClick={close}
                className={cn(FOCUS_RING, 'rounded-lg p-1 text-text-tertiary hover:text-text-primary')}
                aria-label="Закрыть"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div ref={listRef} className="max-h-[60vh] overflow-y-auto py-2" role="listbox">
              {results.length === 0 ? (
                <div className="px-4 py-6 text-sm text-text-tertiary">
                  {query.trim()
                    ? `Ничего не нашли по запросу «${query.trim()}».`
                    : 'Начните вводить название индикатора.'}
                </div>
              ) : (
                results.map((ind, i) => {
                  const cat = CATEGORIES.find((c) => c.apiCategory === ind.category);
                  const active = i === hi;
                  return (
                    <button
                      key={ind.code}
                      type="button"
                      data-row={i}
                      onMouseEnter={() => setHi(i)}
                      onClick={() => go(ind.code)}
                      className={cn(
                        'w-full text-left px-4 py-2.5 flex items-center gap-3 transition-colors',
                        active ? 'bg-champagne/10' : 'hover:bg-obsidian-lighter/60',
                      )}
                      role="option"
                      aria-selected={active}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-text-primary truncate">{ind.name}</div>
                        {ind.name_en && (
                          <div className="text-[11px] font-mono text-text-tertiary truncate">
                            {ind.name_en}
                          </div>
                        )}
                      </div>
                      {cat && (
                        <span className="text-[10px] uppercase tracking-wider font-mono text-text-tertiary shrink-0">
                          {cat.name}
                        </span>
                      )}
                    </button>
                  );
                })
              )}
            </div>

            <div className="px-4 py-2 border-t border-border-subtle flex items-center gap-4 text-[11px] font-mono text-text-tertiary">
              <span><kbd className="px-1 py-0.5 rounded border border-border-subtle">↑</kbd> <kbd className="px-1 py-0.5 rounded border border-border-subtle">↓</kbd> навигация</span>
              <span><kbd className="px-1 py-0.5 rounded border border-border-subtle">Enter</kbd> открыть</span>
              <span><kbd className="px-1 py-0.5 rounded border border-border-subtle">Esc</kbd> закрыть</span>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
