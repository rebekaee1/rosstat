import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight } from 'lucide-react';
import {
  formatWorldValue,
  groupCountriesByRegion,
  pluralRu,
  useWorldCountries,
} from '../../lib/worldApi';
import { HOME_MAP_RUSSIA_COUNTRY } from '../../lib/homeWorkbench';
import { countryPath, russiaHomePath } from '../../lib/sitePaths';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';

function CountryMark({ code }) {
  return (
    <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-champagne/20 bg-champagne/[0.08] font-mono text-[11px] font-semibold tracking-tight text-champagne">
      {code}
    </span>
  );
}

function CountryCard({ country }) {
  const t = useT();
  const { locale } = useLocale();
  const n = Number(country.indicators_count || 0);
  const seriesLabel = locale === 'en'
    ? (n === 1 ? t('world.unit.series_one') : t('world.unit.series_many'))
    : pluralRu(n, [t('world.unit.series_one'), t('world.unit.series_few'), t('world.unit.series_many')]);

  return (
    <Link
      to={country.slug === 'russia' ? russiaHomePath() : countryPath(country.slug)}
      onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'country', code: country.code })}
      className="group flex items-center gap-2 rounded-xl border border-border-subtle bg-surface px-3 py-3 transition-all hover:border-border-champagne hover:shadow-sm sm:gap-2.5"
    >
      <CountryMark code={country.code} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne">
          {country.name}
        </div>
        <div className="mt-0.5 truncate font-mono text-[11px] text-text-tertiary">
          {country.name_en}
        </div>
      </div>
      <div className="w-12 shrink-0 text-right sm:w-14">
        <div className="font-mono text-[13px] font-semibold tabular-nums text-text-primary">
          {n > 0 ? formatWorldValue(n, 0) : '—'}
        </div>
        <div className="text-[10px] text-text-tertiary">{seriesLabel}</div>
      </div>
      <ChevronRight size={14} className="hidden shrink-0 text-text-tertiary transition-colors group-hover:text-champagne sm:block" />
    </Link>
  );
}

function RegionSection({ group, open, onToggle }) {
  const t = useT();
  const { locale } = useLocale();
  const panelId = `home-countries-${group.id}`;
  const n = group.countries.length;
  const countWord = locale === 'en'
    ? (n === 1 ? t('world.unit.country_one') : t('world.unit.country_many'))
    : pluralRu(n, [t('world.unit.country_one'), t('world.unit.country_few'), t('world.unit.country_many')]);
  return (
    <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface/60">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-surface-hover"
      >
        <ChevronDown
          size={16}
          className={`shrink-0 text-text-tertiary transition-transform ${open ? '' : '-rotate-90'}`}
        />
        <span className="min-w-0 flex-1 truncate text-[15px] font-semibold text-text-primary">
          {t(`world.region.${group.id}`, group.region)}
        </span>
        <span className="shrink-0 font-mono text-[11px] text-text-tertiary">
          {n} {countWord}
        </span>
      </button>
      {open && (
        <div id={panelId} className="grid gap-2 border-t border-border-subtle p-3 sm:grid-cols-2 sm:gap-2.5 sm:p-4">
          {group.countries.map((country) => (
            <CountryCard key={country.slug} country={country} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Список стран внизу главной: разделы по регионам, свёрнутые по умолчанию,
 * чтобы до Океании не приходилось листать всю Европу.
 * Россия входит в Европу — карточка ведёт в российский раздел.
 */
export default function HomeCountryList({ russiaSeriesCount = 0 }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading, isError, refetch, isFetching } = useWorldCountries();
  // Первый регион раскрыт: иначе главная заканчивается пятью пустыми полосами.
  const [openRegions, setOpenRegions] = useState(null);

  const groups = useMemo(() => {
    const listed = Number(russiaSeriesCount) || 0;
    const list = [...(data?.countries || [])].map((country) => {
      if ((country.slug === 'russia' || country.code === 'RU') && !Number(country.indicators_count) && listed > 0) {
        return { ...country, indicators_count: listed };
      }
      return country;
    });
    if (!list.some((c) => c.slug === 'russia' || c.code === 'RU')) {
      list.push({
        ...HOME_MAP_RUSSIA_COUNTRY,
        indicators_count: listed,
        name: locale === 'en' ? HOME_MAP_RUSSIA_COUNTRY.name_en : HOME_MAP_RUSSIA_COUNTRY.name,
      });
    }
    return groupCountriesByRegion(list, { locale });
  }, [data?.countries, locale, russiaSeriesCount]);

  const expanded = openRegions ?? new Set(groups.length ? [groups[0].id] : []);

  const toggle = (id) => {
    setOpenRegions((prev) => {
      const next = new Set(prev ?? (groups.length ? [groups[0].id] : []));
      if (next.has(id)) next.delete(id);
      else {
        next.add(id);
        track(events.HOME_COUNTRIES_CTA, { target: 'region-expand', region: id });
      }
      return next;
    });
  };

  return (
    <section
      id="countries"
      data-block="home-countries"
      className="scroll-mt-28"
      aria-labelledby="home-countries-title"
    >
      <div className="mb-4 flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
            {t('home.countries.eyebrow')}
          </div>
          <h2
            id="home-countries-title"
            className="mt-1 text-base font-semibold text-text-primary sm:text-lg"
          >
            {t('home.countries.title')}
          </h2>
        </div>
        <div className="mb-1.5 h-px min-w-[4rem] flex-1 bg-border-subtle" />
      </div>

      {isError && (
        <ApiRetryBanner className="mb-4" onRetry={() => refetch()} isFetching={isFetching}>
          {t('home.countries.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => <SkeletonBox key={i} className="h-14 rounded-2xl" />)}
        </div>
      ) : (
        <div className="space-y-2">
          {groups.map((group) => (
            <RegionSection
              key={group.id}
              group={group}
              open={expanded.has(group.id)}
              onToggle={() => toggle(group.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
