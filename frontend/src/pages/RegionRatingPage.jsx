import { useMemo, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ArrowDown, ArrowUp, Trophy, BarChart3, GitCompare } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useRegionsHeatmap } from '../lib/regionsApi';
import { formatRegionNumber, formatRegionWithUnit, unitLabel } from '../lib/regionUi';
import { priceUnitLabel } from '../lib/r9cPriceUnit';
import { medianOf } from '../components/regions/R4YourRegion';
import RegionsMap from '../components/RegionsMap';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { regionRatingTrail } from '../lib/breadcrumbs';
import {
  regionIndicatorPath,
  regionPath,
  regionRatingHubPath,
  regionRatingPath,
  regionVsPath,
} from '../lib/sitePaths';
import Chip from '../components/Chip';
import { useT, useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';
import '../styles/k6-country.css';
import '../styles/r3b-regions.css';
import '../styles/r7c-regions.css';
import '../styles/r9c-price-rating.css';

/** «Средняя цена: мука, рублей за кг» → «Средняя цена: мука»: единица стоит в колонке, в заголовке она лишняя. */
function cleanPriceName(name, unit) {
  const n = String(name || '');
  if (unit) {
    const tail = `, ${unit}`;
    if (n.toLowerCase().endsWith(tail.toLowerCase())) return n.slice(0, -tail.length);
  }
  return n.replace(/,\s*(рублей|руб\.?|rubles?|RUB)\b[^,]*$/i, '');
}

export default function RegionRatingPage() {
  const t = useT();
  const { locale } = useLocale();
  const { code } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch, isFetching } = useRegionsHeatmap(code);
  const achievement = Boolean(data?.rank_as_achievement);
  const isPrice = data?.month != null;
  // Цены: владельцу точки важно «где дешевле» — по умолчанию сначала дешёвые.
  const serverSort = isPrice ? 'asc' : (data?.default_sort === 'asc' ? 'asc' : 'desc');
  // null = ещё не трогали переключатель → берём направление с сервера.
  // Выбор привязан к коду показателя, поэтому при смене показателя сбрасывается сам.
  const [sortState, setSortState] = useState({ code, value: null });
  const sortOverride = sortState.code === code ? sortState.value : null;
  const setSortOverride = (value) => setSortState({ code, value });
  const sortDirection = sortOverride ?? serverSort;

  const ranked = useMemo(() => {
    if (!data?.values?.length) return [];
    const rows = [...data.values].sort((a, b) => {
      const av = a.raw ?? a.value;
      const bv = b.raw ?? b.value;
      return sortDirection === 'asc' ? av - bv : bv - av;
    });
    return rows.map((row, i) => ({ ...row, rank: i + 1 }));
  }, [data, sortDirection]);

  // «Мой регион» общий с хабом: выбор помнится в браузере.
  const [mine, setMine] = useState(() => { try { return localStorage.getItem('fe-my-region') || localStorage.getItem('r4a-my-region') || ''; } catch { return ''; } });
  const pickMine = (slug) => {
    setMine(slug);
    try { if (slug) { localStorage.setItem('fe-my-region', slug); localStorage.setItem('r4a-my-region', slug); } else { localStorage.removeItem('fe-my-region'); localStorage.removeItem('r4a-my-region'); } } catch { /* без хранилища работает так же */ }
    if (slug && typeof document !== 'undefined') {
      window.requestAnimationFrame(() => document.getElementById(`r7c-row-${slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    }
  };
  const mineRow = ranked.find((r) => r.slug === mine) || null;

  // Цены ЕМИСС (месячный ряд): места не показываем — только значения и сравнение.
  const period = isPrice ? (data.period_label || String(data.year)) : null;
  const rawName = data?.indicator?.name || '';
  const shortName = isPrice ? cleanPriceName(rawName, data.indicator.unit) : rawName;
  const val = (r) => Number(r.raw ?? r.value);
  const stats = useMemo(() => {
    if (!isPrice || !ranked.length) return null;
    const nums = ranked.map(val);
    const med = medianOf(nums);
    const lo = ranked.reduce((a, b) => (val(b) < val(a) ? b : a));
    const hi = ranked.reduce((a, b) => (val(b) > val(a) ? b : a));
    return { med, lo, hi, ratio: val(lo) > 0 ? val(hi) / val(lo) : null };
  }, [ranked, isPrice]);
  const pUnit = isPrice ? priceUnitLabel(data.indicator.unit) : '';
  const fmtU = (v) => (pUnit ? `${formatRegionNumber(v, data.indicator.unit, locale)}\u00a0${pUnit.replace(/ /g, '\u00a0')}` : formatRegionWithUnit(v, data.indicator.unit, locale));
  const num1 = (x) => x.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: 1 });
  const signed = (pct) => `${pct > 0 ? '+' : pct < 0 ? '−' : ''}${num1(Math.abs(pct))}${locale === 'en' ? '%' : '\u00a0%'}`;
  const maxAbs =Math.max(1e-9, ...ranked.map((r) => Math.abs(Number(r.raw ?? r.value) || 0)));
  const top = isPrice && stats ? stats.lo : ranked[0];
  const bottom = isPrice && stats ? stats.hi : ranked[ranked.length - 1];
  const mapValues = useMemo(() => {
    if (!data?.values) return null;
    return new Map(data.values.map((v) => [v.slug, v.raw ?? v.value]));
  }, [data]);
  const nameBySlug = useMemo(() => {
    if (!data?.values) return {};
    return Object.fromEntries(data.values.map((v) => [v.slug, v.name]));
  }, [data]);

  const bestLabel = isPrice ? t('r9c.price.lowest') : (achievement ? t('regions.rating.best') : t('regions.rating.highest'));
  const worstLabel = isPrice ? t('r9c.price.highest') : (achievement ? t('regions.rating.worst') : t('regions.rating.lowest'));
  const listTitle = isPrice ? t('r9c.price.list', { n: ranked.length }) : achievement
    ? t('regions.rating.listAchievement', { n: ranked.length })
    : t('regions.rating.listNeutral', { n: ranked.length });
  const tableCol = achievement ? t('regions.rating.place') : '№';

  useDocumentMeta(data ? {
    title: isPrice
      ? t('r9c.price.title', { name: shortName, period })
      : achievement
      ? t('regions.rating.titleAchievement', { name: data.indicator.name, year: data.year })
      : t('regions.rating.titleNeutral', { name: data.indicator.name, year: data.year }),
    description:
      `${shortName} (${period || data.year}): `
      + `${ranked.length}.`
      + (top ? ` ${bestLabel} — ${top.name}.` : ''),
    path: regionRatingPath(code),
  } : null);

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-12 sm:pb-16">
      <Breadcrumbs
        items={regionRatingTrail(
          achievement ? t('w4.rating.crumb', { name: data?.indicator?.name || '…' }) : (shortName || '…'),
          code,
        )}
      />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.regions.ratingError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => refetch()} className="mb-4" />
          <SkeletonBox className="mb-2 mt-6 h-4 w-48" />
          <SkeletonBox className="mb-3 h-8 w-full max-w-xl sm:h-9" />
          <SkeletonBox className="mb-4 h-12 w-full max-w-3xl" />
          <SkeletonBox className="mb-6 h-9 w-72 max-w-full" />
          <div className="r3b-rate-tiles mb-3 grid grid-cols-1 gap-3">
            <SkeletonBox className="h-[92px] rounded-xl" />
            <SkeletonBox className="h-[92px] rounded-xl" />
            <SkeletonBox className="h-[92px] rounded-xl" />
          </div>
          <SkeletonBox className="mb-8 aspect-[1000/538] w-full rounded-xl" />
          <SkeletonBox className="h-[32rem] rounded-xl" />
        </div>
      )}

      {data && ranked.length >= 10 && (
        <>
          <p className="mb-2 text-sm font-medium text-champagne-ink">
            {achievement ? t('regions.rating.eyebrowAchievement') : t('regions.rating.eyebrowNeutral')}
            {' — '}
            {isPrice ? period : `${data.year} ${t('common.year').toLowerCase()}`}
          </p>
          <h1 className="r3b-rate-h1 font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {shortName}
            :
            {' '}
            {isPrice ? t('r9c.price.h1') : (achievement ? t('regions.rating.h1Achievement') : t('regions.rating.h1Neutral'))}
          </h1>
          <p className="r7c-rate-lead mb-5 max-w-3xl text-[15px] leading-relaxed text-text-secondary">
            {isPrice && stats ? t('r9c.price.lead', {
              n: ranked.length,
              period,
              lo: fmtU(val(stats.lo)),
              loRegion: stats.lo.name,
              hi: fmtU(val(stats.hi)),
              hiRegion: stats.hi.name,
            }) : t('w4.rating.lead', {
              n: ranked.length,
              name: data.indicator.name,
              year: data.year,
              best: bestLabel,
              region: top.name,
              value: fmtU(top.raw ?? top.value),
            })}
          </p>

          <div className="mb-6 flex flex-wrap items-center gap-2">
            <span className="mr-1 text-sm text-text-secondary">
              {t('regions.rating.sort')}
            </span>
            <Chip active={sortDirection === 'desc'} className={isPrice ? 'r9c-chip-last' : ''} onClick={() => setSortOverride('desc')}>
              {t(isPrice ? 'r9c.price.sortDesc' : 'regions.rating.sortDesc')}
            </Chip>
            <Chip active={sortDirection === 'asc'} className={isPrice ? 'r9c-chip-first' : ''} onClick={() => setSortOverride('asc')}>
              {t(isPrice ? 'r9c.price.sortAsc' : 'regions.rating.sortAsc')}
            </Chip>
          </div>

          {(
            <div className="r7c-rate-mine" data-testid="rating-mine">
              <label className="r7c-mine">
                <span className="r7c-mine__label">{t('r7c.rank.mineLabel')}</span>
                <select value={mine} onChange={(e) => pickMine(e.target.value)} aria-label={t('r7c.rank.mineAria')}>
                  <option value="">{t('r7c.rank.minePlaceholder')}</option>
                  {[...ranked].sort((a, b) => a.name.localeCompare(b.name, locale)).map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
                </select>
              </label>
              {mineRow && isPrice && stats && (
                <div className="r9c-mine" data-testid="r9c-mine">
                  <a href="#r7c-mine-row" className="r7c-rate-mine__sum fe-num" onClick={(e) => { e.preventDefault(); document.getElementById(`r7c-row-${mineRow.slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>
                    {fmtU(val(mineRow))}
                  </a>
                  <span className="r9c-mine__cmp">
                    {(() => {
                      const diff = stats.med ? ((val(mineRow) - stats.med) / stats.med) * 100 : 0;
                      if (Math.abs(diff) < 0.5) return t('r4a.your.typical');
                      return t(diff > 0 ? 'r9c.price.more' : 'r9c.price.less', { pct: num1(Math.abs(diff)), typical: fmtU(stats.med) });
                    })()}
                  </span>
                  <span className="r9c-mine__cmp">
                    {t('r9c.price.cheaperThan', { n: ranked.filter((r) => val(r) > val(mineRow)).length, total: ranked.length })}
                  </span>
                  <Link to={regionIndicatorPath(mineRow.slug, code)} className="r9c-mine__link fe-tap-inline">
                    {t('r9c.price.history')}
                  </Link>
                </div>
              )}
              {mineRow && !isPrice && (
                <a href="#r7c-mine-row" className="r7c-rate-mine__sum fe-num" onClick={(e) => { e.preventDefault(); document.getElementById(`r7c-row-${mineRow.slug}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>
                  {t('r7c.rank.mineSub', { rank: mineRow.rank, n: ranked.length })}
                  {', '}
                  {fmtU(mineRow.raw ?? mineRow.value)}
                </a>
              )}
            </div>
          )}

          <div className="r7c-rate-tiles mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="k6-place k6-place--first rounded-2xl p-4 fe-glass-lite">
              <div className="flex items-center gap-1 text-xs font-medium text-text-secondary">
                {achievement && <Trophy size={13} className="text-champagne-ink" aria-hidden="true" />}
                {bestLabel}
              </div>
              <div className="mt-1 font-semibold text-text-primary">
                {isPrice ? <Link to={regionIndicatorPath(top.slug, code)} className="r9c-tile-link">{top.name}</Link> : top.name}
              </div>
              <div className="fe-num text-sm text-text-secondary">
                {fmtU(top.raw ?? top.value)}
              </div>
            </div>
            <div className="k6-place k6-place--last rounded-2xl p-4 fe-glass-lite">
              <div className="text-xs font-medium text-text-secondary">{worstLabel}</div>
              <div className="mt-1 font-semibold text-text-primary">
                {isPrice ? <Link to={regionIndicatorPath(bottom.slug, code)} className="r9c-tile-link">{bottom.name}</Link> : bottom.name}
              </div>
              <div className="fe-num text-sm text-text-secondary">
                {fmtU(bottom.raw ?? bottom.value)}
              </div>
            </div>
            {isPrice && stats ? (
              <div className="r7c-rate-tiles__year r9c-typical rounded-2xl p-4 fe-glass-lite">
                <div className="text-xs font-medium text-text-secondary">{t('r9c.price.typical')}</div>
                <div className="fe-num mt-1 font-semibold text-text-primary">{fmtU(stats.med)}</div>
                {stats.ratio && (
                  <div className="r9c-typical__sub">{t('r9c.price.spread', { x: num1(stats.ratio) })}</div>
                )}
              </div>
            ) : (
              <div className="r7c-rate-tiles__year rounded-2xl p-4 fe-glass-lite">
                <div className="text-xs font-medium text-text-secondary">{t('regions.rating.dataFor')}</div>
                <div className="fe-num mt-1 font-semibold text-text-primary">{t('w4.map.yearLabel', { year: data.year })}</div>
              </div>
            )}
          </div>

          {top.slug && bottom.slug && top.slug !== bottom.slug && (
            <Link to={regionVsPath(top.slug, bottom.slug)} className="r3b-vs-link fe-tap-inline mb-8">
              <GitCompare size={14} aria-hidden="true" />
              {t(isPrice ? 'r4a.rating.extremes' : 'r3b.rating.compareExtremes', { a: top.name, b: bottom.name })}
            </Link>
          )}

          <div className="mb-8 rounded-3xl p-3 sm:p-5 fe-glass-lite">
            <RegionsMap
              valuesBySlug={mapValues}
              unit={data.indicator.unit}
              nameBySlug={nameBySlug}
              colorDirection={sortDirection}
              onSelect={(slug) => navigate(regionIndicatorPath(slug, code))}
            />
            <p className="r7c-map-hint">{t(isPrice ? 'r9c.price.mapHint' : 'r7c.rate.mapHint')}</p>
          </div>

          <section id="chart" className="mb-8 scroll-mt-28">
            <h2 className="mb-3 font-display text-xl font-bold text-text-primary">
              {listTitle}
            </h2>
            <div className="r3b-rate-box max-h-[32rem] overflow-auto rounded-2xl fe-glass-lite">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-obsidian-light/95 z-10">
                  <tr className="text-left text-xs font-medium text-text-secondary">
                    {!isPrice && <th className="px-4 py-2.5 font-medium w-16">{tableCol}</th>}
                    <th className="px-4 py-2.5 font-medium">{t('regions.rating.colRegion')}</th>
                    <th
                      aria-sort={sortDirection === 'asc' ? 'ascending' : 'descending'}
                      className="px-4 py-2.5 font-medium text-right"
                    >
                      <button
                        type="button"
                        onClick={() => setSortOverride(sortDirection === 'asc' ? 'desc' : 'asc')}
                        title={sortDirection === 'asc'
                          ? t('regions.rating.sortAsc')
                          : t('regions.rating.sortDesc')}
                        className="fe-tap-inline gap-1 rounded-lg transition-colors hover:text-champagne-ink"
                      >
                        {pUnit || unitLabel(data.indicator.unit, locale) || t('regions.rating.colValue')}
                        {sortDirection === 'asc'
                          ? <ArrowUp size={12} aria-hidden="true" />
                          : <ArrowDown size={12} aria-hidden="true" />}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((row) => (
                    <tr key={row.slug} id={`r7c-row-${row.slug}`} className={`fe-row-link border-t border-border-subtle${row.slug === mine ? ' is-mine' : ''}`}>
                      {!isPrice && (
                        <td className="fe-num px-4 py-2 text-text-secondary">
                          {achievement && row.rank <= 3
                            ? <span className="w2-rank-pos" data-medal={row.rank} title={t('w6f.rank.topThree')}>{row.rank}</span>
                            : row.rank}
                        </td>
                      )}
                      <td className="px-4 py-2">
                        <Link
                          to={regionPath(row.slug)}
                          className="fe-row-link__a text-text-primary hover:text-champagne-ink transition-colors"
                        >
                          {row.name}
                        </Link>
                        <span className="r3b-rate-bar" aria-hidden="true">
                          <span style={{ width: `${Math.max(2, (Math.abs(Number(row.raw ?? row.value) || 0) / maxAbs) * 100)}%` }} />
                          {isPrice && stats?.med ? <i className="r9c-tick" style={{ left: `${(stats.med / maxAbs) * 100}%` }} /> : null}
                        </span>
                        {isPrice && Number.isFinite(row.prev) && row.prev > 0 && (
                          <span className="r9c-yoy fe-num">
                            {t('r9c.price.yoy', { pct: signed(((val(row) - row.prev) / row.prev) * 100) })}
                          </span>
                        )}
                      </td>
                      <td className="fe-num whitespace-nowrap px-4 py-2 text-right text-text-primary">
                        <Link
                          to={regionIndicatorPath(row.slug, code)}
                          title={t('c9e.rank.valueTitle')}
                          className="relative z-10 hover:text-champagne-ink transition-colors"
                        >
                          {formatRegionNumber(row.raw ?? row.value, data.indicator.unit, locale)}
                        </Link>
                        {isPrice && stats?.med ? (
                          <span className="r9c-dev fe-num" title={t('r9c.price.devTitle')}>
                            {signed(((val(row) - stats.med) / stats.med) * 100)}
                          </span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {isPrice && Array.isArray(data.missing) && data.missing.length > 0 && (
            <p className="r9c-missing" data-testid="r9c-missing">
              {t('r9c.price.missing', { period, names: data.missing.map((m) => m.name).join(', ') })}
            </p>
          )}

          <section className="rounded-3xl p-5 fe-glass-lite">
            <h2 className="mb-2 font-display text-base font-semibold text-text-primary">{t('regions.rating.sourceHeading')}</h2>
            <p className="text-sm leading-relaxed text-text-secondary">
              {isPrice ? t('r9c.price.source', { period }) : t('w4.rating.source', { year: data.year })}
            </p>
          </section>
        </>
      )}

      {!isLoading && !isError && (!data || ranked.length < 10) && (
        <div role="status" className="rounded-3xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
          <BarChart3 size={24} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
          <p>{t('regions.rating.empty')}</p>
          <Link to={regionRatingHubPath()} className="fe-tap-inline mt-2 text-champagne-ink hover:underline">
            {t('w4.rating.backToAll')}
          </Link>
        </div>
      )}
    </div>
  );
}
