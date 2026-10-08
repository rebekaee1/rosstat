// Строка показателя страны: понятное название, число с единицей, смысл изменения словами, мини-график.
import {
  useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar, CalendarDays, CalendarRange, ChevronDown, Clock3, Info,
} from 'lucide-react';
import Button from '../Button';
import {
  useWorldIndicatorData, formatWorldValue, localizeWorldUnit, pluralRu,
} from '../../lib/worldApi';
import { indicatorPublicName } from '../../lib/worldViewModes';
import { formatCount, formatDate, formatValue } from '../../lib/format';
import { indicatorPolarity } from '../../lib/deltaTone';
import { splitUnit } from '../../lib/countryFlag';
import { shortUsIndicatorName } from '../../lib/usCatalogTopics';
import { dropRepeatedUnit, groupMemberLabel, groupNearDuplicates } from '../../lib/countryIndicatorGroups';
import {
  compactMoneyAmount, describeChange, figureDigits, splitTechnicalNote,
} from '../../lib/countryKeyFigures';
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
    ? `${primaryIsAggregated ? '~' : ''}${toLabel(primary)}; ${t('z5.freq.also')}: ${restLabels.join(', ')}`
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

/**
 * Показывает, можно ли грузить мини-график строки: `seen` — строка постояла на экране и бюджет запросов ещё есть,
 * `skipped` — бюджет за визит исчерпан (слот скрывается, а не мерцает вечным скелетом).
 */
