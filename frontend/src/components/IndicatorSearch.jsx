import { Fragment, useState, useEffect, useMemo, useRef, useCallback, useId } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3, Briefcase, Building2, Coins, Fuel, Gem, Globe2, Home, Landmark, MapPin, Percent, Search,
  Tag, TrendingUp, Users, X,
} from 'lucide-react';
import { cn, formatDate, formatValue } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import useGlobalSearch from '../lib/useGlobalSearch';
import { useWorldCountries, useWorldRatingConcepts } from '../lib/worldApi';
import { dedupeSearchRows, describeSearchResult, searchSuggestions, separateVisibleTwins } from '../lib/searchExamples';
import { friendlySearchName } from '../lib/searchGroups';
import { readRecentQueries, rememberQuery } from '../lib/searchRecent';
import { buildSearchView, COUNTRY_CHIPS_VISIBLE } from '../lib/searchView';
import { isGlobalMarketRow, isIndexUnit, isReadableCorrection, openingLabel, plainUnit, searchTopic } from '../lib/searchText';
import { homeConceptLabel } from '../lib/homeWorkbench';
import { splitUnit } from '../lib/countryFlag';
import Chip from './Chip';
import CountryFlag from './CountryFlag';
import EmptyState from './brand/EmptyState';
import { RatingSpark } from './RatingExtras';
import '../styles/shell.css';
import '../styles/w6d.css';
import '../styles/z8-tools.css';
import '../styles/k8-tools.css';

// The palette discovers every public data plane through /search. Empty-query
// suggestions remain small, and typed results preserve geography and slices.
const SEARCH_TRACK_DEBOUNCE_MS = 900;
const SEARCH_MIN_LEN = 2;

const KIND_ICON = { country: Landmark, region: MapPin, subnational_region: MapPin, rating: BarChart3 };
const TOPIC_ICON = {
  labour: Briefcase, prices: Tag, people: Users, energy: Fuel, metal: Gem, money: Coins, rates: Percent,
  housing: Home, output: Building2, state: Landmark, chart: TrendingUp,
};
/** Сколько ждём переход на страницу, прежде чем снять индикатор «Открываем» (панель остаётся, можно повторить). */
const OPENING_TIMEOUT_MS = 12000;
const ENTITY_KINDS = new Set(['country', 'region', 'subnational_region']);
const PERIOD_FORMAT = { daily: 'day', weekly: 'day', monthly: 'full', quarterly: 'quarterly', annual: 'annual' };

/**
 * Подсказка в поле на главной: «Например: Инфляция в Турции». Первый пример стоит неподвижно (виден сразу,
 * без появления), потом раз в 3 секунды плавно сменяется следующим: гаснет за 200 мс и проявляется новым.
 */
