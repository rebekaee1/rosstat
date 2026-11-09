// R10-C: длинная история цены: цена в ключевые годы, «во сколько раз», доля инфляции, пропуски и начало наблюдений.
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useLocale } from '../../i18n';
import { priceText, roundBig, ymLabel, ymLabelFrom } from '../../lib/z2Price';
import { keyYearRows, monthGaps, timesShort, timesText, yearlyRows } from '../../lib/z2PriceHistory';
import '../../styles/r10c-history.css';

const money = (v, unit, locale) => priceText(roundBig(v), unit, locale);

function realText(t, real) {
  if (real == null) return '';
  const pct = Math.round(Math.abs(real - 1) * 100);
  if (pct < 3) return t('r10c.realFlat');
  return t(real > 1 ? 'r10c.realUp' : 'r10c.realDown', { pct });
}

/** Короткий вывод над плитками: что выросло и что из этого инфляция. */
function Headline({ rows, locale, t }) {
  const row = rows.find((r) => r.times != null);
  if (!row || row.times < 1.05) return null;
  const who = row.source === 'russia' ? t('r10c.headRussia') : '';
  const verdict = row.real == null ? '' : (row.real > 1.05 ? t('r10c.fasterThanCpi') : row.real < 0.95 ? t('r10c.slowerThanCpi') : t('r10c.likeCpi'));
  return (
    <p className="r10c-head">
      {t('r10c.head', { year: row.year, who, times: timesText(row.times, locale) }).replace(/\s{2,}/g, ' ')}
      {row.infl ? ` ${t('r10c.headCpi', { times: timesText(row.infl, locale) })}` : ''}
      {verdict ? <strong className="r10c-head__verdict"> {verdict}</strong> : null}
    </p>
  );
}

function Row({ r, unit, locale, t, firstYm, lastGapNote }) {
  if (!r.point) {
    const late = firstYm && Math.floor(firstYm / 100) > r.year;
    return (
      <li className="r10c-row r10c-row--empty">
        <span className="r10c-row__year">{r.year}</span>
        <span className="r10c-row__val">{t('r10c.noData')}</span>
        <span className="r10c-row__why">{late ? t('r10c.startedLater', { ym: ymLabelFrom(firstYm, locale) }) : lastGapNote}</span>
      </li>
    );
  }
  const real = realText(t, r.real);
  return (
    <li className="r10c-row">
      <span className="r10c-row__year">{r.year}<span className="r10c-row__mon">{ymLabel(r.point.year * 100 + r.point.month, locale).split(' ')[0]}</span></span>
      <span className="r10c-row__val fe-num">{money(r.point.value, unit, locale)}{r.source === 'russia' && <em className="r10c-tag">{t('r10c.russiaTag')}</em>}</span>
      <span className="r10c-row__x fe-num">{r.times != null ? timesShort(r.times, locale) : ''}</span>
      {(r.infl || real) && (
        <span className="r10c-row__sub">
          {r.infl ? t('r10c.infl', { times: timesShort(r.infl, locale) }) : ''}
          {r.infl && real ? ' ' : ''}
          {real}
        </span>
      )}
    </li>
  );
}

export function HistoryKeyYears({ series, russiaSeries, cpi, last, unit, discontinued = false }) {
  const { t, locale } = useLocale();
  const [open, setOpen] = useState(false);
  if (!Array.isArray(series) || !last || series.length < 24) return null;
  const rows = keyYearRows(series, russiaSeries, last, cpi);
  if (!rows.some((r) => r.point)) return null;
  const firstYm = series[0].year * 100 + series[0].month;
  const nowRow = (
    <li className="r10c-row r10c-row--now">
      <span className="r10c-row__year">{last.year}<span className="r10c-row__mon">{ymLabel(last.year * 100 + last.month, locale).split(' ')[0]}</span></span>
      <span className="r10c-row__val fe-num">{money(last.value, unit, locale)}</span>
      <span className="r10c-row__x">{t(discontinued ? 'r10c.lastData' : 'r10c.now')}</span>
    </li>
  );
  const yearly = open ? yearlyRows(series, last) : [];
  return (
    <section className="r10c-keys fe-panel" data-block="r10c-key-years" aria-labelledby="r10c-keys-h">
      <h2 id="r10c-keys-h" className="r10c-keys__h">{t('r10c.keyTitle')}</h2>
      <p className="r10c-keys__lead">{t('r10c.keyLead', { month: ymLabel(last.year * 100 + last.month, locale).split(' ')[0] })}</p>
      <Headline rows={rows} locale={locale} t={t} />
      <ul className="r10c-list">
        {rows.map((r) => <Row key={r.year} r={r} unit={unit} locale={locale} t={t} firstYm={firstYm} lastGapNote={t('r10c.noPoint')} />)}
        {nowRow}
      </ul>
      <button type="button" className="r10c-more fe-tap-inline" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {t(open ? 'r10c.hideYears' : 'r10c.allYears')}
        <ChevronDown size={14} aria-hidden="true" className={open ? 'r10c-chev is-open' : 'r10c-chev'} />
      </button>
      {open && (
        <ul className="r10c-list r10c-list--years">
          {yearly.map((y) => (
            <li key={y.year} className={`r10c-row r10c-row--y${y.point ? '' : ' r10c-row--empty'}`}>
              <span className="r10c-row__year">{y.year}</span>
              <span className="r10c-row__val fe-num">{y.point ? money(y.point.value, unit, locale) : t('r10c.noData')}</span>
              <span className="r10c-row__x fe-num">{y.yoy == null ? '' : `${y.yoy > 0 ? '+' : y.yoy < 0 ? '−' : ''}${Math.abs(y.yoy).toFixed(1).replace('.', locale === 'en' ? '.' : ',')}\u00A0%`}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="r10c-src">{cpi && cpi.length ? t('r10c.srcCpi') : t('r10c.srcNoCpi')}</p>
    </section>
  );
}

/** Примечание под графиком: с какого месяца есть данные и где пропуски. */
export function HistoryCoverage({ series, russiaSeries, discontinued }) {
  const { t, locale } = useLocale();
  if (!Array.isArray(series) || series.length < 2) return null;
  const first = series[0];
  const firstYm = first.year * 100 + first.month;
  const rf = Array.isArray(russiaSeries) && russiaSeries.length ? russiaSeries[0] : null;
  const rfYm = rf ? rf.year * 100 + rf.month : null;
  const gaps = monthGaps(series).filter((g) => g.months >= 2);
  const notes = [];
  if (first.year > 2000 || (rfYm && firstYm > rfYm)) {
    notes.push(t('r10c.startNote', { ym: ymLabelFrom(firstYm, locale) }));
  }
  if (gaps.length) {
    const g = gaps.slice(0, 3).map((x) => `${ymLabel(x.from, locale)} – ${ymLabel(x.to, locale)}`).join('; ');
    notes.push(t('r10c.gapNote', { gaps: g }) + (gaps.length > 3 ? t('r10c.gapMore', { n: gaps.length - 3 }) : ''));
  }
  if (!notes.length || discontinued) return notes.length ? <p className="r10c-cover" data-no-export="true">{notes.join(' ')}</p> : null;
  return <p className="r10c-cover" data-no-export="true">{notes.join(' ')}</p>;
}
