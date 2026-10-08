// Первый шаг «Сравнения»: выбор страны. Без вложенной прокрутки (список не перехватывает свайп страницы):
// поиск, быстрые подборки («G7», «БРИКС»; в русской версии ещё «Соседи России») и сетка стран с флагами; полный список — по кнопке.
// Английская версия: страны идут по размеру ВВП, Россия не первая и без отдельной подборки «соседей».
import { useMemo, useState } from 'react';
import { Landmark, Search, X } from 'lucide-react';
import Button from '../Button';
import Chip from '../Chip';
import { SkeletonBox } from '../Skeleton';
import { flagForSlug, COUNTRY_GROUPS } from '../../lib/slugFlags';
import { cn } from '../../lib/format';
import { useLocale, useT } from '../../i18n';
import { orderCountriesByGdp } from '../../lib/countryOrder';
import '../../styles/regions-w4.css';

/** Русская версия: страны, которые люди сравнивают чаще всего, показываются первыми, пока список свёрнут. */
const POPULAR = [
  'russia', 'germany', 'united-states', 'china', 'france', 'united-kingdom',
  'italy', 'japan', 'india', 'brazil', 'turkey', 'poland',
];
const COLLAPSED_COUNT = 12;
/** Подборки, которых нет в английской версии. */
const HIDDEN_GROUPS_EN = new Set(['neighbors']);
const GROUP_LABEL_KEYS = {
  g7: 'w4.compare.group.g7',
  brics: 'w4.compare.group.brics',
  neighbors: 'w4.compare.group.neighbors',
};

function Flag({ slug }) {
  const flag = flagForSlug(slug);
  return (
    <span className="fe-flag" aria-hidden="true">
      {flag || <Landmark className="h-4 w-4 text-champagne-ink" />}
    </span>
  );
}

