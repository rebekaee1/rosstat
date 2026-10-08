import { formatDate, formatValue } from '../lib/format';
import { glueDate, periodPhrase, sincePhrase } from '../lib/periodPhrase';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { formatPercentChange, growthDigits } from '../lib/indicatorSummary';
import { pluralRu } from '../lib/worldApi';
import { splitUnit } from '../lib/countryFlag';
import { useLocale, useT } from '../i18n';
import DeltaBadge from './DeltaBadge';
import WorldCountUp from './WorldCountUp';
import '../styles/world.css';
import '../styles/x2-indicator.css';
import '../styles/w6e-indicator.css';

/**
 * Заголовок под названием показателя и плитки значений страницы показателя страны.
 *
 * Плитки зависят от того, что за ряд. У процентов: сейчас, предыдущее, максимум и среднее за десять лет.
 * У индексов и обычных величин (ВВП, население): сейчас, предыдущее, рост за десять лет и место среди стран.
 * «Среднее за 46 лет» и «исторический максимум» у таких рядов ничего не говорят, поэтому их нет.
 */

function useYearsWord() {
  const t = useT();
  const { locale } = useLocale();
  return (n) => (locale === 'en'
    ? t(`w2.span.years.${n === 1 ? 'one' : 'many'}`)
    : pluralRu(n, [t('w2.span.years.one'), t('w2.span.years.few'), t('w2.span.years.many')]));
}

/** Одна строка под заголовком: «Германия: 2,3 % за 2025 год». Единица рядом с числом, период словами. */
export function WorldHeroLine({ summary, place, dateFormat }) {
  const t = useT();
  const { locale } = useLocale();
  if (!summary) return null;
  const { shown, last, estimate, kind, yearPct } = summary;
  const unitParts = splitUnit(shown.unit);
  const when = estimate
    ? t('w6e.hero.estimate', { date: glueDate(formatDate(last.date, dateFormat, locale)) })
    : periodPhrase(t, last.date, dateFormat, locale);
  // Рост «за год» дописываем только настоящему индексу. У процентного ряда это была бы «проценты от процентов»
  // (из 58,5 % в 34,9 % выходило «−40,4 % за год»): тут важна разница в пунктах, и шапка её не пишет.
  const percentValue = /%/.test(String(shown.unit || ''));
  const yearChange = kind === 'index' && !percentValue ? formatPercentChange(yearPct, locale, growthDigits(yearPct)) : null;
  return (
    <p className="fe-hero-line" data-testid="indicator-hero">
      {place ? <span className="fe-hero-line__place">{place}:</span> : null}
      {' '}
      <strong className="fe-hero-line__value">
        {shown.text}
        {unitParts.short ? <span className="fe-hero-line__unit">{' '}{unitParts.short}</span> : null}
        {!unitParts.short && unitParts.long ? <span className="fe-hero-line__unit">{' '}({unitParts.long})</span> : null}
      </strong>
      {when ? <span className="fe-hero-line__when">{' '}{when}</span> : null}
      {yearChange ? (
        <span className="fe-hero-line__extra">{' '}{t('w6e.hero.yearChange', { change: yearChange })}</span>
      ) : null}
    </p>
  );
}

function StatTile({ label, children, note, delta = null, index = 0 }) {
  return (
    <div
      className={delta ? 'w2-stat fe-reveal' : 'w2-stat w2-stat--nodelta fe-reveal'}
      style={{ '--fe-delay': `${Math.min(index, 4) * 40}ms`, '--fe-duration': '0.4s', '--fe-rise': '10px' }}
    >
      <p className="w2-stat-label">{label}</p>
      <p className="w2-stat-value">{children}</p>
      {delta}
      {note && <p className="w2-stat-note">{note}</p>}
    </div>
  );
}

