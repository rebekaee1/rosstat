import { useMemo, useState } from 'react';
import { Link, useParams, Navigate, useNavigate } from 'react-router-dom';
import { GitCompare, ChevronRight, ArrowLeftRight } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import useDocumentMeta from '../lib/useMeta';
import api from '../lib/api';
import { formatRegionCompact } from '../lib/regionUi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import { SkeletonBox } from '../components/Skeleton';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';
import '../styles/r3b-regions.css';
import { useRegionsHeatmap } from '../lib/regionsApi';
import {
  regionHubPath,
  regionIndicatorPath,
  regionPath,
  regionRatingPath,
  regionVsPath,
} from '../lib/sitePaths';
import R4PriceCompare, { R4PriceSkeleton, useRegionPriceCompare } from '../components/regions/R4PriceCompare';
import Breadcrumbs from '../components/Breadcrumbs';
import { regionVsTrail } from '../lib/breadcrumbs';
import { useLocale } from '../i18n';
import { resolveBrowserLocale } from '../i18n/locale';

function parsePair(raw) {
  if (!raw) return null;
  const idx = raw.lastIndexOf('-vs-');
  if (idx <= 0) return null;
  return [raw.slice(0, idx), raw.slice(idx + 4)];
}

function useRegionCompare(slugA, slugB) {
  return useQuery({
    queryKey: ['region-compare', slugA, slugB, resolveBrowserLocale()],
    queryFn: ({ signal }) =>
      api.get(`/regions/vs/${slugA}/${slugB}`, { signal }).then((r) => r.data),
    enabled: !!slugA && !!slugB,
    staleTime: 10 * 60 * 1000,
  });
}

/** Выбор пары: два списка регионов и кнопка «поменять местами» — не надо возвращаться в хаб. */
function PairPicker({ slugA, slugB }) {
  const { t } = useLocale();
  const navigate = useNavigate();
  const { data } = useRegionsHeatmap('chislennost-naseleniya');
  const options = useMemo(
    () => [...(data?.values || [])].sort((x, y) => String(x.name).localeCompare(String(y.name), 'ru')),
    [data],
  );
  if (options.length === 0) return null;
  const go = (a, b) => { if (a && b && a !== b) navigate(regionVsPath(a, b)); };
  const select = (value, other, label, onChange) => (
    <label className="r3b-pair__field">
      <span className="r3b-pair__label">{label}</span>
      <select className="r3b-pair__select" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.slug} value={o.slug} disabled={o.slug === other}>{o.name}</option>
        ))}
      </select>
    </label>
  );
  return (
    <div className="r3b-pair" data-testid="region-pair-picker">
      {select(slugA, slugB, t('r3b.cmp.first'), (v) => go(v, slugB))}
      <button type="button" className="r3b-pair__swap fe-press" onClick={() => go(slugB, slugA)} aria-label={t('r3b.cmp.swap')} title={t('r3b.cmp.swap')}>
        <ArrowLeftRight size={18} aria-hidden="true" />
      </button>
      {select(slugB, slugA, t('r3b.cmp.second'), (v) => go(slugA, v))}
    </div>
  );
}

const QUICK_SLUGS = ['krasnodarskiy-kray', 'respublika-tatarstan', 'novosibirskaya-oblast', 'sankt-peterburg', 'sverdlovskaya-oblast', 'rostovskaya-oblast'];

