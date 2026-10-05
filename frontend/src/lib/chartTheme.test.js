import { describe, expect, it } from 'vitest';
import {
  CHART_AREA, CHART_HEIGHTS, CHART_LINE, CHART_MOTION, CHART_THEME, GRID_PROPS, PRISM_STOPS, RIBBON_STOPS,
  SAPPHIRE_STOPS, TOOLTIP_STYLES,
  areaGradientStops, axisSampleValues, axisTick, axisWidthForLabels, chartHeightForWidth, lastPointTag, niceAxis,
} from './chartTheme';

function channel(c) {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}
function luminance(hex) {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}
function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('axisWidthForLabels', () => {
  it('даёт ось шире для длинной подписи с единицей и не режет её слева', () => {
    const short = axisWidthForLabels(['0', '700']);
    const long = axisWidthForLabels(['0 ₽', '2,8 млн ₽']);
    expect(long).toBeGreaterThan(short);
    // «2,8 млн ₽» — 9 знаков: нужно не меньше ~6,6 px на знак.
    expect(long).toBeGreaterThanOrEqual(9 * 6.6);
  });

  it('ограничена разумным диапазоном и переживает пустой ввод', () => {
    expect(axisWidthForLabels([])).toBe(36);
    expect(axisWidthForLabels(['x'.repeat(200)])).toBe(110);
    expect(axisWidthForLabels([null, undefined])).toBeGreaterThanOrEqual(36);
  });
});

