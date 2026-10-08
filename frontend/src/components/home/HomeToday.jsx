import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useWorldCompareSnapshot, useWorldCountries } from '../../lib/worldApi';
import { buildTodayTiles, parseShownNumber } from '../../lib/homeToday';
import { formatValue } from '../../lib/format';
import { countryPublicName, mapSelectHref } from '../../lib/homeWorkbench';
import { countryFlag } from '../../lib/countryFlag';
import { worldRatingPath } from '../../lib/sitePaths';
import { formatWorldPeriod } from '../../lib/worldMapPeriod';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import { SkeletonBox } from '../Skeleton';
import CountUp from './CountUp';
import '../../styles/z3-home.css';

/**
 * Шкала места: гладкая трубка «жидкое золото» и камень-самоцвет на ней. Позиция камня по рангу: первое место в самом начале,
 * последнее в конце. Чисто декоративна, смысл дублирует подпись «Место N из M» под ней (поэтому aria-hidden).
 */
function RankScale({ ladder }) {
  const span = Math.max(1, ladder.total - 1);
  const pos = Math.min(1, Math.max(0, (ladder.rank - 1) / span));
  return (
    <span
      className={'fe-today__scale' + (ladder.rank === 1 ? ' is-first' : '')}
      style={{ '--fe-rank-pos': pos }}
      aria-hidden="true"
    >
      <i className="fe-today__gem" />
    </span>
  );
}

function TodayTile({ tile, href, countriesByCode }) {
  const t = useT();
  const { locale } = useLocale();
  const catalog = countriesByCode.get(tile.item.country_code);
  const flag = countryFlag(tile.item.country_code);
  const place = tile.country;
  const label = t(`z3.today.${tile.id}.label`, { country: tile.country || '' });
  // Год общей строкой в заголовке блока («за последний доступный год»), а не в каждой карточке: годы у стран разные, и «2025» рядом с «2026» читалось как ошибка.
  const caption = t(`z3.today.${tile.id}.caption`);
  // Круг 9 (H7): у «худшей» страны (самые высокие цены) и «лучшей» (самая низкая безработица) слово «место 1» читалось как награда или как итог рейтинга.
  // Подпись говорит прямо: «самая высокая из 55», «самая низкая из 55». Для ВВП остаётся «Место 1 из 55».
  const rank = tile.ladder.rank === 1 && tile.id === 'prices'
    ? t('c9b.today.rankHighest', { total: tile.ladder.total })
    : tile.ladder.rank === 1 && tile.id === 'jobs'
      ? t('c9b.today.rankLowest', { total: tile.ladder.total })
      : t('z3.today.rank', { rank: tile.ladder.rank, total: tile.ladder.total });
  // Период рядом с подписью: годы у стран разные, и «30,9 %» без «декабрь 2025» нечем проверить.
  const period = formatWorldPeriod(tile.item.date, tile.item.frequency === 'annual' ? 'annual' : 'full');
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
        {flag ? <span className="fe-today__flag" aria-hidden="true">{flag}</span> : null}
        <span className="fe-today__country">{place}</span>
      </span>
      <span className="fe-today__caption">
        {caption}
        {period ? <span className="fe-today__period">{period}</span> : null}
      </span>
      <span className="fe-today__rank">
        <RankScale ladder={tile.ladder} />
        <span className="fe-today__rank-text">{rank}</span>
      </span>
    </Link>
  );
}

/**
 * «Мир сейчас»: три крупных факта под поиском на главной (левая колонка героя): самая большая экономика, самая быстрая инфляция,
 * самая низкая безработица. Карточку «Россия сейчас» (вторую про Россию в ряду) убрали вместе с шапкой «год у всех разный».
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
  const allTiles = useMemo(() => buildTodayTiles({
    gdp: gdpQ.data,
    inflation: inflationQ.data,
    unemployment: unemploymentQ.data,
    locale,
    countriesByCode,
    localeName: (country) => countryPublicName(country, locale),
  }), [gdpQ.data, inflationQ.data, unemploymentQ.data, locale, countriesByCode]);
  const tiles = useMemo(() => allTiles.filter((tile) => tile.id !== 'home' && tile.id !== 'median'), [allTiles]);

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
        <p className="fe-today__sub">{t('c8h.today.sub')}</p>
      </header>
      {pending ? (
        <div className="fe-today__grid" aria-hidden="true">
          {[0, 1, 2].map((index) => <SkeletonBox key={index} className="fe-today__skeleton" />)}
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
