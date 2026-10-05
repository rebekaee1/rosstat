// Плитки страницы «Численность населения»: «28,1 млн человек», «+0,35 млн (+1,3 %) за год»,
// «5-е место среди 55 стран», «+11 % за 10 лет». Вместо «28 076 986», «+346 630,00», «максимума» и «среднего за 47 лет».
import { useMemo } from 'react';
import { SkeletonBox } from './Skeleton';
import DeltaBadge from './DeltaBadge';
import { useWorldCompareSnapshot } from '../lib/worldApi';
import {
  compactPeople, placeOrdinal, populationRank, populationSummary, signedPeople, signedPercent,
} from '../lib/populationFacts';
import { useLocale, useT } from '../i18n';
import '../styles/world.css';
import '../styles/w6-g.css';

function Tile({ label, note, index = 0, children, tone = null }) {
  return (
    <div
      className="w2-stat fe-reveal"
      style={{ '--fe-delay': `${Math.min(index, 4) * 40}ms`, '--fe-duration': '0.4s', '--fe-rise': '10px' }}
    >
      <p className="w2-stat-label">{label}</p>
      <p className="w2-stat-value">{children}</p>
      {tone}
      {note ? <p className="w2-stat-note">{note}</p> : null}
    </div>
  );
}

export default function PopulationStats({ points, unit, countrySlug, loading = false }) {
  const t = useT();
  const { locale } = useLocale();
  const snapshot = useWorldCompareSnapshot('population');
  const summary = useMemo(() => populationSummary(points, unit), [points, unit]);
  const rank = useMemo(
    () => populationRank(snapshot.data?.items, countrySlug),
    [snapshot.data, countrySlug],
  );

  if (loading || !summary) {
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-4" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => <SkeletonBox key={i} className="h-32 rounded-3xl" />)}
      </div>
    );
  }

  const deltaText = signedPeople(summary.delta, locale);
  const pctText = signedPercent(summary.deltaPct, locale);
  const nowLabel = summary.estimate
    ? t('w6g.pop.nowEstimate', { year: summary.year })
    : t('w6g.pop.now', { year: summary.year });

  return (
    <div className="fe-substat-grid grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-4" data-block="population-stats">
      <Tile index={0} label={nowLabel} note={t('w6g.pop.peopleNote')}>
        {compactPeople(summary.value, locale)}
      </Tile>

      <Tile
        index={1}
        label={t('w6g.pop.yearChange')}
        tone={deltaText && pctText ? (
          <p className="w2-stat-delta">
            <DeltaBadge delta={summary.delta}>{pctText}</DeltaBadge>
          </p>
        ) : null}
        note={deltaText ? undefined : t('w6g.pop.noChange')}
      >
        {deltaText || '0'}
      </Tile>

      {rank && (
        <Tile
          index={2}
          label={t('w6g.pop.place')}
          note={t('w6g.pop.placeNote', { total: rank.total })}
        >
          {placeOrdinal(rank.rank, locale)}
        </Tile>
      )}

      {summary.decadePct != null && (
        <Tile
          index={3}
          label={t('w6g.pop.decade')}
          note={t('w6g.pop.decadeNote', { year: summary.year - 10 })}
        >
          {signedPercent(summary.decadePct, locale)}
        </Tile>
      )}
    </div>
  );
}
