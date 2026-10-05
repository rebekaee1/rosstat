// «Главное» страны: 3-4 крупные цифры с золотым мини-графиком за годы и подписью «год назад».
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Spline } from 'lucide-react';
import {
  useWorldIndicatorData, formatWorldValue, localizeWorldUnit,
} from '../../lib/worldApi';
import { localizedDisplay } from '../../lib/worldViewModes';
import { formatDate } from '../../lib/format';
import { deltaTone, indicatorPolarity } from '../../lib/deltaTone';
import { splitUnit } from '../../lib/countryFlag';
import { homeConceptLabel } from '../../lib/homeWorkbench';
import {
  figureDigits, humanizeQualifier, scaleMoneyUnit, yearAgoPoint,
} from '../../lib/countryKeyFigures';
import { preloadedFigurePoints } from '../../lib/countryBootstrap';
import { indicatorPath } from '../../lib/sitePaths';
import { useT } from '../../i18n';
import DeltaBadge from '../DeltaBadge';
import Sparkline from '../Sparkline';
import WorldCountUp from '../WorldCountUp';
import useSparkHeight from './useSparkHeight';
import '../../styles/z5-country.css';
import '../../styles/k6-country.css';

/** Сколько последних точек ряда рисуем: примерно десять лет при любой частоте. */
const SPARK_POINTS = { daily: 120, weekly: 120, monthly: 120, quarterly: 40, annual: 12 };
export const KEY_FIGURES_MAX = 4;

function kpiDigits(value) {
  const abs = Math.abs(Number(value));
  if (abs >= 1000) return 0;
  return abs >= 1 ? 1 : 2;
}

function formatPeriod(dateStr, frequency, locale) {
  if (!dateStr) return '—';
  if (frequency === 'annual') return formatDate(dateStr, 'annual', locale);
  if (frequency === 'quarterly') return formatDate(dateStr, 'quarterly', locale);
  return formatDate(dateStr, 'full', locale);
}

function KeyFigureCard({ item, slug, locale, index, preload }) {
  const t = useT();
  const sparkHeight = useSparkHeight(88, 52);
  const frequency = item.frequency || 'annual';
  const mode = `${item.concept_slug === 'hicp-index' ? 'yoy' : 'level'}-${frequency}`;
  // Сервер уже положил точки этого ряда в страницу: карточка рисуется без запроса.
  const preloaded = useMemo(() => preloadedFigurePoints(preload, item), [preload, item]);
  const seriesQ = useWorldIndicatorData(slug, item.indicator_code, mode, { enabled: !preloaded });
  const allPoints = useMemo(
    () => preloaded || (seriesQ.data?.points || []).filter((point) => Number.isFinite(Number(point.value))),
    [preloaded, seriesQ.data],
  );
  const spark = useMemo(
    () => allPoints.map((point) => Number(point.value)).slice(-(SPARK_POINTS[frequency] || 40)),
    [allPoints, frequency],
  );
  const unitText = localizeWorldUnit(item.unit, locale);
  const unit = splitUnit(unitText);
  const fullName = localizedDisplay(locale, item.name, item.name_en);
  const kpiName = homeConceptLabel(item.concept_slug, t, fullName);
  const polarity = indicatorPolarity(kpiName, fullName);

  // Крупная сумма читается как «849,7 млрд €», а не «849 680».
  const scaled = scaleMoneyUnit(item.value, unitText, locale);
  const present = (raw) => {
    const s = scaleMoneyUnit(raw, unitText, locale);
    if (s) return { text: formatWorldValue(s.value, figureDigits(s.value), locale), unit: s.unit };
    return { text: formatWorldValue(raw, kpiDigits(raw), locale), unit: unit.short };
  };
  const main = present(item.value);
  const format = (value) => (scaled
    ? formatWorldValue(scaleMoneyUnit(value, unitText, locale)?.value ?? value, figureDigits(scaled.value), locale)
    : formatWorldValue(value, kpiDigits(item.value), locale));

  // «изменение за год, %» уже сказано в названии: не повторяем в подписи периода.
  const longUnit = !scaled && unit.long && unit.long !== unit.short && !/за год|year[- ]over[- ]year|yoy/i.test(unit.long)
    ? unit.long
    : '';
  const qualifier = scaled?.qualifier ? humanizeQualifier(scaled.qualifier, t) : '';
  const period = formatPeriod(item.date, frequency, locale);
  const caption = longUnit || qualifier ? `${period}, ${longUnit || qualifier}` : period;

  const ago = useMemo(() => yearAgoPoint(allPoints, frequency), [allPoints, frequency]);
  const agoText = ago ? present(ago.value) : null;
  const diff = ago ? Number(item.value) - ago.value : 0;

  return (
    <Link
      to={indicatorPath(slug, item.indicator_code)}
      className="w2-kpi z5-key fe-press fe-glint fe-cursor-light fe-reveal fe-reveal--free fe-reveal--stagger"
      data-tone={ago ? deltaTone(diff, polarity) : undefined}
      style={{ '--i': index, '--fe-duration': '0.45s', '--fe-rise': '12px' }}
    >
      <span className="w2-kpi-name z5-key__name" title={fullName}>{kpiName}</span>
      <span className="w2-kpi-value z5-key__value">
        <WorldCountUp value={item.value} format={format} fromZero={false} />
        {main.unit && <small>{main.unit}</small>}
      </span>
      <span className="w2-kpi-period z5-key__period" title={scaled?.qualifier || undefined}>{caption}</span>
      {agoText ? (
        <DeltaBadge delta={diff} polarity={polarity} className="z5-key__ago">
          {t('z5.key.yearAgo', { value: `${agoText.text}${agoText.unit ? `\u00a0${agoText.unit}` : ''}` })}
        </DeltaBadge>
      ) : <span className="z5-key__ago z5-key__ago--empty" aria-hidden="true" />}
      <span className="w2-kpi-spark z5-key__spark" aria-hidden="true">
        {seriesQ.isLoading && !preloaded
          ? <span className="z5-spark-skel" />
          : (spark.length > 1
            ? <Sparkline points={spark} trend="flat" sentiment="neutral" height={sparkHeight} staggerMs={index * 90} />
            : (
              <span className="w2-kpi-nospark">
                <Spline size={14} aria-hidden="true" />
                {t('w6b.country.noChart')}
              </span>
            ))}
      </span>
    </Link>
  );
}

export default function CountryKeyFigures({ items, slug, locale, preload = null }) {
  const t = useT();
  const list = (items || []).slice(0, KEY_FIGURES_MAX);
  return (
    <div id="chart" className={`z5-key-grid z5-key-grid--n${list.length || 3} scroll-mt-28`}>
      {list.map((item, index) => (
        <KeyFigureCard key={item.concept_slug} item={item} slug={slug} locale={locale} index={index} preload={preload} />
      ))}
      {!list.length && (
        <div className="col-span-2 text-sm text-text-secondary sm:col-span-3">
          {t('world.country.coverageAlt')}
        </div>
      )}
    </div>
  );
}
