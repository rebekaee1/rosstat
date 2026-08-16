import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Search } from 'lucide-react';
import {
  HOME_COUNTRY_CONCEPT_SHORT,
  WORLD_CONCEPT_GROUPS,
} from '../lib/homeWorkbench';

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

function labelFor(slug, conceptsBySlug) {
  return HOME_COUNTRY_CONCEPT_SHORT[slug]
    || conceptsBySlug.get(slug)?.name
    || slug;
}

function normalize(text) {
  return (text || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^а-яa-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function buildGroups(available, conceptsBySlug, q) {
  const result = [];
  const used = new Set();
  for (const group of WORLD_CONCEPT_GROUPS) {
    const slugs = group.slugs.filter((slug) => {
      if (!available.has(slug)) return false;
      if (!q) return true;
      const hay = normalize(`${labelFor(slug, conceptsBySlug)} ${slug} ${group.label}`);
      return hay.includes(q);
    });
    if (!slugs.length) continue;
    slugs.forEach((slug) => used.add(slug));
    result.push({ ...group, slugs });
  }
  const orphan = [...available].filter((slug) => {
    if (used.has(slug)) return false;
    if (!q) return true;
    return normalize(`${labelFor(slug, conceptsBySlug)} ${slug}`).includes(q);
  });
  if (orphan.length) {
    result.push({ id: 'other', label: 'Другие', slugs: orphan });
  }
  return result;
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
 * Плотный выбор показателя: плашки текут в одном flex-wrap потоке,
 * подпись группы — слева в той же строке. При 12+ — свёртка в выпадающий список.
 */
export default function WorldConceptPicker({
  concepts = [],
  value,
  onChange,
  mode = 'button',
  linkForSlug = null,
  label = 'Показатель',
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const conceptsBySlug = useMemo(
    () => new Map((concepts || []).map((item) => [item.slug, item])),
    [concepts],
  );
  const available = useMemo(
    () => new Set((concepts || []).map((item) => item.slug)),
    [concepts],
  );
  const collapsed = available.size > COLLAPSE_AT;
  const q = normalize(query);
  const groups = useMemo(
    () => buildGroups(available, conceptsBySlug, q),
    [available, conceptsBySlug, q],
  );
  const activeLabel = labelFor(value, conceptsBySlug);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const chipStream = (
    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1.5">
      {groups.map((group, index) => (
        <span key={group.id} className="inline-flex flex-wrap items-center gap-1.5">
          {index > 0 && (
            <span
              aria-hidden="true"
              className="mx-0.5 hidden h-3.5 w-px shrink-0 bg-border-subtle sm:inline-block"
            />
          )}
          <span className="hidden shrink-0 text-[9px] font-mono uppercase tracking-[0.14em] text-text-tertiary sm:inline">
            {group.label}
          </span>
          {group.slugs.map((slug) => (
            <ConceptChip
              key={slug}
              slug={slug}
              active={slug === value}
              text={labelFor(slug, conceptsBySlug)}
              mode={mode}
              linkForSlug={linkForSlug}
              onChange={onChange}
              onPick={() => setOpen(false)}
            />
          ))}
        </span>
      ))}
      {groups.length === 0 && (
        <span className="text-xs text-text-tertiary">Ничего не найдено</span>
      )}
    </div>
  );

  const searchField = (
    <label className="relative block min-w-0">
      <span className="sr-only">Поиск показателя</span>
      <Search
        size={12}
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary"
      />
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Найти"
        className="h-8 w-full max-w-[11rem] rounded-lg border border-border-subtle bg-obsidian-light py-0 pl-7 pr-2 text-xs text-text-primary outline-none focus:border-border-champagne sm:max-w-[13rem]"
      />
    </label>
  );

  if (collapsed) {
    return (
      <div ref={rootRef} className="relative min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {label}
          </p>
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
          {label}
        </p>
        {searchField}
      </div>
      {chipStream}
    </div>
  );
}
