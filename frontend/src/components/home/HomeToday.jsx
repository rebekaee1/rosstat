import { useId, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useWorldCompareSnapshot, useWorldCountries } from '../../lib/worldApi';
import { buildTodayTiles, parseShownNumber } from '../../lib/homeToday';
import { formatValue } from '../../lib/format';
import { countryPublicName, mapSelectHref } from '../../lib/homeWorkbench';
import { countryFlag } from '../../lib/countryFlag';
import { worldRatingPath } from '../../lib/sitePaths';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import { SkeletonBox } from '../Skeleton';
import CountUp from './CountUp';
import '../../styles/z3-home.css';

const BAR_STEP = 4;
const BAR_WIDTH = 2.6;
const BAR_AREA = 22;

/**
 * Лесенка всех стран в порядке рейтинга: столбики-«стёкла», выбранная страна золотая и выше соседей.
 * Чисто декоративна, смысл дублирует подпись «место N из M». Градиенты заданы в самом SVG (у каждого экземпляра свой id).
 */
function Ladder({ ladder }) {
  const gid = `g${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const count = ladder.bars.length;
  return (
    <svg
      className="fe-today__ladder"
      viewBox={`0 0 ${count * BAR_STEP - (BAR_STEP - BAR_WIDTH)} ${BAR_AREA}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={`${gid}-glass`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="1" stopColor="#C9A24D" stopOpacity="0.42" />
        </linearGradient>
        <linearGradient id={`${gid}-gold`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F3E4B8" />
          <stop offset="0.45" stopColor="#C9A24D" />
          <stop offset="1" stopColor="#8F6B24" />
        </linearGradient>
      </defs>
      {ladder.bars.map((height, index) => {
        const h = Math.max(2, height * BAR_AREA);
        return (
          <rect
            key={index}
            className={index === ladder.mark ? 'is-mark' : undefined}
            fill={`url(#${gid}-${index === ladder.mark ? 'gold' : 'glass'})`}
            x={index * BAR_STEP}
            y={BAR_AREA - h}
            width={BAR_WIDTH}
            height={h}
            rx="0.6"
            style={{ '--i': index }}
          />
        );
      })}
    </svg>
  );
}

function TodayTile({ tile, href, countriesByCode }) {
  const t = useT();
  const { locale } = useLocale();
  const catalog = countriesByCode.get(tile.item.country_code);
  const flag = countryFlag(tile.item.country_code);
  const place = tile.id === 'median'
    ? t('z3.today.median.place', { n: tile.total })
    : tile.country;
  const label = t(`z3.today.${tile.id}.label`, { country: tile.country || '' });
  const caption = t(`z3.today.${tile.id}.caption`)
    + (tile.year ? `, ${tile.year}` : '');
  const rank = t('z3.today.rank', { rank: tile.ladder.rank, total: tile.ladder.total });
  const shown = useMemo(() => {
    const parsed = parseShownNumber(tile.value.num, locale);
    if (!parsed) return null;
    const { prefix, digits, suffix } = parsed;
    return { parsed, format: (n) => `${prefix}${formatValue(n, digits, locale)}${suffix}` };
  }, [tile.value.num, locale]);
  return (
    <Link
      to={href}
      onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'today-tile', tile: tile.id, code: tile.item.country_code })}
      className="fe-today__tile fe-press fe-glint fe-cursor-light"
      data-tile={tile.id}
      title={catalog ? countryPublicName(catalog, locale) : undefined}
    >
      <span className="fe-today__label">{label}</span>
      <span className="fe-today__value">
        <span className="fe-today__num">
          {shown
            ? <CountUp value={shown.parsed.value} format={shown.format} text={tile.value.num} group="today" />
            : tile.value.num}
        </span>
        <span className="fe-today__unit">{tile.value.unit}</span>
      </span>
      <span className="fe-today__place">
        {flag && tile.id !== 'median' ? <span className="fe-today__flag" aria-hidden="true">{flag}</span> : null}
        <span className="fe-today__country">{place}</span>
      </span>
      <span className="fe-today__caption">{caption}</span>
      <span className="fe-today__rank">
        <Ladder ladder={tile.ladder} />
        <span className="fe-today__rank-text">{rank}</span>
      </span>
    </Link>
  );
}

/**
 * «Мир сейчас»: четыре крупных факта под поиском на главной (левая колонка героя).
 * Берёт готовые срезы ВВП, инфляции и безработицы: те же ответы, что у планеты и каталога стран, отдельных запросов нет.
 * Пока срезы грузятся, показывает каркас той же высоты; если данных не хватает, блок не рисуется.
 */
export default function HomeToday() {
  const t = useT();
  const { locale } = useLocale();
  const countriesQ = useWorldCountries();
  const gdpQ = useWorldCompareSnapshot('gdp-usd');
  const inflationQ = useWorldCompareSnapshot('hicp-index');
  const unemploymentQ = useWorldCompareSnapshot('unemployment-rate');

  const countriesByCode = useMemo(
    () => new Map((countriesQ.data?.countries || []).map((country) => [country.code, country])),
    [countriesQ.data],
  );
  const tiles = useMemo(() => buildTodayTiles({
    gdp: gdpQ.data,
    inflation: inflationQ.data,
    unemployment: unemploymentQ.data,
    locale,
    countriesByCode,
    localeName: (country) => countryPublicName(country, locale),
  }), [gdpQ.data, inflationQ.data, unemploymentQ.data, locale, countriesByCode]);

  const pending = (gdpQ.isLoading || inflationQ.isLoading || unemploymentQ.isLoading) && tiles.length === 0;
  if (!pending && tiles.length < 2) return null;

  return (
    <section
      data-block="home-today"
      className="fe-today fe-reveal"
      style={{ '--fe-delay': '0.1s' }}
      aria-labelledby="home-today-title"
      aria-busy={pending || undefined}
    >
      <header className="fe-today__head">
        <h2 id="home-today-title" className="fe-today__title">
          <span className="fe-today__pulse" aria-hidden="true" />
          {t('z3.today.title')}
        </h2>
        <p className="fe-today__sub">{t('z3.today.sub')}</p>
      </header>
      {pending ? (
        <div className="fe-today__grid" aria-hidden="true">
          {[0, 1, 2, 3].map((index) => <SkeletonBox key={index} className="fe-today__skeleton" />)}
        </div>
      ) : (
        <ul className="fe-today__grid">
          {tiles.map((tile) => {
            const country = countriesByCode.get(tile.item.country_code)
              || { code: tile.item.country_code, slug: tile.item.country_slug };
            const href = tile.id === 'median'
              ? worldRatingPath(tile.concept)
              : mapSelectHref(country, tile.item, { conceptSlug: tile.concept }) || worldRatingPath(tile.concept);
            return (
              <li key={tile.id}>
                <TodayTile tile={tile} href={href} countriesByCode={countriesByCode} />
              </li>
            );
          })}
        </ul>
      )}
      {!pending ? (
        <Link
          to={worldRatingPath('gdp-usd')}
          onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'today-all' })}
          className="fe-today__all fe-press"
        >
          {t('z3.today.all')}
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      ) : null}
    </section>
  );
}
