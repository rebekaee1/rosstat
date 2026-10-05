// Строка показателя страны: понятное название, число с единицей, смысл изменения словами, мини-график.
import {
  useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar, CalendarDays, CalendarRange, ChevronDown, Clock3, Info,
} from 'lucide-react';
import {
  useWorldIndicatorData, formatWorldValue, localizeWorldUnit, pluralRu,
} from '../../lib/worldApi';
import { indicatorPublicName } from '../../lib/worldViewModes';
import { formatDate } from '../../lib/format';
import { indicatorPolarity } from '../../lib/deltaTone';
import { splitUnit } from '../../lib/countryFlag';
import { shortUsIndicatorName } from '../../lib/usCatalogTopics';
import { dropRepeatedUnit, groupNearDuplicates } from '../../lib/countryIndicatorGroups';
import { describeChange, splitTechnicalNote } from '../../lib/countryKeyFigures';
import { indicatorPath } from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import DeltaBadge from '../DeltaBadge';
import Sparkline from '../Sparkline';
import { SparkBudgetContext } from './sparkBudget';
import '../../styles/z5-country.css';

function formatIndicatorDate(dateStr, frequency, locale) {
  if (!dateStr) return '—';
  if (frequency === 'annual') return formatDate(dateStr, 'annual', locale);
  if (frequency === 'quarterly') return formatDate(dateStr, 'quarterly', locale);
  return formatDate(dateStr, 'full', locale);
}

/**
 * Частота плитки: самая детальная из доступных. Показывается значком календаря с подсказкой
 * (слово для скринридера скрыто рядом); остальные частоты перечислены в подсказке.
 */
const FREQ_BADGE_PRIORITY = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'];
const FREQ_ICON = {
  daily: Clock3, weekly: Clock3, monthly: CalendarDays, quarterly: CalendarRange, annual: Calendar,
};

export function FreqBadges({ item, t }) {
  const officialFreqs = Array.isArray(item.frequencies)
    ? item.frequencies.map((f) => (typeof f === 'string' ? f : f.freq)).filter(Boolean)
    : (item.frequency ? [item.frequency] : []);
  const aggregated = Array.isArray(item.aggregated_frequencies)
    ? item.aggregated_frequencies.filter((f) => f && !officialFreqs.includes(f))
    : [];
  if (!officialFreqs.length && !aggregated.length) return null;

  const toLabel = (f) => {
    const key = `world.freq.${f}`;
    const label = t(key);
    return label !== key ? label : f;
  };

  const byPriority = (freqs) => FREQ_BADGE_PRIORITY.filter((f) => freqs.includes(f));
  const shown = byPriority([...officialFreqs, ...aggregated]);
  if (!shown.length) return null;
  const primary = shown[0];
  const primaryIsAggregated = !officialFreqs.includes(primary);
  // Официальный годовой ряд: дата «2025» и так говорит «раз в год»; лишний значок только рвёт строку.
  if (primary === 'annual' && !primaryIsAggregated) return null;
  const restLabels = shown.slice(1).map(
    (f) => `${officialFreqs.includes(f) ? '' : '~'}${toLabel(f)}`,
  );
  const title = restLabels.length
    ? `${primaryIsAggregated ? '~' : ''}${toLabel(primary)}; также: ${restLabels.join(', ')}`
    : undefined;
  const Icon = FREQ_ICON[primary] || CalendarDays;

  return (
    <span
      title={title || `${primaryIsAggregated ? '~' : ''}${toLabel(primary)}`}
      className={`z5-freq${primaryIsAggregated ? ' z5-freq--est' : ''}`}
    >
      <Icon size={13} aria-hidden="true" />
      <span className="sr-only">{primaryIsAggregated ? '~' : ''}{toLabel(primary)}</span>
    </span>
  );
}

const SPARK_DELAY_MS = 320;

function useSeenOnce(ref, allowed) {
  const [seen, setSeen] = useState(false);
  const budget = useContext(SparkBudgetContext);
  useEffect(() => {
    if (!allowed || seen || !ref.current || typeof IntersectionObserver === 'undefined') return undefined;
    let timer = 0;
    const observer = new IntersectionObserver(([entry]) => {
      window.clearTimeout(timer);
      if (!entry.isIntersecting) return;
      // Быструю прокрутку не нагружаем запросами: ждём, пока строка постоит на экране.
      timer = window.setTimeout(() => {
        if (budget && !budget.claim()) return;
        setSeen(true);
        observer.disconnect();
      }, SPARK_DELAY_MS);
    }, { rootMargin: '120px 0px' });
    observer.observe(ref.current);
    return () => { window.clearTimeout(timer); observer.disconnect(); };
  }, [allowed, seen, ref, budget]);
  return seen;
}

