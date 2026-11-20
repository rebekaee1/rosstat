/**
 * Раздел «Туризм» (20.11.2026): этажи «Регионы России» и «Мир» под российскими рядами категории.
 *
 * Данные — `GET /api/v1/tourism/overview` (backend tourism_showcase.py): отбор по категории «Туризм»
 * и туристическим названиям, а не по списку кодов, поэтому новые ряды встают сюда сами.
 * Форма: три первых региона прямо в карточке показателя (ответ на «где больше всего» без перехода),
 * остальные показатели — тихими строками; страны — строками с числом показателей и прямыми ссылками
 * на их ряды. Пустой этаж не рисуется.
 */
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useTourismOverview } from '../lib/hooks';
import { formatValue } from '../lib/format';
import { useLocale, useT } from '../i18n';
import '../styles/t6-tourism.css';

const FEATURED = 6;
// «единица», «штука» ничего не говорят человеку: в подписи периода их не пишем.
const SILENT_UNITS = new Set(['единица', 'единиц', 'штука', 'шт.', 'unit', 'units']);

function valueDigits(value) {
  const n = Math.abs(Number(value));
  if (!Number.isFinite(n)) return 0;
  if (n >= 100) return 0;
  return n >= 10 ? 1 : 2;
}

function floorsOf(data) {
  const regions = data?.regions?.items ?? [];
  const featured = regions.filter((r) => r.leaders?.length).slice(0, FEATURED);
  const rest = regions.filter((r) => !featured.includes(r));
  const countries = data?.world?.countries ?? [];
  const concepts = data?.world?.concepts ?? [];
  return { regions, featured, rest, countries, concepts };
}

/** Короткая навигация «Россия · Регионы · Мир» под заголовком; только по этажам, где есть данные. */
export function TourismJump() {
  const t = useT();
  const { data } = useTourismOverview();
  const { regions, countries, concepts } = floorsOf(data);
  const items = [
    { id: 'category-list', label: t('tourism.nav.russia') },
    regions.length > 0 && { id: 'tourism-regions', label: t('tourism.nav.regions') },
    (countries.length > 0 || concepts.length > 0) && { id: 'tourism-world', label: t('tourism.nav.world') },
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

export default function TourismFloors() {
  const t = useT();
  const { locale } = useLocale();
  const { data } = useTourismOverview();
  const { regions, featured, rest, countries, concepts } = floorsOf(data);

  return (
    <>
      {regions.length > 0 && (
        <section id="tourism-regions" data-block="tourism-regions" className="t6-floor">
          <header className="t6-floor__head">
            <h2 className="fe-cat-list__title">{t('tourism.regions.title')}</h2>
            <p className="t6-floor__lead">{t('tourism.regions.lead')}</p>
          </header>
          {featured.length > 0 && (
            <div className="t6-cards">
              {featured.map((row) => (
                <article key={row.code} className="t6-card fe-glass-lite">
                  <Link to={row.rating_path} className="t6-card__title">{row.name}</Link>
                  <p className="t6-card__meta">
                    {row.period ? t('tourism.regions.period', { period: row.period }) : null}
                    {row.period && row.unit && !SILENT_UNITS.has(row.unit) ? ', ' : null}
                    {SILENT_UNITS.has(row.unit) ? null : row.unit}
                  </p>
                  <ol className="t6-rank">
                    {row.leaders.map((leader, i) => (
                      <li key={leader.slug} className="t6-rank__row">
                        <span className="t6-rank__n" aria-hidden="true">{i + 1}</span>
                        <Link to={leader.path} className="t6-rank__name">{leader.name}</Link>
                        <span className="t6-rank__v">{formatValue(leader.value, valueDigits(leader.value), locale)}</span>
                      </li>
                    ))}
                  </ol>
                  <p className="t6-card__links">
                    <Link to={row.rating_path} className="t6-card__more">
                      {t('tourism.regions.rating')}
                      <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                    </Link>
                    <Link to={row.map_path} className="t6-card__map">{t('tourism.regions.map')}</Link>
                  </p>
                </article>
              ))}
            </div>
          )}
          {rest.length > 0 && (
            <>
              {featured.length > 0 && <h3 className="t6-floor__sub">{t('tourism.regions.more')}</h3>}
              <ul className="t6-rows">
                {rest.map((row) => (
                  <li key={row.code}>
                    <Link to={row.rating_path} className="t6-row fe-glass-2">
                      <span className="t6-row__name">{row.name}</span>
                      {row.year ? <span className="t6-row__aux">{row.year}</span> : null}
                      <ArrowRight className="t6-row__arrow w-4 h-4" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {(countries.length > 0 || concepts.length > 0) && (
        <section id="tourism-world" data-block="tourism-world" className="t6-floor">
          <header className="t6-floor__head">
            <h2 className="fe-cat-list__title">{t('tourism.world.title')}</h2>
            <p className="t6-floor__lead">{t('tourism.world.lead')}</p>
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
          {countries.length > 0 && (
            <ul className="t6-countries">
              {countries.map((c) => (
                <li key={c.slug} className="t6-country fe-glass-lite">
                  <div className="t6-country__head">
                    <Link to={c.path} className="t6-country__name">{c.name}</Link>
                    <span className="t6-row__aux">{t('tourism.world.series', { n: c.count })}</span>
                  </div>
                  {c.series?.length > 0 && (
                    <ul className="t6-country__series">
                      {c.series.map((s) => (
                        <li key={s.code}><Link to={s.path}>{s.name}</Link></li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
