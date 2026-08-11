import { describe, expect, it } from 'vitest';
import { displayWorldGeometry } from '../lib/worldMapGeometry';

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
