/**
 * Раздел «Туризм»: под лентой главных рядов России — остальные ряды, регионы и мир.
 *
 * Данные — `GET /api/v1/tourism/overview` (backend tourism_showcase.py); серверная копия — seo_tourism.py.
 * Экран короткий (круг правок 20.11.2026, зона z3):
 * - остальные ряды России — пять свёрнутых групп (выезд и въезд, размещение, цены, транспорт, деньги);
 * - регионы — шесть свёрнутых групп по смыслу, без карточек «топ-3» (они повторяли каталог);
 * - мир — рейтинги стран и один список «Куда ездят россияне»: десять стран по числу выездных поездок
 *   за последний полный год; под ним ссылка «все страны».
 * Пустой этаж не рисуется.
 */
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { useTourismOverview } from '../lib/hooks';
import { formatValue, resolveDateFormat } from '../lib/format';
import { periodPhrase } from '../lib/periodPhrase';
import { TOURISM_RU_GROUPS, countriesLabel, tourismRuGroup } from '../lib/tourismFeed';
import { useLocale, useT } from '../i18n';
import '../styles/t6-tourism.css';

function floorsOf(data) {
  const regions = data?.regions?.items ?? [];
  const groupKeys = data?.regions?.groups ?? [];
  const groups = groupKeys
    .map((key) => ({ key, items: regions.filter((r) => r.group === key) }))
    .filter((g) => g.items.length > 0);
  const world = data?.world ?? {};
  const countries = world.countries ?? [];
  const concepts = world.concepts ?? [];
  const outbound = world.outbound?.items ?? [];
  return { regions, groups, countries, concepts, outbound, world };
}

/** Короткая навигация под заголовком; только по этажам, где есть данные. */
export function TourismJump() {
  const t = useT();
  const { data } = useTourismOverview();
  const { regions, countries, concepts, outbound } = floorsOf(data);
  const items = [
    { id: 'category-list', label: t('kt3_navRussia') },
    regions.length > 0 && { id: 'tourism-regions', label: t('kt3_navRegions') },
    (countries.length > 0 || concepts.length > 0 || outbound.length > 0) && { id: 'tourism-world', label: t('kt3_navWorld') },
  ].filter(Boolean);
  if (items.length < 2) return null;
  return (
    <nav className="t6-jump" aria-label={t('tourism.nav.label')}>
      {items.map((item) => (
        <a key={item.id} href={`#${item.id}`} className="t6-jump__link">{item.label}</a>
      ))}
    </nav>
  );
}

function FoldGroup({ id, title, count, children }) {
  return (
    <details className="t6-group fe-glass-lite" id={id}>
      <summary className="t6-group__head">
        <h3 className="t6-group__title">{title}</h3>
        <span className="t6-row__aux">{count}</span>
        <ChevronDown className="t6-group__chev w-4 h-4" aria-hidden="true" />
      </summary>
      <ul className="t6-group__list">{children}</ul>
    </details>
  );
}

/** Ряды России, не попавшие в ленту (старше года или девятые и дальше), — свёрнутыми группами. */
export function TourismRussiaCatalog({ indicators }) {
  const t = useT();
  const { locale } = useLocale();
  const groups = TOURISM_RU_GROUPS
    .map((key) => ({ key, items: indicators.filter((ind) => tourismRuGroup(ind.code) === key) }))
    .filter((g) => g.items.length > 0);
  if (groups.length === 0) return null;
  return (
    <div className="t6-groups t6-groups--rest" data-block="tourism-russia-rest">
      <h3 className="t6-floor__sub">{t('kt3_rest')}</h3>
      {groups.map((group) => (
        <FoldGroup key={group.key} id={`t6-ru-${group.key}`} title={t(`kt3_group_${group.key}`)} count={group.items.length}>
          {group.items.map((ind) => (
            <li key={ind.code}>
              <Link to={`/russia/indicator/${ind.code}`} className="t6-line">
                <span className="t6-line__name">{locale === 'en' && ind.name_en ? ind.name_en : ind.name}</span>
                <span className="t6-row__aux">
                  {periodPhrase(t, ind.current_date, resolveDateFormat({ frequency: ind.frequency }), locale) || ''}
                </span>
              </Link>
            </li>
          ))}
        </FoldGroup>
      ))}
    </div>
  );
}

export default function TourismFloors() {
  const t = useT();
  const { locale } = useLocale();
  const { data } = useTourismOverview();
  const { regions, groups, countries, concepts, outbound, world } = floorsOf(data);
  const outboundUnit = world.outbound?.unit || '';

  return (
    <>
      {regions.length > 0 && (
        <section id="tourism-regions" data-block="tourism-regions" className="t6-floor">
          <header className="t6-floor__head">
            <h2 className="fe-cat-list__title">{t('tourism.regions.title')}</h2>
          </header>
          <div className="t6-groups">
            {groups.map((group) => (
              <FoldGroup key={group.key} id={`t6-group-${group.key}`} title={t(`tourism.group.${group.key}`)}
                count={group.items.length}>
                {group.items.map((row) => (
                  <li key={row.code}>
                    <Link to={row.path} className="t6-line">
                      <span className="t6-line__name">{row.name}</span>
                      {row.year ? <span className="t6-row__aux">{row.year}</span> : null}
                    </Link>
                  </li>
                ))}
              </FoldGroup>
            ))}
          </div>
        </section>
      )}

      {(countries.length > 0 || concepts.length > 0 || outbound.length > 0) && (
        <section id="tourism-world" data-block="tourism-world" className="t6-floor">
          <header className="t6-floor__head">
            <h2 className="fe-cat-list__title">{t('tourism.world.title')}</h2>
          </header>
          {concepts.length > 0 && (
            <div className="t6-ratings">
              <h3 className="t6-floor__sub">{t('tourism.world.ratings')}</h3>
              <ul className="t6-rows">
                {concepts.map((c) => (
                  <li key={c.slug}>
                    <Link to={c.path} className="t6-row fe-glass-2">
                      <span className="t6-row__name">{c.name}</span>
                      <ArrowRight className="t6-row__arrow w-4 h-4" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {outbound.length > 0 && (
            <div className="t6-trips" data-block="tourism-outbound">
              <h3 className="t6-floor__sub">{t('kt3_outbound')}</h3>
              <ol className="t6-trips__list fe-glass-lite">
                {outbound.map((row) => (
                  <li key={row.slug}>
                    <Link to={row.path} className="t6-trip">
                      <span className="t6-trip__name">{row.name}</span>
                      <span className="t6-trip__period">{row.period}</span>
                      <span className="t6-trip__v">
                        {formatValue(row.value, 0, locale)}
                        {outboundUnit ? <small>{outboundUnit}</small> : null}
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {countries.length > 0 && (
            <p className="t6-trips__all">
              <Link to="/" className="t6-card__more">
                {countriesLabel(world, countries, t, locale)}
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </Link>
            </p>
          )}
        </section>
      )}
    </>
  );
}
