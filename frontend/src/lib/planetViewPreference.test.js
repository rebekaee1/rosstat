// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PLANET_VIEW_KEY, readPlanetViewPreference, writePlanetViewPreference } from './planetViewPreference';

afterEach(() => { vi.restoreAllMocks(); window.localStorage.clear(); });

describe('planetViewPreference', () => {
  it('по умолчанию карта; шар только если выбран явно', () => {
    expect(PLANET_VIEW_KEY).toBe('fe_planet_view');
    expect(readPlanetViewPreference()).toBe('map');
    window.localStorage.setItem(PLANET_VIEW_KEY, 'globe');
    expect(readPlanetViewPreference()).toBe('globe');
    window.localStorage.setItem(PLANET_VIEW_KEY, 'что-то странное');
    expect(readPlanetViewPreference()).toBe('map');
  });

  it('запоминает выбор и не принимает ничего, кроме map и globe', () => {
    writePlanetViewPreference('globe');
    expect(window.localStorage.getItem(PLANET_VIEW_KEY)).toBe('globe');
    writePlanetViewPreference('map');
    expect(window.localStorage.getItem(PLANET_VIEW_KEY)).toBe('map');
    writePlanetViewPreference('earth');
    expect(window.localStorage.getItem(PLANET_VIEW_KEY)).toBe('map');
  });

  it('без хранилища ничего не падает и по умолчанию карта', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(readPlanetViewPreference()).toBe('map');
    expect(() => writePlanetViewPreference('globe')).not.toThrow();
  });
});
