import {
  CHART_AREA, CHART_AREA_COLOR, CHART_THEME, PRISM_STOPS, RIBBON_STOPS, SAPPHIRE_STOPS,
} from '../lib/chartTheme';

/**
 * Градиенты «стеклянной ленты» одного графика. Кладётся внутрь `<defs>` Recharts:
 *   <defs><ChartGlassDefs ids={useChartGlassIds()} /></defs>
 * Линия ссылается на них как `stroke={`url(#${ids.ribbon})`}`. Значения берутся из lib/chartTheme.js.
 *
 * ribbon      золотая лента по длине линии (светлое, золото, тёмное)
 * sapphire    лента второго ряда (сапфир)
 * area/areaSapphire  заливка под лентой: 35 % у линии, к оси 0
 * forecast    линия прогноза: тёмное золото, прозрачность тает вдоль линии (без пунктира)
 * prism       коридор прогноза: золото, затем лёд (слева направо)
 * bar/barForecast    столбцы: градиент сверху вниз
 * width       ширина графика в px: горизонтальные градиенты привязываются к графику, а не к рамке линии (плоский ряд не пропадает)
 * bead        шарик последней точки: блик в левом верхнем углу
 */
export default function ChartGlassDefs({ ids, forecastColor = CHART_THEME.champagneInk, width = null }) {
  // Горизонтальные градиенты по длине линии. У плоской линии (постоянный ряд) высота ограничивающей рамки нулевая, и градиент
  // в долях рамки (objectBoundingBox) не рисуется вовсе: линия исчезает. Поэтому, когда ширина графика известна, задаём
  // градиент в координатах графика (userSpaceOnUse от 0 до ширины).
  const along = width > 0
    ? { gradientUnits: 'userSpaceOnUse', x1: 0, y1: 0, x2: Math.round(width), y2: 0 }
    : { x1: '0', y1: '0', x2: '1', y2: '0' };
  return (
    <>
      <linearGradient id={ids.ribbon} {...along}>
        {RIBBON_STOPS.map((stop) => <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />)}
      </linearGradient>
      <linearGradient id={ids.sapphire} {...along}>
        {SAPPHIRE_STOPS.map((stop) => <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />)}
      </linearGradient>
      <linearGradient id={ids.area} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={CHART_AREA_COLOR} stopOpacity={CHART_AREA.top} />
        <stop offset="100%" stopColor={CHART_AREA_COLOR} stopOpacity={CHART_AREA.bottom} />
      </linearGradient>
      <linearGradient id={ids.areaSapphire} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={CHART_THEME.sapphireLight} stopOpacity={0.22} />
        <stop offset="100%" stopColor={CHART_THEME.sapphireLight} stopOpacity={0} />
      </linearGradient>
      <linearGradient id={ids.forecast} {...along}>
        <stop offset="0%" stopColor={forecastColor} stopOpacity={1} />
        <stop offset="100%" stopColor={forecastColor} stopOpacity={0.3} />
      </linearGradient>
      <linearGradient id={ids.prism} x1="0" y1="0" x2="1" y2="0">
        {PRISM_STOPS.map((stop) => <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />)}
      </linearGradient>
      <linearGradient id={ids.bar} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={CHART_THEME.goldLight} stopOpacity={0.95} />
        <stop offset="100%" stopColor={CHART_THEME.goldDeep} stopOpacity={0.78} />
      </linearGradient>
      <linearGradient id={ids.barForecast} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={CHART_THEME.goldLight} stopOpacity={0.5} />
        <stop offset="100%" stopColor={forecastColor} stopOpacity={0.4} />
      </linearGradient>
      <radialGradient id={ids.bead} cx="34%" cy="28%" r="78%">
        <stop offset="0%" stopColor="#FFF6DA" />
        <stop offset="38%" stopColor={CHART_THEME.goldBright} />
        <stop offset="100%" stopColor={CHART_THEME.goldDeep} />
      </radialGradient>
    </>
  );
}