describe('chartTheme', () => {
  it('axis labels reach 4.5:1 on the white chart card and on the page background', () => {
    expect(contrast(CHART_THEME.axis, CHART_THEME.surface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(CHART_THEME.axis, CHART_THEME.pearl)).toBeGreaterThanOrEqual(4.5);
  });

  it('text accent used in chart tooltips has enough contrast on white', () => {
    expect(contrast(CHART_THEME.champagneInk, CHART_THEME.surface)).toBeGreaterThanOrEqual(4.5);
  });

  it('grid is a dark translucent line, not white-on-white', () => {
    expect(GRID_PROPS.stroke).toMatch(/^rgba\(32,\s*42,\s*60/);
    expect(GRID_PROPS.vertical).toBe(false);
  });

  it('сетка без пунктира: очень мягкие полосы (не больше 3,5 %) чередуются с пустыми', () => {
    expect(GRID_PROPS.strokeDasharray).toBeUndefined();
    expect(GRID_PROPS.horizontalFill).toHaveLength(2);
    const alpha = Number(GRID_PROPS.horizontalFill[0].match(/,\s*([0-9.]+)\)$/)[1]);
    expect(alpha).toBeGreaterThan(0.01);
    expect(alpha).toBeLessThanOrEqual(0.035);
  });

  it('лента: градиент золото-светлое → золото → тёмное, заливка 35 % → 0, второй ряд сапфир', () => {
    expect(RIBBON_STOPS.map((s) => s.color)).toEqual(['#E9CD8E', '#C9A24D', '#A9812F']);
    expect(SAPPHIRE_STOPS.map((s) => s.color)).toEqual(['#5C86C8', '#1E2A4A']);
    expect(CHART_AREA.top).toBe(0.35);
    expect(CHART_AREA.bottom).toBe(0);
    expect(PRISM_STOPS).toHaveLength(2);
  });

  it('axisTick takes font and colour from the theme and allows overrides', () => {
    expect(axisTick()).toMatchObject({ fill: CHART_THEME.axis, fontFamily: CHART_THEME.font, fontSize: 12 });
    expect(axisTick({ fontSize: 13 }).fontSize).toBe(13);
  });

  it('exposes up to ten distinct series colours', () => {
    expect(CHART_THEME.series).toHaveLength(10);
    expect(new Set(CHART_THEME.series).size).toBe(10);
  });

  it('chart height steps 280 / 390 / 480 by container width', () => {
    expect(chartHeightForWidth(328)).toBe(CHART_HEIGHTS.compact);
    expect(chartHeightForWidth(559)).toBe(280);
    expect(chartHeightForWidth(704)).toBe(390);
    expect(chartHeightForWidth(1200)).toBe(480);
    // Ширина ещё неизвестна (SSR / первый кадр) — средняя высота.
    expect(chartHeightForWidth(0)).toBe(390);
    expect(chartHeightForWidth(undefined)).toBe(390);
  });
});

describe('ось Y сравнения не режет «355 000»', () => {
  it('образцы включают края данных с запасом на «красивый» домен', () => {
    const samples = axisSampleValues([190000, 245000, 355000, null, 'x']);
    expect(Math.max(...samples)).toBeGreaterThan(355000);
    expect(Math.min(...samples)).toBeLessThan(190000);
    expect(axisSampleValues([])).toEqual([]);
  });

  it('ширина по длинной подписи больше прежних фиксированных 46–60 px', () => {
    const labels = axisSampleValues([190000, 355000]).map((v) => String(Math.round(v)).replace(/\B(?=(\d{3})+$)/g, '\u00A0'));
    const width = axisWidthForLabels(labels, { min: 40, perChar: 7, pad: 12 });
    expect(width).toBeGreaterThan(60);
  });
});

describe('niceAxis: ровный шаг оси Y', () => {
  it('3 190 000…3 300 000 получает шаг 20 000, а не 55 000', () => {
    const axis = niceAxis([3195000, 3290000]);
    const steps = axis.ticks.slice(1).map((v, i) => v - axis.ticks[i]);
    expect(new Set(steps).size).toBe(1);
    expect([1, 2, 5].includes(Number(String(steps[0]).replace(/0+$/, '')))).toBe(true);
    expect(axis.domain[0]).toBeLessThanOrEqual(3195000);
    expect(axis.domain[1]).toBeGreaterThanOrEqual(3290000);
  });

  it('без данных — null, плоский ряд — не вырождается', () => {
    expect(niceAxis([])).toBeNull();
    expect(niceAxis([null, 'x'])).toBeNull();
    const flat = niceAxis([5, 5]);
    expect(flat.ticks.length).toBeGreaterThan(1);
  });

  it('проценты около нуля: ось проходит через 0 с шагом 1', () => {
    const axis = niceAxis([-0.4, 3.1]);
    expect(axis.ticks).toContain(0);
    expect(axis.ticks[1] - axis.ticks[0]).toBe(1);
  });
});


describe('DS7: золотая линия, заливка, движение, подсказка', () => {
  it('основная линия золотая 2,5–3 px, у ряда сравнения первым идёт золото', () => {
    expect(CHART_LINE.stroke).toBe(CHART_THEME.gold);
    expect(CHART_LINE.strokeWidth).toBeGreaterThanOrEqual(2.5);
    expect(CHART_LINE.strokeWidth).toBeLessThanOrEqual(3);
    expect(CHART_THEME.series[0]).toBe(CHART_THEME.gold);
  });

  it('заливка под линией 12–35 % у линии и почти ноль у оси', () => {
    expect(CHART_AREA.top).toBeGreaterThanOrEqual(0.12);
    expect(CHART_AREA.top).toBeLessThanOrEqual(0.35);
    const [from, to] = areaGradientStops();
    expect(from).toMatchObject({ offset: '0%', stopColor: CHART_THEME.gold, stopOpacity: CHART_AREA.top });
    expect(to.stopOpacity).toBeLessThan(0.05);
    expect(areaGradientStops('#202A3C', { top: 0.2 })[0].stopColor).toBe('#202A3C');
  });

  it('линия рисуется 900 мс (K4.1)', () => {
    expect(CHART_MOTION.drawMs).toBe(900);
  });

  it('подсказка стеклянная, а курсор — золотая вертикаль', () => {
    expect(TOOLTIP_STYLES.contentStyle.backdropFilter).toMatch(/blur\(/);
    expect(TOOLTIP_STYLES.cursor.stroke).toMatch(/^rgba\(176,\s*138,\s*62/);
  });

  it('плашка последнего значения растёт с подписью и не уже своей высоты', () => {
    const short = lastPointTag('28,1 млн');
    const long = lastPointTag('30 767 млрд $');
    expect(long.width).toBeGreaterThan(short.width);
    expect(lastPointTag('').width).toBeGreaterThanOrEqual(short.height);
    expect(short.radius).toBe(short.height / 2);
  });

  it('золото линии и тёмное золото текста различимы на карточке', () => {
    expect(contrast(CHART_THEME.gold, CHART_THEME.surface)).toBeGreaterThanOrEqual(3);
    expect(contrast(CHART_THEME.champagneInk, CHART_THEME.pearl)).toBeGreaterThanOrEqual(4.5);
  });
});