function useSeenOnce(ref, allowed) {
  const [state, setState] = useState('idle');
  const budget = useContext(SparkBudgetContext);
  useEffect(() => {
    if (!allowed || state !== 'idle' || !ref.current || typeof IntersectionObserver === 'undefined') return undefined;
    let timer = 0;
    const observer = new IntersectionObserver(([entry]) => {
      window.clearTimeout(timer);
      if (!entry.isIntersecting) return;
      // Быструю прокрутку не нагружаем запросами: ждём, пока строка постоит на экране.
      timer = window.setTimeout(() => {
        setState(budget && !budget.claim() ? 'skipped' : 'seen');
        observer.disconnect();
      }, SPARK_DELAY_MS);
    }, { rootMargin: '120px 0px' });
    observer.observe(ref.current);
    return () => { window.clearTimeout(timer); observer.disconnect(); };
  }, [allowed, state, ref, budget]);
  return state;
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

export function IndicatorRow({
  item, slug, to, sectionName, sparkEnabled = true, titleOverride = '',
}) {
  const t = useT();
  const { locale } = useLocale();
  const ref = useRef(null);
  const seenState = useSeenOnce(ref, sparkEnabled);
  const seen = seenState === 'seen';
  const unitFull = localizeWorldUnit(item.unit, locale);
  const rawName = dropRepeatedUnit(
    shortUsIndicatorName(indicatorPublicName(item, locale), sectionName, locale),
    unitFull,
  );
  const tech = splitTechnicalNote(rawName, unitFull);
  const unit = splitUnit(tech.unit);
  const polarity = indicatorPolarity(indicatorPublicName(item, locale));
  const change = item.change != null && Number.isFinite(Number(item.change)) ? Number(item.change) : null;
  // Сумма из десяти и более цифр («56 459 257 590 евро») читается как «56,5 млрд €».
  const compactValue = compactMoneyAmount(item.last_value, unit.short, locale);
  const valueText = compactValue
    ? formatValue(compactValue.value, figureDigits(compactValue.value), locale)
    : formatWorldValue(item.last_value, undefined, locale);
  const valueUnit = compactValue ? compactValue.unit : unit.short;
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
        <span className="z5-row__title" title={titleOverride ? tech.name : undefined}>{titleOverride || tech.name}</span>
        {tech.note ? (
          <span className="z5-row__info" title={tech.note} aria-label={tech.note}>
            <Info size={13} aria-hidden="true" />
          </span>
        ) : null}
      </div>
      <div className="z5-row__main">
        <div className="z5-row__value">
          <span className="z5-row__num">{valueText}</span>
          {valueUnit ? <small>{valueUnit}</small> : null}
        </div>
        {sparkEnabled && seenState !== 'skipped' ? (
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

/** Сколько вложенных строк группа показывает сразу: в группе «Занятые по стажу…» их сотни. */
const GROUP_FIRST = 12;

/** Несколько близких показателей («Число родившихся» в трёх разрезах) одной свёрнутой строкой; строки рисуются при раскрытии. */
function IndicatorGroup({ group, slug, sectionName, sparkEnabled, locale }) {
  const t = useT();
  const n = group.items.length;
  const [opened, setOpened] = useState(false);
  const [shown, setShown] = useState(GROUP_FIRST);
  const word = locale === 'en'
    ? t('w6b.country.cuts_many')
    : pluralRu(n, [t('w6b.country.cuts_one'), t('w6b.country.cuts_few'), t('w6b.country.cuts_many')]);
  const visible = group.items.slice(0, shown);
  return (
    <details
      className="fe-ind-group z5-group"
      onToggle={(event) => { if (event.currentTarget.open) setOpened(true); }}
    >
      <summary className="fe-ind-group__summary">
        <span className="fe-ind-group__name">{group.base}</span>
        <span className="fe-ind-group__count">{n} {word}</span>
        <ChevronDown size={16} aria-hidden="true" className="fe-ind-group__chevron" />
      </summary>
      {opened ? (
        <>
          <div className="z5-rows z5-rows--nested">
            {visible.map((ind) => (
              <IndicatorRow
                key={ind.code}
                item={ind}
                slug={slug}
                sectionName={sectionName}
                sparkEnabled={sparkEnabled}
                titleOverride={groupMemberLabel(
                  indicatorPublicName(ind, locale),
                  group.base,
                  localizeWorldUnit(ind.unit, locale),
                )}
              />
            ))}
          </div>
          {n > shown ? (
            <Button variant="secondary" onClick={() => setShown((value) => value + 48)} className="mt-3 rounded-full! px-5">
              {t('c9c.rows.more', { n: formatCount(n - shown, locale) })}
            </Button>
          ) : null}
        </>
      ) : null}
    </details>
  );
}

/** Ряды, по которым давно нет новых данных, лежат в конце одной свёрнутой строкой «В архиве». */
function ArchivedGroup({ items, slug, sectionName, locale }) {
  const t = useT();
  const [opened, setOpened] = useState(false);
  return (
    <details
      className="fe-ind-group z5-group z5-group--archive"
      onToggle={(event) => { if (event.currentTarget.open) setOpened(true); }}
    >
      <summary className="fe-ind-group__summary">
        <span className="fe-ind-group__name">{t('c9c.archive.title')}</span>
        <span className="fe-ind-group__count">{formatCount(items.length, locale)}</span>
        <ChevronDown size={16} aria-hidden="true" className="fe-ind-group__chevron" />
      </summary>
      {opened ? (
        <div className="z5-rows z5-rows--nested">
          {items.map((ind) => (
            <IndicatorRow key={ind.code} item={ind} slug={slug} sectionName={sectionName} sparkEnabled={false} />
          ))}
        </div>
      ) : null}
    </details>
  );
}

/** Первые строки темы, если их много: «Рынок труда» не раскрывается стеной в тысячи карточек. */
export const ROWS_FIRST = 8;
const ROWS_STEP = 24;

/** Строки категории: почти-дубли свёрнуты, архивные ряды в конце, длинная тема открывается порциями. */
export function IndicatorRows({
  items, slug, sectionName, locale, collapse, sparkEnabled = true, firstRows = Infinity,
}) {
  const t = useT();
  const { active, archived } = useMemo(() => {
    const list = Array.isArray(items) ? items : [];
    return collapse
      ? { active: list.filter((item) => !item.archived), archived: list.filter((item) => item.archived) }
      : { active: list, archived: [] };
  }, [items, collapse]);
  const rows = useMemo(
    () => (collapse
      ? groupNearDuplicates(active, (item) => indicatorPublicName(item, locale))
      : active.map((item) => ({ kind: 'single', item }))),
    [active, locale, collapse],
  );
  const [limit, setLimit] = useState(firstRows);
  // Лишняя кнопка «Показать ещё 1» не нужна: небольшой хвост показываем сразу.
  const shownCount = rows.length <= limit + 2 ? rows.length : limit;
  const shownRows = rows.slice(0, shownCount);
  const hiddenIndicators = rows.slice(shownCount)
    .reduce((sum, row) => sum + (row.kind === 'group' ? row.items.length : 1), 0);
  return (
    <>
      {shownRows.map((row) => (row.kind === 'group'
        ? (
          <IndicatorGroup
            key={`g-${row.items[0].code}`}
            group={row}
            slug={slug}
            sectionName={sectionName}
            sparkEnabled={sparkEnabled}
            locale={locale}
          />
        )
        : <IndicatorRow key={row.item.code} item={row.item} slug={slug} sectionName={sectionName} sparkEnabled={sparkEnabled} />))}
      {hiddenIndicators > 0 ? (
        <Button
          variant="secondary"
          onClick={() => setLimit(shownCount + ROWS_STEP)}
          className="z5-rows__more rounded-full! px-5"
        >
          {t('c9c.rows.more', { n: formatCount(hiddenIndicators, locale) })}
        </Button>
      ) : null}
      {archived.length > 0 && hiddenIndicators === 0 ? (
        <ArchivedGroup items={archived} slug={slug} sectionName={sectionName} locale={locale} />
      ) : null}
    </>
  );
}
