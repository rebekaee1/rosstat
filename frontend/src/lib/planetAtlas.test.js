import { describe, expect, it } from 'vitest';
import { outlineRings, ringSpanDegrees, substantialPolygons } from './planetAtlas';

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

describe('planetAtlas dust', () => {
  it('drops islets and small lakes from the painted geometry', () => {
    const geometry = {
      type: 'MultiPolygon',
      coordinates: [
        [square(-100, 30, 20)],
        [square(-76, 24, 0.2)],
        [square(-90, 40, 8), square(-87, 43, 0.15)],
      ],
    };
    const result = substantialPolygons(geometry, 0.7);
    expect(result.type).toBe('MultiPolygon');
    expect(result.coordinates).toHaveLength(2);
    // The lake inside the third polygon is a hole too small to keep.
    expect(result.coordinates[1]).toHaveLength(1);
  });

  it('always keeps the largest part, so a microstate stays painted', () => {
    const malta = { type: 'MultiPolygon', coordinates: [[square(14.2, 35.8, 0.14)], [square(14.3, 36.0, 0.08)]] };
    const result = substantialPolygons(malta, 0.7);
    expect(result).toEqual({ type: 'Polygon', coordinates: [square(14.2, 35.8, 0.14)] });
  });

  it('keeps a ring across the antimeridian and passes other geometry through', () => {
    const wrap = { type: 'Polygon', coordinates: [[[170, 60], [-170, 60], [-170, 70], [170, 70], [170, 60]]] };
    expect(substantialPolygons(wrap, 5)).toEqual(wrap);
    const point = { type: 'Point', coordinates: [0, 0] };
    expect(substantialPolygons(point, 5)).toBe(point);
    expect(substantialPolygons(null, 5)).toBeNull();
  });

  it('on the real 50m atlas the dust is gone from the Aegean, the US east coast and the Azov sea', async () => {
    const { feature } = await import('topojson-client');
    const topology = (await import('world-atlas/countries-50m.json')).default;
    const countries = feature(topology, topology.objects.countries).features;
    let before = 0;
    let after = 0;
    for (const item of countries) {
      const polygons = (g) => (g?.type === 'Polygon' ? 1 : g?.type === 'MultiPolygon' ? g.coordinates.length : 0);
      before += polygons(item.geometry);
      after += polygons(substantialPolygons(item.geometry, 0.7));
    }
    // About 1450 of 1630 rings are smaller than four degrees; most of them are specks of one or two pixels.
    expect(after).toBeLessThan(before * 0.5);
    expect(after).toBeGreaterThan(150);
  });
});
