import { describe, expect, it } from 'vitest';
import map from './usStatesMap.json';
import { countryRegionIndicatorPath, countryRegionsPath } from './sitePaths';

describe('usStatesMap', () => {
  it('covers 50 states plus DC with a DC marker', () => {
    expect(map.viewBox).toBe('0 0 960 600');
    expect(map.regions).toHaveLength(51);
    const slugs = new Set(map.regions.map((r) => r.slug));
    expect(slugs.has('california')).toBe(true);
    expect(slugs.has('alaska')).toBe(true);
    expect(slugs.has('hawaii')).toBe(true);
    expect(slugs.has('district-of-columbia')).toBe(true);
    expect(map.markers).toEqual([
      expect.objectContaining({ slug: 'district-of-columbia' }),
    ]);
    for (const row of map.regions) {
      expect(row.path.length).toBeGreaterThan(20);
    }
  });
});

describe('WorldRegion paths', () => {
  it('keeps US hub plural and Russia hub singular', () => {
    expect(countryRegionsPath('united-states')).toBe('/united-states/regions');
    expect(countryRegionIndicatorPath('united-states', 'california', 'unemployment-rate'))
      .toBe('/united-states/region/california/unemployment-rate');
  });
});
