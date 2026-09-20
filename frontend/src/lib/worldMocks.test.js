import { describe, expect, it } from 'vitest';
import { getWorldMockData, WORLD_MOCK_INDICATOR } from './worldMocks';

describe('getWorldMockData', () => {
  it('отдаёт фикстуру только для известной пары страна/код', () => {
    const key = Object.keys(WORLD_MOCK_INDICATOR)[0];
    const [slug, code] = key.split('/');
    const data = getWorldMockData(slug, code, 'level-monthly');
    expect(data).toBeTruthy();
    expect(data.points.length).toBeGreaterThan(0);
    expect(data._fromMock).toBeUndefined();
  });

  it('не подменяет чужой ряд (nonfarm) немецким HICP', () => {
    expect(getWorldMockData('united-states', 'us-nonfarm-payrolls', 'level-annual')).toBeNull();
  });
});
