// R6-C: годовые карточки показателя региона — разница с Россией рядом с цифрой, абсолютное
// изменение вместо процента от процента, соседи по рейтингу, честная заметка о давности данных.
import { Link } from 'react-router-dom';
import { formatRegionWithUnit } from '../../lib/regionUi';
import { gapText } from '../../lib/r6Annual';
import { regionIndicatorPath } from '../../lib/sitePaths';
import '../../styles/r6c-annual.css';

/** Россия в тот же год, что и регион: значение и «на … ниже/выше». */
export function R6RussiaLine({ value, year, series, unit, locale, t }) {
  const rf = series?.find((p) => p.year === year);
  if (!rf) return null;
  const g = gapText(value, rf.value, unit, locale, { signed: false });
  if (!g) return null;
  const same = Math.abs(g.diff) < 0.005 || (g.pct != null && Math.abs(g.pct) < 0.5);
  const phrase = same ? t('r6c.gapSame') : t(g.diff < 0 ? 'r6c.gapLower' : 'r6c.gapHigher', { d: g.text });
  return (
    <p className="r6c-russia fe-num" data-testid="r6c-russia">
      <span className="r6c-russia__ref">{t('r6c.russiaYear', { year, value: formatRegionWithUnit(rf.value, unit, locale) })}</span>
      <span className="r6c-russia__gap">{phrase}</span>
    </p>
  );
}

/** Подпись под местом в списке: сколько регионов выше и ниже. */
export function R6RankCaption({ position, total, t }) {
  if (!position || !total) return null;
  return (
    <span className="r6c-rank-cap">{t('r6c.rankCaption', { above: position - 1, below: total - position })}</span>
  );
}

/** Изменение за всё время ряда — в тех же единицах. */
export function R6SinceStart({ first, last, unit, locale, t }) {
  if (!first || !last || first.year === last.year) return null;
  const g = gapText(last.value, first.value, unit, locale);
  if (!g) return null;
  return (
    <span className="fe-num">
      {g.text}
      <span className="r6c-since-was">{t('r6c.was', { value: formatRegionWithUnit(first.value, unit, locale) })}</span>
    </span>
  );
}

function RankRow({ r, unit, locale, code, own }) {
  return (
    <li>
      <Link
        to={regionIndicatorPath(r.slug, code)}
        className={`fe-tap flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 -mx-2 text-[13px] transition-colors hover:bg-surface-hover ${own ? 'bg-champagne/5' : ''}`}
        aria-current={own ? 'true' : undefined}
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="fe-num w-5 shrink-0 text-right text-text-secondary">{r.position}</span>
          <span className={`min-w-0 break-words leading-snug ${own ? 'font-medium text-champagne-ink' : 'text-text-primary'}`}>{r.name}</span>
        </span>
        <span className="fe-num shrink-0 whitespace-nowrap font-medium text-text-primary">{formatRegionWithUnit(r.value, unit, locale)}</span>
      </Link>
    </li>
  );
}

/** Под списком лидеров: Россия в целом, соседи по месту, замыкающие. */
export function R6RatingExtras({ rank, slug, code, unit, locale, russiaSeries, t }) {
  const rf = russiaSeries?.find((p) => p.year === rank.year);
  const around = rank.around || [];
  const showAround = rank.position > 5 && around.length > 0;
  const bottom = (rank.bottom || []).map((b, i, arr) => ({ ...b, position: rank.total - arr.length + 1 + i }));
  const showBottom = bottom.length > 0 && rank.position <= rank.total - bottom.length;
  const aroundSet = new Set(around.map((a) => a.slug));
  return (
    <div className="r6c-extras">
      {rf && (
        <p className="r6c-rf fe-num">
          <span>{t('r6c.rfWhole')}</span>
          <span className="font-medium text-text-primary">{formatRegionWithUnit(rf.value, unit, locale)}</span>
        </p>
      )}
      {showAround && (
        <>
          <h3 className="r6c-sub">{t('r6c.near')}</h3>
          <ol className="space-y-0.5">
            {around.map((r) => (
              <RankRow key={r.slug} r={r} unit={unit} locale={locale} code={code} own={r.slug === slug} />
            ))}
          </ol>
        </>
      )}
      {showBottom && (
        <>
          <h3 className="r6c-sub">{t('r6c.last')}</h3>
          <ol className="space-y-0.5">
            {bottom.filter((b) => !aroundSet.has(b.slug)).map((r) => (
              <RankRow key={r.slug} r={r} unit={unit} locale={locale} code={code} own={false} />
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

/** Давность данных: если последний год сильно отстаёт от текущего, говорим об этом прямо. */
export function R6StaleNote({ lastYear, t, now = new Date() }) {
  if (!lastYear || now.getFullYear() - lastYear < 2) return null;
  return <p className="r6c-stale" data-no-export="true">{t('r6c.stale', { year: lastYear })}</p>;
}
