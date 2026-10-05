// Общие детали страниц региона России и территорий мира: крупные карточки, строки показателей,
// смысловой цвет изменений, поле поиска, заголовок раздела. Один вид вместо двух копий.
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import DeltaBadge from '../DeltaBadge';
import { indicatorPolarity } from '../../lib/deltaTone';
import { yearDelta } from '../../lib/regionsApi';
import {
  compactParts, explainIndicator, formatRegionWithUnit, formatDeltaPercent, formatPointsDelta, isPercentUnit, plainIndicatorTitle,
} from '../../lib/regionUi';
import { useLocale } from '../../i18n';
import '../../styles/regions-w4.css';

/** Изменение к прошлому периоду: стрелка и цвет — по смыслу показателя (падение безработицы — хорошо). */
export function RegionDelta({ value, prevValue, name, label, unit }) {
  const { locale } = useLocale();
  // Показатель в процентах (инфляция, безработица): честнее разница в пунктах, а не «+32,9 %».
  if (isPercentUnit(unit)) {
    const pts = formatPointsDelta(value, prevValue, locale);
    if (!pts) return null;
    return (
      <span title={locale === 'en'
        ? 'Change in percentage points: the difference between this year and the previous one.'
        : 'Изменение в процентных пунктах: разница между этим годом и прошлым.'}
      >
        <DeltaBadge delta={pts.diff} polarity={indicatorPolarity(name, label)} className="text-xs">
          {pts.text}
        </DeltaBadge>
      </span>
    );
  }
  const d = yearDelta(value, prevValue);
  if (!d) return null;
  const signed = d.pct < 0 ? -Math.abs(d.pct) : Math.abs(d.pct);
  return (
    <DeltaBadge
      delta={d.up || d.down ? signed : 0}
      polarity={indicatorPolarity(name, label)}
      className="text-xs"
    >
      {formatDeltaPercent(signed, locale)}
    </DeltaBadge>
  );
}

/**
 * Крошечный указатель направления «было → стало» (прошлый год и последний): короткая линия с точкой.
 * Это не история ряда, а наглядный знак роста или падения; полный график открывается по нажатию на строку.
 */
export function TrendTick({ value, prevValue, polarity = 'neutral' }) {
  const a = Number(prevValue);
  const b = Number(value);
  if (value == null || prevValue == null || !Number.isFinite(a) || !Number.isFinite(b)) return null;
  const same = Math.abs(b - a) < 1e-9;
  const y1 = same ? 10 : (b > a ? 15 : 5);
  const y2 = same ? 10 : (b > a ? 5 : 15);
  const good = (b > a && polarity === 'up-good') || (b < a && polarity === 'up-bad');
  const bad = (b > a && polarity === 'up-bad') || (b < a && polarity === 'up-good');
  const color = good ? '#15803d' : bad ? '#b91c1c' : '#AD8A48';
  return (
    <svg className="fe-trend-tick" viewBox="0 0 44 20" width="44" height="20" aria-hidden="true" focusable="false">
      <line x1="3" y1={y1} x2="39" y2={y2} stroke={color} strokeWidth="2" strokeLinecap="round" />
      <circle cx="39" cy={y2} r="2.6" fill={color} />
    </svg>
  );
}

/** Значение: число жирным, единица обычным шрифтом и не переносится отдельно от числа. */
export function RegionValue({ value, unit, locale }) {
  const parts = compactParts(value, unit, locale);
  return (
    <>
      {parts.num}
      {parts.unit ? <>{'\u00A0'}<span className="font-normal text-text-secondary">{parts.unit}</span></> : null}
    </>
  );
}

