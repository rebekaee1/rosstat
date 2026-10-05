import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity, Banknote, BarChart3, Briefcase, ChevronDown, Coins, Landmark, LayoutGrid, Percent,
  PiggyBank, Scale, Search, TrendingUp, Users,
} from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { cn } from '../lib/format';
import { homeConceptLabel } from '../lib/homeWorkbench';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { groupRatingConcepts, quickRatingConcepts, ratingIconKey } from '../lib/ratingConcepts';
import { localizeWorldUnit, prefetchWorldMapSeries } from '../lib/worldApi';
import { splitUnit } from '../lib/countryFlag';
import '../styles/w6d.css';
import '../styles/z6-rating.css';

const ICONS = {
  banknote: Banknote,
  coins: Coins,
  scale: Scale,
  trending: TrendingUp,
  briefcase: Briefcase,
  activity: Activity,
  landmark: Landmark,
  piggy: PiggyBank,
  percent: Percent,
  users: Users,
  chart: BarChart3,
};

function ConceptIcon({ slug, size = 18 }) {
  const Icon = ICONS[ratingIconKey(slug)] || BarChart3;
  return <Icon size={size} aria-hidden="true" />;
}

/**
 * Выбор показателя рейтинга: быстрая полоса популярных и кнопка «Все показатели», которая раскрывает
 * крупные плитки по группам (значок, название, единица) с поиском. Каждая плитка — ссылка, так что адрес
 * показателя можно скопировать. Соседние показатели подгружаются заранее: к нажатию данные уже в кэше.
 */
export default function RatingMetricPicker({
  concepts = [], value, linkForSlug, label, onPick = null,
  // Справка («Что это за показатель») ложится в ту же строку, а не под плиту; `loading` рисует заглушки чипов.
  trailing = null, loading = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const queryClient = useQueryClient();
  const panelId = useId().replaceAll(':', '');
  const rootRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const list = useMemo(() => (concepts || []).filter((item) => item?.slug), [concepts]);
  const nameOf = (item) => homeConceptLabel(item.slug, t, item.name || item.slug);
  const quick = useMemo(() => quickRatingConcepts(list), [list]);
  const needle = query.trim();
  const matches = useMemo(() => {
    if (!needle) return list;
    return filterSearchOptions(list, needle, {
      getSearchItem: (item) => ({ ...item, concept_slug: item.slug, search_label: homeConceptLabel(item.slug, t, item.name) }),
    });
  }, [list, needle, t]);
  const groups = useMemo(() => groupRatingConcepts(matches), [matches]);
  const showSearch = list.length > 6;
  const activeItem = list.find((item) => item.slug === value);

  // Закрытие по Escape и касанию вне панели.
  useEffect(() => {
    if (!open) return undefined;
    const outside = (event) => { if (!rootRef.current?.contains(event.target)) setOpen(false); };
    const key = (event) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', key, true);
    return () => {
      document.removeEventListener('pointerdown', outside, true);
      document.removeEventListener('keydown', key, true);
    };
  }, [open]);

  // Соседние показатели грузим в простое страницы: два следующих по порядку каталога.
  useEffect(() => {
    if (!list.length || !value) return undefined;
    const at = list.findIndex((item) => item.slug === value);
    const next = [list[(at + 1) % list.length], list[(at + 2) % list.length]]
      .filter((item) => item && item.slug !== value);
    const timer = setTimeout(() => {
      next.forEach((item) => prefetchWorldMapSeries(queryClient, item.slug, locale));
    }, 1200);
    return () => clearTimeout(timer);
  }, [list, value, queryClient, locale]);

  const warm = (slug) => () => prefetchWorldMapSeries(queryClient, slug, locale);
  const pick = (slug) => {
    setOpen(false);
    setQuery('');
    onPick?.(slug);
  };

  const tile = (item) => {
    const active = item.slug === value;
    const unit = splitUnit(localizeWorldUnit(item.unit, locale)).short;
    return (
      <Link
        key={item.slug}
        to={linkForSlug(item.slug)}
        className={cn('w6d-tile fe-press', active && 'is-active')}
        aria-current={active ? 'page' : undefined}
        onPointerEnter={warm(item.slug)}
        onFocus={warm(item.slug)}
        onTouchStart={warm(item.slug)}
        onClick={() => pick(item.slug)}
      >
        <span className="w6d-tile__icon"><ConceptIcon slug={item.slug} /></span>
        <span className="w6d-tile__text">
          <span className="w6d-tile__name">{nameOf(item)}</span>
          {unit ? <span className="w6d-tile__unit">{unit}</span> : null}
        </span>
      </Link>
    );
  };

  return (
    <div ref={rootRef} className="w6d-picker">
      <p className="w6d-picker__label">{label}</p>
      <div className="w6d-picker__bar">
        <div className="w6d-picker__quick" role="group" aria-label={label}>
          {quick.map((item) => {
            const active = item.slug === value;
            return (
              <Link
                key={item.slug}
                to={linkForSlug(item.slug)}
                className={cn('w6d-quick fe-press', active && 'is-active')}
                aria-current={active ? 'page' : undefined}
                onPointerEnter={warm(item.slug)}
                onFocus={warm(item.slug)}
                onTouchStart={warm(item.slug)}
                onClick={() => pick(item.slug)}
              >
                <ConceptIcon slug={item.slug} size={16} />
                {nameOf(item)}
              </Link>
            );
          })}
          {loading && quick.length === 0 && [0, 1, 2, 3].map((i) => (
            <span key={i} className="z6-quick-ghost" aria-hidden="true" />
          ))}
        </div>
        <button
          type="button"
          className={cn('w6d-picker__all fe-press', open && 'is-open')}
          aria-expanded={open}
          aria-controls={panelId}
          disabled={list.length === 0}
          onClick={() => setOpen((previous) => !previous)}
        >
          <LayoutGrid size={16} aria-hidden="true" />
          <span>{t('z6.rating.otherMetric')}</span>
          <ChevronDown size={15} aria-hidden="true" className="w6d-picker__chev" />
        </button>
        {trailing ? <div className="z6-picker__trailing">{trailing}</div> : null}
      </div>
      {activeItem && !quick.some((item) => item.slug === value) && (
        <p className="w6d-picker__current">
          <ConceptIcon slug={value} size={15} />
          {t('w6d.rating.shown', { name: nameOf(activeItem) })}
        </p>
      )}
      {open && (
        <div id={panelId} className="w6d-picker__panel fe-reveal" role="group" aria-label={t('w6d.rating.allMetricsTitle')}>
          {showSearch && (
            <label className="w6d-picker__search">
              <Search size={16} aria-hidden="true" />
              <span className="sr-only">{t('w6d.rating.searchMetric')}</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('w6d.rating.searchMetric')}
                enterKeyHint="search"
                autoComplete="off"
              />
            </label>
          )}
          {groups.map((group) => (
            <section key={group.id} className="w6d-group" aria-label={t(group.labelKey)}>
              <h3 className="w6d-group__title">{t(group.labelKey)}</h3>
              <div className="w6d-group__tiles">{group.items.map(tile)}</div>
            </section>
          ))}
          {groups.length === 0 && (
            <p className="w6d-picker__empty" role="status">{t('home.map.conceptNotFound', { query: needle })}</p>
          )}
        </div>
      )}
    </div>
  );
}
