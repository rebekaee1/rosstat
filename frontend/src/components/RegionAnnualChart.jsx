// График годового регионального ряда: area + опциональный ряд РФ для сравнения.
// Лёгкий и мобильный: без forecast/view-mode машинерии макроблока.
//
// Ось Y для ряда «Россия»: если масштабы региона и РФ несопоставимы (напр.
// посевные площади Краснодарского края ~500 тыс. га против ~7 млн га по РФ),
// одна общая ось прижимает линию региона к нулю и график перестаёт читаться.
// В этом случае РФ автоматически уводится на правую ось (dual-axis), а под
// графиком появляется подпись, какая линия к какой оси относится.
import { useMemo } from 'react';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { formatRegionValue, formatCompactTick, compactTickAxisWidth } from '../lib/regionsApi';

// Порог несопоставимости масштабов: если maxРФ/maxРегион больше — вторая ось.
const DUAL_AXIS_RATIO = 3;

const COMPARE_COLOR = '#5B7DA8';

function RegionTooltip({ active, payload, label, unit, regionName, compareName }) {
  if (!active || !payload?.length) return null;
  const region = payload.find(p => p.dataKey === 'value' && p.value != null);
  const compare = payload.find(p => p.dataKey === 'compare' && p.value != null);
  const russia = payload.find(p => p.dataKey === 'russia' && p.value != null);
  return (
    <div className="bg-surface border border-border-subtle rounded-lg px-3 py-2 shadow-lg text-xs">
      <div className="text-text-tertiary font-mono mb-1">{label}</div>
      {region && (
        <div className="font-mono font-semibold text-champagne">
          {regionName}: {formatRegionValue(region.value, unit)}
        </div>
      )}
      {compare && (
        <div className="font-mono font-semibold mt-0.5" style={{ color: COMPARE_COLOR }}>
          {compareName}: {formatRegionValue(compare.value, unit)}
        </div>
      )}
      {russia && (
        <div className="font-mono text-text-secondary mt-0.5">
          Россия: {formatRegionValue(russia.value, unit)}
        </div>
      )}
    </div>
  );
}

const tickStyle = { fontSize: 11, fill: 'rgba(26,26,46,0.45)', fontFamily: 'JetBrains Mono, monospace' };

export default function RegionAnnualChart({
  series,
  russiaSeries = null,
  compareSeries = null,
  compareName = '',
  unit = '',
  regionName = '',
  height = 320,
}) {
  const data = useMemo(() => {
    const rfByYear = new Map((russiaSeries || []).map(p => [p.year, p.value]));
    const cmpByYear = new Map((compareSeries || []).map(p => [p.year, p.value]));
    return (series || []).map(p => ({
      year: p.year,
      value: p.value,
      compare: cmpByYear.get(p.year) ?? null,
      russia: rfByYear.get(p.year) ?? null,
    }));
  }, [series, russiaSeries, compareSeries]);

  const showRussia = useMemo(
    () => data.some(d => d.russia != null),
    [data],
  );

  // Несоразмерные масштабы (регион ≪ Россия или наоборот) → РФ на правую ось.
  const dualAxis = useMemo(() => {
    if (!showRussia) return false;
    const regionMax = Math.max(...data.map(d => Math.abs(d.value ?? 0)));
    const rfMax = Math.max(...data.map(d => Math.abs(d.russia ?? 0)));
    if (!regionMax || !rfMax) return false;
    const ratio = rfMax / regionMax;
    return ratio > DUAL_AXIS_RATIO || ratio < 1 / DUAL_AXIS_RATIO;
  }, [data, showRussia]);

  // Ширина осей — по самой длинной подписи, чтобы «148,5 тыс» не обрезалось.
  const leftAxisWidth = useMemo(
    () => compactTickAxisWidth(data.flatMap(d => [d.value, d.compare])),
    [data],
  );
  const rightAxisWidth = useMemo(
    () => compactTickAxisWidth(data.map(d => d.russia)),
    [data],
  );

  if (!data.length) return null;

  return (
    <div>
      <div style={{ width: '100%', height }} role="img"
        aria-label={`График: ${regionName}, ${data[0].year}–${data[data.length - 1].year}`}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 12, right: dualAxis ? 4 : 8, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="regionArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#B8942F" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#B8942F" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
            <XAxis
              dataKey="year"
              tick={tickStyle}
              tickLine={false}
              axisLine={false}
              minTickGap={28}
            />
            <YAxis
              yAxisId="region"
              tick={{ ...tickStyle, fill: dualAxis ? 'rgba(184,148,47,0.75)' : tickStyle.fill }}
              tickFormatter={formatCompactTick}
              tickLine={false}
              axisLine={false}
              width={leftAxisWidth}
              domain={['auto', 'auto']}
            />
            {dualAxis && (
              <YAxis
                yAxisId="rf"
                orientation="right"
                tick={{ ...tickStyle, fill: 'rgba(58,58,80,0.6)' }}
                tickFormatter={formatCompactTick}
                tickLine={false}
                axisLine={false}
                width={rightAxisWidth}
                domain={['auto', 'auto']}
              />
            )}
            <Tooltip content={<RegionTooltip unit={unit} regionName={regionName} compareName={compareName} />} />
            <Area
              yAxisId="region"
              type="monotone"
              dataKey="value"
              stroke="#B8942F"
              strokeWidth={2.2}
              fill="url(#regionArea)"
              dot={false}
              activeDot={{ r: 4, fill: '#B8942F' }}
              isAnimationActive={false}
            />
            {compareSeries?.length > 0 && (
              <Line
                yAxisId="region"
                type="monotone"
                dataKey="compare"
                stroke={COMPARE_COLOR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3.5, fill: COMPARE_COLOR }}
                isAnimationActive={false}
              />
            )}
            {showRussia && (
              <Line
                yAxisId={dualAxis ? 'rf' : 'region'}
                type="monotone"
                dataKey="russia"
                stroke="#3A3A50"
                strokeWidth={1.6}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {dualAxis && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-tertiary px-1">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded bg-champagne" />
            {regionName} — левая ось
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-4 border-t-2 border-dashed border-[#3A3A50]" />
            Россия — правая ось
          </span>
        </div>
      )}
    </div>
  );
}
