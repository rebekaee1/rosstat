import { describe, expect, it } from 'vitest';
import { geoContains } from 'd3-geo';
import { WORLD_FEATURES } from './worldTopology';
import {
  bindPlanetCountries,
  countryCodeForFeature,
  countryFocusLonLat,
  loadPlanetFeatures,
  lonLatToSphere,
  normalizePlanetCountryCode,
  pickPlanetCountry,
  planetNeedsFineFeatures,
  sphereToLonLat,
} from './planetGeometry';

const ring = (west, south, east, north) => [
  [west, south], [west, north], [east, north], [east, south], [west, south],
];
const polygon = (id, coordinates, name = '') => ({
  type: 'Feature', id, properties: { name }, geometry: { type: 'Polygon', coordinates },
});

describe('planet country identity', () => {
  it.each([
    ['uk', 'GB'], [' GB ', 'GB'], ['EL', 'GR'], ['300', 'GR'], [4, 'AF'],
    ['158', 'TW'], ['383', 'XK'], ['ZZ', null], ['', null], [null, null],
  ])('normalizes %s to %s', (input, expected) => {
    expect(normalizePlanetCountryCode(input)).toBe(expected);
  });

  it('covers every numeric country code in the real base atlas', () => {
    for (const item of WORLD_FEATURES.filter((candidate) => candidate.id != null)) {
      expect(countryCodeForFeature(item), `${item.id}: ${item.properties.name}`).toMatch(/^[A-Z]{2}$/);
    }
  });

  it('keeps public data keys and catalog objects while matching geometry aliases', () => {
    const countries = [
      { code: 'UK', slug: 'united-kingdom', name: 'Великобритания', name_en: 'United Kingdom' },
      { code: 'EL', slug: 'greece', name: 'Греция', name_en: 'Greece' },
    ];
    const items = bindPlanetCountries(countries);
    expect(items.find((item) => item.code === 'GB')).toMatchObject({ dataCode: 'UK', country: countries[0] });
    expect(items.find((item) => item.code === 'GR')).toMatchObject({ dataCode: 'EL', country: countries[1] });
    expect(items.find((item) => item.code === 'GB').country).toBe(countries[0]);
  });

  it('names countries without inventing a public catalog route', () => {
    const items = bindPlanetCountries([], WORLD_FEATURES, { locale: 'ru' });
    expect(items.find((item) => item.code === 'BR')).toMatchObject({ name: 'Бразилия', country: null });
    expect(bindPlanetCountries([], WORLD_FEATURES, { locale: 'en' }).find((item) => item.code === 'BR').name).toBe('Brazil');
    const uncoded = items.filter((item) => item.code == null);
    expect(new Set(uncoded.map((item) => item.id)).size).toBe(uncoded.length);
    expect(items.find((item) => item.feature.properties.name === 'Kosovo').code).toBe('XK');
  });

  it('loads every detailed feature without collapsing duplicate or missing IDs', async () => {
    const items = await loadPlanetFeatures('detailed');
    expect(items.length).toBeGreaterThan(WORLD_FEATURES.length);
    expect(items.filter((item) => item.id == null).map((item) => item.properties.name))
      .toEqual(expect.arrayContaining(['Somaliland', 'Kosovo', 'N. Cyprus']));
    const bound = bindPlanetCountries([], items);
    expect(bound).toHaveLength(items.length);
    expect(new Set(bound.map((item) => item.id)).size).toBe(items.length);
  });

  it('retains country IDs when the atlas resolution or array order changes', async () => {
    const base = bindPlanetCountries([]).find((item) => item.code === 'DE');
    const detailed = bindPlanetCountries([], [...await loadPlanetFeatures('detailed')].reverse())
      .find((item) => item.code === 'DE');
    expect(base.id).toBe(detailed.id);
  });
});

describe('planet coordinates', () => {
  it('uses the agreed renderer axes and preserves radius', () => {
    expect(lonLatToSphere([0, 0], 2)).toEqual([0, 0, 2]);
    const east = lonLatToSphere([90, 0]);
    expect(east[0]).toBeCloseTo(1);
    expect(east[2]).toBeCloseTo(0);
    expect(lonLatToSphere([0, 90])[1]).toBeCloseTo(1);
  });

  it.each([[179.9, 35], [-179.9, -35], [30, 70], [-120, -80], [380, 10]])(
    'round-trips longitude %s latitude %s', (longitude, latitude) => {
      const vector = lonLatToSphere([longitude, latitude], 3);
      const point = sphereToLonLat({ x: vector[0], y: vector[1], z: vector[2] });
      expect(point[0]).toBeCloseTo(((longitude + 180) % 360 + 360) % 360 - 180);
      expect(point[1]).toBeCloseTo(latitude);
    },
  );

  it('rejects invalid surface coordinates and zero vectors', () => {
    expect(lonLatToSphere([0, 91])).toBeNull();
    expect(lonLatToSphere([NaN, 0])).toBeNull();
    expect(lonLatToSphere([0, 0], 0)).toBeNull();
    expect(sphereToLonLat([0, 0, 0])).toBeNull();
    expect(sphereToLonLat([Infinity, 1, 0])).toBeNull();
  });
});