function RotatingHint({ lead, items }) {
  const [index, setIndex] = useState(0);
  const [fading, setFading] = useState(false);
  const rootRef = useRef(null);
  useEffect(() => {
    if (items.length < 2) return undefined;
    if (typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;
    let swap = 0;
    let swaps = 0;
    const timer = setInterval(() => {
      // Круг 8: пока человек читает подсказку (курсор над полем или оно в фокусе), текст не меняется; после двух кругов остаётся на месте.
      const field = rootRef.current?.closest('button');
      if (field && (field.matches(':hover') || field === document.activeElement)) return;
      if (swaps >= items.length * 2) { clearInterval(timer); return; }
      swaps += 1;
      setFading(true);
      swap = setTimeout(() => {
        setIndex((i) => (i + 1) % items.length);
        setFading(false);
      }, 200);
    }, 3000);
    return () => {
      clearInterval(timer);
      clearTimeout(swap);
    };
  }, [items.length]);
  return (
    <span ref={rootRef} className="flex-1 min-w-0 truncate text-sm text-text-tertiary">
      {lead}{' '}
      <span className={cn('fe-z8-hint__text text-text-secondary', fading && 'is-fading')}>{items[index % items.length]}</span>
    </span>
  );
}

export default function IndicatorSearch({
  className, variant = 'icon', inlinePlaceholder, examples, initialQuery,
}) {
  const t = useT();
  const { locale } = useLocale();
  const navigate = useNavigate();
  const location = useLocation();
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
  // После выбора панель не исчезает, пока страница не открылась: полоса «Открываем: …» вместо тишины.
  const [opening, setOpening] = useState(null);
  // Подсказка без готового адреса: ищем и открываем лучший результат сами.
  const [autoOpen, setAutoOpen] = useState(null);
  const [expandedKey, setExpandedKey] = useState('');
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
  const suggestions = useMemo(() => searchSuggestions(t), [t]);
  const popular = useMemo(() => suggestions.map((item) => item.text), [suggestions]);
  // Флаги в выдаче: код страны берём из общего (кэшированного) каталога стран, он грузится только при открытом поиске.
  const countriesQ = useWorldCountries({ enabled: shouldLoad && open });
  const flagBySlug = useMemo(() => {
    const map = new Map([['russia', 'RU']]);
    for (const country of countriesQ.data?.countries || []) {
      if (country?.slug && country?.code) map.set(country.slug, country.code);
    }
    return map;
  }, [countriesQ.data]);
  // Каталог рейтингов нужен только для строк «ВВП: рейтинг стран»; грузится, когда есть запрос.
  const ratingQ = useWorldRatingConcepts({ enabled: shouldLoad && open && qTrim.length >= SEARCH_MIN_LEN });
  const ratingConcepts = useMemo(() => ratingQ.data?.concepts || [], [ratingQ.data]);

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
  const detailOf = useCallback((item) => describeSearchResult(item, t, locale), [t, locale]);
  const titleOf = useCallback((item) => friendlySearchName(item, nameOf(item), t, locale), [nameOf, t, locale]);
  const ratingLabelOf = useCallback((concept) => homeConceptLabel(concept.slug, t, concept.name), [t]);
  // Круг 9 (P7): в пустом поле сначала недавние запросы этого браузера, затем примеры. Список читается при каждом открытии окна.
  const recent = useMemo(() => (open ? readRecentQueries() : []), [open]);
  const suggestionRows = useMemo(() => [
    ...recent.map((text, i) => ({
      type: 'suggestion', recent: true, id: `recent:${i}`, item: { kind: 'suggestion', key: `recent:${i}`, path: null }, name: text, query: text, path: null,
    })),
    ...suggestions.map((item, i) => ({
      type: 'suggestion', id: `suggest:${i}`, item: { kind: 'suggestion', key: `suggest:${i}`, path: item.path }, name: item.text, query: item.text, path: item.path,
    })),
  ], [suggestions, recent]);
  // Раскладка: «Страны», «Рейтинги», «Показатели»; вариации частот и страны свёрнуты в строки, лишнее — в «Ещё варианты».
  const view = useMemo(() => {
    if (!qTrim) return null;
    const deduped = dedupeSearchRows(results, nameOf, detailOf);
    // Круг 9 (Q3): одинаково названные на экране ряды разводятся различителем («за год», «к пред. месяцу», «индекс») или склеиваются.
    const { rows: separated, variants } = separateVisibleTwins(deduped, { titleOf, detailOf, nameOf, t });
    const shownTitle = (item) => (variants.has(item.key) ? `${titleOf(item)}, ${variants.get(item.key)}` : titleOf(item));
    return buildSearchView(separated, {
      query: qTrim, intent: globalSearch.data?.intent || null, locale, nameOf, titleOf: shownTitle, detailOf, t, ratingConcepts, ratingLabelOf,
    });
  }, [qTrim, results, nameOf, detailOf, titleOf, t, locale, ratingConcepts, ratingLabelOf, globalSearch.data?.intent]);
  const [moreFor, setMoreFor] = useState('');
  const showMore = Boolean(qTrim) && moreFor === qTrim;
  const rows = useMemo(() => {
    if (!qTrim) return suggestionRows;
    return view ? [...view.flat, ...(showMore ? view.more : [])] : [];
  }, [qTrim, view, showMore, suggestionRows]);
  const hiddenCount = view ? view.hiddenCount : 0;
  // «Ещё: инфляция и цены, курсы валют, ставки (51)»: темы вместо безликих «Ещё варианты».
  const moreLabel = useMemo(() => {
    const topics = (view?.moreTopics || []).filter((id) => id !== 'chart').slice(0, 3)
      .map((id) => String(t(`z8.search.topic.${id}`)).toLocaleLowerCase(locale === 'en' ? 'en' : 'ru'));
    if (!topics.length) return t('shell3.search.moreVariants', { n: hiddenCount });
    return t('z8.search.moreTopics', { topics: topics.join(', '), n: hiddenCount });
  }, [view, hiddenCount, t, locale]);
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
    setOpening(null);
    setAutoOpen(null);
    setExpandedKey('');
  }, []);

  // Открыть страницу: панель остаётся с полосой «Открываем: …», пока адрес не сменился (или 12 секунд).
  const openTarget = useCallback((item, { label = '', position = null } = {}) => {
    if (!item?.path?.startsWith('/') || item.path.startsWith('//') || item.path.includes('\\')) return;
    const q = (queryRef.current || '').trim();
    selectedRef.current = true;
    rememberQuery(q);
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
    const pathname = item.path.split(/[?#]/)[0];
    const shownLabel = openingLabel(label);
    if (item.navigation === 'document') {
      setOpening({ name: shownLabel, pathname });
      window.location.assign(item.path);
      return;
    }
    if (pathname === location.pathname) {
      close();
      navigate(item.path);
      return;
    }
    setOpening({ name: shownLabel, pathname });
    navigate(item.path);
  }, [close, navigate, location.pathname, globalSearch.data?.version]);

  // Страница открылась: панель закрывается сама. Если переход затянулся, полосу снимаем: можно выбрать снова.
  useEffect(() => {
    if (!opening) return undefined;
    // Адрес сменился: закрываем в следующем такте (состояние не меняется прямо в теле эффекта).
    const arrived = opening.pathname === location.pathname;
    const timer = setTimeout(arrived ? close : () => setOpening(null), arrived ? 0 : OPENING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [opening, location.pathname, close]);

  const startAutoOpen = useCallback((row) => {
    setAutoOpen({ q: row.query, label: openingLabel(row.name) });
    globalSearch.flush?.(row.query);
    setQuery(row.query);
    setHi(0);
  }, [globalSearch]);

  const go = useCallback((row, position = null, chipItem = null) => {
    if (row?.type === 'suggestion') {
      // Подсказка с готовым адресом открывает страницу сразу; остальные ищут и открывают лучший результат сами.
      if (row.path) openTarget({ kind: 'suggestion', key: row.id, path: row.path, navigation: 'spa' }, { label: row.name });
      else startAutoOpen(row);
      return;
    }
    const item = chipItem || row?.open || row?.item;
    openTarget(item, { label: chipItem ? (row.name || '') : (row?.name || ''), position });
  }, [openTarget, startAutoOpen]);

  // Автооткрытие: как только пришла выдача на подсказку, открываем лучший показатель (не страну).
  useEffect(() => {
    if (!autoOpen || !view || qTrim !== autoOpen.q || isSearchPending) return undefined;
    const flat = view.flat;
    const target = isSearchError ? null : flat.find((r) => r.type !== 'rating' && !ENTITY_KINDS.has(r.item?.kind)) || flat[0];
    const timer = setTimeout(() => {
      setAutoOpen(null);
      if (target) go(target, 1);
    }, 0);
    return () => clearTimeout(timer);
  }, [autoOpen, view, qTrim, isSearchPending, isSearchError, go]);

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
    // Круг 9 (Q4): фокус ставится сразу, в том же событии нажатия: на iOS клавиатура открывается только так.
    // Таймер остался запасным, если поле смонтировалось позже.
    const focusInput = () => inputRef.current?.focus({ preventScroll: true });
    focusInput();
    const timer = setTimeout(() => { if (document.activeElement !== inputRef.current) focusInput(); }, 30);
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

  const indexById = useMemo(() => new Map(rows.map((row, i) => [row.id, i])), [rows]);
  const renderRow = (row) => {
    const i = indexById.get(row.id);
    return (
      <SearchRow
        key={row.id}
        row={row}
        index={i}
        id={`${resultId}-result-${i}`}
        active={i === highlighted}
        flagCode={flagBySlug.get(row.item?.country_slug) || ''}
        flagBySlug={flagBySlug}
        locale={locale}
        t={t}
        expanded={expandedKey === row.id}
        onToggle={() => setExpandedKey(expandedKey === row.id ? '' : row.id)}
        onHover={setHi}
        onPick={go}
        onQuick={(text) => { onQueryChange(text); inputRef.current?.focus(); }}
      />
    );
  };

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
            'flex items-center gap-2 rounded-full pl-3 pr-3.5 py-1.5 text-text-secondary hover:text-text-primary transition-colors fe-glass-2',
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
            onKeyDown={(event) => {
              // Круг 9 (Q4): символ, набранный на «кнопке-строке», попадает в поле поиска, а не пропадает.
              if (event.key.length !== 1 || event.key === ' ' || event.ctrlKey || event.metaKey || event.altKey || event.nativeEvent?.isComposing) return;
              event.preventDefault();
              arm();
              setQuery(event.key);
              setHi(0);
              setOpen(true);
            }}
            className={cn(
              FOCUS_RING,
              'group w-full flex min-h-14 items-center gap-3 rounded-2xl px-4 py-3.5 text-left fe-press fe-glass-lite',
              'shadow-sm transition-colors',
              className,
            )}
            aria-label={t('search.openAria')}
          >
            <Search className="w-5 h-5 text-text-tertiary shrink-0 group-hover:text-champagne transition-colors" aria-hidden="true" />
            {examples?.length
              ? <RotatingHint lead={t('shell.search.hintLead')} items={examples} />
              : <span className="flex-1 text-sm text-text-tertiary truncate">{placeholder}</span>}
            {/* Подсказка про клавиши только там, где есть клавиатура и мышь: на планшете «⌘K» ничего не говорит. */}
            <kbd className="fe-k8-kbd fe-search-trigger-kbd hidden pointer-fine:inline">
              {isAppleModKey ? '⌘K' : 'Ctrl K'}
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
            'rounded-xl flex items-center justify-center p-1.5 text-text-secondary hover:text-text-primary transition-colors [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11 fe-glass-2',
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
            className="absolute inset-0 fe-k8-scrim"
            onClick={close}
          />
          <div className="fe-dialog-panel fe-search-panel relative flex max-h-[calc(100dvh-1.5rem)] w-full max-w-2xl flex-col rounded-2xl shadow-2xl overflow-hidden sm:max-h-[calc(90dvh-1rem)]">
            <div className="fe-search-field fe-k8-well relative flex shrink-0 items-center gap-3 px-4 py-1">
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
                onClick={() => {
                  // Крестик сначала очищает запрос, и только пустое поле закрывает окно.
                  if (query) { setAutoOpen(null); onQueryChange(''); inputRef.current?.focus(); } else close();
                }}
                className={cn(FOCUS_RING, 'fe-press flex min-h-11 min-w-11 items-center justify-center rounded-xl p-1 text-text-tertiary hover:text-text-primary')}
                aria-label={query ? t('w6d.search.clear') : t('common.close')}
              >
                <X className="w-5 h-5" />
              </button>
              <span className="fe-search-progress" data-active={isLoading && qTrim ? 'true' : 'false'} aria-hidden="true" />
            </div>

            <p id={`${resultId}-help`} className="px-4 pt-3 pb-1 text-xs leading-relaxed text-text-secondary [@media(pointer:coarse)]:sr-only">
              {t('search.help')}
            </p>

            {qTrim && !isLoading && rows.length > 0 && globalSearch.data?.corrected_query && globalSearch.data.corrected_query !== qTrim
              && isReadableCorrection(globalSearch.data.corrected_query) && (
              <div className="px-4 py-2 text-sm text-text-secondary" role="status">
                {t('c9b.search.showingFor', { query: globalSearch.data.corrected_query })}
              </div>
            )}

            <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain py-2 sm:max-h-[60vh]" role="listbox" id={`${resultId}-list`} aria-busy={isLoading}>
              {opening || (autoOpen && qTrim === autoOpen.q) ? (
                <div className="w6d-open-progress" role="status" aria-live="polite" data-testid="search-opening">
                  <span className="w6d-open-progress__bar" aria-hidden="true" />
                  <span className="fe-search-spinner shrink-0" aria-hidden="true" />
                  <span className="min-w-0 break-words">{t('w6d.search.opening', { name: (opening?.name || autoOpen?.label || '') })}</span>
                </div>
              ) : null}
              {!qTrim ? (
                <div role="group" aria-labelledby={`${resultId}-${recent.length ? 'recent' : 'popular'}`} className={opening ? 'pointer-events-none opacity-60' : undefined}>
                  {recent.length > 0 && (
                    <p id={`${resultId}-recent`} className="px-4 pb-1 pt-1 text-sm font-semibold text-text-secondary">
                      {t('c9b.search.recent')}
                    </p>
                  )}
                  {rows.map((row, i) => (
                    <Fragment key={row.id}>
                      {i === recent.length && (
                        <p id={recent.length ? undefined : `${resultId}-popular`} className="px-4 pb-1 pt-1 text-sm font-semibold text-text-secondary">
                          {t('shell.search.popular')}
                        </p>
                      )}
                      <SearchRow
                        row={row}
                        index={i}
                        id={`${resultId}-result-${i}`}
                        active={i === highlighted}
                        onHover={setHi}
                        onPick={go}
                        onWarm={() => { if (!row.path) globalSearch.prefetch?.(row.query); }}
                      />
                    </Fragment>
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
                              <EmptyState variant="no-results" size={80} title={t('search.nothingFound', { query: qTrim })} />
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
                <div className={opening ? 'pointer-events-none opacity-60' : undefined}>
                  {view?.sections.map((section) => (
                    <div key={section.id} role="group" aria-labelledby={`${resultId}-sec-${section.id}`} className="w6d-sr-group">
                      <p id={`${resultId}-sec-${section.id}`} className="w6d-sr-title">{t(`w6d.search.section.${section.id}`)}</p>
                      {section.rows.map((row) => renderRow(row))}
                    </div>
                  ))}
                  {showMore && view?.more.length > 0 && view.moreGroups.map((group) => (
                    <div key={group.id} role="group" aria-labelledby={`${resultId}-more-${group.id}`} className="w6d-sr-group">
                      <p id={`${resultId}-more-${group.id}`} className="w6d-sr-title">
                        {t('w6d.search.section.more')}: {t(`z8.search.topic.${group.id}`)}
                      </p>
                      {group.rows.map((row) => renderRow(row))}
                    </div>
                  ))}
                  {globalSearch.data?.has_more && !isLoading && (
                    <p className="px-4 pb-2 pt-3 text-sm text-text-secondary">{t('search.refine')}</p>
                  )}
                </div>
              )}
            </div>

            {qTrim && hiddenCount > 0 && !isLoading ? (
              <button
                type="button"
                className={cn(FOCUS_RING, 'fe-search-more fe-press shrink-0')}
                aria-expanded={showMore}
                onClick={() => setMoreFor(showMore ? '' : qTrim)}
              >
                {showMore ? t('shell3.search.fewerVariants') : moreLabel}
              </button>
            ) : null}

            <div className="fe-search-kbd px-4 pb-3 pt-2 flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-tertiary [@media(pointer:coarse)]:hidden">
              <span><kbd className="fe-k8-kbd">↑</kbd> <kbd className="fe-k8-kbd">↓</kbd> {t('search.hint.nav')}</span>
              <span><kbd className="fe-k8-kbd">Enter</kbd> {t('search.hint.open')}</span>
              <span><kbd className="fe-k8-kbd">Esc</kbd> {t('search.hint.close')}</span>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}

/** Последнее значение строки: «4,0 %, август 2026» (число и месяц по языку страницы). */
function latestText(item, locale, t) {
  const latest = item?.latest;
  if (!latest || latest.value == null || !Number.isFinite(Number(latest.value))) return '';
  const abs = Math.abs(Number(latest.value));
  const short = splitUnit(plainUnit(String(item.unit || '').trim(), locale)).short;
  // Годовой процент читается как «34,9 % за 2025» (один знак после запятой), остальное как «4,00 %, август 2026».
  const yearPercent = item.frequency === 'annual' && /%/.test(short);
  const value = formatValue(latest.value, yearPercent ? 1 : abs >= 10000 ? 0 : abs >= 100 ? 1 : 2, locale);
  const period = latest.date ? formatDate(latest.date, PERIOD_FORMAT[item.frequency] || 'full', locale) : '';
  const shown = short ? `${value}\u00A0${short}` : value;
  const hasPeriod = period && period !== '—';
  if (hasPeriod && yearPercent && typeof t === 'function') {
    return t('z8.search.valueForYear', { value: shown, period });
  }
  return [shown, hasPeriod ? period : ''].filter(Boolean).join(', ');
}

/**
 * Одна строка выдачи: значок по теме, название, подпись «где и как часто», последнее значение с мини-графиком.
 * Строка-семья несёт переключатель частот, строка «по странам» — кнопки стран; сама строка открывает главное.
 */
function SearchRow({
  row, index, id, active, flagCode = '', flagBySlug = null, locale = 'ru', t, expanded = false, onToggle, onHover, onPick, onWarm, onQuick,
}) {
  const isSuggestion = row.type === 'suggestion';
  const item = row.item || {};
  const globalMarket = !isSuggestion && isGlobalMarketRow(item);
  const Icon = isSuggestion ? Search : KIND_ICON[item.kind] || TOPIC_ICON[searchTopic(item)] || TrendingUp;
  // Страна — её флаг вместо значка; у региона и показателя значок темы, а флаг страны — маленьким бейджем в углу.
  // Мировая цена (нефть, газ) получает глобус: чужой флаг на ней сбивает с толку.
  const flagAsIcon = item.kind === 'country' && Boolean(flagCode);
  const flagBadge = !isSuggestion && !flagAsIcon && !globalMarket && row.type !== 'byCountry' && row.type !== 'rating' && Boolean(flagCode);
  const isValueRow = row.type === 'item' || row.type === 'family';
  // Индекс без базы («1 645,7») ничего не говорит: число уходит в «Подробнее», в строке остаётся название.
  const indexRow = isValueRow && isIndexUnit(item.unit);
  const rawValue = isValueRow ? latestText(item, locale, t) : '';
  const value = indexRow ? '' : rawValue;
  const spark = (row.type === 'item' || row.type === 'family') && Array.isArray(item.spark) && item.spark.length >= 3
    ? item.spark.map((v) => ({ value: v })) : null;
  const countries = row.type === 'byCountry' ? row.countries : [];
  const shownCountries = expanded ? countries : countries.slice(0, COUNTRY_CHIPS_VISIBLE);
  return (
    <div className="w6d-sr-row">
      <button
        type="button"
        data-row={index}
        id={id}
        onMouseEnter={() => { onHover(index); onWarm?.(); }}
        onFocus={onWarm}
        onTouchStart={onWarm}
        onClick={() => onPick(row, index + 1)}
        className={cn(
          'fe-search-row w-full min-h-14 text-left px-3 py-2.5 flex items-center gap-3 transition-colors',
          active && 'is-active',
        )}
        role="option"
        tabIndex={-1}
        aria-selected={active}
      >
        <span className="fe-search-row__tile relative grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-champagne/10 text-champagne-ink" aria-hidden="true">
          {flagAsIcon ? <CountryFlag code={flagCode} className="fe-search-row__flag" /> : <Icon size={18} />}
          {flagBadge ? <CountryFlag code={flagCode} className="fe-search-row__badge" /> : null}
          {globalMarket ? <Globe2 className="w6d-sr-globe" size={14} /> : null}
        </span>
        <span className="min-w-0 flex-1">
          <span className="w6d-sr-name block text-[15px] font-medium leading-snug text-text-primary">{row.name}</span>
          {row.detail ? <span className="mt-0.5 block text-[13px] leading-snug text-text-secondary whitespace-normal break-words">{row.detail}</span> : null}
          {value ? (
            <span className="w6d-sr-value">
              <strong>{value}</strong>
              {spark ? <RatingSpark points={spark} width={56} height={20} label={t('w6d.search.trendAria')} /> : null}
            </span>
          ) : indexRow && rawValue ? (
            // Круг 9 (Q3): число индекса видно сразу, с подписью «Значение индекса»; раньше оно пряталось за «Подробнее».
            <span className="w6d-sr-value">
              <span className="w6d-sr-value__label">{t('c9b.search.indexValueLabel')}</span>
              <strong>{rawValue}</strong>
            </span>
          ) : null}
        </span>
      </button>
      {row.type === 'family' ? (
        <div className="w6d-sr-chips" role="group" aria-label={t('w6d.search.freqAria')}>
          {row.chips.map((chip) => (
            <button
              key={chip.frequency}
              type="button"
              className="w6d-sr-chip fe-press"
              aria-current={chip.item === row.item ? 'true' : undefined}
              onClick={() => onPick(row, index + 1, chip.item)}
            >
              {t(`w6d.search.freq.${chip.frequency}`)}
            </button>
          ))}
        </div>
      ) : null}
      {row.quick?.length ? (
        <div className="w6d-sr-chips" role="group" aria-label={t('c9b.search.quickAria')}>
          {row.quick.map((chip) => (
            <button key={chip.id} type="button" className="w6d-sr-chip fe-press" onClick={() => onQuick?.(chip.query)}>{chip.label}</button>
          ))}
        </div>
      ) : null}
      {row.type === 'byCountry' ? (
        <div className="w6d-sr-chips">
          {row.rating ? (
            <button type="button" className="w6d-sr-chip fe-press" onClick={() => onPick(row, index + 1, row.rating)}>
              <BarChart3 size={15} aria-hidden="true" />
              {t('w6d.search.ratingChip')}
            </button>
          ) : null}
          {shownCountries.map((country) => (
            <button
              key={country.key}
              type="button"
              className="w6d-sr-chip fe-press"
              onClick={() => onPick(row, index + 1, country)}
            >
              {flagBySlug?.get(country.country_slug) ? <CountryFlag code={flagBySlug.get(country.country_slug)} /> : null}
              {country.country_name}
            </button>
          ))}
          {countries.length > COUNTRY_CHIPS_VISIBLE ? (
            <button type="button" className="w6d-sr-chip fe-press" aria-expanded={expanded} onClick={onToggle}>
              {expanded ? t('w6d.search.countryLess') : t('w6d.search.countryMore', { n: countries.length - COUNTRY_CHIPS_VISIBLE })}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
