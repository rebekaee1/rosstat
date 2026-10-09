// Круг 11 (E): крупный график выбранной пары на странице курсов. Переключатель периода (неделя, месяц, год, всё время)
// и вторая пара поверх первой: обе в индексе «начало периода = 100», чтобы рубль и биткоин можно было сравнить на одной оси.
// Курсы без красного и зелёного (решение владельца): линии синяя и бирюзовая, изменение читается числом.
import { useMemo, useState } from 'react';
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import Chip from './Chip';
import DeltaBadge from './DeltaBadge';
import CurrencySelect from './CurrencySelect';
import { ChartLegend } from './ChartTouchHint';
import { SkeletonBox } from './Skeleton';
import EdgeAwareTick from './ChartAxisTick';
import ChartGlassDefs from './ChartGlassDefs';
import { useIndicatorData } from '../lib/hooks';
import { formatDate, formatValue } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { indicatorPolarity } from '../lib/deltaTone';
import { CHART_THEME, COMPARE_COLORS, GRID_PROPS, axisTick, niceAxis } from '../lib/chartTheme';
import { useChartGlassIds, useElementWidth } from '../lib/chartHooks';
import { pairTitle, parsePair, unitMeta } from '../lib/currencyRates';
import {
  CHART_PERIODS, alignIndex, axisPlan, changePct, cleanSeries, coinOf, digitsForStep, limitForPeriod,
  rateDigits, sliceByPeriod, unitName,
} from '../lib/currencyChart';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/z8-tools.css';
import '../styles/k4-charts.css';
import '../styles/c8-currency.css';

const SECOND_COLOR = COMPARE_COLORS[1];

function ChartTip({ active, payload, locale, unitA, unitB, nameA, nameB, compare }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  const fmt = (v, unit) => `${formatValue(v, rateDigits(v), locale)}${unit ? `\u00A0${unit}` : ''}`;
  return (
    <div className="fe-z8-tip glass-surface">
      {/* День целиком («9 октября 2026»): раньше в подсказке стоял только месяц. */}
      <p className="fe-z8-tip__date">{formatDate(point.date, 'day', locale)}</p>
      {compare ? (
        <>
          <p className="fe-z8-tip__val">{`${nameA}: ${fmt(point.rawA, unitA)}`}</p>
          <p className="fe-z8-tip__val fe-c11e-tip__second">{`${nameB}: ${fmt(point.rawB, unitB)}`}</p>
        </>
      ) : (
        <p className="fe-z8-tip__val">{fmt(point.rawA, unitA)}</p>
      )}
    </div>
  );
}

/** Точка на конце ленты: плоский круг и тихое гало. */
function EndBead({ cx, cy, color }) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  return (
    <g pointerEvents="none" className="k4-lastpoint">
      <circle className="k4-lastpoint__halo" cx={cx} cy={cy} r={8} fill={color} fillOpacity={0.2} />
      <circle cx={cx} cy={cy} r={3} fill={color} />
    </g>
  );
}

