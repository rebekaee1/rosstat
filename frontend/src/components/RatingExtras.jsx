import { Link } from 'react-router-dom';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { pluralRu } from '../lib/worldApi';
import { cn, formatValue } from '../lib/format';
import { deltaTone } from '../lib/deltaTone';
import '../styles/w6d.css';

/** Мини-график страны по годам: линия и точка последнего значения; цветом не оценивает, только форма. */
export function RatingSpark({ points = [], label = '', width = 76, height = 26 }) {
  if (!points || points.length < 2) return <span className="w6d-spark w6d-spark--empty" aria-hidden="true" />;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pad = 3;
  const step = (width - pad * 2) / (points.length - 1);
  const flat = max === min;
  const xy = points.map((p, i) => [
    pad + i * step,
    flat ? height / 2 : pad + (height - pad * 2) - ((p.value - min) / range) * (height - pad * 2),
  ]);
  const last = xy[xy.length - 1];
  return (
    <svg
      className="w6d-spark"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role={label ? 'img' : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : 'true'}
      focusable="false"
    >
      <polyline points={xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="2.4" fill="currentColor" />
    </svg>
  );
}

/**
 * Изменение к прошлому году: стрелка и число. Для показателей в процентах — разность в процентных пунктах,
 * иначе относительное изменение в процентах. Цвет отражает смысл («лучше/хуже»), а при неясном смысле остаётся нейтральным.
 */
export function RatingDelta({ change, percentUnit = false, polarity = 'neutral', locale = 'ru' }) {
  const t = useT();
  if (!change) return <span className="w6d-delta w6d-delta--none" aria-label={t('w6d.rating.noChange')}>—</span>;
  const amount = percentUnit || change.pct == null ? change.abs : change.pct;
  const unit = percentUnit ? t('w6d.rating.pp') : change.pct == null ? '' : '%';
  const flat = Math.abs(amount) < 0.05;
  const tone = flat ? 'flat' : deltaTone(amount, polarity);
  const Icon = flat ? Minus : amount > 0 ? ArrowUpRight : ArrowDownRight;
  const sign = flat ? '' : amount > 0 ? '+' : '−';
  const text = flat ? '0' : `${sign}${formatValue(Math.abs(amount), Math.abs(amount) >= 100 ? 0 : 1, locale)}${unit ? ` ${unit}` : ''}`;
  return (
    <span
      className={cn('w6d-delta', `w6d-delta--${tone}`)}
      title={t('w6d.rating.vsYear', { year: change.year })}
      aria-label={`${text}, ${t('w6d.rating.vsYear', { year: change.year })}`}
    >
      <Icon size={14} aria-hidden="true" />
      {text}
    </span>
  );
}

/** Блок «Другие годы»: постоянные ссылки на рейтинг за каждый год. */
export function OtherYears({ years = [], activeYear, hrefFor, onPick = null }) {
  const t = useT();
  const list = [...(years || [])].filter((y) => y !== activeYear).sort((a, b) => b - a);
  if (!list.length) return null;
  return (
    <section className="w6d-years" aria-labelledby="w6d-years-title">
      <h2 id="w6d-years-title" className="w6d-block-title">{t('w6d.rating.otherYears')}</h2>
      <ul className="w6d-years__list">
        {list.map((year) => (
          <li key={year}>
            <Link className="w6d-year-link fe-press" to={hrefFor(year)} onClick={() => onPick?.(year)}>{year}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Блок «Как изменились места за 5 лет»: кто поднялся, кто опустился. */
export function RankShifts({ shifts, nameOf, hrefOf }) {
  const t = useT();
  const { locale } = useLocale();
  if (!shifts || (!shifts.risers.length && !shifts.fallers.length)) return null;
  const spanYears = shifts.toYear - shifts.fromYear;
  const row = (move, sign) => (
    <li key={move.code} className="w6d-shift">
      <Link to={hrefOf(move.code)} className="w6d-shift__name fe-press">{nameOf(move.code)}</Link>
      <span className={cn('w6d-shift__delta', sign > 0 ? 'is-up' : 'is-down')}>
        {sign > 0 ? <ArrowUpRight size={14} aria-hidden="true" /> : <ArrowDownRight size={14} aria-hidden="true" />}
        {Math.abs(move.change)}
      </span>
      <span className="w6d-shift__places">{t('w6d.rating.fromTo', { from: move.then, to: move.now })}</span>
    </li>
  );
  return (
    <section className="w6d-shifts" aria-labelledby="w6d-shifts-title">
      <h2 id="w6d-shifts-title" className="w6d-block-title">
        {t('w6d.rating.shiftsTitle', {
          n: spanYears,
          unit: t(`w6d.rating.yearUnit.${locale === 'ru' ? pluralRu(spanYears, ['one', 'few', 'many']) : spanYears === 1 ? 'one' : 'many'}`),
        })}
      </h2>
      <p className="w6d-shifts__lead">{t('w6d.rating.shiftsLead', { from: shifts.fromYear, to: shifts.toYear })}</p>
      <div className="w6d-shifts__cols">
        {shifts.risers.length > 0 && (
          <div>
            <h3 className="w6d-shifts__head">{t('w6d.rating.risers')}</h3>
            <ul className="w6d-shifts__list">{shifts.risers.map((m) => row(m, 1))}</ul>
          </div>
        )}
        {shifts.fallers.length > 0 && (
          <div>
            <h3 className="w6d-shifts__head">{t('w6d.rating.fallers')}</h3>
            <ul className="w6d-shifts__list">{shifts.fallers.map((m) => row(m, -1))}</ul>
          </div>
        )}
      </div>
    </section>
  );
}
