import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Globe2, Search } from 'lucide-react';
import {
  groupCountriesByRegion,
  pluralRu,
  useWorldCompareSnapshot,
  useWorldCountries,
  useWorldMapSeries,
} from '../../lib/worldApi';
import { buildCountryFacts, formatEconomySize, formatPercentValue } from '../../lib/countryFacts';
import Sparkline from '../Sparkline';
import { HOME_MAP_RUSSIA_COUNTRY, countryPublicName, homeScopeCountriesCount } from '../../lib/homeWorkbench';
import { countryFlag } from '../../lib/countryFlag';
import { countryPath, russiaHomePath } from '../../lib/sitePaths';
import { SkeletonBox } from '../Skeleton';
import Chip from '../Chip';
import ChipGroup from '../ChipGroup';
import ApiRetryBanner from '../ApiRetryBanner';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import '../../styles/shell.css';

/** Сколько стран видно, пока человек не искал и не раскрыл список: хватает на два экрана телефона. */
const COLLAPSED_COUNT = 12;

function CountryMark({ code }) {
  // Флаг вместо двухбуквенного кода; для не-ISO кодов — нейтральный глобус, а не «XX».
  const flag = countryFlag(code);
  return (
    <span className="fe-country-row__flag" aria-hidden="true">
      {flag || <Globe2 size={18} className="text-champagne-ink" />}
    </span>
  );
}

function CountryRow({ country, regionLabel, facts }) {
  const t = useT();
  const { locale } = useLocale();
  const primary = countryPublicName(country, locale);
  const economy = facts ? formatEconomySize(facts.economyBn, locale) : '';
  const inflation = facts && Number.isFinite(facts.inflation) ? formatPercentValue(facts.inflation, locale) : '';
  const unemployment = facts && Number.isFinite(facts.unemployment) ? formatPercentValue(facts.unemployment, locale) : '';
  const hasFacts = Boolean(economy || inflation || unemployment);
  const spark = facts?.spark?.length > 1 ? facts.spark : null;
  return (
    <Link
      // Карточка ведёт на обзор страны (главные цифры и все темы), а не на отдельный показатель.
      to={country.slug === 'russia' ? russiaHomePath() : countryPath(country.slug)}
      onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'country', code: country.code })}
      className="fe-country-row fe-press group"
    >
      <CountryMark code={country.code} />
      <span className="min-w-0 flex-1">
        <span className="fe-country-row__name">{primary}</span>
        {regionLabel ? <span className="fe-country-row__meta">{regionLabel}</span> : null}
        {hasFacts ? (
          <span className="fe-country-row__facts">
            {economy ? <span><span className="fe-country-row__fact-label">{t('w6b.catalog.gdp')}</span>{economy}</span> : null}
            {inflation ? <span><span className="fe-country-row__fact-label">{t('w6b.catalog.inflation')}</span>{inflation}</span> : null}
            {unemployment ? <span><span className="fe-country-row__fact-label">{t('w6b.catalog.unemployment')}</span>{unemployment}</span> : null}
          </span>
        ) : null}
      </span>
      {spark ? (
        <span className="fe-country-row__spark" aria-hidden="true">
          <Sparkline points={spark} trend="flat" sentiment="neutral" height={34} />
        </span>
      ) : null}
      <ChevronRight size={16} className="fe-country-row__chevron" aria-hidden="true" />
    </Link>
  );
}

function normalize(text) {
  return String(text || '').toLocaleLowerCase().replace(/ё/g, 'е').trim();
}

/**
 * Каталог стран внизу главной: один список по алфавиту, поиск и фильтр по региону.
 * Без счётчиков «Африка — 1 страна»: малые регионы не должны выглядеть как неполный каталог.
 * Пока человек ничего не искал, видны первые строки и кнопка «Показать все»; поиск и регион раскрывают всё.
 * Россия входит в Европу — строка ведёт в российский раздел.
 */