describe('planet focus and geographic picking', () => {
  it('reserves the fine atlas for missing or genuinely small countries', () => {
    const large = polygon('276', [ring(0, 0, 2, 2)]);
    const small = polygon('492', [ring(10, 10, 10.1, 10.1)]);
    const entries = bindPlanetCountries([], [large, small]);
    expect(planetNeedsFineFeatures(entries, 'DE')).toBe(false);
    expect(planetNeedsFineFeatures(entries, 'MC')).toBe(true);
    expect(planetNeedsFineFeatures(entries, 'MT')).toBe(true);
    expect(planetNeedsFineFeatures(entries, 'ZZ')).toBe(false);
    expect(planetNeedsFineFeatures(entries, null)).toBe(false);
  });

  it('does not download the fine atlas for typical catalog selections or aliases', () => {
    const entries = bindPlanetCountries([]);
    for (const code of ['DE', 'FR', 'UK', 'EL', 'RU', 'US']) {
      expect(planetNeedsFineFeatures(entries, code), code).toBe(false);
    }
  });

  it('recognizes real microstates in the detailed atlas instead of hiding them', async () => {
    const entries = bindPlanetCountries([], await loadPlanetFeatures('detailed'));
    expect(planetNeedsFineFeatures(entries, 'MT')).toBe(true);
    expect(planetNeedsFineFeatures(entries, 'LU')).toBe(true);
    expect(planetNeedsFineFeatures(entries, 'DE')).toBe(false);
  });

  it('handles an empty or partial atlas without an invented focus', () => {
    expect(bindPlanetCountries([], [])).toEqual([]);
    expect(pickPlanetCountry([], [0, 0])).toBeNull();
    expect(countryFocusLonLat(null)).toBeNull();
    expect(countryFocusLonLat({ type: 'MultiPolygon', coordinates: [] })).toBeNull();
    expect(countryFocusLonLat({ type: 'Polygon', coordinates: [] })).toBeNull();
  });
  it('focuses across the antimeridian rather than averaging toward Greenwich', () => {
    const item = polygon('242', [ring(179, -10, -179, 10)]);
    const focus = countryFocusLonLat(item);
    expect(Math.abs(focus[0])).toBeGreaterThan(179);
    expect(focus[1]).toBeCloseTo(0);
    const entries = bindPlanetCountries([], [item]);
    expect(pickPlanetCountry(entries, [180, 0])?.code).toBe('FJ');
    expect(pickPlanetCountry(entries, [-179.5, 0])?.code).toBe('FJ');
    expect(pickPlanetCountry(entries, [0, 0])).toBeNull();
  });

  it('focuses the dominant mainland while preserving an overseas polygon for picking', () => {
    const item = {
      type: 'Feature', id: '250', properties: { name: 'France' },
      geometry: { type: 'MultiPolygon', coordinates: [[ring(0, 40, 10, 50)], [ring(-54, 2, -52, 4)]] },
    };
    const entries = bindPlanetCountries([], [item]);
    expect(entries[0].feature).toBe(item);
    expect(countryFocusLonLat(item)[0]).toBeCloseTo(5);
    expect(pickPlanetCountry(entries, [-53, 3])).toBe(entries[0]);
    expect(pickPlanetCountry(entries, [5, 45])).toBe(entries[0]);
  });

  it('honors holes and does not select ocean or invalid input', () => {
    const hole = ring(2, 2, 4, 4).reverse();
    const item = polygon('076', [ring(0, 0, 10, 10), hole]);
    const entries = bindPlanetCountries([], [item]);
    expect(pickPlanetCountry(entries, [1, 1])).toBe(entries[0]);
    expect(pickPlanetCountry(entries, [3, 3])).toBeNull();
    expect(pickPlanetCountry(entries, [20, 20])).toBeNull();
    expect(pickPlanetCountry(entries, [0, 95])).toBeNull();
  });

  it('picks representative real atlas countries on both sides of the planet', () => {
    const entries = bindPlanetCountries([]);
    for (const [point, code] of [[[13.4, 52.5], 'DE'], [[-99.1, 19.4], 'MX'], [[133.9, -25.3], 'AU']]) {
      expect(pickPlanetCountry(entries, point)?.code).toBe(code);
    }
    expect(pickPlanetCountry(entries, [-140, 0])).toBeNull();
  });

  it('preserves exhaustive geographic picking when skipping distant country bounds', async () => {
    const entries = bindPlanetCountries([], await loadPlanetFeatures('detailed'));
    for (let longitude = -175; longitude <= 175; longitude += 30) {
      for (let latitude = -75; latitude <= 75; latitude += 15) {
        const point = [longitude, latitude];
        const exhaustive = entries.find((entry) => geoContains(entry.feature, point)) || null;
        expect(pickPlanetCountry(entries, point), point.join(',')).toBe(exhaustive);
      }
    }
  });
});
