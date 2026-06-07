import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { CATEGORIES } from '../lib/categories';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';

const MAX_RESULTS = 12;

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
export default function IndicatorSearch({ className }) {
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
    setOpen(false);
    setQuery('');
    setHi(0);
  }, []);

  const go = useCallback((code) => {
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

  // фокус при открытии
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open]);

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

  return (
    <>
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

      {open && (
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
        </div>
      )}
    </>
  );
}
