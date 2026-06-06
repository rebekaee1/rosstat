import { describe, it, expect } from 'vitest';
import {
  HOUSING_TOP_GROUPS,
  normalizeHousingViewMode,
  topGroupForMode,
  expandedGroupForMode,
} from './housingViewModeGroups';
import { housingCanonicalTarget } from './housingViewModeResolve';
import { getHousingViewModeContent } from './housingViewModeContent';

describe('housingViewModeGroups', () => {
  it('две верхние группы: к прошлому периоду + индекс (как у ИПЦ, без 12 мес.)', () => {
    expect(HOUSING_TOP_GROUPS.map((g) => g.id)).toEqual(['step', 'index']);
    const step = HOUSING_TOP_GROUPS.find((g) => g.id === 'step');
    expect(step.modes.map((m) => m.mode)).toEqual(['qoq', 'yoy']);
  });

  it('дефолтный режим — год к году', () => {
    expect(normalizeHousingViewMode(null)).toBe('yoy');
    expect(normalizeHousingViewMode('level')).toBe('index');
  });

  it('г/г и к/к — одна группа «К прошлому периоду»', () => {
    expect(topGroupForMode('qoq')).toBe('step');
    expect(topGroupForMode('yoy')).toBe('step');
    expect(expandedGroupForMode('yoy')).toBe('step');
  });

  it('canonical redirect derived URL', () => {
    expect(housingCanonicalTarget('housing-qoq-primary')).toEqual({
      parentCode: 'housing-price-primary',
      mode: 'qoq',
    });
  });

  it('контент г/г не про ИПЦ', () => {
    const { description } = getHousingViewModeContent({
      chartMode: 'yoy',
      indicator: { code: 'housing-price-primary' },
    });
    expect(description).toMatch(/новостро|первичн/i);
    expect(description).not.toMatch(/потребительск/i);
  });
});