export default function CompareCountryStep({
  countries, query, onQuery, onSelect,
  indicatorMatches = [], matchesPending = false, onAddIndicator, atCap = false, capHint,
  loading = false,
  restrictNote = '',
}) {
  const t = useT();
  const { locale } = useLocale();
  const english = locale === 'en';
  const [group, setGroup] = useState('all');
  const [expanded, setExpanded] = useState(false);
  const searching = query.trim().length > 0;
  const groups = useMemo(
    () => COUNTRY_GROUPS.filter((g) => !(english && HIDDEN_GROUPS_EN.has(g.id))),
    [english],
  );

  const visible = useMemo(() => {
    if (searching) return countries;
    // Английская версия: весь список по размеру ВВП (первые строки — крупнейшие экономики), Россия на своём месте.
    const ordered = english ? orderCountriesByGdp(countries, (c) => c.key) : countries;
    if (group !== 'all') {
      const slugs = groups.find((g) => g.id === group)?.slugs || [];
      const members = slugs.map((slug) => ordered.find((c) => c.key === slug)).filter(Boolean);
      return english ? orderCountriesByGdp(members, (c) => c.key) : members;
    }
    if (expanded || ordered.length <= COLLAPSED_COUNT) return ordered;
    if (english) return ordered.slice(0, COLLAPSED_COUNT);
    const popular = POPULAR.map((slug) => ordered.find((c) => c.key === slug)).filter(Boolean);
    const rest = ordered.filter((c) => !popular.includes(c));
    return [...popular, ...rest].slice(0, COLLAPSED_COUNT);
  }, [countries, searching, group, expanded, english, groups]);

  const canExpand = !searching && group === 'all' && !expanded && countries.length > COLLAPSED_COUNT;
  const noCountries = countries.length === 0;
  const waitingCatalog = loading && !searching && countries.length <= 1;

  return (
    <div>
      <div className="mb-2 text-sm font-medium text-text-secondary">{t('compare.country')}</div>
      <div className="mb-3 flex items-center gap-2 rounded-xl px-3 transition-colors fe-glass-2">
        <Search className="h-4 w-4 shrink-0 text-text-tertiary" aria-hidden="true" />
        <input
          type="text"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={t('compare.findCountry')}
          aria-label={t('compare.findCountryAria')}
          className="min-h-12 min-w-0 flex-1 bg-transparent text-[15px] text-text-primary outline-none placeholder:text-text-tertiary"
        />
        {query && (
          <button
            type="button"
            aria-label={t('common.clear')}
            onClick={() => onQuery('')}
            className="fe-map-btn shrink-0 text-text-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {!searching && (
        <div className="fe-scroll-row mb-3" role="group" aria-label={t('w4.compare.groupsAria')}>
          <Chip active={group === 'all'} onClick={() => { setGroup('all'); setExpanded(false); }}>
            {t('w4.compare.group.all')}
          </Chip>
          {groups.map((g) => (
            <Chip key={g.id} active={group === g.id} onClick={() => setGroup(g.id)}>
              {t(GROUP_LABEL_KEYS[g.id])}
            </Chip>
          ))}
        </div>
      )}

      {restrictNote && !searching && (
        <p className="mb-3 text-xs leading-snug text-text-secondary" data-testid="compare-country-restrict">{restrictNote}</p>
      )}

      {noCountries && indicatorMatches.length > 0 ? (
        <div data-testid="compare-indicator-matches" className="overflow-hidden rounded-xl fe-glass-2">
          <div className="px-4 py-2.5 text-sm leading-snug text-text-secondary fe-divider-b">
            {t('compare.indicatorMatches')}
          </div>
          {indicatorMatches.map((ind) => (
            <button
              key={ind.code}
              type="button"
              disabled={atCap}
              title={atCap ? capHint : undefined}
              onClick={() => onAddIndicator(ind)}
              className="fe-tap fe-press flex min-h-12 w-full items-center gap-3 px-4 py-2.5 text-left transition-colors last:border-b-0 hover:bg-obsidian-lighter disabled:cursor-not-allowed disabled:opacity-60 fe-glass-2"
            >
              <Flag slug="russia" />
              <span className="min-w-0 flex-1 break-words leading-snug text-[15px] text-text-primary">{ind.label}</span>
              <span className="shrink-0 text-xs text-text-secondary">{t('compare.russia')}</span>
            </button>
          ))}
        </div>
      ) : noCountries ? (
        <div role="status" className="rounded-xl px-4 py-6 text-center text-sm text-text-secondary fe-glass-2">
          <Search className="mx-auto mb-2 h-5 w-5 text-champagne-ink" aria-hidden="true" />
          <p>{t(matchesPending ? 'common.loading' : 'w4.compare.noCountry')}</p>
          {!matchesPending && query && (
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => onQuery('')}>
              {t('w4.compare.clearSearch')}
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="fe-compare-countries grid grid-cols-2 content-start gap-2">
            {visible.map((c) => (
              <button
                key={c.key}
                type="button"
                onClick={() => onSelect(c.key)}
                className={cn(
                  'fe-tap fe-press flex min-h-12 min-w-0 items-center gap-2.5 rounded-xl px-3 text-left fe-glass-2',
                  'transition-colors hover:bg-obsidian-lighter',
                )}
              >
                <Flag slug={c.key} />
                <span className="min-w-0 flex-1 line-clamp-2 text-[15px] leading-snug text-text-primary">{c.label}</span>
              </button>
            ))}
            {waitingCatalog && (
              <>
                <span className="sr-only" role="status" aria-busy="true">{t('common.loading')}</span>
                {Array.from({ length: Math.max(0, COLLAPSED_COUNT - visible.length) }, (_, i) => (
                  <SkeletonBox key={`sk-${i}`} className="h-12 rounded-xl" />
                ))}
              </>
            )}
          </div>
          {canExpand && (
            <Button variant="secondary" className="mt-3 w-full" onClick={() => setExpanded(true)}>
              {t('w4.compare.showAll', { n: countries.length })}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
