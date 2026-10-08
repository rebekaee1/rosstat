// «Главная пятёрка» России: инфляция за год, ставка, курс доллара, ВВП, безработица. Крупно, со спарклайном и «год назад».
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useIndicatorData } from '../../lib/hooks';
import { formatValue, resolveDateFormat } from '../../lib/format';
import { deltaTone, indicatorPolarity } from '../../lib/deltaTone';
import { periodPhrase } from '../../lib/periodPhrase';
import { russiaMainFive } from '../../lib/russiaHomeCards';
import {
  figureDigits, scaleMoneyUnit, typographicMinus, yearAgoPoint,
} from '../../lib/countryKeyFigures';
import { russiaIndicatorPath } from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import DeltaBadge from '../DeltaBadge';
import Sparkline from '../Sparkline';
import { SkeletonBox } from '../Skeleton';
import useSparkHeight from '../country/useSparkHeight';
import '../../styles/z5-country.css';
import '../../styles/k6-country.css';

const SPARK_ROWS = 96;
// Ряд с ежедневными точками (ставка, курс): за 96 точек не набирается год, а «год назад» нужен.
const DAILY_ROWS = 400;

function formatFigure(value, unit, locale) {
  const scaled = scaleMoneyUnit(value, unit, locale);
  if (scaled) return { text: typographicMinus(formatValue(scaled.value, figureDigits(scaled.value), locale)), unit: scaled.unit };
  const abs = Math.abs(Number(value));
  const digits = abs >= 1000 ? 0 : abs >= 100 ? 1 : 2;
  // Без хвоста нулей: 17 вместо 17,00, 5,4 вместо 5,40.
  const rounded = Number(Number(value).toFixed(digits));
  const decimals = Number.isInteger(rounded) ? 0 : (String(rounded).split('.')[1] || '').length;
  return { text: typographicMinus(formatValue(rounded, decimals, locale)), unit };
}

/** Не больше SPARK_ROWS точек для мини-графика: длинный дневной ряд прореживаем равномерно, последняя точка остаётся. */
function thinForSpark(values) {
  if (values.length <= SPARK_ROWS) return values;
  const step = (values.length - 1) / (SPARK_ROWS - 1);
  return Array.from({ length: SPARK_ROWS }, (_, i) => values[Math.round(i * step)]);
}

function MainCard({ card, index }) {
  const t = useT();
  const { locale } = useLocale();
  const sparkHeight = useSparkHeight(64, 48);
  const { indicator } = card;
  const frequency = indicator.frequency || 'monthly';
  // Карточка читает тот ряд, чьё число показывает (для инфляции — годовой `cpi-yoy`), иначе «год назад» и график говорили бы о другом.
  const seriesQ = useIndicatorData(card.seriesCode, {
    limit: frequency === 'daily' ? DAILY_ROWS : SPARK_ROWS,
  });
  const rows = useMemo(
    () => (seriesQ.data?.data || []).filter((row) => Number.isFinite(Number(row.value))),
    [seriesQ.data],
  );
  const values = useMemo(() => thinForSpark(rows.map((row) => Number(row.value))), [rows]);
  const ago = useMemo(() => (card.noYearAgo ? null : yearAgoPoint(rows, frequency)), [rows, frequency, card.noYearAgo]);
  const polarity = indicatorPolarity(indicator.name, indicator.name_en, indicator.code);
  const fullName = locale === 'en' && indicator.name_en ? indicator.name_en : indicator.name;
  const main = formatFigure(card.value, card.unit, locale);
  const agoFigure = ago ? formatFigure(ago.value, card.unit, locale) : null;
  const monthly = card.monthly ? formatFigure(card.monthly.value, card.monthly.unit, locale) : null;
  const date = periodPhrase(t, card.date, resolveDateFormat({ frequency }), locale) || '';

  return (
    <Link
      to={russiaIndicatorPath(card.code)}
      className="z5-key z5-ru-key fe-press fe-glint fe-cursor-light fe-reveal fe-reveal--free fe-reveal--stagger"
      data-stone={card.id}
      data-tone={ago ? deltaTone(card.value - ago.value, polarity) : undefined}
      style={{ '--i': index, '--fe-duration': '0.45s', '--fe-rise': '12px' }}
    >
      <span className="z5-key__name" title={fullName}>
        {t(card.titleKey || `z5.ru.main.${card.id}`)}
        <span className="sr-only">{`: ${fullName}`}</span>
      </span>
      <span className="z5-key__value">
        <span>{main.text}</span>
        {main.unit ? <small>{main.unit}</small> : null}
      </span>
      <span className="z5-key__period">{date}</span>
      {monthly ? (
        <span className="z5-ru-key__monthly">
          {t('z5.ru.main.monthly', { value: `${monthly.text}${monthly.unit ? `\u00a0${monthly.unit}` : ''}` })}
        </span>
      ) : null}
      {agoFigure ? (
        <DeltaBadge delta={card.value - ago.value} polarity={polarity} className="z5-key__ago">
          {t('z5.key.yearAgo', { value: `${agoFigure.text}${agoFigure.unit ? `\u00a0${agoFigure.unit}` : ''}` })}
        </DeltaBadge>
      ) : <span className="z5-key__ago z5-key__ago--empty" aria-hidden="true" />}
      <span className="z5-key__spark" aria-hidden="true">
        {seriesQ.isLoading
          ? <span className="z5-spark-skel" />
          : (values.length > 1
            ? <Sparkline points={values} trend="flat" sentiment="neutral" height={sparkHeight} staggerMs={index * 90} />
            : null)}
      </span>
    </Link>
  );
}

export default function RussiaKeyFigures({ indicators, isLoading }) {
  const cards = useMemo(() => russiaMainFive(indicators), [indicators]);
  return (
    <div className="z5-ru-main" data-testid="russia-overview-chips">
      {cards.map((card, index) => <MainCard key={card.id} card={card} index={index} />)}
      {isLoading && [0, 1, 2, 3, 4].map((i) => (
        <SkeletonBox key={i} className="z5-key z5-key--skel h-[170px] rounded-[22px]" />
      ))}
    </div>
  );
}