function RowSpark({ slug, item, spark }) {
  const seriesQ = useWorldIndicatorData(slug, item.code, `level-${item.frequency || 'annual'}`);
  const values = useMemo(
    () => (seriesQ.data?.points || []).map((point) => Number(point.value)).filter(Number.isFinite).slice(-48),
    [seriesQ.data],
  );
  if (seriesQ.isLoading) return <span className="z5-spark-skel z5-spark-skel--row" />;
  if (values.length < 2) return <span className="z5-row__spark-empty" />;
  return (
    <Sparkline points={values} trend="flat" sentiment="neutral" height={spark} />
  );
}

/** Единица для фразы об изменении: проценты и индексы дают «пункты», остальное — как есть. */
function changeUnit(unitText, short) {
  const text = String(unitText || '').trim();
  if (/^%/.test(text)) return '%';
  if (/^(индекс|index|пункт|point)/i.test(text)) return 'индекс';
  return short;
}

export function IndicatorRow({ item, slug, to, sectionName, sparkEnabled = true }) {
  const t = useT();
  const { locale } = useLocale();
  const ref = useRef(null);
  const seen = useSeenOnce(ref, sparkEnabled);
  const unitFull = localizeWorldUnit(item.unit, locale);
  const rawName = dropRepeatedUnit(
    shortUsIndicatorName(indicatorPublicName(item, locale), sectionName, locale),
    unitFull,
  );
  const tech = splitTechnicalNote(rawName, unitFull);
  const unit = splitUnit(tech.unit);
  const polarity = indicatorPolarity(indicatorPublicName(item, locale));
  const change = item.change != null && Number.isFinite(Number(item.change)) ? Number(item.change) : null;
  const meaning = change != null
    ? describeChange({
      change,
      unit: changeUnit(tech.unit, unit.short),
      frequency: item.frequency,
      locale,
      t,
    })
    : '';
  return (
    <Link
      ref={ref}
      to={to || indicatorPath(slug, item.code)}
      className="z5-row fe-press group"
    >
      <div className="z5-row__name">
        <span className="z5-row__title">{tech.name}</span>
        {tech.note ? (
          <span className="z5-row__info" title={tech.note} aria-label={tech.note}>
            <Info size={13} aria-hidden="true" />
          </span>
        ) : null}
      </div>
      <div className="z5-row__main">
        <div className="z5-row__value">
          <span className="z5-row__num">{formatWorldValue(item.last_value, undefined, locale)}</span>
          {unit.short ? <small>{unit.short}</small> : null}
        </div>
        {sparkEnabled ? (
          <div className="z5-row__spark" aria-hidden="true">
            {seen
              ? <RowSpark slug={slug} item={item} spark={40} />
              : <span className="z5-spark-skel z5-spark-skel--row" />}
          </div>
        ) : null}
      </div>
      {meaning ? (
        <DeltaBadge delta={change} polarity={polarity} className="z5-row__meaning">
          {meaning}
        </DeltaBadge>
      ) : null}
      <div className="z5-row__meta">
        <FreqBadges item={item} t={t} />
        {unit.long ? <span className="z5-row__unit" title={unit.long}>{unit.long}</span> : null}
        <span className="z5-row__date">{formatIndicatorDate(item.last_date, item.frequency, locale)}</span>
      </div>
    </Link>
  );
}

/** Несколько близких показателей («Число родившихся» в трёх разрезах) одной свёрнутой строкой. */
function IndicatorGroup({ group, slug, sectionName, sparkEnabled }) {
  const t = useT();
  const { locale } = useLocale();
  const n = group.items.length;
  const word = locale === 'en'
    ? t('w6b.country.cuts_many')
    : pluralRu(n, [t('w6b.country.cuts_one'), t('w6b.country.cuts_few'), t('w6b.country.cuts_many')]);
  return (
    <details className="fe-ind-group z5-group">
      <summary className="fe-ind-group__summary">
        <span className="fe-ind-group__name">{group.base}</span>
        <span className="fe-ind-group__count">{n} {word}</span>
        <ChevronDown size={16} aria-hidden="true" className="fe-ind-group__chevron" />
      </summary>
      <div className="z5-rows z5-rows--nested">
        {group.items.map((ind) => (
          <IndicatorRow key={ind.code} item={ind} slug={slug} sectionName={sectionName} sparkEnabled={sparkEnabled} />
        ))}
      </div>
    </details>
  );
}

/** Строки категории: почти-дубли свёрнуты, остальные показатели идут как есть. */
export function IndicatorRows({
  items, slug, sectionName, locale, collapse, sparkEnabled = true,
}) {
  const rows = useMemo(
    () => (collapse
      ? groupNearDuplicates(items, (item) => indicatorPublicName(item, locale))
      : items.map((item) => ({ kind: 'single', item }))),
    [items, locale, collapse],
  );
  return rows.map((row) => (row.kind === 'group'
    ? <IndicatorGroup key={`g-${row.items[0].code}`} group={row} slug={slug} sectionName={sectionName} sparkEnabled={sparkEnabled} />
    : <IndicatorRow key={row.item.code} item={row.item} slug={slug} sectionName={sectionName} sparkEnabled={sparkEnabled} />));
}