export default function HomeCountryList({ russiaSeriesCount = 0 }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading, isError, refetch, isFetching } = useWorldCountries();
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('all');
  const [expanded, setExpanded] = useState(false);
  const [sort, setSort] = useState('alpha');
  // Те же ответы, что у карты и рейтинга главной: общий кэш, лишних запросов нет.
  const gdpQ = useWorldCompareSnapshot('gdp-usd');
  const inflationQ = useWorldCompareSnapshot('hicp-index');
  const unemploymentQ = useWorldCompareSnapshot('unemployment-rate');
  const gdpSeriesQ = useWorldMapSeries('gdp-usd');
  const facts = useMemo(() => buildCountryFacts({
    gdp: gdpQ.data,
    inflation: inflationQ.data,
    unemployment: unemploymentQ.data,
    gdpSeries: gdpSeriesQ.data,
  }), [gdpQ.data, inflationQ.data, unemploymentQ.data, gdpSeriesQ.data]);

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

  const regionLabel = (group) => t(`world.region.${group.id}`, group.region);

  // Единый список по алфавиту: регион остаётся подписью строки и фильтром.
  const entries = useMemo(() => {
    const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
    return groups
      .flatMap((group) => group.countries.map((country) => ({
        country,
        regionId: group.id,
        regionName: t(`world.region.${group.id}`, group.region),
        name: countryPublicName(country, locale),
      })))
      .sort((a, b) => collator.compare(a.name, b.name));
  }, [groups, locale, t]);
  // «По размеру экономики»: крупные сверху, страны без значения в конце (по алфавиту).
  const ordered = useMemo(() => {
    if (sort !== 'size') return entries;
    const size = (entry) => facts.get(entry.country.code)?.economyBn;
    return [...entries].sort((a, b) => {
      const sa = size(a);
      const sb = size(b);
      const ha = Number.isFinite(sa);
      const hb = Number.isFinite(sb);
      if (ha && hb) return sb - sa;
      if (ha !== hb) return ha ? -1 : 1;
      return 0;
    });
  }, [entries, facts, sort]);

  const needle = normalize(query);
  const filtered = useMemo(() => ordered.filter((entry) => {
    if (region !== 'all' && entry.regionId !== region) return false;
    if (!needle) return true;
    return normalize(entry.name).includes(needle)
      || normalize(entry.country.name_en).includes(needle)
      || normalize(entry.country.name).includes(needle);
  }), [ordered, region, needle]);

  const narrowed = Boolean(needle) || region !== 'all';
  const collapsible = !narrowed && filtered.length > COLLAPSED_COUNT;
  const visible = collapsible && !expanded ? filtered.slice(0, COLLAPSED_COUNT) : filtered;

  const countriesTotal = homeScopeCountriesCount(data);
  const countriesWord = locale === 'en'
    ? t('world.unit.country_many')
    : pluralRu(countriesTotal || 0, [
      t('world.unit.country_one'), t('world.unit.country_few'), t('world.unit.country_many'),
    ]);

  const pickRegion = (id) => {
    setRegion(id);
    setExpanded(false);
    if (id !== 'all') track(events.HOME_COUNTRIES_CTA, { target: 'region-expand', region: id });
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
            {sort === 'size' ? t('w6b.catalog.titleSize') : t('shell3.catalog.title')}
          </h2>
          {countriesTotal ? (
            <p className="mt-1 text-sm text-text-secondary">
              {t('shell3.catalog.lead', { n: countriesTotal, word: countriesWord })}
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

      <div className="fe-country-tools">
        <label className="fe-country-search">
          <span className="sr-only">{t('shell3.catalog.search')}</span>
          <Search size={18} aria-hidden="true" className="fe-country-search__icon" />
          <input
            type="search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setExpanded(false); }}
            placeholder={t('shell3.catalog.search')}
            autoComplete="off"
            className="fe-country-search__input"
            disabled={isLoading}
          />
        </label>
        <ChipGroup
          label={t('shell3.catalog.regionsAria')}
          nowrap
          className="fe-fade-x fe-country-regions"
        >
          <Chip active={region === 'all'} onClick={() => pickRegion('all')}>{t('shell3.catalog.all')}</Chip>
          {groups.map((group) => (
            <Chip key={group.id} active={region === group.id} onClick={() => pickRegion(group.id)}>
              {regionLabel(group)}
            </Chip>
          ))}
        </ChipGroup>
        <ChipGroup label={t('w6b.catalog.sortAria')} nowrap className="fe-fade-x fe-country-sort">
          <Chip active={sort === 'alpha'} onClick={() => { setSort('alpha'); setExpanded(false); }}>{t('w6b.catalog.sortAlpha')}</Chip>
          <Chip active={sort === 'size'} onClick={() => { setSort('size'); setExpanded(false); }}>{t('w6b.catalog.sortSize')}</Chip>
        </ChipGroup>
      </div>

      {isLoading ? (
        <div className="fe-country-grid" aria-hidden="true">
          {[0, 1, 2, 3, 4, 5].map((i) => <SkeletonBox key={i} className="h-14 rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="fe-country-empty" role="status">
          <p>{t('shell3.catalog.nothing')}</p>
          <Chip onClick={() => { setQuery(''); pickRegion('all'); }}>{t('shell3.catalog.reset')}</Chip>
        </div>
      ) : (
        <ul className="fe-country-grid">
          {visible.map((entry) => (
            <li key={entry.country.slug}>
              <CountryRow country={entry.country} regionLabel={entry.regionName} facts={facts.get(entry.country.code)} />
            </li>
          ))}
        </ul>
      )}

      {collapsible && !isLoading ? (
        <div className="mt-3 flex justify-center">
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((open) => !open)}
            className="fe-country-more fe-press"
          >
            {expanded
              ? t('shell3.catalog.showLess')
              : t('shell3.catalog.showAll', { n: filtered.length })}
          </button>
        </div>
      ) : null}
    </section>
  );
}
