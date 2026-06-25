import { describe, it, expect } from 'vitest';
import {
  getViewModeFamily,
  isViewModeFamily,
  viewModeCanonicalTarget,
  normalizeViewMode,
  resolveViewMode,
  buildViewModeGroups,
  topGroupForMode,
  expandedGroupForMode,
  defaultSubModeForGroup,
  viewModeFamilyBases,
} from './viewModeEngine';

describe('viewModeEngine — generic resolver', () => {
  it('exposes families and resolves base cards', () => {
    expect(viewModeFamilyBases().length).toBeGreaterThan(20);
    expect(isViewModeFamily('m2')).toBe(true);
    expect(isViewModeFamily('not-a-family')).toBe(false);
    expect(getViewModeFamily('m2').template).toBe('T3');
  });

  it('normalizes invalid/empty url modes to default', () => {
    const fam = getViewModeFamily('m2');
    expect(normalizeViewMode(fam, undefined)).toBe('level');
    expect(normalizeViewMode(fam, 'garbage')).toBe('level');
    expect(normalizeViewMode(fam, 'yoy')).toBe('yoy');
  });

  it('resolves a mode to its backend derived code + unit + frequency', () => {
    const fam = getViewModeFamily('m2');
    expect(resolveViewMode(fam, 'level').code).toBe('m2');
    const yoy = resolveViewMode(fam, 'yoy');
    expect(yoy.code).toBe('m2-yoy');
    expect(yoy.unit).toBe('%');
    expect(yoy.frequency).toBe('monthly');
    const avgQ = resolveViewMode(fam, 'avg-quarter');
    expect(avgQ.code).toBe('m2-avg-quarter');
    expect(avgQ.frequency).toBe('quarterly');
    expect(avgQ.unit).toBe('млрд руб.');
  });

  it('canonical target maps derived child code → {base, mode}', () => {
    expect(viewModeCanonicalTarget('m2-yoy')).toEqual({ base: 'm2', mode: 'yoy' });
    expect(viewModeCanonicalTarget('m2')).toBeNull();
  });

  it('builds two-level groups with a multi-level yoy group', () => {
    const groups = buildViewModeGroups(getViewModeFamily('m2'));
    const byId = Object.fromEntries(groups.map((g) => [g.id, g]));
    expect(byId.level.modes.map((m) => m.mode)).toEqual(['level', 'eop-quarter', 'eop-year']);
    // правило «без дубль-линий»: средняя без месячной гранулярности
    expect(byId.avg.modes.map((m) => m.mode)).toEqual(['avg-quarter', 'avg-year']);
    expect(byId.pop.modes.map((m) => m.mode)).toEqual(['mom', 'qoq']);
    // Г/г теперь многоуровневая: по месяцам / кварталам / годам
    expect(byId.yoy.modes.map((m) => m.mode)).toEqual(['yoy', 'yoy-quarter', 'yoy-year']);
  });

  it('computes top group / expansion for a mode', () => {
    const fam = getViewModeFamily('m2');
    expect(topGroupForMode(fam, 'avg-quarter')).toBe('avg');
    expect(expandedGroupForMode(fam, 'avg-quarter')).toBe('avg');
    expect(expandedGroupForMode(fam, 'yoy')).toBe('yoy'); // многоуровневая группа
    expect(defaultSubModeForGroup(fam, 'pop')).toBe('mom');
  });

  it('budget-deficit exposes flow + absolute growth groups', () => {
    const fam = getViewModeFamily('budget-deficit');
    const groups = buildViewModeGroups(fam);
    expect(groups.map((g) => g.id)).toEqual(['flow', 'pop', 'yoy']);
    expect(resolveViewMode(fam, 'sum-year').code).toBe('budget-deficit-sum-year');
    expect(resolveViewMode(fam, 'qoq').code).toBe('budget-deficit-qoq');
    expect(resolveViewMode(fam, 'yoy').code).toBe('budget-deficit-yoy');
  });

  it('gdp reuses legacy derived codes', () => {
    const fam = getViewModeFamily('gdp-nominal');
    expect(resolveViewMode(fam, 'yoy').code).toBe('gdp-yoy');
    expect(resolveViewMode(fam, 'qoq').code).toBe('gdp-qoq');
    expect(resolveViewMode(fam, 'sum-year').code).toBe('gdp-nominal-annual');
  });
});
