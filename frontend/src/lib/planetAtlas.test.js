import { describe, expect, it } from 'vitest';
import { outlineRings, ringSpanDegrees } from './planetAtlas';

const square = (west, south, size) => [
  [west, south], [west + size, south], [west + size, south + size], [west, south + size], [west, south],
];

describe('planetAtlas outlines', () => {
  it('measures a ring by its larger side', () => {
    expect(ringSpanDegrees([[0, 0], [4, 0], [4, 1], [0, 1], [0, 0]])).toBe(4);
  });

  it('treats a ring across the antimeridian as large', () => {
    expect(ringSpanDegrees([[170, 60], [-170, 60], [-170, 70], [170, 70], [170, 60]])).toBe(Infinity);
  });

  it('skips tiny islets and lakes so they cannot become black specks', () => {
    const geometry = {
      type: 'MultiPolygon',
      coordinates: [
        [square(-100, 30, 20)],
        [square(-76, 24, 0.2)],
        [square(-90, 40, 8), square(-87, 43, 0.15)],
      ],
    };
    const rings = outlineRings(geometry, 0.5);
    expect(rings).toHaveLength(2);
    expect(rings.every((ring) => ringSpanDegrees(ring) >= 0.5)).toBe(true);
  });

  it('accepts a plain polygon and ignores other geometry', () => {
    expect(outlineRings({ type: 'Polygon', coordinates: [square(0, 0, 5)] }, 1)).toHaveLength(1);
    expect(outlineRings({ type: 'Point', coordinates: [0, 0] }, 1)).toEqual([]);
    expect(outlineRings(null, 1)).toEqual([]);
  });
});
