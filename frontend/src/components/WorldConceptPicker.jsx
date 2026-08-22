import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { homeConceptLabel } from '../lib/homeWorkbench';
import { useT } from '../i18n';

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
 * Плотный выбор показателя: плашки одним потоком, без подписей групп и без
 * поискового поля — поиск по показателям пока снят целиком (правка 18),
 * на главной вместо него подсказка со ссылкой на полный список.
 */
export default function WorldConceptPicker({
  concepts = [],
  value,
  onChange,
  mode = 'button',
  linkForSlug = null,
  label,
  hint = null,
}) {
  const t = useT();
  const sectionLabel = label || t('home.map.metricFallback');
  const list = useMemo(() => (concepts || []).filter((item) => item?.slug), [concepts]);
  const conceptsBySlug = useMemo(
    () => new Map(list.map((item) => [item.slug, item])),
    [list],
  );

  const chipStream = (
    <div className="flex flex-wrap items-center gap-1.5">
      {list.map((item) => (
        <ConceptChip
          key={item.slug}
          slug={item.slug}
          active={item.slug === value}
          text={labelFor(item.slug, conceptsBySlug, t)}
          mode={mode}
          linkForSlug={linkForSlug}
          onChange={onChange}
        />
      ))}
      {list.length === 0 && (
        <span className="text-xs text-text-tertiary">{t('common.noData')}</span>
      )}
    </div>
  );

  return (
    <div className="min-w-0">
      <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
          {sectionLabel}
        </p>
      </div>
      {chipStream}
      {hint ? <div className="mt-1.5">{hint}</div> : null}
    </div>
  );
}
