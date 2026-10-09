import { describe, expect, it } from 'vitest';
import {
  ZOOM_STEP, bestStartFocus, dataVectors, focusDistance, hasVisibleData, liftedFocus, playbackYears,
  oceanReach, viewHalfExtent, viewRectangles, yearTag, zoomedDistance,
} from './planetView';
import { lonLatToSphere } from './planetGeometry';

const square = (lon, lat, size) => ({
  type: 'Feature',
  geometry: { type: 'Polygon', coordinates: [[[lon - size, lat - size], [lon + size, lat - size], [lon + size, lat + size], [lon - size, lat + size], [lon - size, lat - size]]] },
});
const country = (code, lon, lat, size = 3) => ({ code, dataCode: code, focus: [lon, lat], feature: square(lon, lat, size) });

describe('planet zoom step', () => {
  it('multiplies and divides the camera distance by exactly 1.5 and respects the limits', () => {
    expect(ZOOM_STEP).toBe(1.5);
    expect(zoomedDistance(3.6, 'in', { min: 1.45, max: 4.8 })).toBeCloseTo(2.4, 6);
    expect(zoomedDistance(2.4, 'out', { min: 1.45, max: 4.8 })).toBeCloseTo(3.6, 6);
    expect(zoomedDistance(1.6, 'in', { min: 1.45, max: 4.8 })).toBe(1.45);
    expect(zoomedDistance(4.0, 'out', { min: 1.45, max: 4.8 })).toBe(4.8);
  });
});

describe('selecting a country keeps the zoom the person made', () => {
  it('does not zoom out from a closer view, and gently approaches from the overview', () => {
    expect(focusDistance({ current: 1.9, fit: 3.3, min: 1.45, area: 0.01 })).toBe(1.9);
    expect(focusDistance({ current: 3.4, fit: 3.3, min: 1.45, area: 0.01 })).toBe(2.4);
    expect(focusDistance({ current: 3.4, fit: 3.3, min: 1.45, area: 0.0000062 })).toBe(1.7);
    // A giant country is framed from a bit closer than the overview, never closer than a medium one.
    const giant = focusDistance({ current: 3.4, fit: 3.3, min: 1.45, area: 0.4 });
    expect(giant).toBeCloseTo(3.3 / 1.2, 6);
    expect(giant).toBeGreaterThan(2.4);
  });

  it('lifts the aim point so the country sits above the card sheet', () => {
    expect(liftedFocus([10, 50], 11)).toEqual([10, 39]);
    expect(liftedFocus([10, -78], 11)[1]).toBe(-80);
  });
});

describe('start side of the globe', () => {
  const values = new Map();
  const entries = [];
  const add = (code, lon, lat, size) => { entries.push(country(code, lon, lat, size)); values.set(code, 1); };

  it('prefers the side with the most coloured countries, weighting big ones, over empty Africa', () => {
    ['DE', 'FR', 'PL', 'IT', 'ES'].forEach((code, index) => add(code, 3 + index * 4, 46 + index, 2));
    add('US', -98, 39, 12);
    add('BR', -52, -10, 10);
    add('CA', -100, 58, 12);
    const [lon, lat] = bestStartFocus(entries, values);
    expect(lat).toBe(24);
    // The Atlantic: both Americas and Europe in the same hemisphere.
    expect(lon).toBeGreaterThan(-75);
    expect(lon).toBeLessThan(5);
  });

  it('falls back when there is almost nothing to show', () => {
    expect(bestStartFocus([country('DE', 10, 50)], new Map([['DE', 1]]), { fallback: [-25, 24] })).toEqual([-25, 24]);
    expect(bestStartFocus([], null)).toEqual([-25, 24]);
  });

  it('ignores countries without a numeric value', () => {
    const list = [country('DE', 10, 50), country('FR', 2, 46), country('IT', 12, 42), country('ES', -4, 40)];
    const vectors = dataVectors(list, new Map([['DE', 1], ['FR', '2'], ['IT', ''], ['ES', null]]));
    expect(vectors).toHaveLength(2);
  });
});

describe('«only water in view»', () => {
  const vectors = dataVectors([country('US', -98, 39, 10)], new Map([['US', 1]]));

  it('is false while a coloured country is within reach of the view centre, true over the empty Pacific', () => {
    expect(hasVisibleData(vectors, lonLatToSphere([-90, 30], 3.3))).toBe(true);
    expect(hasVisibleData(vectors, lonLatToSphere([170, 0], 3.3))).toBe(false);
  });

  it('never claims water when there is nothing coloured at all (no data is not a reason to send people back)', () => {
    expect(hasVisibleData([], [0, 0, 3])).toBe(true);
  });
});

describe('minimap frame', () => {
  it('grows as the camera moves away and covers the full disk when near the sphere limit', () => {
    const near = viewHalfExtent(1.6);
    const far = viewHalfExtent(3.3);
    expect(far.lat).toBeGreaterThan(near.lat);
    expect(viewHalfExtent(1.05).lat).toBeLessThanOrEqual(90);
  });

  it('wraps over the antimeridian into two rectangles', () => {
    const rects = viewRectangles({ lon: 175, lat: 10, distance: 1.7 });
    expect(rects).toHaveLength(2);
    expect(rects[1].x).toBeCloseTo(rects[0].x - 360, 6);
    expect(viewRectangles({ lon: 0, lat: 10, distance: 1.7 })).toHaveLength(1);
  });
});

describe('years that are not facts yet', () => {
  const now = new Date('2026-10-05T12:00:00Z');
  it('calls a coming year a forecast and the running annual year an estimate, but not monthly data', () => {
    expect(yearTag(2027, { now })).toBe('forecast');
    expect(yearTag(2026, { annual: true, now })).toBe('estimate');
    expect(yearTag(2026, { annual: false, now })).toBeNull();
    expect(yearTag(2025, { now })).toBeNull();
    expect(yearTag(null, { now })).toBeNull();
  });

  it('plays at most sixteen years and never past the last finished one', () => {
    const years = Array.from({ length: 41 }, (_, index) => 1990 + index);
    const sequence = playbackYears(years, now);
    expect(sequence.at(-1)).toBe(2025);
    expect(sequence).toHaveLength(16);
    expect(playbackYears([2025], now)).toEqual([]);
  });
});

describe('круг 11 (D): окрестность для проверки «виден ли океан»', () => {
  it('издалека видно почти полушарие, вблизи окрестность сужается, но с запасом на центр страны', () => {
    expect(oceanReach(3.35)).toBe(62);
    expect(oceanReach(2.4)).toBeLessThan(62);
    expect(oceanReach(1.45)).toBeGreaterThan(20);
    expect(oceanReach(1.45)).toBeLessThan(oceanReach(2.0));
    expect(oceanReach(0.5)).toBe(62);
  });
  it('вблизи над океаном без страны рядом это вода, над сушей с окрашенной страной нет', () => {
    const vectors = dataVectors([country('RU', 100, 60, 3)], { RU: 1 });
    // Камера над Тихим океаном у самой воды: страны в 30° от центра нет.
    expect(hasVisibleData(vectors, lonLatToSphere([-150, 0], 1.45), oceanReach(1.45))).toBe(false);
    expect(hasVisibleData(vectors, lonLatToSphere([100, 60], 1.45), oceanReach(1.45))).toBe(true);
  });
});