export function RegionHeadlineCard({ item, to, index = 0 }) {
  const { locale, t } = useLocale();
  const empty = item.value == null;
  const Card = empty ? 'div' : Link;
  const label = item.label || item.name;
  return (
    <Card
      {...(empty ? { 'aria-disabled': true } : { to })}
      className="fe-panel fe-summary-card fe-press fe-reveal group flex min-w-0 flex-col rounded-2xl border border-border-subtle bg-surface p-3.5 transition-colors hover:border-border-champagne"
      style={{ '--fe-delay': `${Math.min(index, 5) * 0.04}s`, '--fe-rise': '8px' }}
    >
      <div className="line-clamp-2 min-h-[2.4em] text-[13px] leading-snug text-text-secondary">{label}</div>
      <div className="fe-num mt-1.5 whitespace-nowrap text-[1.15rem] font-semibold leading-tight tabular-nums text-text-primary">
        <RegionValue value={item.value} unit={item.unit} locale={locale} />
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-xs text-text-tertiary">{item.period_label || item.year}</span>
        <RegionDelta value={item.value} prevValue={item.prev_value} name={item.name} label={item.label} unit={item.unit} />
      </div>
      {empty && <span className="sr-only">{t('common.noData')}</span>}
    </Card>
  );
}

export function RegionIndicatorRow({ item, to, title }) {
  const { locale } = useLocale();
  const empty = item.value == null;
  const explain = explainIndicator(item.name, item.unit, locale);
  const Card = empty ? 'div' : Link;
  return (
    <Card
      {...(empty ? { 'aria-disabled': true } : { to })}
      className="fe-press group flex min-w-0 flex-col gap-2 rounded-2xl border border-border-subtle bg-surface px-3.5 py-3 transition-colors hover:border-border-champagne sm:min-h-[84px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[14px] leading-snug text-text-primary transition-colors group-hover:text-champagne-ink">
          {title || plainIndicatorTitle(item.name, locale)}
        </div>
        {explain ? <div className="mt-1 text-xs leading-snug text-text-secondary" data-testid="row-explain">{explain}</div> : null}
      </div>
      <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle/60 pt-2 sm:w-[9.5rem] sm:shrink-0 sm:flex-col sm:items-end sm:justify-center sm:gap-1 sm:border-0 sm:pt-0 sm:text-right">
        <div className="fe-num whitespace-nowrap text-[15px] font-semibold tabular-nums text-text-primary">
          <RegionValue value={item.value} unit={item.unit} locale={locale} />
        </div>
        <div className="flex items-center gap-2">
          <TrendTick value={item.value} prevValue={item.prev_value} polarity={indicatorPolarity(item.name)} />
          <RegionDelta value={item.value} prevValue={item.prev_value} name={item.name} unit={item.unit} />
          <span className="text-xs text-text-tertiary">{item.period_label || item.year}</span>
        </div>
      </div>
    </Card>
  );
}

/** Заголовок раздела: небольшая надпись обычным регистром, крупное имя, число показателей. */
export function RegionSectionHeading({ eyebrow, title, count, id }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4">
      <div className="min-w-0">
        {eyebrow && <div className="text-xs font-medium text-champagne-ink">{eyebrow}</div>}
        <h2 id={id} className="mt-0.5 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">{title}</h2>
      </div>
      {count != null && <span className="shrink-0 pb-1 text-sm tabular-nums text-text-secondary">{count}</span>}
    </div>
  );
}

export function RegionSearchField({ value, onChange, placeholder, ariaLabel, className = '' }) {
  return (
    <div className={`relative ${className}`}>
      <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary" aria-hidden="true" />
      <input
        type="search"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="min-h-12 w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-[15px] text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-champagne-ink focus:outline-none focus:ring-[3px] focus:ring-champagne/25"
        aria-label={ariaLabel}
      />
    </div>
  );
}

/** Одна строка «Показатель: 3,4 %, 15-е место» в списке территорий. */
export function RegionMetricLine({ name, value, unit, rank }) {
  const { locale, t } = useLocale();
  if (value == null) return null;
  return (
    <div className="mt-1 text-sm leading-snug text-text-secondary">
      {name ? <span>{name}: </span> : null}
      <span className="fe-num font-medium text-text-primary">{formatRegionWithUnit(value, unit, locale)}</span>
      {rank != null && <span>, {t('w4.rank.place', { n: rank })}</span>}
    </div>
  );
}
