import { describe, expect, it } from 'vitest';
import {
  RESERVED_FIRST_SEGMENTS,
  RUSSIA,
  calendarPath,
  categoryPath,
  countryPath,
  demographicsPath,
  indicatorPath,
  indicatorYearPath,
  isReservedFirstSegment,
  regionHubPath,
  regionIndicatorPath,
  regionMapPath,
  regionPath,
  regionRatingHubPath,
  regionRatingPath,
  regionVsPath,
  russiaCategoriesPath,
  russiaIndicatorPath,
  todayPath,
  worldHubPath,
  worldRatingPath,
} from './sitePaths';

describe('sitePaths', () => {
  it('строит единую схему country/indicator/region', () => {
    expect(countryPath('germany')).toBe('/germany');
    expect(indicatorPath('germany', 'nama_10_gdp')).toBe('/germany/indicator/nama_10_gdp');
    expect(indicatorYearPath('russia', 'cpi', 2024)).toBe('/russia/indicator/cpi/2024');
    expect(categoryPath('russia', 'prices')).toBe('/russia/category/prices');
    expect(russiaIndicatorPath('cpi')).toBe('/russia/indicator/cpi');
    expect(regionHubPath()).toBe('/russia/region');
    expect(regionPath('tatarstan')).toBe('/russia/region/tatarstan');
    expect(regionIndicatorPath('tatarstan', 'naselenie')).toBe('/russia/region/tatarstan/naselenie');
    expect(regionMapPath('naselenie')).toBe('/russia/region/map/naselenie');
    expect(regionRatingPath('naselenie')).toBe('/russia/region-rating/naselenie');
    expect(regionVsPath('a', 'b')).toBe('/russia/region-vs/a-vs-b');
    expect(todayPath()).toBe('/russia/today');
    expect(todayPath('cpi')).toBe('/russia/today/cpi');
    expect(calendarPath(2026, 8)).toBe('/russia/calendar/2026/08');
    expect(demographicsPath()).toBe('/russia/demographics');
    expect(worldHubPath()).toBe('/world');
    expect(worldRatingPath('gdp')).toBe('/world/rating/gdp');
    expect(russiaCategoriesPath()).toBe('/russia/category');
    expect(regionRatingHubPath()).toBe('/russia/region-rating');
  });

  it('russia не reserved; platform roots — reserved', () => {
    expect(RUSSIA).toBe('russia');
    expect(isReservedFirstSegment(RUSSIA)).toBe(false);
    expect(RESERVED_FIRST_SEGMENTS).toContain('compare');
    expect(RESERVED_FIRST_SEGMENTS).toContain('world');
    expect(isReservedFirstSegment('sitemap-core.xml')).toBe(true);
  });
});