/** Быстрый выбор: куда обычно переезжают — одно касание меняет второй регион. */
function QuickPairs({ slugA, slugB }) {
  const { t } = useLocale();
  const navigate = useNavigate();
  const { data } = useRegionsHeatmap('chislennost-naseleniya');
  const names = useMemo(() => Object.fromEntries((data?.values || []).map((o) => [o.slug, o.name])), [data]);
  const list = QUICK_SLUGS.filter((s) => names[s] && s !== slugA && s !== slugB);
  if (list.length === 0) return null;
  return (
    <div className="r4a-quick" data-testid="r4a-quick-pairs">
      <p className="r4a-quick__lead">{t('r4a.quick.lead', { a: names[slugA] || '' })}</p>
      <div className="r4a-quick__row">
        {list.map((s) => (
          <button key={s} type="button" className="r4a-quick__chip fe-press" onClick={() => navigate(regionVsPath(slugA, s))}>
            {names[s]}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function RegionComparePage() {
  const { t, locale } = useLocale();
  const { pair } = useParams();
  const parsed = parsePair(pair);
  const [slugA, slugB] = parsed || [null, null];
  const { data, isLoading, isError, refetch, isFetching } = useRegionCompare(slugA, slugB);
  const prices = useRegionPriceCompare(slugA, slugB);
  const [view, setView] = useState('prices');
  const hasPrices = !!prices.data?.items?.length;
  // Сервер отдаёт пару в алфавитном порядке; заголовок и крошки следуют порядку выбора в адресе, как поля выбора.
  const nameOf = (slug) => (data?.region_a?.slug === slug ? data.region_a.name : data?.region_b?.name);
  const nameA = data ? nameOf(slugA) : '';
  const nameB = data ? nameOf(slugB) : '';
  const showFacts = view === 'facts' || !hasPrices;

  useDocumentMeta(data ? {
    title: t('regions.compareTitle', { a: data.region_a.name, b: data.region_b.name }),
    description: t('regions.compareMetaDesc', {
      a: data.region_a.name,
      b: data.region_b.name,
      bits: (data.summary_bits || []).slice(0, 3).join('; '),
    }),
    path: data.canonical_path,
  } : null);

  const tally = {
    total: data?.rows?.length || 0,
    a: (data?.rows || []).filter((r) => r.leader_slug === data.region_a.slug).length,
    b: (data?.rows || []).filter((r) => r.leader_slug === data.region_b.slug).length,
  };

  if (!parsed) return <Navigate to={regionHubPath()} replace />;

  if (!isLoading && !data && !isError) {
    return <Navigate to={regionHubPath()} replace />;
  }

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-12 sm:pb-16">
      <Breadcrumbs
        items={regionVsTrail(
          data ? `${nameA} — ${nameB}` : t('regions.compareCrumb'),
          regionVsPath(slugA, slugB),
        )}
        className="mb-4"
      />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.regions.compareError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => refetch()} className="mb-4" />
          <SkeletonBox className="mb-2 h-4 w-40" />
          <SkeletonBox className="mb-3 h-9 w-full max-w-xl sm:h-10" />
          <SkeletonBox className="mb-8 h-6 w-full max-w-3xl" />
          <SkeletonBox className="mb-3 h-7 w-56" />
          <SkeletonBox className="h-[26rem] rounded-xl" />
        </div>
      )}

      {data && (
        <>
          <p className="mb-2 text-sm font-medium text-champagne-ink">
            {t('regions.compareEyebrow')}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {t('regions.compareH1', { a: nameA, b: nameB })}
          </h1>
          <p className="mb-6 max-w-3xl text-[15px] leading-relaxed text-text-secondary">
            {t('regions.compareIntro')}
          </p>

          <PairPicker slugA={slugA} slugB={slugB} />
          <QuickPairs slugA={slugA} slugB={slugB} />

          {prices.isLoading && <R4PriceSkeleton />}
          {hasPrices && (
            <div className="r4a-seg" role="tablist" data-testid="r4a-seg">
              {['prices', 'facts'].map((v) => (
                <button key={v} type="button" role="tab" aria-selected={view === v} className={`r4a-seg__btn fe-press${view === v ? ' is-on' : ''}`} onClick={() => setView(v)}>
                  {t(`r4a.seg.${v}`)}
                </button>
              ))}
            </div>
          )}

          {tally.total > 0 && showFacts && (
            <p className="r3b-tally" data-testid="region-compare-tally">
              {t('r3b.cmp.tally', {
                a: data.region_a.name, na: tally.a, b: data.region_b.name, nb: tally.b, n: tally.total,
              })}
            </p>
          )}

          {data.rows.length === 0 && (
            <div className="mb-8 rounded-3xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
              <GitCompare size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
              {t('pgui.regions.compareNoRows')}
            </div>
          )}

          {hasPrices && view === 'prices' && <R4PriceCompare data={prices.data} />}

          <div className="mb-8 grid gap-3 sm:grid-cols-2" hidden={!showFacts}>
            {data.rows.map((row, index) => {
              const peak = Math.max(Math.abs(row.a.value ?? 0), Math.abs(row.b.value ?? 0), 1e-9);
              const side = (region, point) => {
                const leader = row.leader_slug === region.slug;
                const share = Math.max(3, (Math.abs(point.value ?? 0) / peak) * 100);
                return (
                  <Link
                    to={regionIndicatorPath(region.slug, row.code)}
                    className={`fe-press r3b-side min-w-0 rounded-2xl p-3 transition-colors ${leader ? 'is-more fe-shadow-2' : 'fe-glass-2'}`}
                  >
                    <span className="block text-[13px] leading-snug text-text-secondary">{region.name}</span>
                    <span className="fe-num mt-1 block whitespace-nowrap text-lg font-semibold text-text-primary">
                      {formatRegionCompact(point.value, row.unit, locale)}
                    </span>
                    <span className="r3b-side__bar" aria-hidden="true"><span style={{ width: `${share}%` }} /></span>
                  </Link>
                );
              };
              return (
                <section
                  key={row.code}
                  className="fe-panel fe-reveal rounded-3xl p-4"
                  style={{ '--fe-delay': `${Math.min(index, 5) * 0.04}s`, '--fe-rise': '8px' }}
                >
                  <h2 className="font-display text-base font-semibold leading-snug text-text-primary">
                    {row.name}
                    <span className="font-normal text-text-secondary">{` (${row.year})`}</span>
                  </h2>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {side(data.region_a, row.a)}
                    {side(data.region_b, row.b)}
                  </div>
                  {row.verdict && (
                    <p className="mt-3 text-sm text-text-secondary">{t('regions.compareVerdict', { verdict: row.verdict })}</p>
                  )}
                  <Link to={regionRatingPath(row.code)} className="fe-tap-inline mt-1 gap-1 text-sm text-champagne-ink hover:underline">
                    {t('regions.compareAllRating')}
                    <ChevronRight size={14} aria-hidden="true" />
                  </Link>
                </section>
              );
            })}
          </div>

          <section className="rounded-3xl p-5 fe-glass-lite">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2 flex items-center gap-2">
              <GitCompare size={16} className="text-champagne-ink" /> {t('regions.compareProfiles')}
            </h2>
            <p className="text-sm text-text-secondary">
              {t('regions.compareProfilesLead')}{' '}
              <Link to={regionPath(data.region_a.slug)} className="text-champagne-ink hover:underline">{data.region_a.name}</Link>
              {', '}
              <Link to={regionPath(data.region_b.slug)} className="text-champagne-ink hover:underline">{data.region_b.name}</Link>.
              {' '}{t('regions.compareProfilesTail')}{' '}
              <Link to="/compare" className="text-champagne-ink hover:underline">{t('regions.compareSection')}</Link>.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
