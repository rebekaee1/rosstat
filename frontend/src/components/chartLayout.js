/** Высота плота графика показателя: общая для IndicatorChart и его скелетона, чтобы подмена не сдвигала страницу. */
export const CHART_PLOT_NARROW_BELOW = 600;
export const CHART_PLOT_HEIGHT_NARROW = 280;
export const CHART_PLOT_HEIGHT_WIDE = 390;

export function chartPlotHeight(plotWidth) {
  return plotWidth > 0 && plotWidth < CHART_PLOT_NARROW_BELOW
    ? CHART_PLOT_HEIGHT_NARROW
    : CHART_PLOT_HEIGHT_WIDE;
}