/** pair: { code, base, quote, invert }; edges: рёбра курсов (для списка второй пары). */
export default function CurrencyPairChart({ pair, edges = [] }) {
  const t = useT();
  const { locale } = useLocale();
  const [period, setPeriod] = useState('year');
  const [secondCode, setSecondCode] = useState('');
  const limit = limitForPeriod(period);
  const { data, isLoading } = useIndicatorData(pair?.code, { limit });
  const secondEnabled = Boolean(secondCode) && secondCode !== pair?.code;
  const { data: secondData } = useIndicatorData(secondEnabled ? secondCode : null, { limit });
  const glass = useChartGlassIds('k8cur');
  const [setPlotNode, plotWidth] = useElementWidth();

  // Круг 9 (V3): обратный курс мелкой монеты («1 доллар = 0,000012 биткоина») показываем как есть: «1 биткоин = N долларов».
  const rawSeries = useMemo(() => cleanSeries(data?.data), [data]);
  const lastRaw = rawSeries.length ? rawSeries[rawSeries.length - 1].value : null;
  const flipped = Boolean(pair?.invert && lastRaw != null && lastRaw > 100);
  const baseSeries = useMemo(
    () => (pair?.invert && !flipped ? cleanSeries(data?.data, { invert: true }) : rawSeries),
    [data, pair?.invert, flipped, rawSeries],
  );
  const primary = useMemo(() => sliceByPeriod(baseSeries, period), [baseSeries, period]);
  const secondSeries = useMemo(
    () => (secondEnabled ? cleanSeries(secondData?.data) : []),
    [secondEnabled, secondData],
  );
  const joined = useMemo(
    () => (secondSeries.length ? alignIndex(primary, secondSeries) : []),
    [primary, secondSeries],
  );
  const compare = joined.length >= 2;

  const options = useMemo(() => [
    { value: '', name: t('c11e.cur.noSecond'), symbol: '–', search: t('c11e.cur.noSecond').toLowerCase() },
    ...edges.filter((edge) => edge.code !== pair?.code).map((edge) => {
      const meta = unitMeta(edge.from);
      return {
        value: edge.code,
        name: pairTitle(edge.code, locale, edge.code),
        ...coinOf(edge.from),
        search: [edge.code, pairTitle(edge.code, 'ru'), pairTitle(edge.code, 'en'), meta?.symbol].join(' ').toLowerCase(),
      };
    }),
  ], [edges, pair?.code, locale, t]);

  const points = useMemo(
    () => (compare ? joined : primary.map((p) => ({ date: p.date, a: p.value, rawA: p.value }))),
    [compare, joined, primary],
  );

  if (!pair) return null;
  const baseUnit = flipped ? pair.quote : pair.base;
  const quoteUnit = flipped ? pair.base : pair.quote;
  const unit = unitMeta(quoteUnit)?.symbol || '';
  const nameA = `${unitName(baseUnit, locale)} → ${unitName(quoteUnit, locale)}`;
  const secondPair = secondEnabled ? parsePair(secondCode) : null;
  const unitB = secondPair ? unitMeta(secondPair.quote)?.symbol || '' : '';
  const nameB = secondEnabled ? pairTitle(secondCode, locale, secondCode) : '';
  const titleKey = period === 'year' ? 'z8.cur.chartTitle' : `c11e.cur.title.${period}`;
  const title = compare
    ? t('c11e.cur.titleCompare', { a: nameA, b: nameB })
    : t(titleKey, { pair: nameA });

  const toolbar = (
    <div className="fe-c11e-chartbar">
      <div className="fe-c11e-periods" role="group" aria-label={t('c11e.cur.periodAria')}>
        {CHART_PERIODS.map((id) => (
          <Chip
            key={id}
            active={period === id}
            onClick={() => { setPeriod(id); track(events.COMPARE_CHANGE, { converter: 'chart-period', period: id }); }}
          >
            {t(`c11e.cur.period.${id}`)}
          </Chip>
        ))}
      </div>
      <CurrencySelect
        label={t('c11e.cur.second')}
        value={secondEnabled ? secondCode : ''}
        options={options}
        onChange={(value) => { setSecondCode(value); track(events.COMPARE_CHANGE, { converter: 'chart-second', second: value || 'none' }); }}
        searchPlaceholder={t('w6g.cur.search')}
        emptyText={t('w6g.cur.nothing')}
        className="fe-c11e-second"
      />
    </div>
  );

  if (isLoading) {
    return (
      <section className="fe-panel fe-z8-chart" aria-busy="true" data-block="currency-year-chart">
        <SkeletonBox className="fe-z8-chart__skeleton" />
      </section>
    );
  }
  if (points.length < 2) {
    // Даже без данных за период панель остаётся: человек может переключить период обратно.
    if (period === 'year' && !secondEnabled) return null;
    return (
      <section className="fe-panel fe-z8-chart" data-block="currency-year-chart" aria-label={title}>
        <header className="fe-z8-chart__head"><h2 className="fe-z8-chart__title">{title}</h2></header>
        {toolbar}
        <p className="fe-z8-conv__note" role="status">{t('c11e.cur.noData')}</p>
      </section>
    );
  }

  const first = points[0];
  const last = points[points.length - 1];
  const pct = changePct(points, (p) => p.rawA);
  const delta = pct != null ? formatDeltaWithUnit(pct, '%', { pct: true, locale, digits: 1 }) : null;
  const pctB = compare ? changePct(points, (p) => p.rawB) : null;
  const deltaB = pctB != null ? formatDeltaWithUnit(pctB, '%', { pct: true, locale, digits: 1 }) : null;
  const lastIndex = points.length - 1;

  const plan = axisPlan(points, plotWidth > 0 && plotWidth < 340);
  const monthOf = (date) => new Date(`${date}T12:00:00Z`).toLocaleDateString(
    locale === 'en' ? 'en-US' : 'ru-RU', { month: 'short', timeZone: 'UTC' },
  ).replace('.', '');
  const tickLabel = (date) => {
    if (plan.kind === 'year') return String(date).slice(0, 4);
    if (plan.kind === 'day') return formatDate(date, 'dayShort', locale);
    const edge = date === plan.ticks[0] || date === plan.ticks[plan.ticks.length - 1];
    const jan = String(date).slice(5, 7) === '01';
    return edge || jan ? `${monthOf(date)} ${String(date).slice(0, 4)}` : monthOf(date);
  };

  const yValues = compare ? points.flatMap((p) => [p.a, p.b]) : points.map((p) => p.a);
  const yAxis = niceAxis(yValues, 5);
  const yTicks = yAxis?.ticks;
  const yStep = yTicks && yTicks.length > 1 ? Math.abs(yTicks[1] - yTicks[0]) : 0;
  const yDigits = compare ? digitsForStep(yStep) : digitsForStep(yStep);
  const yWidthPx = Math.max(40, Math.min(70, Math.round(String(yTicks ? formatValue(yTicks[yTicks.length - 1], yDigits, locale) : '88,30').length * 8 + 12)));
  const perKey = period === 'year' ? 'z8.cur.perYear' : `c11e.cur.per.${period}`;
  const fillId = `url(#${glass.area})`;

  return (
    <section className="fe-panel fe-z8-chart" data-block="currency-year-chart" aria-label={title}>
      <header className="fe-z8-chart__head">
        <div>
          <h2 className="fe-z8-chart__title">{title}</h2>
          <p className="fe-z8-chart__value">
            <span className="fe-z8-chart__num">{formatValue(last.rawA, rateDigits(last.rawA), locale)}</span>
            {unit && <span className="fe-z8-chart__unit">{unit}</span>}
          </p>
        </div>
        {delta && !delta.flat && (
          <p className="fe-z8-chart__delta">
            <DeltaBadge delta={pct} polarity={indicatorPolarity(pair.code)}>{delta.text}</DeltaBadge>
            <span>{t(perKey)}</span>
          </p>
        )}
      </header>
      {toolbar}
      <div ref={setPlotNode} className="fe-z8-chart__plot k4-glass k4-glass-plot" role="img" aria-label={title}>
        <div className="fe-z8-chart__abs">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs><ChartGlassDefs ids={glass} /></defs>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis
                dataKey="date"
                ticks={plan.ticks}
                interval={0}
                tickLine={false}
                axisLine={false}
                height={30}
                tick={<EdgeAwareTick format={tickLabel} minX={yWidthPx} maxX={plotWidth > 0 ? plotWidth - 8 : Infinity} />}
              />
              <YAxis
                domain={yAxis ? yAxis.domain : [(min) => min * 0.985, (max) => max * 1.015]}
                ticks={yTicks}
                tickCount={5}
                tickLine={false}
                axisLine={false}
                width={yWidthPx}
                tick={axisTick({ fontSize: 12 })}
                tickFormatter={(v) => formatValue(v, yTicks ? yDigits : (rateDigits(v) > 2 ? 3 : rateDigits(v)), locale)}
              />
              <Tooltip
                content={<ChartTip locale={locale} unitA={unit} unitB={unitB} nameA={unitName(baseUnit, locale)} nameB={nameB} compare={compare} />}
                cursor={{ stroke: CHART_THEME.champagne, strokeWidth: 1, strokeOpacity: 0.55 }}
              />
              {compare ? (
                <Line type="monotone" dataKey="b" stroke={SECOND_COLOR} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: SECOND_COLOR, stroke: '#FFFFFF', strokeWidth: 2 }} isAnimationActive={false} />
              ) : null}
              <Area
                className="k4-ribbon"
                type="monotone"
                dataKey="a"
                stroke={CHART_THEME.gold}
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                fill={compare ? 'none' : fillId}
                dot={false}
                activeDot={{ r: 5, fill: CHART_THEME.gold, stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
              />
              <ReferenceDot
                x={points[lastIndex].date}
                y={points[lastIndex].a}
                r={4.5}
                ifOverflow="visible"
                shape={(props) => <EndBead cx={props.cx} cy={props.cy} color={CHART_THEME.gold} />}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
      {compare && (
        <>
          <ChartLegend
            items={[
              { color: CHART_THEME.gold, label: `${nameA}: ${formatValue(last.rawA, rateDigits(last.rawA), locale)}${unit ? `\u00A0${unit}` : ''}${delta && !delta.flat ? `, ${delta.text}` : ''}` },
              { color: SECOND_COLOR, label: `${nameB}: ${formatValue(last.rawB, rateDigits(last.rawB), locale)}${unitB ? `\u00A0${unitB}` : ''}${deltaB && !deltaB.flat ? `, ${deltaB.text}` : ''}` },
            ]}
          />
          <p className="fe-c11e-chartnote">{t('c11e.cur.indexNote', { date: formatDate(first.date, 'day', locale) })}</p>
        </>
      )}
    </section>
  );
}
