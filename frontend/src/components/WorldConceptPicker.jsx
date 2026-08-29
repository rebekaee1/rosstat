import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Search } from 'lucide-react';
import { homeConceptLabel } from '../lib/homeWorkbench';
import { useT } from '../i18n';
import useSearchTracking from '../lib/useSearchTracking';

/** Выше порога — свёрнутый триггер + панель с поиском (рост до 20+). */
const COLLAPSE_AT = 12;

function chipClass(active) {
  return [
    'rounded-xl px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap',
    active
      ? 'bg-champagne/15 text-champagne'
      : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
  ].join(' ');
}

function labelFor(slug, conceptsBySlug, t) {
  return homeConceptLabel(slug, t, conceptsBySlug.get(slug)?.name || slug);
}

function normalize(text) {
  return (text || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^а-яa-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Поисковая база показателя: подпись, код и синонимы из реестра понятий
 * (`keywords` приходит с API). Благодаря синонимам «дефицит бюджета» находит
 * сальдо бюджета, а «цены» — инфляцию.
 */
function haystack(concept, slug, conceptsBySlug, t) {
  const keywords = Array.isArray(concept?.keywords) ? concept.keywords.join(' ') : '';
  return normalize(`${labelFor(slug, conceptsBySlug, t)} ${concept?.name || ''} ${slug} ${keywords}`);
}

function ConceptChip({
  slug, active, text, mode, linkForSlug, onChange, onPick,
}) {
  if (mode === 'link' && linkForSlug) {
    return (
      <Link
        to={linkForSlug(slug)}
        className={chipClass(active)}
        aria-current={active ? 'page' : undefined}
        onClick={onPick}
      >
        {text}
      </Link>
    );
  }
  return (
    <button
      type="button"
      className={chipClass(active)}
      aria-pressed={active}
      onClick={() => {
        onChange?.(slug);
        onPick?.();
      }}
    >
      {text}
    </button>
  );
}

/**
 * Плотный выбор показателя: плашки одним потоком, без подписей групп.
 * Поиск включается по умолчанию; при длинном списке (выше COLLAPSE_AT)
 * сворачивается в триггер с выпадающей панелью и полем поиска.
 */
export default function WorldConceptPicker({
  concepts = [],
  value,
  onChange,
  mode = 'button',
  linkForSlug = null,
  label,
  searchable = true,
  hint = null,
  trailing = null,
  /** Одна горизонтальная полоса без переноса (главная / мобилка). */
  nowrap = false,
}) {
  const t = useT();
  const sectionLabel = label || t('home.map.metricFallback');
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const list = useMemo(() => (concepts || []).filter((item) => item?.slug), [concepts]);
  const conceptsBySlug = useMemo(
    () => new Map(list.map((item) => [item.slug, item])),
    [list],
  );
  const collapsed = searchable && list.length > COLLAPSE_AT;
  const q = searchable ? normalize(query) : '';
  const matches = useMemo(() => {
    if (!q) return list;
    return list.filter((item) => haystack(item, item.slug, conceptsBySlug, t).includes(q));
  }, [list, conceptsBySlug, q, t]);
  // Поле видимо всегда в развёрнутом режиме; в свёртке — только при open.
  useSearchTracking(
    'world-concept-picker',
    collapsed && !open ? '' : query,
    matches.length,
  );
  const activeLabel = labelFor(value, conceptsBySlug, t);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const chipStream = (
    <div
      className={
        nowrap
          ? 'scrollbar-hide flex flex-nowrap items-center gap-1.5 overflow-x-auto overscroll-x-contain pb-0.5'
          : 'flex flex-wrap items-center gap-1.5'
      }
    >
      {matches.map((item) => (
        <ConceptChip
          key={item.slug}
          slug={item.slug}
          active={item.slug === value}
          text={labelFor(item.slug, conceptsBySlug, t)}
          mode={mode}
          linkForSlug={linkForSlug}
          onChange={onChange}
          onPick={() => setOpen(false)}
        />
      ))}
      {matches.length === 0 && (
        <span className="text-xs text-text-tertiary">
          {q ? t('home.map.conceptNotFound', { query }) : t('common.noData')}
        </span>
      )}
    </div>
  );

  const searchField = (
    <label className="relative block min-w-0">
      <span className="sr-only">{t('common.search')}</span>
      <Search
        size={12}
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary"
      />
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t('common.search')}
        className="h-8 w-full max-w-[11rem] rounded-lg border border-border-subtle bg-obsidian-light py-0 pl-7 pr-2 text-xs text-text-primary outline-none focus:border-border-champagne sm:max-w-[13rem]"
      />
    </label>
  );

  if (collapsed) {
    return (
      <div ref={rootRef} className="relative min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
              {sectionLabel}
            </p>
            {trailing}
          </div>
        </div>
        <button
          type="button"
          className="inline-flex h-9 max-w-full items-center gap-2 rounded-xl border border-border-subtle bg-surface px-3 text-left text-sm font-medium text-text-primary transition-colors hover:border-border-champagne"
          aria-expanded={open}
          aria-haspopup="listbox"
          onClick={() => setOpen((prev) => !prev)}
        >
          <span className="min-w-0 truncate">{activeLabel}</span>
          <ChevronDown size={14} className={`shrink-0 text-text-tertiary transition ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && (
          <div
            className="absolute left-0 right-0 z-30 mt-1.5 max-h-[min(20rem,50vh)] overflow-y-auto rounded-xl border border-border-subtle bg-surface p-3 shadow-lg sm:right-auto sm:min-w-[22rem]"
            role="listbox"
          >
            <div className="mb-2">{searchField}</div>
            {chipStream}
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="min-w-0">
      <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
          {sectionLabel}
        </p>
        {trailing}
        {searchable ? searchField : null}
      </div>
      {chipStream}
      {hint ? <div className="mt-1.5">{hint}</div> : null}
    </div>
  );
}
