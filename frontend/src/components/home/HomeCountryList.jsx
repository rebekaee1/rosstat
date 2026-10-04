import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, Globe2 } from 'lucide-react';
import {
  formatWorldValue,
  groupCountriesByRegion,
  pluralRu,
  useWorldCountries,
} from '../../lib/worldApi';
import { HOME_MAP_RUSSIA_COUNTRY, countryPublicName, homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { countryFlag } from '../../lib/countryFlag';
import { countryPath, russiaHomePath } from '../../lib/sitePaths';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';

function CountryMark({ code }) {
  // Флаг вместо двухбуквенного кода; для не-ISO кодов — нейтральный глобус, а не «XX».
  const flag = countryFlag(code);
  return (
    <span
      className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-champagne/20 bg-champagne/[0.08] text-xl leading-none"
      aria-hidden="true"
    >
      {flag || <Globe2 size={18} className="text-champagne-ink" />}
    </span>
  );
}

function CountryCard({ country }) {
  const t = useT();
  const { locale } = useLocale();
  const n = Number(country.indicators_count || 0);
  const indicatorsLabel = locale === 'en'
    ? (n === 1 ? t('homehero.catalog.indicator_one') : t('homehero.catalog.indicator_many'))
    : pluralRu(n, [
      t('homehero.catalog.indicator_one'), t('homehero.catalog.indicator_few'), t('homehero.catalog.indicator_many'),
    ]);
  const primary = countryPublicName(country, locale);

  return (
    <Link
      to={country.slug === 'russia' ? russiaHomePath() : countryPath(country.slug)}
      onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'country', code: country.code })}
      className="group fe-press flex min-h-16 items-center gap-3 rounded-xl border border-border-subtle bg-surface px-3 py-2.5 transition-all hover:border-border-champagne hover:shadow-sm"
    >
      <CountryMark code={country.code} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[15px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne-ink">
          {primary}
        </div>
        {n > 0 ? (
          <div className="mt-0.5 text-xs text-text-secondary tabular-nums">
            {formatWorldValue(n, 0)} {indicatorsLabel}
          </div>
        ) : null}
      </div>
      <ChevronRight size={16} className="shrink-0 text-text-tertiary transition-colors group-hover:text-champagne-ink" aria-hidden="true" />
    </Link>
  );
}

const PENDING_REGIONS = ['europe', 'americas', 'asia', 'africa', 'oceania']
  .map((id) => ({ id, region: id, countries: [] }));

function RegionSection({ group, open, onToggle, loading = false }) {
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
        className="fe-press flex min-h-14 w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-surface-hover"
      >
        <ChevronDown
          size={16}
          className={`shrink-0 text-text-tertiary transition-transform ${open ? '' : '-rotate-90'}`}
        />
        <span className="min-w-0 flex-1 truncate text-[15px] font-semibold text-text-primary">
          {t(`world.region.${group.id}`, group.region)}
        </span>
        <span className="shrink-0 text-xs text-text-secondary tabular-nums">
          {loading ? '…' : `${n} ${countWord}`}
        </span>
      </button>
      {open && (
        <div id={panelId} className="grid gap-2 border-t border-border-subtle p-3 sm:grid-cols-2 sm:gap-2.5 sm:p-4">
          {loading
            ? [0, 1, 2, 3].map((i) => <SkeletonBox key={i} className="h-16 rounded-xl" />)
            : group.countries.map((country) => (
              <CountryCard key={country.slug} country={country} />
            ))}
        </div>
      )}
    </div>
  );
}

/**
 * Список стран внизу главной: разделы по регионам, свёрнутые по умолчанию.
 * Раскрывается по клику — иначе до Океании пришлось бы листать всю Европу.
 * Россия входит в Европу — карточка ведёт в российский раздел.
 */
export default function HomeCountryList({ russiaSeriesCount = 0 }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading, isError, refetch, isFetching } = useWorldCountries();
  const [openRegions, setOpenRegions] = useState(() => new Set());

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

  const countriesTotal = homeScopeCountriesCount(data);
  const countriesWord = locale === 'en'
    ? t('world.unit.country_many')
    : pluralRu(countriesTotal || 0, [
      t('world.unit.country_one'), t('world.unit.country_few'), t('world.unit.country_many'),
    ]);

  const toggle = (id) => {
    setOpenRegions((prev) => {
      const next = new Set(prev);
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
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-champagne-ink">
            {t('home.countries.eyebrow')}
          </div>
          <h2
            id="home-countries-title"
            className="mt-1 text-lg font-semibold text-text-primary"
          >
            {t('home.countries.title')}
          </h2>
          {countriesTotal ? (
            <p className="mt-1 text-sm text-text-secondary">
              {t('homehero.catalog.lead', { n: countriesTotal, word: countriesWord })}
            </p>
          ) : null}
        </div>
        <div className="mb-1.5 h-px min-w-[4rem] flex-1 bg-border-subtle" />
      </div>

      {isError && (
        <ApiRetryBanner className="mb-4" onRetry={() => refetch()} isFetching={isFetching}>
          {t('home.countries.loadError')}
        </ApiRetryBanner>
      )}

      <div className="space-y-2">
        {(isLoading ? PENDING_REGIONS : groups).map((group) => (
          <RegionSection
            key={group.id}
            group={group}
            open={openRegions.has(group.id)}
            onToggle={() => toggle(group.id)}
            loading={isLoading}
          />
        ))}
      </div>
    </section>
  );
}
