/**
 * Раздел «Туризм» (20.11.2026): этажи «Регионы России» и «Мир» под российскими рядами категории.
 *
 * Данные — `GET /api/v1/tourism/overview` (backend tourism_showcase.py): отбор по категории «Туризм»
 * и туристическим названиям, а не по списку кодов, поэтому новые ряды встают сюда сами.
 *
 * Форма (второй заход, по живым данным стенда: 157 региональных рядов, 54 страны — страница была простынёй):
 * - регионы: сверху по одной карточке с тремя лидерами на смысловую группу (турпоток, размещение, деньги,
 *   цены, транспорт, турфирмы) — ответ на «где больше всего» без перехода; ниже группы стеклянными панелями,
 *   в каждой первые строки, остальное раскрывается кнопкой «Показать все»;
 * - мир: рейтинги стран строкой, затем страны плиткой (название, число рядов, ключевой ряд — «из России»
 *   или итог); видны первые 12, остальные по кнопке.
 * Пустой этаж не рисуется.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { useTourismOverview } from '../lib/hooks';
import { formatValue } from '../lib/format';
import { useLocale, useT } from '../i18n';
import '../styles/t6-tourism.css';

const GROUP_PREVIEW = 5;
const COUNTRY_PREVIEW = 12;
// «единица», «штука» ничего не говорят человеку: в подписи периода их не пишем.
const SILENT_UNITS = new Set(['единица', 'единиц', 'штука', 'шт.', 'ед.', 'unit', 'units']);

function valueDigits(value) {
  const n = Math.abs(Number(value));
  if (!Number.isFinite(n) || Number.isInteger(n) || n >= 100) return 0;
  return n >= 10 ? 1 : 2;
}

function floorsOf(data) {
  const regions = data?.regions?.items ?? [];
  const groupKeys = data?.regions?.groups ?? [];
  const featured = regions.filter((r) => r.leaders?.length);
  const groups = groupKeys
    .map((key) => ({ key, items: regions.filter((r) => r.group === key) }))
    .filter((g) => g.items.length > 0);
  const countries = data?.world?.countries ?? [];
  const concepts = data?.world?.concepts ?? [];
  return { regions, featured, groups, countries, concepts };
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

function MoreToggle({ open, total, onToggle, controls, labelKey }) {
  const t = useT();
  return (
    <button type="button" className="t6-more fe-press" aria-expanded={open} aria-controls={controls} onClick={onToggle}>
      {open ? t('tourism.collapse') : t(labelKey, { n: total })}
      <ChevronDown className={`t6-more__icon w-4 h-4${open ? ' is-open' : ''}`} aria-hidden="true" />
    </button>
  );
}

function LeaderCard({ row }) {
  const t = useT();
  const { locale } = useLocale();
  const unit = SILENT_UNITS.has(row.unit) ? '' : row.unit;
  return (
    <article className="t6-card fe-glass-lite">
      <p className="t6-card__group">{t(`tourism.group.${row.group}`)}</p>
      <Link to={row.path} className="t6-card__title">{row.name}</Link>
      <p className="t6-card__meta">
        {row.period ? t('tourism.regions.period', { period: row.period }) : null}
        {row.period && unit ? ', ' : null}
        {unit}
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
        <Link to={row.path} className="t6-card__more">
          {row.rating_path ? t('tourism.regions.rating') : t('tourism.regions.all')}
          <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
        </Link>
        {row.map_path ? <Link to={row.map_path} className="t6-card__map">{t('tourism.regions.map')}</Link> : null}
      </p>
    </article>
  );
}

function RegionGroup({ group }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const shown = open ? group.items : group.items.slice(0, GROUP_PREVIEW);
  const listId = `t6-group-${group.key}`;
  return (
    <section className="t6-group fe-glass-lite" aria-labelledby={`${listId}-title`}>
      <header className="t6-group__head">
        <h3 id={`${listId}-title`} className="t6-group__title">{t(`tourism.group.${group.key}`)}</h3>
        <span className="t6-row__aux">{t('tourism.world.series', { n: group.items.length })}</span>
      </header>
      <ul id={listId} className="t6-group__list">
        {shown.map((row) => (
          <li key={row.code}>
            <Link to={row.path} className="t6-line">
              <span className="t6-line__name">{row.name}</span>
              {row.year ? <span className="t6-row__aux">{row.year}</span> : null}
            </Link>
          </li>
        ))}
      </ul>
      {group.items.length > GROUP_PREVIEW && (
        <MoreToggle open={open} total={group.items.length} controls={listId} labelKey="tourism.showAll"
          onToggle={() => setOpen((v) => !v)} />
      )}
    </section>
  );
}

export default function TourismFloors() {
  const t = useT();
  const { data } = useTourismOverview();
  const { regions, featured, groups, countries, concepts } = floorsOf(data);
  const [allCountries, setAllCountries] = useState(false);
  const shownCountries = allCountries ? countries : countries.slice(0, COUNTRY_PREVIEW);

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
              {featured.map((row) => <LeaderCard key={row.code} row={row} />)}
            </div>
          )}
          {groups.length > 0 && (
            <div className="t6-groups">
              {groups.map((group) => <RegionGroup key={group.key} group={group} />)}
            </div>
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
            <>
              <h3 className="t6-floor__sub">{t('tourism.world.countries')}</h3>
              <ul id="t6-countries" className="t6-countries">
                {shownCountries.map((c) => (
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
              {countries.length > COUNTRY_PREVIEW && (
                <MoreToggle open={allCountries} total={countries.length} controls="t6-countries"
                  labelKey="tourism.world.showAll" onToggle={() => setAllCountries((v) => !v)} />
              )}
            </>
          )}
        </section>
      )}
    </>
  );
}