export default function WorldStatTiles({
  summary,
  dateFormat,
  frequency,
  previousLabel,
  deltaSuffix,
  polarity = 'neutral',
  rank = null,
}) {
  const t = useT();
  const { locale } = useLocale();
  const yearsWord = useYearsWord();
  if (!summary) return null;
  const {
    kind, shown, prevShown, last, prev, estimate, changeAbs, changePct, growth, stats, yearPct, fmt,
  } = summary;
  const unitParts = splitUnit(shown.unit);
  const unitText = unitParts.short;
  const dateText = (date) => glueDate(formatDate(date, dateFormat, locale));

  // Изменение к прошлому значению: у процентов в пунктах, у остальных в процентах. Нулевое после округления: «без изменений».
  let deltaNode = null;
  if (prev) {
    const useAbs = kind === 'rate';
    const flatShown = useAbs
      ? formatDeltaWithUnit(changeAbs, unitText.startsWith('%') ? '%' : unitText, { digits: shown.digits, locale })
      : { flat: formatPercentChange(changePct, locale, growthDigits(changePct)) == null, text: formatPercentChange(changePct, locale, growthDigits(changePct)) };
    const sinceLabel = frequency === 'annual'
      ? t('w6e.delta.toYear', { date: formatDate(prev.date, 'annual', locale) })
      : deltaSuffix;
    if (useAbs ? changeAbs != null : changePct != null) {
      deltaNode = flatShown.flat ? (
        <p className="w2-stat-delta">
          <DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge>
        </p>
      ) : (
        <p className="w2-stat-delta">
          <DeltaBadge delta={useAbs ? changeAbs : changePct} polarity={polarity}>{flatShown.text}</DeltaBadge>
          <span>{sinceLabel}</span>
        </p>
      );
    }
  }

  const tiles = [];
  tiles.push(
    <StatTile
      key="now"
      index={0}
      label={estimate ? t('w6e.tile.estimate', { date: dateText(last.date) }) : t('w2.ind.now')}
      note={estimate ? t('w6e.tile.estimateNote') : dateText(last.date)}
      delta={deltaNode}
    >
      <WorldCountUp value={last.value} format={fmt} />
      {unitText && <small>{unitText}</small>}
    </StatTile>,
  );
  tiles.push(
    <StatTile key="prev" index={1} label={previousLabel} note={prev ? dateText(prev.date) : undefined}>
      {prevShown ? prevShown.text : '—'}
      {unitText && prevShown && <small>{unitText}</small>}
    </StatTile>,
  );

  if (kind === 'rate' && stats) {
    tiles.push(
      <StatTile
        key="max"
        index={2}
        label={stats.years >= 1 ? t('w6e.tile.max', { n: stats.years, word: yearsWord(stats.years) }) : t('w6e.tile.maxAll')}
        note={dateText(stats.highest.date)}
      >
        {formatValue(stats.highest.value, shown.digits, locale)}
        {unitText && <small>{unitText}</small>}
      </StatTile>,
    );
    tiles.push(
      <StatTile
        key="avg"
        index={3}
        label={stats.years >= 1 ? t('w6e.tile.avg', { n: stats.years, word: yearsWord(stats.years) }) : t('w6e.tile.avgAll')}
      >
        {formatValue(stats.average, shown.digits, locale)}
        {unitText && <small>{unitText}</small>}
      </StatTile>,
    );
  } else if (kind !== 'rate') {
    if (kind === 'index' && yearPct != null) {
      tiles.push(
        <StatTile key="year" index={2} label={t('w6e.tile.yearChange')}>
          {formatPercentChange(yearPct, locale, growthDigits(yearPct)) || t('w6e.delta.flat')}
        </StatTile>,
      );
    }
    if (growth) {
      tiles.push(
        <StatTile
          key="growth"
          index={tiles.length}
          label={t('w6e.tile.growth', { n: growth.years, word: yearsWord(growth.years) })}
          note={sincePhrase(t, growth.from.date, dateFormat, locale)}
        >
          {formatPercentChange(growth.pct, locale, growthDigits(growth.pct)) || t('w6e.delta.flat')}
        </StatTile>,
      );
    }
    if (rank && kind === 'level') {
      tiles.push(
        <StatTile key="rank" index={tiles.length} label={t('w6e.tile.rank')} note={t('w6e.tile.rankNote')}>
          {rank.rank}
          <small>{t('w6e.tile.rankOf', { total: rank.total })}</small>
        </StatTile>,
      );
    }
  }

  return (
    <>
      <div className="fe-substat-grid grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-4" data-count={tiles.length}>
        {tiles}
      </div>
      {unitParts.long && unitParts.long !== unitParts.short && (
        <p className="mt-3 text-sm text-text-secondary">{t('w2.ind.unitNote', { unit: unitParts.long })}</p>
      )}
    </>
  );
}
