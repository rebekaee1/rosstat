import { describe, expect, it } from 'vitest';
import { geoBounds } from 'd3-geo';
import { feature } from 'topojson-client';
import { displayWorldGeometry, mainlandWorldGeometry } from '../lib/worldMapGeometry';

const square = (west, south, size) => [[
  [west, south],
  [west, south + size],
  [west + size, south + size],
  [west + size, south],
  [west, south],
]];

const multi = (...polygons) => ({
  type: 'Feature',
  id: '000',
  geometry: { type: 'MultiPolygon', coordinates: polygons },
  properties: {},
});

describe('displayWorldGeometry', () => {
  it('keeps only the largest France polygon for the analytical map', () => {
    const small = [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]];
    const mainland = [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]];
    const feature = {
      type: 'Feature',
      id: '250',
      geometry: { type: 'MultiPolygon', coordinates: [small, mainland] },
      properties: {},
    };

    const result = displayWorldGeometry(feature, 'FR');

    expect(result.geometry.type).toBe('Polygon');
    expect(result.geometry.coordinates).toEqual(mainland);
  });

  it('does not alter other countries', () => {
    const feature = {
      type: 'Feature',
      id: '620',
      geometry: { type: 'Polygon', coordinates: [] },
      properties: {},
    };
    expect(displayWorldGeometry(feature, 'PT')).toBe(feature);
  });
});

describe('mainlandWorldGeometry', () => {
  it('leaves single-polygon countries untouched', () => {
    const item = {
      type: 'Feature',
      id: '040',
      geometry: { type: 'Polygon', coordinates: square(10, 46, 4) },
      properties: {},
    };
    expect(mainlandWorldGeometry(item)).toBe(item);
  });

  it('keeps islands hugging the mainland', () => {
    const item = multi(square(0, 44, 6), square(8, 41, 1));
    expect(mainlandWorldGeometry(item)).toBe(item);
  });

  it('drops overseas territories thousands of kilometres away', () => {
    const mainland = square(0, 44, 6);
    const item = multi(mainland, square(-53, 3, 2));
    expect(mainlandWorldGeometry(item).geometry.coordinates).toEqual([mainland]);
  });

  it('drops offshore specks that only stretch the frame', () => {
    const mainland = square(5, 58, 10);
    const item = multi(mainland, square(-9, 70, 0.3));
    expect(mainlandWorldGeometry(item).geometry.coordinates).toEqual([mainland]);
  });

  it('keeps a large detached region of a large country', () => {
    const item = multi(square(-100, 30, 20), square(-130, 55, 12));
    expect(mainlandWorldGeometry(item).geometry.coordinates).toHaveLength(2);
  });
});

describe('mainlandWorldGeometry on the real atlas', () => {
  const span = (item) => {
    const [[west, south], [east, north]] = geoBounds(item);
    return { width: east - west, height: north - south };
  };

  it.each([
    ['250', 'Франция без заморских департаментов', 20, 15],
    ['528', 'Нидерланды без Карибов', 8, 8],
    ['620', 'Португалия без Азорских островов', 8, 10],
    ['724', 'Испания без Канарских островов', 18, 12],
    ['554', 'Новая Зеландия без Кермадека', 20, 20],
  ])('trims %s (%s)', async (id, _label, maxWidth, maxHeight) => {
    const topology = (await import('world-atlas/countries-50m.json')).default;
    const item = feature(topology, topology.objects.countries)
      .features.find((candidate) => String(candidate.id).padStart(3, '0') === id);
    const trimmed = mainlandWorldGeometry(item);
    const { width, height } = span(trimmed);
    expect(width).toBeLessThan(maxWidth);
    expect(height).toBeLessThan(maxHeight);
    expect(width).toBeGreaterThan(0);
  });

  it('keeps the whole archipelago of Indonesia', async () => {
    const topology = (await import('world-atlas/countries-50m.json')).default;
    const item = feature(topology, topology.objects.countries)
      .features.find((candidate) => String(candidate.id).padStart(3, '0') === '360');
    expect(span(mainlandWorldGeometry(item)).width).toBeGreaterThan(40);
  });
});
