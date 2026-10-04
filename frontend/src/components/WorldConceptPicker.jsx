import { useEffect, useMemo, useRef, useState } from 'react';
import Chip from './Chip';
import ChipGroup, { ChipLink } from './ChipGroup';
import { ChevronDown, Search } from 'lucide-react';
import { homeConceptLabel } from '../lib/homeWorkbench';
import { useT } from '../i18n';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions } from '../lib/searchSynonyms';

/** Выше порога — свёрнутый триггер + панель с поиском (рост до 20+). */
const COLLAPSE_AT = 12;

function labelFor(slug, conceptsBySlug, t) {
  return homeConceptLabel(slug, t, conceptsBySlug.get(slug)?.name || slug);
}

function ConceptChip({
  slug, active, text, mode, linkForSlug, onChange, onPick,
}) {
  if (mode === 'link' && linkForSlug) {
    return (
      <ChipLink
        to={linkForSlug(slug)}
        className="fe-chip--wrap"
        active={active}
        onClick={onPick}
      >
        {text}
      </ChipLink>
    );
  }
  return (
    <Chip
      className="fe-chip--wrap"
      active={active}
      onClick={() => {
        onChange?.(slug);
        onPick?.();
      }}
    >
      {text}
    </Chip>
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
  /** Только на узком экране: одна прокручиваемая лента с затуханием по краям; активный показатель выводится в центр. */
  mobileScroll = false,
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
  const q = searchable ? query.trim() : '';
  const matches = useMemo(() => {
    if (!q) return list;
    return filterSearchOptions(list, q, {
      getSearchItem: (item) => ({ ...item, concept_slug: item.slug, search_label: labelFor(item.slug, conceptsBySlug, t) }),
    });
  }, [list, conceptsBySlug, q, t]);
  // Поле видимо всегда в развёрнутом режиме; в свёртке — только при open.
  useSearchTracking(
    'world-concept-picker',
    collapsed && !open ? '' : query,
    matches.length,
  );
  const activeLabel = labelFor(value, conceptsBySlug, t);

  useEffect(() => {
    if (!mobileScroll) return;
    const row = rootRef.current?.querySelector('.fe-chip-row--mscroll');
    const active = row?.querySelector('[aria-current="page"], [aria-pressed="true"]');
    if (!row || !active || row.scrollWidth <= row.clientWidth) return;
    row.scrollLeft = Math.max(0, active.offsetLeft - (row.clientWidth - active.offsetWidth) / 2);
  }, [mobileScroll, value, matches.length]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const chipStream = (
    <ChipGroup label={sectionLabel} nowrap={nowrap} className={mobileScroll ? 'fe-chip-row--mscroll' : undefined}>
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
        <span className="text-xs text-text-secondary">
          {q ? t('home.map.conceptNotFound', { query }) : t('common.noData')}
        </span>
      )}
    </ChipGroup>
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
            <p className="text-[13px] font-semibold text-text-secondary">
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
        <p className="text-[13px] font-semibold text-text-secondary">
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
